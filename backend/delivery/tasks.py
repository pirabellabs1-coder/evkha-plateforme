from __future__ import annotations

from celery import shared_task

from generation.models import GenerationJob

from .services import deliver_job, purge_expired_artifacts


@shared_task(name="delivery.deliver_job")  # type: ignore[untyped-decorator]
def deliver_job_task(job_id: str) -> str:
    job = GenerationJob.objects.get(id=job_id)
    batch = deliver_job(job)
    return str(batch.id)


@shared_task(name="delivery.purge_expired_artifacts")  # type: ignore[untyped-decorator]
def purge_expired_artifacts_task() -> int:
    return purge_expired_artifacts()
