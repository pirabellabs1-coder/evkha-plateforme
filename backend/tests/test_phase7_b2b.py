"""Phase 7 — Accès B2B : Subscription model + webhook Systeme.io.

Scope (brief p.8, livrable n°3, D9) :
  Gestion automatique des accès B2B selon statut abonnement Systeme.io.
  Ouverture à la souscription, fermeture à l'arrêt.

Tests (tous déterministes, aucun appel réseau) :
  - sync_subscription : création / activation / annulation
  - sync_subscription : passage customer_type B2C → B2B
  - sync_subscription : champs manquants → SubscriptionIngestionError
  - sync_subscription : event_type inconnu → SubscriptionIngestionError
  - sync_subscription : idempotence (update_or_create)
  - has_active_subscription : property Customer
  - Webhook endpoint POST /webhooks/systeme/subscription/ → 202
  - Webhook endpoint : doublon → 202 duplicate=True
  - process_webhook_event task → route SYSTEME_SUB → subscription
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client

from customers.models import (
    Customer,
    CustomerType,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
)
from customers.services import (
    SubscriptionIngestionError,
    sync_subscription_from_systeme_payload,
)
from integrations.models import IntegrationProvider, WebhookEvent, WebhookStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sub_started_payload() -> dict[str, Any]:
    return {
        "event_type": "subscription.started",
        "subscription": {"id": "sub-001"},
        "contact": {
            "id": "cid-001",
            "email": "rym@example.com",
            "first_name": "Rym",
            "last_name": "Test",
            "company_name": "Rym Consulting",
        },
        "product": {"slug": "pro"},
    }


@pytest.fixture()
def sub_cancelled_payload() -> dict[str, Any]:
    return {
        "event_type": "subscription.cancelled",
        "subscription": {"id": "sub-001"},
        "contact": {"email": "rym@example.com"},
        "product": {"slug": "pro"},
    }


@pytest.fixture()
def sub_renewed_payload() -> dict[str, Any]:
    return {
        "event_type": "subscription.renewed",
        "subscription": {"id": "sub-002"},
        "contact": {"email": "kenya@example.com"},
        "product": {"slug": "solo"},
    }


# ---------------------------------------------------------------------------
# sync_subscription_from_systeme_payload
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sync_subscription_creates_active_subscription(
    sub_started_payload: dict[str, Any],
) -> None:
    sub = sync_subscription_from_systeme_payload(sub_started_payload)

    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.tier == SubscriptionTier.PRO
    assert sub.systeme_subscription_id == "sub-001"
    assert sub.customer.email == "rym@example.com"


@pytest.mark.django_db
def test_sync_subscription_upgrades_customer_to_b2b(
    sub_started_payload: dict[str, Any],
) -> None:
    # Client existant B2C avant la souscription
    Customer.objects.create(email="rym@example.com", customer_type=CustomerType.B2C)

    sync_subscription_from_systeme_payload(sub_started_payload)

    customer = Customer.objects.get(email="rym@example.com")
    assert customer.customer_type == CustomerType.B2B


@pytest.mark.django_db
def test_sync_subscription_cancellation(
    sub_started_payload: dict[str, Any],
    sub_cancelled_payload: dict[str, Any],
) -> None:
    sync_subscription_from_systeme_payload(sub_started_payload)

    sub = sync_subscription_from_systeme_payload(sub_cancelled_payload)

    assert sub.status == SubscriptionStatus.CANCELLED
    assert sub.systeme_subscription_id == "sub-001"


@pytest.mark.django_db
def test_sync_subscription_renewal_creates_new_record(
    sub_renewed_payload: dict[str, Any],
) -> None:
    sub = sync_subscription_from_systeme_payload(sub_renewed_payload)

    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.tier == SubscriptionTier.SOLO
    assert sub.customer.email == "kenya@example.com"


@pytest.mark.django_db
def test_sync_subscription_idempotent(sub_started_payload: dict[str, Any]) -> None:
    sub1 = sync_subscription_from_systeme_payload(sub_started_payload)
    sub2 = sync_subscription_from_systeme_payload(sub_started_payload)

    assert sub1.id == sub2.id
    assert Subscription.objects.filter(systeme_subscription_id="sub-001").count() == 1


@pytest.mark.django_db
def test_sync_subscription_missing_email_raises() -> None:
    payload: dict[str, Any] = {
        "event_type": "subscription.started",
        "subscription": {"id": "sub-x"},
        "product": {"slug": "pro"},
    }
    with pytest.raises(SubscriptionIngestionError, match="email"):
        sync_subscription_from_systeme_payload(payload)


@pytest.mark.django_db
def test_sync_subscription_missing_subscription_id_raises() -> None:
    payload: dict[str, Any] = {
        "event_type": "subscription.started",
        "contact": {"email": "test@example.com"},
        "product": {"slug": "pro"},
    }
    with pytest.raises(SubscriptionIngestionError, match="subscription_id"):
        sync_subscription_from_systeme_payload(payload)


@pytest.mark.django_db
def test_sync_subscription_unknown_event_type_raises() -> None:
    payload: dict[str, Any] = {
        "event_type": "order.completed",  # ordre, pas abonnement
        "subscription": {"id": "sub-x"},
        "contact": {"email": "test@example.com"},
        "product": {"slug": "pro"},
    }
    with pytest.raises(SubscriptionIngestionError, match="Unhandled"):
        sync_subscription_from_systeme_payload(payload)


@pytest.mark.django_db
def test_sync_subscription_unknown_tier_slug_defaults_to_solo(
    sub_started_payload: dict[str, Any],
) -> None:
    sub_started_payload["product"]["slug"] = "super-pack-inconnu"
    sub = sync_subscription_from_systeme_payload(sub_started_payload)
    assert sub.tier == SubscriptionTier.SOLO


# ---------------------------------------------------------------------------
# Customer.has_active_subscription
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_has_active_subscription_true(sub_started_payload: dict[str, Any]) -> None:
    sync_subscription_from_systeme_payload(sub_started_payload)
    customer = Customer.objects.get(email="rym@example.com")
    assert customer.has_active_subscription is True


@pytest.mark.django_db
def test_has_active_subscription_false_after_cancel(
    sub_started_payload: dict[str, Any],
    sub_cancelled_payload: dict[str, Any],
) -> None:
    sync_subscription_from_systeme_payload(sub_started_payload)
    sync_subscription_from_systeme_payload(sub_cancelled_payload)
    customer = Customer.objects.get(email="rym@example.com")
    assert customer.has_active_subscription is False


@pytest.mark.django_db
def test_has_active_subscription_false_when_none() -> None:
    customer = Customer.objects.create(email="new@example.com")
    assert customer.has_active_subscription is False


# ---------------------------------------------------------------------------
# Webhook endpoint POST /webhooks/systeme/subscription/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_subscription_webhook_returns_202(sub_started_payload: dict[str, Any]) -> None:
    client = Client()
    response = client.post(
        "/webhooks/systeme/subscription/",
        data=json.dumps(sub_started_payload),
        content_type="application/json",
    )
    assert response.status_code == 202
    data = response.json()
    assert data["accepted"] is True
    assert data["duplicate"] is False


@pytest.mark.django_db
def test_subscription_webhook_duplicate_returns_202(
    sub_started_payload: dict[str, Any],
) -> None:
    client = Client()
    client.post(
        "/webhooks/systeme/subscription/",
        data=json.dumps(sub_started_payload),
        content_type="application/json",
    )
    # Deuxième envoi identique
    response = client.post(
        "/webhooks/systeme/subscription/",
        data=json.dumps(sub_started_payload),
        content_type="application/json",
    )
    assert response.status_code == 202
    assert response.json()["duplicate"] is True


@pytest.mark.django_db
def test_subscription_webhook_rejects_get() -> None:
    client = Client()
    response = client.get("/webhooks/systeme/subscription/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_subscription_webhook_stores_provider_systeme_sub(
    sub_started_payload: dict[str, Any],
) -> None:
    client = Client()
    with patch("integrations.views._enqueue_processing"):
        client.post(
            "/webhooks/systeme/subscription/",
            data=json.dumps(sub_started_payload),
            content_type="application/json",
        )
    event = WebhookEvent.objects.filter(provider=IntegrationProvider.SYSTEME_SUB).first()
    assert event is not None


# ---------------------------------------------------------------------------
# process_webhook_event task — route SYSTEME_SUB
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_process_webhook_routes_systeme_sub_to_subscription_service(
    sub_started_payload: dict[str, Any],
) -> None:
    event = WebhookEvent.objects.create(
        provider=IntegrationProvider.SYSTEME_SUB,
        event_id="sub-task-001",
        payload_hash="abc",
        raw_payload=sub_started_payload,
        status=WebhookStatus.ACCEPTED,
    )

    with patch(
        "integrations.tasks.sync_subscription_from_systeme_payload"
    ) as mock_sync:
        from integrations.tasks import process_webhook_event
        process_webhook_event(str(event.id))

    mock_sync.assert_called_once_with(sub_started_payload)
    event.refresh_from_db()
    assert event.status == WebhookStatus.PROCESSED
