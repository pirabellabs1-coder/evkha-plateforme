from __future__ import annotations

from celery import shared_task

from .models import GenerationJob, JobStatus
from .runner import run_generation_job


@shared_task(name="generation.run_generation_job")  # type: ignore[untyped-decorator]
def run_generation_job_task(job_id: str) -> str:
    """Lance la generation complete d'un job (chapitres + garde-fous).

    Si la generation reussit, declenche automatiquement la livraison
    (assemblage PDF + email client).
    """
    job = GenerationJob.objects.get(id=job_id)
    run_generation_job(job)
    if job.status == JobStatus.DONE:
        from delivery.tasks import deliver_job_task  # noqa: PLC0415
        deliver_job_task.delay(job_id)
    return str(job.id)
