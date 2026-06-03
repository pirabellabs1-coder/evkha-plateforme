from __future__ import annotations

from celery import shared_task

from .models import GenerationJob
from .runner import run_generation_job


@shared_task(name="generation.run_generation_job")  # type: ignore[untyped-decorator]
def run_generation_job_task(job_id: str) -> str:
    """Lance la generation complete d'un job (chapitres + garde-fous).

    L'assemblage du livrable est declenche ensuite par la chaine de livraison.
    """
    job = GenerationJob.objects.get(id=job_id)
    run_generation_job(job)
    return str(job.id)
