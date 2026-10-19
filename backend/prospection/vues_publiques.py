"""Les deux points d'entrée PUBLICS de la prospection.

Ni l'un ni l'autre ne passe par le jeton admin : Brevo et les destinataires ne
l'ont pas. Le webhook est authentifié par un secret partagé (comme les autres
webhooks du projet) ; la désinscription par un jeton opaque propre au prospect.

Montés sous `/webhooks/brevo/` et `/p/desinscription/<jeton>/` (hors `/api/`),
à côté des webhooks Systeme/Tally/Stripe.
"""
from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from integrations.models import IntegrationProvider
from integrations.views import _extract_token
from integrations.webhooks import is_webhook_authorized, record_webhook_event, stable_payload_hash

from . import services
from .models import Prospect
from .webhooks import enregistrer_evenement_brevo


def _evenements_du_corps(parse: Any) -> list[dict[str, Any]]:
    """Brevo poste soit un événement, soit un lot : on rend toujours une liste."""
    if isinstance(parse, list):
        return [e for e in parse if isinstance(e, dict)]
    if isinstance(parse, dict):
        lot = parse.get("events")
        if isinstance(lot, list):
            return [e for e in lot if isinstance(e, dict)]
        return [parse]
    return []


@csrf_exempt
@require_http_methods(["POST"])
def webhook_brevo(request: HttpRequest) -> JsonResponse:
    """Reçoit les événements d'e-mail Brevo et les trace en `Evenement`."""
    if not is_webhook_authorized(IntegrationProvider.BREVO, _extract_token(request)):
        return JsonResponse({"accepted": False, "error": "unauthorized"}, status=401)
    try:
        parse = json.loads(request.body.decode("utf-8") or "null")
    except (json.JSONDecodeError, ValueError) as exc:
        return JsonResponse({"accepted": False, "error": str(exc)}, status=400)

    evenements = _evenements_du_corps(parse)
    # Trace d'audit du POST entier (dédoublonné), comme les autres webhooks.
    charge_audit = parse if isinstance(parse, dict) else {"events": evenements}
    record_webhook_event(
        provider=IntegrationProvider.BREVO,
        event_id=f"brevo:{stable_payload_hash(charge_audit)}",
        payload=charge_audit,
    )
    traces = sum(1 for e in evenements if enregistrer_evenement_brevo(e) is not None)
    return JsonResponse({"accepted": True, "traces": traces, "recus": len(evenements)}, status=202)


_PAGE = (
    "<!doctype html><html lang=fr><head><meta charset=utf-8>"
    "<meta name=viewport content='width=device-width, initial-scale=1'>"
    "<title>Désinscription</title></head>"
    "<body style='font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;"
    "padding:0 1rem;line-height:1.6'>{corps}</body></html>"
)


def _page(corps_html: str, status: int = 200) -> HttpResponse:
    return HttpResponse(_PAGE.format(corps=corps_html), status=status, content_type="text/html")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def desinscription(request: HttpRequest, jeton: str) -> HttpResponse:
    """Lien public de désinscription : un clic suffit, et ne bloque jamais.

    Le routeur contraint `jeton` à un UUID (`<uuid:…>`), donc un lien mal formé
    rend un 404 propre avant d'entrer ici. Jeton inconnu : page polie. Déjà
    désinscrit : on reconfirme sans se plaindre (idempotent). La confidentialité
    tient : le jeton ne porte aucune donnée personnelle, et la page n'en montre
    aucune au-delà de la raison sociale du destinataire lui-même.
    """
    prospect = Prospect.objects.filter(jeton_desinscription=jeton).first()
    if prospect is None:
        return _page(
            "<h1>Lien introuvable</h1><p>Ce lien de désinscription n'est plus valide. "
            "Si vous recevez encore nos messages, répondez simplement « STOP ».</p>",
            status=404,
        )
    services.desinscrire(prospect)
    nom = escape(prospect.raison_sociale)
    return _page(
        f"<h1>Vous êtes désinscrit·e</h1><p>{nom} ne recevra plus de message de notre "
        "part. Aucune autre démarche n'est nécessaire. Merci.</p>"
    )
