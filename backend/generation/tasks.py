from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from monitoring.models import IncidentSeverity, OperationalIncident

from .models import GenerationJob, JobStatus
from .runner import run_generation_job

# Un job RUNNING depuis plus de 2h est considere bloque (crash worker, timeout reseau).
_STUCK_JOB_TIMEOUT_HOURS = 2


@shared_task(name="generation.reset_stuck_generation_jobs")  # type: ignore[untyped-decorator]
def reset_stuck_generation_jobs() -> int:
    """Risque 6 — detecte et reset les jobs bloques en RUNNING depuis trop longtemps.

    Cree un incident HIGH pour chaque job concerne afin que l'admin puisse
    relancer manuellement depuis le dashboard.
    """
    cutoff = timezone.now() - timedelta(hours=_STUCK_JOB_TIMEOUT_HOURS)
    stuck_jobs = list(
        GenerationJob.objects.filter(status=JobStatus.RUNNING, updated_at__lt=cutoff)
        .select_related("order")
    )
    for job in stuck_jobs:
        GenerationJob.objects.filter(pk=job.pk).update(
            status=JobStatus.FAILED,
            error_message=(
                f"Job bloque detecte par le gardien automatique "
                f"(aucune activite depuis >{_STUCK_JOB_TIMEOUT_HOURS}h)."
            ),
        )
        OperationalIncident.objects.create(
            title=f"Job IA bloque — reset automatique (job {job.id})",
            severity=IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details={
                "stuck_since": str(job.updated_at),
                "deliverable_type": job.deliverable_type,
                "hint": "Relancer manuellement depuis le dashboard admin.",
            },
        )
    return len(stuck_jobs)


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
