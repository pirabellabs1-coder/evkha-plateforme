from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import IntegrationProvider, WebhookEvent, WebhookStatus

# Maps each inbound provider to the setting holding its shared secret (M1).
_SECRET_SETTING: dict[str, str] = {
    IntegrationProvider.SYSTEME.value: "SYSTEME_WEBHOOK_SECRET",
    IntegrationProvider.SYSTEME_SUB.value: "SYSTEME_WEBHOOK_SECRET",
    IntegrationProvider.TALLY.value: "TALLY_WEBHOOK_SECRET",
    IntegrationProvider.BREVO.value: "BREVO_WEBHOOK_SECRET",
}


#: Au-delà, un événement resté « accepté » n'est plus en cours de traitement :
#: le processus qui le traitait est mort. Un traitement Stripe dure moins
#: d'une seconde.
DELAI_D_UN_TRAITEMENT_PERDU = timedelta(minutes=5)


@dataclass(frozen=True)
class RecordedWebhook:
    event: WebhookEvent
    is_duplicate: bool
    #: Déjà reçu, mais jamais mené au bout : l'appelant doit le traiter.
    a_retraiter: bool = False


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
    retraiter_les_echecs: bool = False,
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
        # UN ÉVÉNEMENT QUI A ÉCHOUÉ N'EST PAS UN DOUBLON : c'est un rejeu attendu.
        #
        # Audit du 19/11/2026. Quand le traitement d'un événement Stripe échoue,
        # la vue répond 500 pour que Stripe le renvoie — il retente trois jours.
        # Mais au renvoi, le même identifiant retombait ici, était requalifié
        # « doublon » (le statut FAILED était écrasé) et la vue répondait 200 :
        # Stripe s'arrêtait, et un prélèvement encaissé n'était jamais doté. La
        # garantie « il sera retenté » était annulée par la garde censée
        # protéger du rejeu d'un événement RÉUSSI.
        #
        # Est à retraiter, pour l'appelant qui le demande : un événement en
        # échec, ou resté « accepté » plus de quelques minutes (le processus
        # est mort en le traitant, par exemple pendant un déploiement). Ses
        # traitements doivent être idempotents — c'est ce qui rend le rejeu sûr.
        if retraiter_les_echecs and (
            event.status == WebhookStatus.FAILED
            or (
                event.status == WebhookStatus.ACCEPTED
                and timezone.now() - event.updated_at > DELAI_D_UN_TRAITEMENT_PERDU
            )
        ):
            # La reprise est une PRISE : mise à jour conditionnelle sur l'état
            # lu. Deux renvois arrivés ensemble liraient tous deux « en échec »
            # et le traiteraient tous deux ; un seul change la ligne.
            pris = WebhookEvent.objects.filter(
                pk=event.pk, status=event.status, updated_at=event.updated_at
            ).update(status=WebhookStatus.ACCEPTED, updated_at=timezone.now())
            event.status = WebhookStatus.ACCEPTED
            return RecordedWebhook(event=event, is_duplicate=True, a_retraiter=bool(pris))
        if event.status != WebhookStatus.DUPLICATE and not (
            retraiter_les_echecs and event.status == WebhookStatus.ACCEPTED
        ):
            # Un événement encore « accepté » est EN COURS de traitement par un
            # autre processus : le requalifier effacerait son statut final.
            WebhookEvent.objects.filter(pk=event.pk).update(status=WebhookStatus.DUPLICATE)
            event.status = WebhookStatus.DUPLICATE
        return RecordedWebhook(event=event, is_duplicate=True)
