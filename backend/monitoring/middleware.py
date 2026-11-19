"""Chaque erreur 500 laisse un incident qui dit sa CAUSE.

Le 03 puis le 04/11/2026, la cliente a vu « Erreur 500 » trois fois — à la
commande d'une étude, puis à « Ajouter un client ». Les journaux que l'API de
Coolify rend sont ceux du serveur web : on y lisait « POST … 500 », jamais
l'exception. Il a fallu, chaque fois, deviner la cause depuis le code.

Ce middleware n'attrape rien et ne change aucune réponse : il note
l'exception, puis laisse Django répondre comme avant. Un incident par chemin
et par type d'erreur et par heure — pas un par clic.
"""
from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from datetime import timedelta

from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpRequest, HttpResponse
from django.utils import timezone

_log = logging.getLogger(__name__)


#: Les exceptions dont Django fait une réponse 404, 403 ou 400 — pas une 500.
#:
#: Mesuré en production le 19/11/2026 : 433 incidents ouverts, dont « Erreur
#: 500 : GET /static/admin/js/nav_sidebar.js.map — Http404 », de gravité haute.
#: Un fichier absent n'est pas une panne ; un navigateur qui demande une carte
#: de source en crée un par heure et par fichier. `process_exception` reçoit
#: TOUTE exception levée par une vue, y compris celles qui sont la façon
#: normale de répondre « introuvable » ou « interdit ». Les compter noyait les
#: vraies erreurs 500, celles pour lesquelles ce middleware existe.
_REPONSES_ATTENDUES: tuple[type[BaseException], ...] = (
    Http404, PermissionDenied, SuspiciousOperation,
)


class IncidentSurErreur500:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        if isinstance(exception, _REPONSES_ATTENDUES):
            return
        try:
            _noter(request, exception)
        except Exception:  # noqa: BLE001 — noter une panne ne doit pas en créer une
            _log.exception("Incident d'erreur 500 non enregistré.")


def _noter(request: HttpRequest, exception: Exception) -> None:
    from .models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    nature = type(exception).__name__
    titre = f"Erreur 500 : {request.method} {request.path} — {nature}"[:200]
    une_heure = timezone.now() - timedelta(hours=1)
    if OperationalIncident.objects.filter(title=titre, created_at__gte=une_heure).exists():
        return
    pile = traceback.format_exception(type(exception), exception, exception.__traceback__)
    OperationalIncident.objects.create(
        title=titre,
        severity=IncidentSeverity.HIGH,
        details={
            "type": "erreur_500",
            "methode": request.method,
            "chemin": request.path,
            "exception": f"{nature}: {exception}"[:1000],
            # La fin de la pile : c'est là qu'est la ligne fautive. Pas le corps
            # de la requête — il peut porter des données personnelles.
            "pile": "".join(pile[-6:])[-4000:],
        },
    )
