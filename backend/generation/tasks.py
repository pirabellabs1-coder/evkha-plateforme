from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from monitoring.models import IncidentSeverity, OperationalIncident

from .echecs import marquer_echec
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
    try:
        run_generation_job(job)
    except Exception as erreur:  # noqa: BLE001 — dernier filet, voir `echecs`
        # Sans ce filet, une exception qui traverse le pipeline laisse le job
        # affiche `running` jusqu'a ce que le gardien des jobs bloques passe
        # — deux heures plus tard. Vecu le 31/07/2026 : refus de l'API en 0,9
        # seconde, job « en cours » pendant quatorze minutes (regle 1).
        #
        # On attrape `Exception` et non une liste de types : une liste fermee
        # serait incomplete par construction, et c'est precisement le cas non
        # prevu qui produit le silence (regle 4).
        marquer_echec(job, erreur, etape="generation")
        raise

    if job.status == JobStatus.DONE:
        # ── Passe QA (corrective) ───────────────────────────────────────────
        from .qa import run_qa_pass  # noqa: PLC0415
        run_qa_pass(job)

        # ── Boucle d'auto-correction + gate de livraison (bloquant) ─────────
        # Avant de bloquer, on régénère les chapitres fautifs (contamination,
        # incohérence chiffrée, troncature) avec les défauts en consigne, puis
        # on repasse le gate. Borné par EVKHA_CORRECTION_ROUNDS (défaut 1).
        from .correction import run_correction_loop  # noqa: PLC0415
        report = run_correction_loop(job)

        if not report.passed:
            GenerationJob.objects.filter(pk=job.pk).update(qa_status=QAStatus.BLOCKED)
            OperationalIncident.objects.create(
                title=f"Gate qualité : livraison bloquée (job {job.id})",
                severity=IncidentSeverity.HIGH,
                job=job,
                order=job.order,
                details=report.as_details(),
            )
            # Document assemblé pour relecture admin — AUCUN email client.
            # Par la MÊME chaîne que la livraison : relire un document produit
            # autrement que celui qui serait parti ne dit rien de ce qui serait
            # parti (règle 3).
            try:
                from django.conf import settings as _reglages  # noqa: PLC0415
                if getattr(_reglages, "EVKHA_LIVRABLE_WORD", True):
                    from documents.livrable_word import (  # noqa: PLC0415
                        assembler_livrable_word,
                    )
                    assembler_livrable_word(job)
                else:
                    from documents.services import assemble_document  # noqa: PLC0415
                    assemble_document(job)
            except Exception:  # noqa: BLE001 — l'assemblage admin ne doit pas masquer le blocage
                import logging  # noqa: PLC0415
                logging.getLogger(__name__).exception(
                    "Assemblage PDF admin impossible pour le job bloqué %s", job.id
                )
            return str(job.id)

        # Mémorise les faits de marché validés pour les futurs runs
        # sur le même secteur/pays (fact store inter-runs).
        try:
            from .fact_store import export_facts  # noqa: PLC0415
            export_facts(job)
        except Exception:  # noqa: BLE001
            import logging  # noqa: PLC0415
            logging.getLogger(__name__).exception(
                "fact_store: export non bloquant échoué pour le job %s", job.id
            )

        from delivery.tasks import deliver_job_task  # noqa: PLC0415
        deliver_job_task.delay(job_id)

    return str(job.id)
