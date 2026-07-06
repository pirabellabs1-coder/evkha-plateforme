from __future__ import annotations

from celery import shared_task

from .models import GenerationJob, JobStatus
from .runner import run_generation_job


@shared_task(name="generation.run_generation_job")  # type: ignore[untyped-decorator]
def run_generation_job_task(job_id: str) -> str:
    """Lance la generation complete d'un job (chapitres + QA + livraison).

    Pipeline :
    1. Génération de tous les chapitres (runner)
    2. Passe QA post-génération (correction code fence, tables coupées,
       complétion IA des troncatures sévères)
    3. Livraison (assemblage PDF + email client) — uniquement si DONE
    """
    job = GenerationJob.objects.get(id=job_id)
    run_generation_job(job)

    if job.status == JobStatus.DONE:
        # ── Passe QA ────────────────────────────────────────────────────────
        # Non bloquante : un échec QA partiel n'empêche pas la livraison,
        # il est tracé dans qa_status pour monitoring admin.
        from .qa import run_qa_pass  # noqa: PLC0415
        run_qa_pass(job)

        from delivery.tasks import deliver_job_task  # noqa: PLC0415
        deliver_job_task.delay(job_id)

    return str(job.id)
