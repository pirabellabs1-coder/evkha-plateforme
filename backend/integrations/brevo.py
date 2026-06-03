from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from django.conf import settings


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
    def send_delivery_email(
        self,
        *,
        recipient_email: str,
        subject: str,
        html_body: str,
        attachments: tuple[EmailAttachment, ...],
    ) -> EmailSendResult:
        msg = (
            "Envoi Brevo reel non configure : renseigner la cle API Brevo et "
            "cabler l'endpoint transactionnel."
        )
        raise NotImplementedError(msg)


def get_transactional_email_client() -> TransactionalEmailClient:
    """Stub par defaut ; client reel quand EVKHA_USE_STUB_EMAIL=false."""
    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_EMAIL", True))
    if use_stub:
        return StubBrevoClient()
    return BrevoApiClient()
