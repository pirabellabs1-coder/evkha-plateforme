from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from monitoring.models import IncidentSeverity, OperationalIncident

from .models import GenerationJob, JobStatus, QAStatus
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
    """Lance la generation complete d'un job (chapitres + QA + gate + livraison).

    Pipeline :
    1. Génération de tous les chapitres (runner)
    2. Passe QA post-génération (correction code fence, tables coupées,
       complétion IA des troncatures sévères)
    3. GATE DE LIVRAISON (Brique 3, brief client juillet 2026) — BLOQUANT :
       contamination pipeline, cohérence chiffrée vs brief, complétude des
       verticales, troncature. Un seul échec → le document NE PART PAS chez
       le client ; incident HIGH + statut qa BLOCKED ; le PDF est tout de
       même assemblé pour relecture admin (sans email). La livraison ne peut
       alors être déclenchée que manuellement depuis le dashboard.
    4. Livraison (assemblage PDF + email client) — uniquement si gate PASSED
    """
    job = GenerationJob.objects.get(id=job_id)
    run_generation_job(job)

    if job.status == JobStatus.DONE:
        # ── Passe QA (corrective) ───────────────────────────────────────────
        from .qa import run_qa_pass  # noqa: PLC0415
        run_qa_pass(job)

        # ── Gate de livraison (bloquant) ────────────────────────────────────
        from .gate import run_delivery_gate  # noqa: PLC0415
        report = run_delivery_gate(job)

        if not report.passed:
            GenerationJob.objects.filter(pk=job.pk).update(qa_status=QAStatus.BLOCKED)
            OperationalIncident.objects.create(
                title=f"Gate qualité : livraison bloquée (job {job.id})",
                severity=IncidentSeverity.HIGH,
                job=job,
                order=job.order,
                details=report.as_details(),
            )
            # PDF assemblé pour relecture admin — AUCUN email client.
            try:
                from documents.services import assemble_document  # noqa: PLC0415
                assemble_document(job)
            except Exception:  # noqa: BLE001 — l'assemblage admin ne doit pas masquer le blocage
                import logging  # noqa: PLC0415
                logging.getLogger(__name__).exception(
                    "Assemblage PDF admin impossible pour le job bloqué %s", job.id
                )
            return str(job.id)

        from delivery.tasks import deliver_job_task  # noqa: PLC0415
        deliver_job_task.delay(job_id)

    return str(job.id)
