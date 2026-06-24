from __future__ import annotations

from celery import shared_task

from customers.services import sync_subscription_from_systeme_payload
from generation.services import GenerationBootstrapError, bootstrap_generation_job
from generation.tasks import run_generation_job_task
from intake.models import IntakeStatus
from intake.services import sync_intake_from_tally_payload
from monitoring.models import IncidentSeverity, OperationalIncident
from orders.services import sync_order_from_systeme_payload

from .models import IntegrationProvider, WebhookEvent, WebhookStatus


@shared_task(name="integrations.process_webhook_event")  # type: ignore[untyped-decorator]
def process_webhook_event(event_id: str) -> str:
    event = WebhookEvent.objects.get(id=event_id)
    try:
        if event.provider == IntegrationProvider.SYSTEME:
            sync_order_from_systeme_payload(event.raw_payload)
        elif event.provider == IntegrationProvider.SYSTEME_SUB:
            sync_subscription_from_systeme_payload(event.raw_payload)
        elif event.provider == IntegrationProvider.TALLY:
            submission = sync_intake_from_tally_payload(event.raw_payload)
            # Déclenche la génération si les variables sont complètes.
            if submission.status == IntakeStatus.NORMALIZED:
                try:
                    job = bootstrap_generation_job(submission)
                    run_generation_job_task.delay(str(job.id))
                except GenerationBootstrapError as exc:
                    # Client a paye et soumis Tally, mais le type de livrable est
                    # invalide/manquant. Sans incident, la commande resterait orpheline.
                    OperationalIncident.objects.create(
                        title="Generation impossible apres soumission Tally",
                        severity=IncidentSeverity.HIGH,
                        order=submission.order,
                        details={
                            "error": str(exc),
                            "submission_id": str(submission.id),
                            "offer_slug": submission.order.offer.slug,
                            "deliverable_type_from_payload": submission.normalized_variables.get(
                                "DELIVERABLE_TYPE"
                            ),
                            "hint": (
                                "Verifier que le champ cache 'deliverable_type' du "
                                "formulaire Tally vaut bien market_study, competitor_study, "
                                "business_plan ou business_strategy."
                            ),
                        },
                    )
        else:
            msg = f"Unsupported webhook provider: {event.provider}"
            raise ValueError(msg)
    except Exception as exc:
        event.status = WebhookStatus.FAILED
        event.error_message = str(exc)
        event.save(update_fields=["status", "error_message", "updated_at"])
        raise

    event.status = WebhookStatus.PROCESSED
    event.error_message = ""
    event.save(update_fields=["status", "error_message", "updated_at"])
    return event_id
