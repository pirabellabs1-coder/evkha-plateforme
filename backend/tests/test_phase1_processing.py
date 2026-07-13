from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from intake.models import IntakeStatus, IntakeSubmission
from integrations.models import IntegrationProvider, WebhookEvent, WebhookStatus
from integrations.tasks import process_webhook_event
from orders.models import Order, OrderStatus


@pytest.mark.django_db
def test_process_systeme_event_creates_customer_and_order() -> None:
    Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    event = WebhookEvent.objects.create(
        provider=IntegrationProvider.SYSTEME,
        event_id="evt_order",
        payload_hash="abc",
        raw_payload={
            "order_id": "order_123",
            "customer_email": "client@example.com",
            "offer_slug": "etude-marche",
            "customer": {"first_name": "Eva"},
        },
    )

    process_webhook_event(str(event.id))

    event.refresh_from_db()
    assert event.status == WebhookStatus.PROCESSED
    assert Customer.objects.filter(email="client@example.com").exists()
    order = Order.objects.get(systeme_order_id="order_123")
    assert order.status == OrderStatus.WAITING_INTAKE
    assert order.offer.slug == "etude-marche"


@pytest.mark.django_db
def test_process_tally_event_creates_normalized_intake_submission() -> None:
    offer = Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="client@example.com")
    Order.objects.create(systeme_order_id="order_123", customer=customer, offer=offer)
    event = WebhookEvent.objects.create(
        provider=IntegrationProvider.TALLY,
        event_id="evt_tally",
        payload_hash="def",
        raw_payload={
            "order_id": "order_123",
            "answers": {
                "SECTEUR": "beaute",
                "PAYS": "Benin",
                "PROJET": "concept store beaute",
                "ZONE": "Cotonou",
            },
        },
    )

    process_webhook_event(str(event.id))

    event.refresh_from_db()
    submission = IntakeSubmission.objects.get(order__systeme_order_id="order_123")
    assert event.status == WebhookStatus.PROCESSED
    assert submission.status == IntakeStatus.NORMALIZED
    assert submission.normalized_variables["SECTEUR"] == "beaute"
    assert submission.normalized_variables["ZONE"] == "Cotonou"
    assert submission.missing_fields == []


@pytest.mark.django_db
def test_process_tally_event_flags_missing_required_variables() -> None:
    offer = Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche-2",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="client2@example.com")
    Order.objects.create(systeme_order_id="order_456", customer=customer, offer=offer)
    event = WebhookEvent.objects.create(
        provider=IntegrationProvider.TALLY,
        event_id="evt_tally_incomplete",
        payload_hash="jkl",
        raw_payload={
            "order_id": "order_456",
            "data": {"fields": [{"label": "Secteur", "value": "beaute"}]},
        },
    )

    process_webhook_event(str(event.id))

    submission = IntakeSubmission.objects.get(order__systeme_order_id="order_456")
    assert submission.status == IntakeStatus.INCOMPLETE
    assert submission.normalized_variables == {"SECTEUR": "beaute", "PAYS": "France", "ZONE": "France"}
    assert set(submission.missing_fields) == {"PROJET"}


@pytest.mark.django_db
def test_processing_failure_marks_webhook_event_failed() -> None:
    event = WebhookEvent.objects.create(
        provider=IntegrationProvider.SYSTEME,
        event_id="evt_bad",
        payload_hash="ghi",
        raw_payload={"order_id": "order_123"},
    )

    with pytest.raises(ValueError):
        process_webhook_event(str(event.id))

    event.refresh_from_db()
    assert event.status == WebhookStatus.FAILED
    assert "missing required fields" in event.error_message
