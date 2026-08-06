"""Le point de terminaison qui recoit les evenements de paiement Stripe.

## Pourquoi il ne reutilise pas `integrations.views._handle_webhook`

Le socle webhook du depot est bon — enregistrement idempotent, mise en file,
incidents — et ce module lui reprend `record_webhook_event`. Mais son
authentification ne convient pas ici, pour deux raisons distinctes :

1. **Elle est fail-open.** `is_webhook_authorized` rend `True` quand aucun
   secret n'est configure (`integrations/webhooks.py:42`). Sur cette route, cela
   voudrait dire : « personne n'a encore branche Stripe, donc j'accepte que
   n'importe qui declare un paiement ». C'est la regle 1 exactement a l'envers,
   et le prix se compte en etudes livrees gratuitement.

2. **Stripe ne signe pas avec un secret partage.** Il envoie un en-tete
   `Stripe-Signature` contenant un horodatage et un HMAC du CORPS BRUT. Comparer
   un jeton ne verifierait donc rien, et surtout ne protegerait pas du rejeu
   d'un evenement authentique capture ailleurs — ce que la tolerance horaire de
   `construct_event` refuse.

## Pourquoi le traitement est synchrone

Les autres webhooks passent par Celery. Celui-ci travaille dans la requete, et
c'est delibere : si le traitement echoue, on repond 500 et **Stripe retente
pendant trois jours** avec un recul croissant. Cette garantie de reprise est
meilleure que la notre, et gratuite. Passer par Celery l'aurait remplacee par
la notre : un `delay()` reussi renvoie 200 a Stripe, qui considere l'affaire
close — et si le worker meurt ensuite, le client a paye sans jamais recevoir
ses credits, sans que Stripe ne retente jamais.

Le travail est court (quelques ecritures) : rien ne justifie de differer.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast

import stripe
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from integrations.models import IntegrationProvider, WebhookEvent, WebhookStatus
from integrations.webhooks import record_webhook_event
from monitoring.models import IncidentSeverity, OperationalIncident

from .abonnements import EvenementInexploitable, traiter
from .stripe_api import PaiementIndisponible, secret_de_signature

_log = logging.getLogger(__name__)

#: `stripe.Webhook.construct_event` n'est pas annotee dans la bibliotheque, et
#: mypy refuse de l'appeler depuis du code type. On declare donc sa signature
#: une fois, ici, plutot que de museler l'erreur au point d'appel : le `cast`
#: dit ce que la fonction fait, un `type: ignore` aurait seulement dit qu'on
#: renonce a le savoir.
#:
#: Signature reelle, verifiee sur stripe 13.2.0 :
#:     construct_event(payload, sig_header, secret, tolerance=300, api_key=None)
_verifier_signature = cast(
    Callable[[bytes, str, str], dict[str, Any]], stripe.Webhook.construct_event
)


def _refus(motif: str, statut: int) -> JsonResponse:
    """Refus laconique. Stripe ne lit pas nos phrases, un attaquant si.

    Le detail part dans le journal, jamais dans la reponse : dire « signature
    invalide » plutot que « secret absent » apprend a qui frappe ou en est la
    configuration.
    """
    return JsonResponse({"recu": False, "erreur": motif}, status=statut)


@csrf_exempt
def webhook(request: HttpRequest) -> JsonResponse:
    """Recoit, verifie, traite. Refuse tout ce qui n'est pas prouve."""
    if request.method != "POST":
        return _refus("methode_non_autorisee", 405)

    try:
        secret = secret_de_signature()
    except PaiementIndisponible:
        # Fail-closed. Un evenement non verifiable n'est pas un evenement.
        _log.error(
            "Evenement Stripe recu alors que STRIPE_WEBHOOK_SECRET est absent : "
            "refuse. Aucun paiement ne sera pris en compte tant qu'il manque."
        )
        return _refus("verification_indisponible", 503)

    signature = request.headers.get("Stripe-Signature", "")
    if not signature:
        return _refus("signature_absente", 400)

    try:
        evenement: dict[str, Any] = _verifier_signature(
            request.body, signature, secret
        )
    except stripe.SignatureVerificationError:
        _log.warning("Signature Stripe invalide sur %s octets.", len(request.body))
        return _refus("signature_invalide", 400)
    except ValueError:
        return _refus("charge_illisible", 400)

    identifiant = str(evenement.get("id") or "")
    if not identifiant:
        return _refus("evenement_sans_identifiant", 400)

    # A partir d'ici l'evenement est PROUVE. Le rejeu du meme identifiant ne
    # doit rien refaire : c'est la deuxieme barriere, apres `assurer_abonnement`
    # qui protege du cas ou deux evenements DIFFERENTS disent la meme chose.
    enregistre = record_webhook_event(
        provider=IntegrationProvider.STRIPE,
        event_id=identifiant,
        payload=dict(evenement),
    )
    if enregistre.is_duplicate:
        return JsonResponse({"recu": True, "doublon": True}, status=200)

    try:
        verdict = traiter(evenement)
    except EvenementInexploitable as exc:
        # Authentique mais inexploitable : retenter n'y changera rien. On
        # repond 200 pour que Stripe cesse, et on ouvre un incident pour que
        # quelqu'un le voie — se taire ici, c'est perdre un paiement en silence.
        WebhookEvent.objects.filter(pk=enregistre.event.pk).update(
            status=WebhookStatus.REJECTED, error_message=str(exc)[:500]
        )
        OperationalIncident.objects.create(
            title="Evenement Stripe inexploitable",
            severity=IncidentSeverity.HIGH,
            details={
                "evenement": identifiant,
                "type": str(evenement.get("type") or ""),
                "motif": str(exc),
            },
        )
        _log.error("Evenement Stripe %s inexploitable : %s", identifiant, exc)
        return JsonResponse({"recu": True, "traite": False}, status=200)
    except Exception as exc:  # noqa: BLE001 - on veut que Stripe retente
        WebhookEvent.objects.filter(pk=enregistre.event.pk).update(
            status=WebhookStatus.FAILED, error_message=str(exc)[:500]
        )
        _log.exception("Echec de traitement de l'evenement Stripe %s.", identifiant)
        return _refus("traitement_en_echec", 500)

    WebhookEvent.objects.filter(pk=enregistre.event.pk).update(
        status=WebhookStatus.PROCESSED, error_message=verdict[:500]
    )
    _log.info(
        "Evenement Stripe %s (%s) : %s", identifiant, evenement.get("type"), verdict
    )
    return JsonResponse({"recu": True, "traite": True, "verdict": verdict}, status=200)
