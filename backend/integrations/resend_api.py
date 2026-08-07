"""Client Resend — l'autre implémentation du port `TransactionalEmailClient`.

Le protocole, la doublure et la fabrique vivent dans `integrations.brevo` : ce
module n'ajoute qu'un adaptateur. Il n'y a donc toujours qu'UN chemin d'envoi
dans le produit, et basculer de fournisseur ne change rien à l'appelant
(règle 5).

Le nom du module est `resend_api` et non `resend` : le paquet officiel du même
nom existe sur PyPI, et un module local qui le masque produit une erreur
d'import incompréhensible le jour où quelqu'un l'installe.

**Aucune dépendance ajoutée.** L'API de Resend est un simple POST JSON ;
`urllib` suffit, comme pour Brevo. Ajouter un SDK pour trois champs, c'est une
dépendance de plus à suivre, à mettre à jour et à auditer.
"""
from __future__ import annotations

import json
from typing import Any

from django.conf import settings

from .brevo import EmailAttachment, EmailSendResult

_RESEND_ENDPOINT = "https://api.resend.com/emails"
_RESEND_TIMEOUT_SECONDS = 30


class ResendApiClient:
    """Envoi transactionnel via `POST https://api.resend.com/emails`.

    Les pièces jointes sont passées par URL (`path`), comme chez Brevo :
    Resend les télécharge lui-même. `EVKHA_BASE_URL` doit donc rester
    joignable depuis Internet — c'est la même contrainte qu'avant, et elle est
    déjà tenue par la livraison des documents.

    Sur erreur HTTP, l'exception remonte : `deliver_job` la rattrape déjà et
    enregistre un lot FAILED avec son incident. Se taire ici ferait passer un
    document jamais reçu pour un document livré (règle 1).
    """

    def send_delivery_email(
        self,
        *,
        recipient_email: str,
        subject: str,
        html_body: str,
        attachments: tuple[EmailAttachment, ...],
    ) -> EmailSendResult:
        import urllib.request  # import paresseux : jamais utilisé en dev/CI (doublure)

        cle = str(getattr(settings, "RESEND_API_KEY", "") or "")
        if not cle:
            msg = (
                "RESEND_API_KEY manquante alors que EVKHA_EMAIL_PROVIDER vaut "
                "« resend » et que la doublure est désactivée."
            )
            raise RuntimeError(msg)

        expediteur = str(getattr(settings, "EVKHA_SENDER_EMAIL", "") or "")
        nom = str(getattr(settings, "EVKHA_SENDER_NAME", "") or "")
        payload: dict[str, Any] = {
            # Resend attend « Nom <adresse> » sur un seul champ, là où Brevo
            # sépare les deux. La différence s'arrête ici : les réglages, eux,
            # restent communs aux deux fournisseurs.
            "from": f"{nom} <{expediteur}>" if nom else expediteur,
            "to": [recipient_email],
            "subject": subject,
            "html": html_body,
        }
        if attachments:
            payload["attachments"] = [
                {"path": piece.url, "filename": piece.filename}
                for piece in attachments
            ]

        requete = urllib.request.Request(
            _RESEND_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "authorization": f"Bearer {cle}",
                "content-type": "application/json",
                "accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(requete, timeout=_RESEND_TIMEOUT_SECONDS) as reponse:
            corps: dict[str, Any] = json.loads(reponse.read().decode("utf-8"))
        return EmailSendResult(provider_message_id=str(corps.get("id", "")))
