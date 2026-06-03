from __future__ import annotations

from unittest.mock import Mock

import pytest
from django.test import Client, override_settings
from integrations.models import IntegrationProvider, WebhookEvent, WebhookStatus
from monitoring.models import OperationalIncident


def test_healthz_returns_ok(client: Client) -> None:
    response = client.get("/healthz/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_systeme_webhook_records_event_and_returns_202(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delay = Mock()
    monkeypatch.setattr("integrations.views.process_webhook_event.delay", delay)

    response = client.post(
        "/webhooks/systeme/order/",
        data={"event_id": "evt_123", "order_id": "order_123"},
        content_type="application/json",
    )

    assert response.status_code == 202
    assert response.json()["accepted"] is True
    assert response.json()["duplicate"] is False
    assert WebhookEvent.objects.filter(
        provider=IntegrationProvider.SYSTEME,
        event_id="evt_123",
        status=WebhookStatus.ACCEPTED,
    ).exists()
    delay.assert_called_once()


@pytest.mark.django_db
def test_systeme_webhook_is_idempotent(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    delay = Mock()
    monkeypatch.setattr("integrations.views.process_webhook_event.delay", delay)
    payload = {"event_id": "evt_duplicate", "order_id": "order_456"}

    first_response = client.post(
        "/webhooks/systeme/order/",
        data=payload,
        content_type="application/json",
    )
    second_response = client.post(
        "/webhooks/systeme/order/",
        data=payload,
        content_type="application/json",
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json()["duplicate"] is True
    assert WebhookEvent.objects.filter(
        provider=IntegrationProvider.SYSTEME,
        event_id="evt_duplicate",
    ).count() == 1
    delay.assert_called_once()


@pytest.mark.django_db
def test_tally_webhook_records_submission_event(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delay = Mock()
    monkeypatch.setattr("integrations.views.process_webhook_event.delay", delay)

    response = client.post(
        "/webhooks/tally/intake/",
        data={"submission_id": "sub_123", "answers": {"secteur": "beaute"}},
        content_type="application/json",
    )

    assert response.status_code == 202
    assert WebhookEvent.objects.filter(
        provider=IntegrationProvider.TALLY,
        event_id="sub_123",
    ).exists()
    delay.assert_called_once()


def test_webhook_rejects_invalid_json(client: Client) -> None:
    response = client.post(
        "/webhooks/tally/intake/",
        data="[1, 2, 3]",
        content_type="application/json",
    )

    assert response.status_code == 400


@override_settings(SYSTEME_WEBHOOK_SECRET="topsecret")
@pytest.mark.django_db
def test_webhook_rejects_wrong_secret_when_configured(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("integrations.views.process_webhook_event.delay", Mock())

    rejected = client.post(
        "/webhooks/systeme/order/",
        data={"event_id": "evt_secret", "order_id": "order_secret"},
        content_type="application/json",
        HTTP_X_WEBHOOK_TOKEN="wrong",
    )
    assert rejected.status_code == 401
    assert not WebhookEvent.objects.filter(event_id="evt_secret").exists()

    accepted = client.post(
        "/webhooks/systeme/order/",
        data={"event_id": "evt_secret", "order_id": "order_secret"},
        content_type="application/json",
        HTTP_X_WEBHOOK_TOKEN="topsecret",
    )
    assert accepted.status_code == 202


@pytest.mark.django_db
def test_enqueue_failure_creates_incident_and_marks_event_failed(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_event_id: str) -> None:
        raise RuntimeError("broker down")

    monkeypatch.setattr("integrations.views.process_webhook_event.delay", boom)

    response = client.post(
        "/webhooks/tally/intake/",
        data={"submission_id": "sub_fail"},
        content_type="application/json",
    )

    assert response.status_code == 202
    event = WebhookEvent.objects.get(event_id="sub_fail")
    assert event.status == WebhookStatus.FAILED
    assert OperationalIncident.objects.filter(severity="high").exists()
