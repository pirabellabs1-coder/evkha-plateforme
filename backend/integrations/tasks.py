from __future__ import annotations

from celery import shared_task
from intake.services import sync_intake_from_tally_payload
from orders.services import sync_order_from_systeme_payload

from .models import IntegrationProvider, WebhookEvent, WebhookStatus


@shared_task(name="integrations.process_webhook_event")  # type: ignore[untyped-decorator]
def process_webhook_event(event_id: str) -> str:
    event = WebhookEvent.objects.get(id=event_id)
    try:
        if event.provider == IntegrationProvider.SYSTEME:
            sync_order_from_systeme_payload(event.raw_payload)
        elif event.provider == IntegrationProvider.TALLY:
            sync_intake_from_tally_payload(event.raw_payload)
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
