from __future__ import annotations

from decimal import Decimal

from catalog.models import DeliverableType
from intake.models import IntakeStatus, IntakeSubmission

from .blueprints import chapters_for_deliverable
from .models import ChapterGeneration, ChapterStatus, GenerationJob, JobStatus

# Livrables couverts par le moteur de generation (phases 2-5).
_SUPPORTED_DELIVERABLES = frozenset(
    {
        DeliverableType.MARKET_STUDY,
        DeliverableType.COMPETITOR_STUDY,
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.BUSINESS_STRATEGY,
    }
)

# Budget IA = 2.00 EUR pour tous les types (contrainte métier stricte).
# Garanti par max_tokens = 3500 dans integrations/claude.py :
#   pire cas MARKET_STUDY (30 appels) × cout max/appel ≈ 1.74 EUR < 2.00 EUR.
_BUDGET_EUR_BY_TYPE: dict[str, Decimal] = {
    DeliverableType.MARKET_STUDY: Decimal("2.0000"),
    DeliverableType.BUSINESS_PLAN: Decimal("2.0000"),
    DeliverableType.BUSINESS_STRATEGY: Decimal("2.0000"),
    DeliverableType.COMPETITOR_STUDY: Decimal("2.0000"),
}


class GenerationBootstrapError(ValueError):
    pass


def bootstrap_generation_job(submission: IntakeSubmission) -> GenerationJob:
    if submission.status != IntakeStatus.NORMALIZED:
        msg = "Generation requires a normalized intake submission."
        raise GenerationBootstrapError(msg)

    # Offres B2B génériques (abonnements, crédits suppl.) :
    # deliverable_type est dans le payload Tally.
    deliverable_type = (
        submission.order.offer.deliverable_type
        or submission.normalized_variables.get("DELIVERABLE_TYPE")
    )
    if deliverable_type not in _SUPPORTED_DELIVERABLES:
        msg = f"Unsupported deliverable type for generation: {deliverable_type}"
        raise GenerationBootstrapError(msg)

    job, _created = GenerationJob.objects.get_or_create(
        order=submission.order,
        defaults={
            "deliverable_type": str(deliverable_type),
            "status": JobStatus.PENDING,
            "budget_eur": _BUDGET_EUR_BY_TYPE[deliverable_type],
        },
    )

    for blueprint in chapters_for_deliverable(deliverable_type):
        ChapterGeneration.objects.get_or_create(
            job=job,
            chapter_number=blueprint.number,
            defaults={
                "chapter_title": blueprint.title,
                "prompt_key": blueprint.prompt_key,
            },
        )

    return job


def relaunch_generation_job(job: GenerationJob) -> None:
    """Réinitialise les statuts d'un job échoué/annulé pour permettre sa relance.

    Recale aussi le budget sur la valeur correcte pour le type de livrable —
    couvre les jobs créés avant l'introduction de _BUDGET_EUR_BY_TYPE.
    """
    job.status = JobStatus.PENDING
    job.error_message = ""
    job.started_at = None
    job.completed_at = None
    # Recale le budget uniquement si aucun chapitre n'est déjà DONE (job vierge).
    # Pour un job partiellement généré, le coût cumulé est déjà fixé — on ne touche
    # pas au budget afin d'éviter un faux incident dès le redémarrage.
    if not job.chapters.filter(status=ChapterStatus.DONE).exists():
        job.budget_eur = _BUDGET_EUR_BY_TYPE.get(job.deliverable_type, job.budget_eur)
    job.save(update_fields=["status", "error_message", "started_at", "completed_at", "budget_eur"])

    job.chapters.filter(
        status__in=[ChapterStatus.FAILED, ChapterStatus.SKIPPED]
    ).update(status=ChapterStatus.PENDING, error_message="")
