from __future__ import annotations

from celery import shared_task

from generation.models import GenerationJob

from .services import (
    deliver_job,
    generate_pdf_for_failed_job,
    purge_expired_artifacts,
    send_email_for_job,
)


@shared_task(name="delivery.deliver_job")  # type: ignore[untyped-decorator]
def deliver_job_task(job_id: str, renvoi_voulu: bool = False) -> str:
    """Livre un dossier terminé.

    `renvoi_voulu` n'est posé que par la console (`job_redeliver`) : tout autre
    appelant — fin de génération, gardien, tâche rejouée — laisse le défaut, et
    un dossier déjà livré ne renvoie alors aucun courriel.
    """
    job = GenerationJob.objects.get(id=job_id)
    batch = deliver_job(job, renvoi_voulu=renvoi_voulu)
    return str(batch.id)


@shared_task(name="delivery.generate_pdf_for_failed_job")  # type: ignore[untyped-decorator]
def generate_pdf_for_failed_job_task(job_id: str) -> str:
    job = GenerationJob.objects.get(id=job_id)
    artifact = generate_pdf_for_failed_job(job)
    return str(artifact.id)


@shared_task(name="delivery.send_email_for_job")  # type: ignore[untyped-decorator]
def send_email_for_job_task(job_id: str) -> str:
    job = GenerationJob.objects.get(id=job_id)
    batch = send_email_for_job(job)
    return str(batch.id)


@shared_task(name="delivery.purge_expired_artifacts")  # type: ignore[untyped-decorator]
def purge_expired_artifacts_task() -> int:
    return purge_expired_artifacts()
