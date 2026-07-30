"""Tâches Celery — une par chapitre, indépendantes et idempotentes (§6.2).

Chaque chapitre est sa propre tâche. Une étude n'est donc plus une tâche unique
de trente minutes qu'un redémarrage de worker perd en entier : c'est une suite
de tâches courtes, reprenables une par une.
"""
from __future__ import annotations

import logging

from celery import Task, shared_task

from ..models import GenerationJob, JobStatus
from .configuration import type_document
from .runner import ChapitreInvalideError
from .services import (
    chapitres_a_produire,
    marquer_intervention_requise,
    produire_chapitre,
    temporisation,
)

_log = logging.getLogger(__name__)


@shared_task(bind=True, name="generation.chapitres.produire")  # type: ignore[untyped-decorator]
def produire_chapitre_task(self: Task, job_id: str, numero: int) -> str:
    """Produit un chapitre, avec reprise exponentielle puis blocage de l'étude.

    `tentatives_max` vient de la configuration du type de document : 3 par
    défaut, c'est-à-dire un premier essai puis deux reprises (30 s, puis 120 s).
    Après quoi l'étude passe en `intervention_requise` et l'administrateur est
    alerté — aucun e-mail client ne peut partir sur une étude incomplète.
    """
    from integrations.claude import get_claude_client  # noqa: PLC0415

    job = GenerationJob.objects.get(id=job_id)
    document = type_document(str(job.deliverable_type))
    tentative = self.request.retries + 1

    try:
        produire_chapitre(job, numero, client=get_claude_client())
    except Exception as erreur:  # noqa: BLE001 — toute erreur ouvre la reprise
        motifs = (
            erreur.motifs if isinstance(erreur, ChapitreInvalideError) else [str(erreur)]
        )
        if tentative >= document.tentatives_max:
            marquer_intervention_requise(job, numero, motifs, tentative)
            return f"bloque:{numero}"

        delai = temporisation(tentative)
        _log.warning(
            "Job %s chapitre %s : tentative %s/%s échouée, reprise dans %s s.",
            job_id, numero, tentative, document.tentatives_max, delai,
        )
        raise self.retry(
            exc=erreur, countdown=delai, max_retries=document.tentatives_max - 1
        ) from erreur

    return f"ok:{numero}"


@shared_task(name="generation.chapitres.orchestrer")  # type: ignore[untyped-decorator]
def orchestrer_chapitres_task(job_id: str) -> str:
    """Enchaîne les chapitres restants, dans l'ordre.

    L'ordre est imposé : chaque chapitre lit les résumés des précédents. La
    liste vient de la configuration du type de document — il n'y a nulle part
    de constante `22`.
    """
    from celery import chain  # noqa: PLC0415

    job = GenerationJob.objects.get(id=job_id)
    restants = chapitres_a_produire(job)
    if not restants:
        return "rien-a-faire"

    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.RUNNING)

    chain(
        *[produire_chapitre_task.si(job_id, numero) for numero in restants]
    ).apply_async()
    return f"enchaine:{len(restants)}"
