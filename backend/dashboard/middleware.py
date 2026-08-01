"""Garde de `/api/dashboard/`.

Deux défauts réels ont motivé cette version, tous deux constatés le 31/07/2026
sur l'instance en ligne.

**1. Le contournement de développement était actif en production.**
`EVKHA_DASHBOARD_AUTH_DISABLED=true` était posé sur le serveur public, alors
qu'un jeton valide de 64 signes y était configuré juste à côté. Le tableau de
bord — clients, incidents, coûts, dossiers — était donc consultable par
quiconque connaissait l'adresse.

Le correctif ne consiste pas à rebasculer la variable : ça, c'est corriger
l'instance. Le contournement **n'est désormais honoré que si `DEBUG` est vrai**.
Reposé par erreur en production, il n'ouvre plus rien et le dit dans les
journaux. C'est la règle 4 : viser la classe, pas l'exemple.

**2. Le jeton était accepté en paramètre d'URL** (`?token=`), « pour les
clients simples ». Une URL se retrouve dans les journaux du serveur, dans
l'historique du navigateur, dans l'en-tête `Referer` envoyé aux sites tiers et
sur toute capture d'écran. Un jeton d'administration n'a rien à y faire. Seul
l'en-tête `Authorization` est lu.
"""
from __future__ import annotations

import hmac
import logging
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

_log = logging.getLogger(__name__)

#: Prefixe des routes protegees par ce middleware.
_PROTECTED_PREFIX = "/api/dashboard/"


def contournement_actif() -> bool:
    """Le contournement de développement s'applique-t-il ?

    Il exige **deux** conditions, et la seconde n'est pas négociable :
    `EVKHA_DASHBOARD_AUTH_DISABLED` demandé, ET `DEBUG` vrai. Un serveur de
    production tourne toujours avec `DEBUG=False` ; le drapeau y est donc sans
    effet, quel que soit celui qui l'a posé et pourquoi.

    Le refus est journalisé en ERREUR : une protection qui se rétablit en
    silence laisserait croire que la configuration est correcte, et le drapeau
    resterait posé jusqu'au prochain incident (règle 1).
    """
    if not getattr(settings, "EVKHA_DASHBOARD_AUTH_DISABLED", False):
        return False
    if not getattr(settings, "DEBUG", False):
        _log.error(
            "EVKHA_DASHBOARD_AUTH_DISABLED est pose alors que DEBUG=False : "
            "IGNORE. L'administration reste protegee par jeton. Retirez cette "
            "variable de la configuration du serveur."
        )
        return False
    return True


class DashboardAuthMiddleware:
    """Protège `/api/dashboard/` par un jeton partagé.

    Comparaison en temps constant (`hmac.compare_digest`) : une comparaison
    ordinaire s'arrête au premier octet différent, ce qui laisse deviner le
    jeton signe par signe en mesurant le temps de réponse.
    """

    def __init__(self, get_response: Callable[..., Any]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith(_PROTECTED_PREFIX) and not self._autorise(request):
            return JsonResponse(
                {"error": "Authentication required.", "code": "unauthorized"},
                status=401,
            )
        return self.get_response(request)  # type: ignore[no-any-return]

    @staticmethod
    def _autorise(request: HttpRequest) -> bool:
        if contournement_actif():
            return True

        jeton = str(getattr(settings, "EVKHA_DASHBOARD_TOKEN", "") or "")
        if not jeton:
            # Aucun secret configure : on REFUSE. Ouvrir « puisqu'il n'y a rien
            # a comparer » serait exactement le defaut de la regle 1.
            return False

        presente = _jeton_presente(request)
        if not presente:
            return False

        return hmac.compare_digest(jeton.encode("utf-8"), presente.encode("utf-8"))


def _jeton_presente(request: HttpRequest) -> str:
    """Jeton lu dans l'en-tête `Authorization`, et NULLE PART ailleurs.

    Le paramètre d'URL `?token=` était accepté auparavant. Une URL est
    journalisée par le serveur, conservée dans l'historique du navigateur,
    transmise aux sites tiers via `Referer` et visible sur toute capture
    d'écran. Un jeton qui ouvre l'administration ne peut pas y transiter.
    """
    entete = request.headers.get("Authorization", "")
    if entete.lower().startswith("bearer "):
        return entete[7:].strip()
    return ""
