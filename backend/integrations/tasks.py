from __future__ import annotations

from celery import shared_task

from customers.services import sync_subscription_from_systeme_payload
from generation.services import GenerationBootstrapError, bootstrap_generation_job
from generation.tasks import run_generation_job_task
from intake.models import IntakeStatus
from intake.services import OrderNotYetAvailableError, sync_intake_from_tally_payload
from monitoring.models import IncidentSeverity, OperationalIncident
from orders.services import UnknownOfferSlugError, sync_order_from_systeme_payload

from .models import IntegrationProvider, WebhookEvent, WebhookStatus

# Risque 1 — Race condition Systeme/Tally : si la commande n'existe pas encore
# quand Tally arrive, on retente jusqu'a 5 fois toutes les 60 s.
# Cela couvre un delai de propagation de 5 minutes entre les deux webhooks.
_RETRY_COUNTDOWN = 60
_RETRY_MAX = 5


@shared_task(  # type: ignore[untyped-decorator]
    name="integrations.process_webhook_event",
    autoretry_for=(OrderNotYetAvailableError,),
    retry_kwargs={"max_retries": _RETRY_MAX, "countdown": _RETRY_COUNTDOWN},
    retry_backoff=False,
)
def process_webhook_event(event_id: str) -> str:
    event = WebhookEvent.objects.get(id=event_id)
    try:
        if event.provider == IntegrationProvider.SYSTEME:
            try:
                sync_order_from_systeme_payload(event.raw_payload)
            except UnknownOfferSlugError:
                # Vente d'un produit non-EVKHA (formation, etude prete...).
                # Comportement normal si le webhook global Systeme.io est active.
                event.status = WebhookStatus.SKIPPED
                event.error_message = ""
                event.save(update_fields=["status", "error_message", "updated_at"])
                return event_id
        elif event.provider == IntegrationProvider.SYSTEME_SUB:
            sync_subscription_from_systeme_payload(event.raw_payload)
        elif event.provider == IntegrationProvider.TALLY:
            # OrderNotYetAvailableError est relancee telle quelle pour que
            # autoretry_for la catche et relance la tache sans marquer FAILED.
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
    except OrderNotYetAvailableError:
        # Laisse autoretry_for prendre la main — NE PAS marquer l'event FAILED.
        raise
    except Exception as exc:
        event.status = WebhookStatus.FAILED
        event.error_message = str(exc)
        event.save(update_fields=["status", "error_message", "updated_at"])
        raise

    event.status = WebhookStatus.PROCESSED
    event.error_message = ""
    event.save(update_fields=["status", "error_message", "updated_at"])
    return event_id
