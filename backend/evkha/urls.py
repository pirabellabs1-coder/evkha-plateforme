from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import path
from integrations.views import systeme_order_webhook, tally_intake_webhook


def healthz(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    path("webhooks/systeme/order/", systeme_order_webhook, name="systeme-order-webhook"),
    path("webhooks/tally/intake/", tally_intake_webhook, name="tally-intake-webhook"),
]
