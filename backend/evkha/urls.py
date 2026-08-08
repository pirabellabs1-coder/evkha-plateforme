from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve
from paiement.vues import webhook as stripe_webhook

from integrations.views import (
    systeme_order_webhook,
    systeme_subscription_webhook,
    tally_intake_webhook,
)

from .media import servir_media


def healthz(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    path("webhooks/systeme/order/", systeme_order_webhook, name="systeme-order-webhook"),
    path(
        "webhooks/systeme/subscription/",
        systeme_subscription_webhook,
        name="systeme-subscription-webhook",
    ),
    path("webhooks/tally/intake/", tally_intake_webhook, name="tally-intake-webhook"),
    # Stripe. Volontairement a cote des autres webhooks et pas sous /api/ : ce
    # n'est pas notre interface, c'est une adresse que l'on copie dans le
    # tableau de bord Stripe et qui ne bouge plus. Elle se verifie par signature
    # et non par jeton partage — voir `paiement/vues.py`.
    path("webhooks/stripe/", stripe_webhook, name="stripe-webhook"),
    # Dashboard API — consomme par le frontend TanStack (phase 6).
    # A securiser avec Better Auth token en production.
    path("api/dashboard/", include("dashboard.urls", namespace="dashboard")),
    # Espace client (lot 4). Prefixe distinct de /api/dashboard/ : ce dernier
    # est protege par un jeton PARTAGE, qui ne distingue pas les organisations.
    path("api/espace/", include("organisations.urls", namespace="espace")),
    # Catalogue commercial, SANS authentification : la page partenaires est
    # ouverte a qui n'a pas encore de compte. Prefixe distinct de
    # `/api/espace/`, ou tout est nominatif — voir `vues_publiques`.
    path(
        "api/public/",
        include("organisations.urls_publiques", namespace="public"),
    ),
    # Sert les PDFs/HTML générés (MEDIA_ROOT) y compris en production : Brevo
    # télécharge les pièces jointes par URL publique et les clients ouvrent
    # leur lien de livraison — aucun des deux ne présente de session.
    #
    # Trois protections, et elles existent TOUTES aujourd'hui. Ce commentaire a
    # longtemps dit le contraire, bien après que le manque eut été comblé — et
    # ça n'est pas anodin : une relecture de sécurité menée le 08/08/2026 a
    # conclu, sur la foi de ces lignes, que les livrables étaient accessibles
    # sans contrôle. Elle avait lu le commentaire, pas le code. Un fichier qui
    # se contredit lui-même est pire qu'un fichier sans commentaire.
    #
    # - **Signature horodatée**, liée au chemin (`evkha/signatures.py`). Un nom
    #   deviné ne suffit plus, et un lien n'est plus éternel. `servir_media`
    #   répond 404 quand elle manque — volontairement indiscernable d'un
    #   fichier absent, pour ne pas faire de cette route un oracle.
    # - **Téléchargement forcé** : `Content-Disposition: attachment` et
    #   `X-Content-Type-Options: nosniff`, pour qu'un fichier ne soit jamais
    #   *rendu* sur l'origine qui héberge `/admin/` (voir `evkha/media.py`).
    # - **Purge à échéance** : `purge_expired_artifacts` supprime bien du
    #   disque, et pas seulement en base.
    #
    # Ce n'est pas une authentification, et c'est délibéré : ni Brevo, qui
    # récupère les pièces jointes depuis Internet, ni le client final de
    # l'abonné, qui n'a pas de compte chez nous, ne peuvent présenter de
    # session. Un lien transmis reste donc utilisable jusqu'à son expiration.
    #
    # Corollaire à ne pas perdre de vue : toute URL de média remise à un client
    # DOIT passer par `signatures.lien`. Le client PDF réel la construisait à la
    # main, et le bouton du courriel de livraison menait à un 404 que rien ne
    # signalait — voir `test_les_liens_livres_sont_servables.py`.
    re_path(
        r"^media/(?P<path>.*)$",
        servir_media,
        {"document_root": settings.MEDIA_ROOT},
        name="media",
    ),
    # Statics admin (collectstatic) — meme stratégie que /media/ : Django les
    # sert directement, suffisant pour un trafic admin interne.
    re_path(
        r"^static/(?P<path>.*)$",
        serve,
        {"document_root": settings.STATIC_ROOT},
        name="static",
    ),
]
