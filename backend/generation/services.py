from __future__ import annotations

from catalog.models import DeliverableType
from intake.models import IntakeStatus, IntakeSubmission

from .blueprints import chapters_for_deliverable
from .models import ChapterGeneration, GenerationJob, JobStatus


class GenerationBootstrapError(ValueError):
    pass


def bootstrap_generation_job(submission: IntakeSubmission) -> GenerationJob:
    if submission.status != IntakeStatus.NORMALIZED:
        msg = "Generation requires a normalized intake submission."
        raise GenerationBootstrapError(msg)

    deliverable_type = submission.order.offer.deliverable_type
    if deliverable_type != DeliverableType.MARKET_STUDY:
        msg = f"Phase 2 only supports market study, got: {deliverable_type}"
        raise GenerationBootstrapError(msg)

    job, _created = GenerationJob.objects.get_or_create(
        order=submission.order,
        defaults={
            "deliverable_type": deliverable_type,
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
