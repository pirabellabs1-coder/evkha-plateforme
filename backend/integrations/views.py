from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from monitoring.models import IncidentSeverity, OperationalIncident

from .models import IntegrationProvider, WebhookEvent, WebhookStatus
from .tasks import process_webhook_event
from .webhooks import is_webhook_authorized, record_webhook_event, stable_payload_hash


def _json_body(request: HttpRequest) -> dict[str, Any]:
    if not request.body:
        return {}
    parsed = json.loads(request.body.decode("utf-8"))
    if not isinstance(parsed, dict):
        msg = "Webhook payload must be a JSON object."
        raise ValueError(msg)
    return parsed


def _event_id(payload: dict[str, Any], fallback_prefix: str) -> str:
    for key in ("event_id", "id", "order_id", "submission_id"):
        value = payload.get(key)
        if value:
            return str(value)
    return f"{fallback_prefix}:{stable_payload_hash(payload)}"


def _extract_token(request: HttpRequest) -> str:
    header = request.headers.get("X-Webhook-Token", "")
    if header:
        return header
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.GET.get("token", "")


def _enqueue_processing(event: WebhookEvent) -> None:
    """Enqueue async processing; surface broker failures as incidents (M3)."""
    try:
        process_webhook_event.delay(str(event.id))
    except Exception as exc:  # noqa: BLE001 - broker outage must not be swallowed
        OperationalIncident.objects.create(
            title=f"Echec d'enfilement Celery (webhook {event.provider})",
            severity=IncidentSeverity.HIGH,
            details={
                "event_id": str(event.id),
                "provider": event.provider,
                "error": str(exc),
            },
        )
        WebhookEvent.objects.filter(pk=event.pk).update(
            status=WebhookStatus.FAILED,
            error_message=f"enqueue failed: {exc}",
        )


def _handle_webhook(
    request: HttpRequest,
    *,
    provider: IntegrationProvider,
    fallback_prefix: str,
) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed."}, status=405)

    if not is_webhook_authorized(provider, _extract_token(request)):
        return JsonResponse({"accepted": False, "error": "unauthorized"}, status=401)

    try:
        payload = _json_body(request)
    except (json.JSONDecodeError, ValueError) as exc:
        return JsonResponse({"accepted": False, "error": str(exc)}, status=400)

    # Systeme.io automations "Appeler un webhook" envoient un payload fixe
    # sans champs custom. On accepte offer_slug / order_id / email en query
    # params pour router correctement depuis l'URL de l'automatisation.
    for _qkey in ("offer_slug", "order_id", "email"):
        if _qkey not in payload and _qkey in request.GET:
            payload = {**payload, _qkey: request.GET[_qkey]}

    recorded = record_webhook_event(
        provider=provider,
        event_id=_event_id(payload, fallback_prefix),
        payload=payload,
    )
    if not recorded.is_duplicate:
        _enqueue_processing(recorded.event)

    return JsonResponse(
        {
            "accepted": True,
            "duplicate": recorded.is_duplicate,
            "event_id": str(recorded.event.id),
        },
        status=202,
    )


@csrf_exempt
def systeme_order_webhook(request: HttpRequest) -> JsonResponse:
    return _handle_webhook(
        request, provider=IntegrationProvider.SYSTEME, fallback_prefix="systeme-order"
    )


@csrf_exempt
def systeme_subscription_webhook(request: HttpRequest) -> JsonResponse:
    return _handle_webhook(
        request, provider=IntegrationProvider.SYSTEME_SUB, fallback_prefix="systeme-sub"
    )


@csrf_exempt
def tally_intake_webhook(request: HttpRequest) -> JsonResponse:
    return _handle_webhook(request, provider=IntegrationProvider.TALLY, fallback_prefix="tally")
