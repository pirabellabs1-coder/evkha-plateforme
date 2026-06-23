from __future__ import annotations

from catalog.models import DeliverableType
from intake.models import IntakeStatus, IntakeSubmission

from .blueprints import chapters_for_deliverable
from .models import ChapterGeneration, GenerationJob, JobStatus

# Livrables couverts par le moteur de generation (phases 2-5).
_SUPPORTED_DELIVERABLES = frozenset(
    {
        DeliverableType.MARKET_STUDY,
        DeliverableType.COMPETITOR_STUDY,
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.BUSINESS_STRATEGY,
    }
)


class GenerationBootstrapError(ValueError):
    pass


def bootstrap_generation_job(submission: IntakeSubmission) -> GenerationJob:
    if submission.status != IntakeStatus.NORMALIZED:
        msg = "Generation requires a normalized intake submission."
        raise GenerationBootstrapError(msg)

    # Offres B2B génériques (abonnements, crédits suppl.) : deliverable_type est dans le payload Tally.
    deliverable_type = submission.order.offer.deliverable_type or submission.normalized_variables.get(
        "DELIVERABLE_TYPE"
    )
    if deliverable_type not in _SUPPORTED_DELIVERABLES:
        msg = f"Unsupported deliverable type for generation: {deliverable_type}"
        raise GenerationBootstrapError(msg)

    job, _created = GenerationJob.objects.get_or_create(
        order=submission.order,
        defaults={
            "deliverable_type": str(deliverable_type),
            "status": JobStatus.PENDING,
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
