from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

from integrations.views import (
    systeme_order_webhook,
    systeme_subscription_webhook,
    tally_intake_webhook,
)


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
    # Sert les PDFs/HTML générés (MEDIA_ROOT) y compris en production :
    # Brevo télécharge les pièces jointes par URL publique et les clients
    # ouvrent leur lien de livraison. Noms de fichiers non devinables (hash),
    # rétention 7 jours (purge_expired_artifacts). À remplacer par nginx/S3
    # si le volume devient significatif.
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
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
