"""Cycle de vie d'un chapitre : production, persistance, reprise, blocage."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from django.db import transaction

from intake.models import IntakeSubmission
from monitoring.models import IncidentSeverity, OperationalIncident

from ..modele.conformite import Arbitrage
from ..models import (
    ChapterGeneration,
    ChapterStatus,
    GenerationJob,
    JobStatus,
)
from ..socle.schema import Socle
from ..socle.services import socle_verrouille
from .configuration import type_document
from .runner import (
    ChapitreInvalideError,
    formater_motifs,
    generer_chapitre,
    payload_vers_markdown,
)
from .schema import ChapitrePayload

_log = logging.getLogger(__name__)

#: Temporisation exponentielle entre deux tentatives, en secondes.
#: 1re reprise à 30 s, 2e à 120 s. Assez long pour absorber une surcharge de
#: l'API, assez court pour qu'une étude ne traîne pas une heure sur un incident.
BASE_TEMPORISATION_S = 30
FACTEUR_TEMPORISATION = 4


def temporisation(tentative: int) -> int:
    """Délai avant la tentative `tentative` (1 = première reprise)."""
    return int(BASE_TEMPORISATION_S * FACTEUR_TEMPORISATION ** max(tentative - 1, 0))


class SocleManquantError(RuntimeError):
    """Aucun socle verrouillé : impossible de rédiger quoi que ce soit."""


def variables_du_job(job: GenerationJob) -> dict[str, object]:
    soumission = IntakeSubmission.objects.filter(order=job.order).first()
    return dict(soumission.normalized_variables) if soumission else {}


#: Préfixes de `error_message` sur un chapitre TERMINÉ. Ils ne signalent pas un
#: échec : ils disent ce que la passe de conformité a laissé passer, ou n'a pas
#: pu juger. Distincts de `[contrat] `, qui porte un refus et se relit dans le
#: prompt de la tentative suivante.
PREFIXE_ECARTS = "[écarts acceptés] "
PREFIXE_NON_CONTROLE = "[non contrôlé] "


def _mention_arbitrage(arbitrage: Arbitrage | None) -> str:
    """Trace lisible de la passe de conformité sur un chapitre accepté.

    Vide quand tout est conforme : une mention systématique se lirait comme du
    bruit et finirait ignorée, y compris le jour où elle dit quelque chose.
    """
    if arbitrage is None:
        return ""
    if arbitrage.non_controle:
        return (PREFIXE_NON_CONTROLE + arbitrage.non_controle)[:2000]
    if arbitrage.acceptes:
        return (PREFIXE_ECARTS + " ; ".join(arbitrage.acceptes))[:2000]
    return ""


@transaction.atomic
def enregistrer_chapitre(
    chapter: ChapterGeneration,
    payload: ChapitrePayload,
    consommation: Mapping[str, int],
    model: str | None = None,
    arbitrage: Arbitrage | None = None,
) -> ChapterGeneration:
    """Persiste la sortie structurée ET son rendu markdown.

    Les deux : la structure est la nouvelle source de vérité, le markdown
    permet à la chaîne de rendu actuelle de continuer à produire un document
    tant que le lot 3 n'est pas livré.
    """
    from ..cost import record_chapter_cost  # noqa: PLC0415 — évite un cycle

    chapter.payload = payload.model_dump(mode="json")
    chapter.content = payload_vers_markdown(payload)
    chapter.operational_summary = payload.resume
    chapter.status = ChapterStatus.DONE
    # Un chapitre accepté malgré des écarts de forme reste DONE — mais ne passe
    # pas pour parfait. Le préfixe le distingue de `[contrat] `, que la
    # tentative suivante relit pour se corriger : celui-ci ne doit surtout pas
    # être réinjecté dans un prompt, la décision est prise.
    chapter.error_message = _mention_arbitrage(arbitrage)
    chapter.save(
        update_fields=[
            "payload", "content", "operational_summary",
            "status", "error_message", "updated_at",
        ]
    )
    record_chapter_cost(
        chapter=chapter,
        input_tokens=consommation.get("input_tokens", 0),
        output_tokens=consommation.get("output_tokens", 0),
        model=model,
    )
    return chapter


def produire_chapitre(
    job: GenerationJob,
    numero: int,
    *,
    client: Any,
    socle: Socle | None = None,
    derniere_tentative: bool | None = None,
) -> ChapterGeneration:
    """Produit et enregistre un chapitre. Idempotent : un chapitre DONE est rendu tel quel.

    C'est l'unité de travail de la tâche Celery. L'idempotence est exigée par
    le §6.2 : une tâche rejouée après un crash de worker ne doit pas repayer
    un chapitre déjà écrit.
    """
    chapter = job.chapters.get(chapter_number=numero)
    if chapter.status == ChapterStatus.DONE and chapter.payload:
        return chapter

    socle = socle or socle_verrouille(job)
    if socle is None:
        msg = (
            f"Job {job.id} : aucun socle verrouillé. Un chapitre ne peut pas "
            "être rédigé avant que ses chiffres de référence soient établis."
        )
        raise SocleManquantError(msg)

    chapter.status = ChapterStatus.RUNNING
    chapter.save(update_fields=["status", "updated_at"])

    try:
        payload, consommation, arbitrage = generer_chapitre(
            client=client,
            chapter=chapter,
            socle=socle,
            variables=variables_du_job(job),
            derniere_tentative=derniere_tentative,
        )
    except ChapitreInvalideError as erreur:
        # Les motifs sont conservés : la tentative suivante les recevra.
        ChapterGeneration.objects.filter(pk=chapter.pk).update(
            status=ChapterStatus.FAILED,
            error_message=formater_motifs(erreur.motifs),
            retry_count=chapter.retry_count + 1,
        )
        raise

    return enregistrer_chapitre(chapter, payload, consommation, arbitrage=arbitrage)


def regenerer_chapitre(job: GenerationJob, numero: int, *, client: Any) -> ChapterGeneration:
    """Régénère UN chapitre sans toucher aux autres.

    Critère de recette du cahier des charges. La remise à zéro est explicite :
    sans elle, `produire_chapitre` rendrait le chapitre déjà DONE tel quel.
    """
    chapter = job.chapters.get(chapter_number=numero)
    ChapterGeneration.objects.filter(pk=chapter.pk).update(
        status=ChapterStatus.PENDING,
        payload={},
        content="",
        operational_summary="",
        error_message="",
    )
    chapter.refresh_from_db()
    return produire_chapitre(job, numero, client=client)


def marquer_intervention_requise(
    job: GenerationJob, numero: int, motifs: list[str], tentatives: int
) -> None:
    """Le chapitre a épuisé ses tentatives : l'étude s'arrête, un humain reprend.

    Aucun e-mail client n'est déclenché — l'étude est incomplète. C'est le
    cinquième critère de recette.
    """
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.INTERVENTION_REQUISE,
        error_message=(
            f"Chapitre {numero} : {tentatives} tentative(s) échouée(s). "
            + " ; ".join(motifs)
        )[:2000],
    )
    OperationalIncident.objects.create(
        title=f"Chapitre {numero} bloqué après {tentatives} tentatives (job {job.id})",
        severity=IncidentSeverity.HIGH,
        job=job,
        order=job.order,
        details={
            "chapitre": numero,
            "tentatives": tentatives,
            "motifs": motifs[:20],
            "consigne": (
                "Étude incomplète : aucun e-mail client. Corriger le socle ou "
                "le prompt du chapitre, puis relancer depuis le tableau de bord."
            ),
        },
    )
    _log.error("Job %s : chapitre %s bloqué après %s tentatives.", job.id, numero, tentatives)


def chapitres_a_produire(job: GenerationJob) -> list[int]:
    """Numéros restant à produire, dans l'ordre. Piloté par la configuration."""
    document = type_document(str(job.deliverable_type))
    prevus = [bp.number for bp in document.chapitres()]
    faits = set(
        job.chapters.filter(status=ChapterStatus.DONE)
        .exclude(payload={})
        .values_list("chapter_number", flat=True)
    )
    return [numero for numero in prevus if numero not in faits]


def etude_complete(job: GenerationJob) -> bool:
    return not chapitres_a_produire(job)
