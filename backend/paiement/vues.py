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
import re
from collections.abc import Callable
from typing import Any, cast

import stripe
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from integrations.models import IntegrationProvider, WebhookEvent, WebhookStatus
from integrations.webhooks import record_webhook_event
from monitoring.models import IncidentSeverity, OperationalIncident

from .abonnements import EvenementInexploitable, traiter
from .achats import reference_abregee
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


#: Ce qu'on garde de l'événement lui-même.
_CLES_DE_L_EVENEMENT = ("id", "object", "type", "created", "livemode", "api_version")

#: Ce qu'on garde de l'objet qu'il porte : de quoi comprendre ce qui s'est
#: passé et retrouver le paiement chez le prestataire, et rien qui désigne ou
#: permette de joindre une personne. Une liste de ce qui est ANODIN, et non de
#: ce qui est sensible : un champ que le prestataire ajoutera demain n'est pas
#: gardé tant que personne ne l'a inscrit ici.
_CLES_DE_L_OBJET = (
    "object", "mode", "status", "payment_status", "created",
    "amount", "amount_total", "amount_subtotal", "amount_paid", "amount_due",
    "amount_refunded", "currency", "refunded", "reason", "billing_reason",
    "payment_intent", "subscription", "customer", "invoice", "charge",
    "client_reference_id", "cancel_at_period_end", "current_period_end",
)

#: Les métadonnées que NOUS posons à l'ouverture d'un paiement
#: (`stripe_api`). Liste fermée, comme le reste : une clé ajoutée un jour —
#: un nom, un téléphone — n'est pas gardée tant qu'elle n'est pas inscrite ici.
_CLES_DES_METADONNEES = (
    "achat", "offre_slug", "produit_slug", "formation_slug",
    "organisation_id", "formule_code", "quantite",
)

_SESSION_DANS_UN_TEXTE = re.compile(r"cs_(?:test|live)_[A-Za-z0-9]+")
_ADRESSE_DANS_UN_TEXTE = re.compile(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+")


def _est_simple(valeur: object) -> bool:
    return valeur is None or isinstance(valeur, (str, int, float, bool))


def charge_a_conserver(evenement: dict[str, Any]) -> dict[str, Any]:
    """Ce qu'on ÉCRIT EN BASE d'un événement de paiement — pas l'événement.

    ## Le défaut, relevé à l'audit de sécurité du 20/11/2026

    L'événement entier était enregistré (`WebhookEvent.raw_payload`), et la
    table se lit dans l'administration. Il porte l'identifiant de session
    COMPLET — qui, présenté à une page de retour, rend les liens d'une étude
    achetée ou ouvre la première session d'un compte né du paiement — ainsi
    que le nom, l'adresse de courriel et l'adresse postale de l'acheteur.
    C'est exactement ce que `achats.reference_abregee` retire des journaux et
    des incidents.

    ## La règle

    Rien ne RELIT cette charge pour traiter un paiement : en cas d'échec,
    c'est le prestataire qui renvoie l'événement. Elle ne sert qu'à
    comprendre après coup. On en garde donc le squelette (voir
    `_CLES_DE_L_OBJET`), les métadonnées — que nous posons nous-mêmes — et
    l'identifiant de l'objet, abrégé quand c'est une session.

    Le dédoublonnage n'en dépend pas : il se fait sur l'identifiant de
    l'événement.
    """
    gardee: dict[str, Any] = {
        cle: evenement[cle]
        for cle in _CLES_DE_L_EVENEMENT
        if cle in evenement and _est_simple(evenement[cle])
    }
    # La marque de ce qui est passé par ici : `dashboard/system/` compte les
    # lignes qui ne la portent pas, c'est-à-dire celles qui gardent encore un
    # événement entier.
    gardee["expurge"] = True
    objet = (evenement.get("data") or {}).get("object")
    if not isinstance(objet, dict):
        return gardee

    retenu: dict[str, Any] = {
        cle: objet[cle]
        for cle in _CLES_DE_L_OBJET
        if cle in objet and _est_simple(objet[cle])
    }
    identifiant = str(objet.get("id") or "")
    retenu["id"] = (
        reference_abregee(identifiant) if identifiant.startswith("cs_") else identifiant
    )
    metadonnees = objet.get("metadata")
    if isinstance(metadonnees, dict):
        retenu["metadata"] = {
            cle: sans_secrets(metadonnees[cle])[:200]
            for cle in _CLES_DES_METADONNEES
            if metadonnees.get(cle) is not None and _est_simple(metadonnees[cle])
        }
    gardee["data"] = {"object": retenu}
    return gardee


def sans_secrets(texte: object) -> str:
    """Un message d'erreur tel qu'on l'écrit en base ou dans un journal.

    Une erreur d'intégrité de la base cite la valeur qui a heurté la
    contrainte : une référence de session, une adresse. Les deux sont
    remplacées avant que le message ne soit enregistré.
    """
    propre = _SESSION_DANS_UN_TEXTE.sub(
        lambda trouve: reference_abregee(trouve.group(0)), str(texte)
    )
    return _ADRESSE_DANS_UN_TEXTE.sub("<adresse>", propre)


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
        payload=charge_a_conserver(dict(evenement)),
        retraiter_les_echecs=True,
    )
    if enregistre.is_duplicate and not enregistre.a_retraiter:
        if enregistre.event.status == WebhookStatus.ACCEPTED:
            # ENCORE « accepté » : un autre processus le traite — ou est mort
            # en le traitant. Répondre 200 dirait à Stripe « c'est fait » et il
            # ne le renverrait plus : si le premier traitement a été tué (un
            # déploiement, un dépassement de délai), rien ne serait jamais
            # versé (audit de sécurité du 19/11/2026). 409 : Stripe renverra,
            # et passé `DELAI_D_UN_TRAITEMENT_PERDU` le renvoi sera retraité.
            return _refus("traitement_en_cours", 409)
        return JsonResponse({"recu": True, "doublon": True}, status=200)

    try:
        verdict = traiter(evenement)
    except EvenementInexploitable as exc:
        # Authentique mais inexploitable : retenter n'y changera rien. On
        # repond 200 pour que Stripe cesse, et on ouvre un incident pour que
        # quelqu'un le voie — se taire ici, c'est perdre un paiement en silence.
        WebhookEvent.objects.filter(pk=enregistre.event.pk).update(
            status=WebhookStatus.REJECTED, error_message=sans_secrets(exc)[:500]
        )
        OperationalIncident.objects.create(
            title="Evenement Stripe inexploitable",
            severity=IncidentSeverity.HIGH,
            details={
                "evenement": identifiant,
                "type": str(evenement.get("type") or ""),
                "motif": sans_secrets(exc),
            },
        )
        _log.error(
            "Evenement Stripe %s inexploitable : %s", identifiant, sans_secrets(exc)
        )
        return JsonResponse({"recu": True, "traite": False}, status=200)
    except Exception as exc:  # noqa: BLE001 - on veut que Stripe retente
        WebhookEvent.objects.filter(pk=enregistre.event.pk).update(
            status=WebhookStatus.FAILED, error_message=sans_secrets(exc)[:500]
        )
        # Sans la trace brute : une erreur d'integrite cite la valeur qui a
        # heurte la contrainte — une reference de session, une adresse. Le
        # type et le message expurge suffisent a retrouver la cause.
        _log.error(
            "Echec de traitement de l'evenement Stripe %s : %s (%s)",
            identifiant, type(exc).__name__, sans_secrets(exc),
        )
        return _refus("traitement_en_echec", 500)

    WebhookEvent.objects.filter(pk=enregistre.event.pk).update(
        status=WebhookStatus.PROCESSED, error_message=verdict[:500]
    )
    _log.info(
        "Evenement Stripe %s (%s) : %s", identifiant, evenement.get("type"), verdict
    )
    return JsonResponse({"recu": True, "traite": True, "verdict": verdict}, status=200)
