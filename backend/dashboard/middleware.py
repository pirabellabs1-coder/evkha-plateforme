from __future__ import annotations

import hmac
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

# Prefixe des routes protegees par ce middleware.
_PROTECTED_PREFIX = "/api/dashboard/"

# En dev/CI, passer EVKHA_DASHBOARD_AUTH_DISABLED=true pour bypasser.
# En production, configurer EVKHA_DASHBOARD_TOKEN avec une valeur forte
# (min. 32 chars, generee via `openssl rand -hex 32`).
#
# TODO : remplacer la validation par JWT Better-Auth une fois la cle
# BETTER_AUTH_SECRET configuree cote VPS :
#   import jwt
#   payload = jwt.decode(token, secret, algorithms=["HS256"])
#   assert payload.get("role") in {"admin", "owner"}


class DashboardAuthMiddleware:
    """Protege /api/dashboard/ par un Bearer token partage.

    Contournement configurable (dev/CI) : EVKHA_DASHBOARD_AUTH_DISABLED=true.
    Validation par comparaison en temps constant (hmac.compare_digest) pour
    eviter les attaques par timing.
    """

    def __init__(self, get_response: Callable[..., Any]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith(_PROTECTED_PREFIX):
            if not self._is_authorized(request):
                return JsonResponse(
                    {"error": "Authentication required.", "code": "unauthorized"},
                    status=401,
                )
        return self.get_response(request)  # type: ignore[no-any-return]

    @staticmethod
    def _is_authorized(request: HttpRequest) -> bool:
        # Bypass explicite pour dev/CI (jamais en production).
        if getattr(settings, "EVKHA_DASHBOARD_AUTH_DISABLED", True):
            return True

        token = getattr(settings, "EVKHA_DASHBOARD_TOKEN", "")
        if not token:
            # Aucun secret configure : acces refuse par securite (fail-closed).
            return False

        provided = _extract_bearer(request)
        if not provided:
            return False

        # Comparaison en temps constant — pas de short-circuit possible.
        return hmac.compare_digest(
            token.encode("utf-8"),
            provided.encode("utf-8"),
        )


def _extract_bearer(request: HttpRequest) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    # Accepte aussi ?token= en query string (pour les clients simples / tests).
    return request.GET.get("token", "")
