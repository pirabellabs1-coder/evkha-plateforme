"""Assemblage du livrable Word et de son PDF (lot 3).

Chaîne parallèle à `assemble_document`, qui reste en place et inchangée : elle
produit l'aperçu HTML et le PDF issus de l'ancien moteur. Les deux coexistent
le temps de la bascule, et c'est délibéré — remplacer la chaîne en service
avant d'avoir vu un livrable Word sur un dossier réel reviendrait à parier sur
du code que personne n'a encore lu en production (règle 7).

Ordre imposé : **le Word d'abord, le PDF ensuite, converti depuis lui**. Le PDF
est une photographie du Word, jamais un second rendu — sans quoi les deux
fichiers livrés au même client divergeraient sur la pagination.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from generation.models import GenerationJob
from generation.rendu_word.assemblage import RapportAssemblage
from generation.rendu_word.services import produire_docx
from generation.verification import RapportControle, verifier_livrable
from integrations.docx_pdf import (
    ConversionPdfError,
    ConvertisseurDocx,
    get_convertisseur_docx,
)

from .models import ArtifactKind, ArtifactStatus, DocumentArtifact

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LivrableAssemble:
    docx: DocumentArtifact
    pdf: DocumentArtifact | None
    rapport: RapportAssemblage
    pages: int = 0
    controle: RapportControle | None = None

    @property
    def livrable(self) -> bool:
        """Le document peut-il partir au client ?

        Absence de contrôle vaut **non** : ne pas avoir vérifié n'est pas la
        même chose qu'avoir vérifié sans rien trouver (règle 1).
        """
        return self.controle is not None and self.controle.livrable


def _url(cle: str, duree_s: int | None = None) -> str:
    """URL de telechargement, SIGNEE et datee sur la duree du dossier.

    Sans signature, `/media/` servait n'importe quel chemin a qui le devinait
    ou l'avait vu passer, sans limite de duree. Le lien reste ouvrable par qui
    le recoit — Brevo et le client final n'ont pas de session a presenter —
    mais il ne se devine plus et il expire.

    `duree_s` vient de l'offre du dossier : le lien doit mourir avec le
    fichier, pas sur une valeur globale que le courriel de livraison ne
    promet pas.
    """
    from evkha import signatures  # noqa: PLC0415 — evite un cycle a l'import

    base = str(getattr(settings, "EVKHA_BASE_URL", "")).rstrip("/")
    return f"{base}{signatures.lien(cle, duree_s)}"


def _retention(job: GenerationJob) -> timedelta:
    """Délégué à `evkha.retention` : ce repli `7` était l'une de cinq copies."""
    from evkha import retention  # noqa: PLC0415 — evite un cycle a l'import

    return retention.duree(job)


#: Marqueur lu par le tableau de bord : ce dossier a perdu des figures.
INCIDENT_TYPE_VISUELS_ABANDONNES = "visuels_abandonnes"


def _consigner_les_visuels_abandonnes(
    job: GenerationJob, rapport: RapportAssemblage
) -> None:
    """Rend LISIBLE le motif de chaque graphique abandonné.

    `RapportAssemblage` note depuis toujours, pour chaque figure écartée, la
    raison exacte — « identifiants absents du socle : … », « unités
    hétérogènes : … », « un seul chiffre ». Sa propre docstring en explique
    l'enjeu : « un graphique abandonné en silence ferait passer un livrable
    amputé pour un livrable complet ».

    Ce rapport partait pourtant dans un `logger.warning`, c'est-à-dire dans le
    journal du conteneur — que l'administration ne consulte pas et que
    l'exploitant n'atteint pas toujours. Constaté le 05/08/2026 sur la première
    étude réelle complète : le livrable portait **2 figures** contre 10 au
    document validé, et il a été impossible de dire pourquoi. La mesure existait
    et était perdue à la seconde même où elle était prise.

    Un incident la conserve, à côté du dossier qu'elle concerne. Il ne bloque
    rien — un livrable sans une de ses figures reste un livrable — mais il rend
    la prochaine correction possible, ce qui est tout l'objet du journal des
    générations (règle 10).
    """
    if not rapport.graphiques_abandonnes:
        return

    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    demandes = rapport.graphiques_demandes
    rendus = rapport.graphiques_rendus
    OperationalIncident.objects.update_or_create(
        job=job,
        title=f"Figures abandonnées à l'assemblage ({rendus}/{demandes}) — job {job.id}"[:200],
        defaults={
            "severity": IncidentSeverity.MEDIUM,
            "order": job.order,
            "details": {
                "type": INCIDENT_TYPE_VISUELS_ABANDONNES,
                "demandes": demandes,
                "rendus": rendus,
                # Le motif AVEC la figure : « ch.4 · Répartition… : unités
                # hétérogènes ». Sans le motif, l'entrée dirait qu'il manque
                # quelque chose sans dire quoi corriger (règle 2).
                "abandonnes": rapport.graphiques_abandonnes[:60],
                "convertis": rapport.graphiques_convertis[:30],
            },
        },
    )


def chaine_word_active(job: GenerationJob) -> bool:
    """La chaîne Word peut-elle servir CE dossier ?

    Défaut mesuré le 05/08/2026, sur une répétition à blanc gratuite : le
    drapeau `EVKHA_LIVRABLE_WORD` est GLOBAL et vaut `true` en production, mais
    la chaîne Word exige un socle verrouillé et des chapitres structurés — que
    seuls l'étude de marché et l'étude concurrentielle produisent. Le business
    plan et la stratégie tournent encore sur le moteur hérité (`_PAR_LIVRABLE`
    ne les couvre pas) : ils écrivaient leurs 21 chapitres, puis `produire_docx`
    levait `LivrableIncompletError` et **le client n'obtenait aucun document**.
    L'échec était de surcroît silencieux : la tâche l'attrape et journalise
    « Assemblage PDF admin impossible ».

    Un drapeau unique décidait donc pour quatre produits dont deux ne peuvent
    pas l'honorer. La décision se prend désormais sur ce que le dossier
    CONTIENT, et non sur ce qu'un réglage souhaite — c'est-à-dire sur les mêmes
    faits que le rendu emploie (règle 9 : un contrôle et sa réparation ne
    doivent pas juger sur des évidences différentes).

    Le repli n'est pas silencieux : le drapeau demandait le Word, il ne l'aura
    pas, et cela se lit dans les journaux (règle 1).
    """
    if not getattr(settings, "EVKHA_LIVRABLE_WORD", True):
        return False

    from generation.rendu_word.services import payloads_du_job  # noqa: PLC0415
    from generation.socle.services import socle_verrouille  # noqa: PLC0415

    if socle_verrouille(job) is None:
        _log.warning(
            "Job %s (%s) : EVKHA_LIVRABLE_WORD demande le Word, mais ce dossier "
            "n'a pas de socle verrouillé. Repli sur la chaîne HTML/PDF.",
            job.id, job.deliverable_type,
        )
        return False
    if not payloads_du_job(job):
        _log.warning(
            "Job %s (%s) : socle présent mais aucun chapitre structuré. "
            "Repli sur la chaîne HTML/PDF.",
            job.id, job.deliverable_type,
        )
        return False
    return True


def assembler_livrable_word(
    job: GenerationJob,
    *,
    convertisseur: ConvertisseurDocx | None = None,
    verifier: bool = True,
) -> LivrableAssemble:
    """Produit le `.docx`, le convertit en PDF, et enregistre les deux artefacts.

    Idempotent par (job, kind) : une relance met à jour les artefacts existants
    au lieu d'en empiler de nouveaux.

    Un échec de conversion **ne perd pas le Word**. L'artefact `docx` est
    enregistré prêt, l'artefact `pdf` est marqué en échec, et l'exception n'est
    pas propagée : le client a payé pour un livrable, pas pour une chaîne
    d'outils. L'échec reste visible en base, ce qui est le point.
    """
    racine = Path(str(getattr(settings, "MEDIA_ROOT", "") or "media"))
    cle_docx = f"livrables/{job.id}.docx"
    cle_pdf = f"livrables/{job.id}.pdf"

    livrable = produire_docx(job, destination=racine / cle_docx)
    octets = livrable.chemin.read_bytes()
    expire_le = timezone.now() + _retention(job)
    # Un seul nombre pour les deux : la date de purge du fichier et l'echeance
    # inscrite dans la signature du lien. Les separer, c'est promettre au client
    # une duree que le lien ne tient pas.
    duree_lien_s = int(_retention(job).total_seconds())

    _consigner_les_visuels_abandonnes(job, livrable.rapport)

    # La vérification porte sur le FICHIER, et elle passe avant l'enregistrement
    # des artefacts : ce qui refait le document après le contrôle doit être
    # contrôlé à son tour (règle 3). Ici plus rien ne le refait.
    controle = (
        verifier_livrable(job, livrable.chemin, assemblage=livrable.rapport)
        if verifier
        else None
    )
    if controle is not None and not controle.livrable:
        _log.error(
            "Job %s : livrable retenu à la vérification — %s",
            job.id, " | ".join(a.detail for a in controle.bloquantes),
        )

    artefact_docx, _ = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.DOCX,
        defaults={
            "status": ArtifactStatus.READY,
            "storage_key": cle_docx,
            "download_url": _url(cle_docx, duree_lien_s),
            "checksum_sha256": hashlib.sha256(octets).hexdigest(),
            "expires_at": expire_le,
        },
    )

    convertisseur = convertisseur or get_convertisseur_docx()
    try:
        conversion = convertisseur.convertir(livrable.chemin, racine / cle_pdf)
    except ConversionPdfError as erreur:
        _log.error("Job %s : conversion PDF échouée — %s", job.id, erreur)
        artefact_pdf, _ = DocumentArtifact.objects.update_or_create(
            job=job,
            kind=ArtifactKind.PDF,
            defaults={
                "status": ArtifactStatus.FAILED,
                "storage_key": "",
                "download_url": "",
                "checksum_sha256": "",
                "expires_at": expire_le,
            },
        )
        return LivrableAssemble(
            docx=artefact_docx, pdf=artefact_pdf, rapport=livrable.rapport,
            controle=controle,
        )

    artefact_pdf, _ = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.PDF,
        defaults={
            "status": ArtifactStatus.READY,
            "storage_key": cle_pdf,
            "download_url": _url(cle_pdf, duree_lien_s),
            "checksum_sha256": "",
            "expires_at": expire_le,
        },
    )
    _log.info(
        "Job %s : livrable Word et PDF prêts (%s, %s pages).",
        job.id, livrable.rapport.resume(), conversion.pages or "inconnu",
    )
    return LivrableAssemble(
        docx=artefact_docx,
        pdf=artefact_pdf,
        rapport=livrable.rapport,
        pages=conversion.pages,
        controle=controle,
    )
