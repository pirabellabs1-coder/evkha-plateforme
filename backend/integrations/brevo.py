from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from django.conf import settings

_BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
_BREVO_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    url: str


@dataclass(frozen=True)
class EmailSendResult:
    provider_message_id: str


@runtime_checkable
class TransactionalEmailClient(Protocol):
    def send_delivery_email(
        self,
        *,
        recipient_email: str,
        subject: str,
        html_body: str,
        attachments: tuple[EmailAttachment, ...],
    ) -> EmailSendResult: ...


class StubBrevoClient:
    """Client Brevo deterministe pour dev/CI : aucun envoi reel.

    Renvoie un message_id stable base sur le contenu du message (hash)
    pour permettre la verification deterministe en test.
    """

    def send_delivery_email(
        self,
        *,
        recipient_email: str,
        subject: str,
        html_body: str,
        attachments: tuple[EmailAttachment, ...],
    ) -> EmailSendResult:
        digest = hashlib.sha256(
            f"{recipient_email}:{subject}:{html_body}:{len(attachments)}".encode()
        ).hexdigest()[:16]
        return EmailSendResult(provider_message_id=f"brevo-stub-{digest}")


class BrevoApiClient:
    """Client Brevo reel — API transactionnelle v3 (POST /smtp/email).

    Lit BREVO_API_KEY / BREVO_SENDER_EMAIL / BREVO_SENDER_NAME dans les settings.
    Les pieces jointes sont transmises par URL publique (champ `attachment[].url`),
    Brevo les telecharge lui-meme : EVKHA_BASE_URL doit donc etre accessible
    depuis Internet.
    Sur erreur HTTP, l'exception remonte a deliver_job qui persiste le batch
    FAILED + incident (chemin d'echec deja teste).
    """

    def send_delivery_email(
        self,
        *,
        recipient_email: str,
        subject: str,
        html_body: str,
        attachments: tuple[EmailAttachment, ...],
    ) -> EmailSendResult:
        import urllib.request  # import paresseux : jamais utilise en dev/CI (stub)

        api_key = str(getattr(settings, "BREVO_API_KEY", "") or "")
        if not api_key:
            msg = "BREVO_API_KEY manquante pour BrevoApiClient."
            raise RuntimeError(msg)

        payload: dict[str, Any] = {
            "sender": {
                "name": str(getattr(settings, "BREVO_SENDER_NAME", "Evkha")),
                "email": str(getattr(settings, "BREVO_SENDER_EMAIL", "")),
            },
            "to": [{"email": recipient_email}],
            "subject": subject,
            "htmlContent": html_body,
        }
        if attachments:
            payload["attachment"] = [
                {"url": attachment.url, "name": attachment.filename}
                for attachment in attachments
            ]

        request = urllib.request.Request(
            _BREVO_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": api_key,
                "content-type": "application/json",
                "accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=_BREVO_TIMEOUT_SECONDS) as response:
            body: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        return EmailSendResult(provider_message_id=str(body.get("messageId", "")))


def get_transactional_email_client() -> TransactionalEmailClient:
    """Stub par defaut ; client reel quand EVKHA_USE_STUB_EMAIL=false."""
    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_EMAIL", True))
    if use_stub:
        return StubBrevoClient()
    return BrevoApiClient()
