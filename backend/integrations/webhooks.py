from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction

from .models import IntegrationProvider, WebhookEvent, WebhookStatus

# Maps each inbound provider to the setting holding its shared secret (M1).
_SECRET_SETTING: dict[str, str] = {
    IntegrationProvider.SYSTEME.value: "SYSTEME_WEBHOOK_SECRET",
    IntegrationProvider.TALLY.value: "TALLY_WEBHOOK_SECRET",
}


@dataclass(frozen=True)
class RecordedWebhook:
    event: WebhookEvent
    is_duplicate: bool


def stable_payload_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def is_webhook_authorized(provider: IntegrationProvider, provided_token: str) -> bool:
    """Constant-time shared-secret check.

    Fail-open when no secret is configured (dev/test), fail-closed otherwise.
    Les schemas de signature propres aux fournisseurs (ex. Tally `tally-signature`)
    restent a cabler une fois confirmes.
    """
    setting_name = _SECRET_SETTING.get(provider.value, "")
    expected = getattr(settings, setting_name, "") if setting_name else ""
    if not expected:
        return True
    if not provided_token:
        return False
    return hmac.compare_digest(provided_token, expected)


def record_webhook_event(
    *,
    provider: IntegrationProvider,
    event_id: str,
    payload: dict[str, Any],
) -> RecordedWebhook:
    payload_hash = stable_payload_hash(payload)

    try:
        with transaction.atomic():
            event = WebhookEvent.objects.create(
                provider=provider,
                event_id=event_id,
                payload_hash=payload_hash,
                raw_payload=payload,
                status=WebhookStatus.ACCEPTED,
            )
            return RecordedWebhook(event=event, is_duplicate=False)
    except IntegrityError:
        event = WebhookEvent.objects.get(provider=provider, event_id=event_id)
        if event.status != WebhookStatus.DUPLICATE:
            WebhookEvent.objects.filter(pk=event.pk).update(status=WebhookStatus.DUPLICATE)
            event.status = WebhookStatus.DUPLICATE
        return RecordedWebhook(event=event, is_duplicate=True)
