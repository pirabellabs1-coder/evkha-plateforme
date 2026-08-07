"""Tests BrevoApiClient — client transactionnel reel (urlopen mocke, aucun reseau).

Couvre :
- payload conforme a l'API Brevo v3 (sender, to, subject, htmlContent, attachment)
- attachments omis du payload quand il n'y en a pas
- BREVO_API_KEY manquante → RuntimeError
- messageId Brevo propage dans EmailSendResult
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from integrations.brevo import BrevoApiClient, EmailAttachment


def _fake_urlopen_response(body: dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(body).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


@override_settings(
    BREVO_API_KEY="test-key",
    EVKHA_SENDER_EMAIL="contact@evkha.fr",
    EVKHA_SENDER_NAME="Evkha",
)
def test_brevo_client_builds_conformant_payload() -> None:
    client = BrevoApiClient()
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int = 0) -> MagicMock:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["api_key"] = request.headers.get("Api-key")
        return _fake_urlopen_response({"messageId": "<msg-123@brevo>"})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = client.send_delivery_email(
            recipient_email="client@example.com",
            subject="Livrables EVKHA - order_1",
            html_body="<p>Vos livrables</p>",
            attachments=(
                EmailAttachment(filename="etude.pdf", url="https://evkha.fr/media/etude.pdf"),
            ),
        )

    assert result.provider_message_id == "<msg-123@brevo>"
    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    assert captured["api_key"] == "test-key"
    payload = captured["payload"]
    assert payload["sender"] == {"name": "Evkha", "email": "contact@evkha.fr"}
    assert payload["to"] == [{"email": "client@example.com"}]
    assert payload["subject"] == "Livrables EVKHA - order_1"
    assert payload["htmlContent"] == "<p>Vos livrables</p>"
    assert payload["attachment"] == [
        {"url": "https://evkha.fr/media/etude.pdf", "name": "etude.pdf"}
    ]


@override_settings(
    BREVO_API_KEY="test-key",
    EVKHA_SENDER_EMAIL="contact@evkha.fr",
    EVKHA_SENDER_NAME="Evkha",
)
def test_brevo_client_omits_attachment_field_when_empty() -> None:
    client = BrevoApiClient()
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int = 0) -> MagicMock:
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _fake_urlopen_response({"messageId": "<msg-456@brevo>"})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        client.send_delivery_email(
            recipient_email="client@example.com",
            subject="Sujet",
            html_body="<p>Corps</p>",
            attachments=(),
        )

    assert "attachment" not in captured["payload"]


@override_settings(BREVO_API_KEY="")
def test_brevo_client_missing_api_key_raises() -> None:
    client = BrevoApiClient()
    with pytest.raises(RuntimeError, match="BREVO_API_KEY"):
        client.send_delivery_email(
            recipient_email="client@example.com",
            subject="Sujet",
            html_body="<p>Corps</p>",
            attachments=(),
        )
