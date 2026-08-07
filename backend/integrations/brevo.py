"""Port du courriel transactionnel : protocole, doublure, fabrique.

Le module porte le nom de l'un des fournisseurs pour une raison d'histoire
— Brevo etait le seul — et tout le produit importe
`get_transactional_email_client` d'ici. Le renommer imposerait de toucher
chaque appelant pour un gain nul ; ce qui compte est qu'il n'existe QU'UN
port, et que les adaptateurs se rangent derriere lui. Resend vit dans
`resend_api.py`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from django.conf import settings

_BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
_BREVO_TIMEOUT_SECONDS = 30

#: Agent utilisateur annonce au prestataire. Brevo l'accepte sans, mais
#: Resend non : son API est derriere Cloudflare, qui bannit l'agent par
#: defaut d'urllib (403 Error 1010). Le meme oubli dort donc ici — et Brevo
#: est justement le repli vers lequel on basculerait un jour de panne
#: Resend. Un repli qui echoue silencieusement le jour ou l'on en a besoin
#: ne vaut pas mieux que pas de repli (regle 4 : viser la CLASSE du defaut).
_AGENT = "EVKHA/1.0 (+https://evkha.fr)"


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

    Lit BREVO_API_KEY, et l'expediteur COMMUN aux deux fournisseurs
    (EVKHA_SENDER_EMAIL / EVKHA_SENDER_NAME) : basculer de prestataire ne
    doit pas changer l'adresse d'ou EVKHA ecrit a ses partenaires.
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
                "name": str(getattr(settings, "EVKHA_SENDER_NAME", "Evkha")),
                "email": str(getattr(settings, "EVKHA_SENDER_EMAIL", "")),
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
                "user-agent": _AGENT,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=_BREVO_TIMEOUT_SECONDS) as response:
            body: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        return EmailSendResult(provider_message_id=str(body.get("messageId", "")))


def _fournisseurs() -> dict[str, type]:
    """Table FERMEE des fournisseurs branchables.

    Construite a l'appel et non au chargement : `resend_api` importe les
    dataclasses de ce module, et un import en tete produirait un cycle.

    Fermee, parce qu'un nom inconnu doit echouer bruyamment plutot que de
    retomber en silence sur un fournisseur que personne n'a choisi : une
    faute de frappe enverrait tout le courrier chez l'ancien prestataire
    sans que rien ne le dise (regle 1).
    """
    from .resend_api import ResendApiClient  # noqa: PLC0415 — evite un cycle

    return {"brevo": BrevoApiClient, "resend": ResendApiClient}


def get_transactional_email_client() -> TransactionalEmailClient:
    """Doublure par defaut ; fournisseur reel quand EVKHA_USE_STUB_EMAIL=false.

    Le choix du fournisseur se fait par `EVKHA_EMAIL_PROVIDER`, donc sans
    redeploiement : le jour ou Resend tombe, on repasse a Brevo depuis Coolify.
    """
    if bool(getattr(settings, "EVKHA_USE_STUB_EMAIL", True)):
        return StubBrevoClient()

    nom = str(getattr(settings, "EVKHA_EMAIL_PROVIDER", "resend") or "").lower().strip()
    table = _fournisseurs()
    fournisseur = table.get(nom)
    if fournisseur is None:
        connus = ", ".join(sorted(table))
        msg = (
            f"EVKHA_EMAIL_PROVIDER inconnu : {nom!r}. Valeurs acceptees : {connus}."
        )
        raise RuntimeError(msg)
    client: TransactionalEmailClient = fournisseur()
    return client
