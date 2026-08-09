"""Persistance et cycle de vie du socle.

Règle du cahier des charges : une fois validé, le socle n'est jamais recalculé
pendant la génération. La régénération est une action explicite qui invalide
tous les chapitres.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import (
    ChapterStatus,
    GenerationJob,
    SocleDonnees,
    SocleStatut,
)
from .builder import SocleGenerationError, produire_socle
from .referentiel import livrable_couvert
from .schema import Socle, valider_socle

_log = logging.getLogger(__name__)


def socle_actif() -> bool:
    """Le nouveau moteur de socle est-il activé ?

    Faux par défaut : l'ancien moteur reste seul en service tant que la
    bascule n'est pas décidée. C'est le drapeau réversible en une ligne.
    """
    return bool(getattr(settings, "EVKHA_SOCLE_ENABLED", False))


def socle_du_job(job: GenerationJob) -> SocleDonnees | None:
    return SocleDonnees.objects.filter(job=job).first()


def socle_verrouille(job: GenerationJob) -> Socle | None:
    """Socle validé du job, prêt à être injecté. None si absent ou non validé.

    Relit systématiquement depuis la base : c'est ce qui rend effective une
    correction manuelle faite en admin entre deux chapitres.
    """
    enregistrement = socle_du_job(job)
    if enregistrement is None or not enregistrement.est_verrouille:
        return None
    try:
        socle = Socle.model_validate(enregistrement.contenu)
    except Exception:  # noqa: BLE001 — un socle corrompu ne doit pas tuer le job
        _log.exception("Socle illisible pour le job %s", job.id)
        return None
    socle.deliverable_type = str(job.deliverable_type)
    return socle


def _journaliser_la_verification(job: GenerationJob, rapport: Any) -> None:
    """Porte le résultat de la vérification au journal des incidents.

    Un socle vérifié et un socle non vérifié ne doivent pas se ressembler. Trois
    cas, trois traces distinctes :

    - la passe n'a PAS pu tourner → incident MOYEN. Les chiffres ne sont pas
      faux pour autant, mais personne ne les a confrontés, et l'ignorer
      laisserait un socle non contrôlé passer pour contrôlé (règle 1) ;
    - des chiffres ont été déclassés → incident MOYEN, avec la liste. C'est
      l'information la plus utile du dossier : elle dit où l'étude s'appuie sur
      une estimation plutôt que sur une donnée publiée ;
    - tout est confirmé → rien. Un journal qui parle quand tout va bien cesse
      d'être lu.
    """
    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    if not rapport.passe_executee:
        OperationalIncident.objects.create(
            title=f"Socle NON vérifié (job {job.id})",
            severity=IncidentSeverity.MEDIUM,
            job=job,
            order=job.order,
            details=rapport.as_details(),
        )
        return

    if rapport.total_declassees:
        OperationalIncident.objects.create(
            title=(
                f"Socle : {rapport.total_declassees} chiffre(s) déclassé(s) en "
                f"estimation (job {job.id})"
            ),
            severity=IncidentSeverity.MEDIUM,
            job=job,
            order=job.order,
            details=rapport.as_details(),
        )


@transaction.atomic
def etablir_socle(
    job: GenerationJob,
    *,
    client: Any,
    variables: Mapping[str, object],
    brief_recherche: str = "",
    forcer: bool = False,
) -> SocleDonnees:
    """Produit le socle du job et le persiste.

    Idempotent : si un socle validé existe déjà, il est renvoyé tel quel sans
    aucun appel au modèle. `forcer=True` déclenche une régénération explicite,
    qui invalide tous les chapitres (voir `regenerer_socle`).
    """
    existant = socle_du_job(job)
    if existant is not None and existant.est_verrouille and not forcer:
        return existant

    version = (existant.version + 1) if existant is not None else 1

    try:
        socle, consommation, tentatives = produire_socle(
            client=client,
            deliverable_type=str(job.deliverable_type),
            variables=variables,
            brief_recherche=brief_recherche,
        )
    except SocleGenerationError as erreur:
        enregistrement, _ = SocleDonnees.objects.update_or_create(
            job=job,
            defaults={
                "version": version,
                "statut": SocleStatut.INVALIDE,
                "motifs_rejet": erreur.motifs,
                "tentatives": erreur.tentatives,
                "contenu": {},
            },
        )
        raise

    # ── Vérification AVANT verrouillage ──────────────────────────────────────
    #
    # Le socle est le point unique de vérité de l'étude : ses chiffres sont
    # repris dans les vingt-trois chapitres. C'est sa force, et c'est ce qui
    # rend une erreur initiale si chère — retour de la cliente du 09/08/2026 :
    # « si un chiffre initial est errone, date, issu d'un mauvais perimetre ou
    # mal interprete, il est actuellement repete dans toute l'etude ».
    #
    # Rien ne le regardait : le socle etait scelle VALIDE des sa production.
    # Ce qui n'est pas confirme par les sources collectees passe desormais en
    # `estimee`, motif inscrit dans son libelle — donc lisible par le client.
    from .verification import verifier_le_socle  # noqa: PLC0415

    rapport_verif = verifier_le_socle(
        socle, client=client, brief_recherche=brief_recherche
    )
    _journaliser_la_verification(job, rapport_verif)

    from ..cost import estimate_call_cost_eur  # noqa: PLC0415 — évite un cycle

    cout = estimate_call_cost_eur(
        consommation["input_tokens"], consommation["output_tokens"]
    )

    enregistrement, _ = SocleDonnees.objects.update_or_create(
        job=job,
        defaults={
            "version": version,
            "statut": SocleStatut.VALIDE,
            "contenu": socle.model_dump(mode="json"),
            "motifs_rejet": [],
            "tentatives": tentatives,
            "corrige_manuellement": False,
            "valide_at": timezone.now(),
            "input_tokens": consommation["input_tokens"],
            "output_tokens": consommation["output_tokens"],
            "cost_eur": cout,
        },
    )

    GenerationJob.objects.filter(pk=job.pk).update(
        total_cost_eur=job.total_cost_eur + cout
    )
    return enregistrement


def revalider_socle(enregistrement: SocleDonnees) -> list[str]:
    """Revalide un socle corrigé à la main. Retourne les motifs de rejet.

    Appelée après une modification en admin : une correction humaine n'a
    aucune raison d'échapper aux contrôles qui s'appliquent au modèle.
    """
    deliverable_type = str(enregistrement.job.deliverable_type)
    try:
        socle = Socle.model_validate(enregistrement.contenu)
    except Exception as erreur:  # noqa: BLE001
        return [f"Structure invalide : {erreur}"]

    motifs = valider_socle(socle, deliverable_type)
    enregistrement.motifs_rejet = motifs
    enregistrement.statut = SocleStatut.INVALIDE if motifs else SocleStatut.VALIDE
    if not motifs:
        enregistrement.valide_at = timezone.now()
    enregistrement.save(
        update_fields=["motifs_rejet", "statut", "valide_at", "updated_at"]
    )
    return motifs


@transaction.atomic
def regenerer_socle(job: GenerationJob) -> int:
    """Invalide le socle ET tous les chapitres du job.

    Le cahier des charges l'impose : régénérer le socle est une action
    explicite qui remet à zéro ce qui a été construit dessus. Laisser des
    chapitres écrits sur l'ancien socle reproduirait exactement l'incohérence
    que le lot 1 supprime.

    Retourne le nombre de chapitres remis en attente.
    """
    enregistrement = socle_du_job(job)
    if enregistrement is not None:
        enregistrement.statut = SocleStatut.INVALIDE
        enregistrement.motifs_rejet = ["Régénération demandée par l'administrateur."]
        enregistrement.save(update_fields=["statut", "motifs_rejet", "updated_at"])

    return job.chapters.exclude(status=ChapterStatus.PENDING).update(
        status=ChapterStatus.PENDING,
        content="",
        operational_summary="",
        error_message="",
    )


def livrable_supporte(job: GenerationJob) -> bool:
    return livrable_couvert(str(job.deliverable_type))
