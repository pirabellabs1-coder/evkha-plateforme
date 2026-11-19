"""Une requête trop lourde est refusée AVANT d'être lue.

Audit du 19/11/2026. Le nginx du front coupe à 12 Mo — mais il ne garde que
`app2.evkha.fr`. L'API est aussi jointe directement, par `api2.evkha.fr`, et là
rien ne bornait un envoi : Django ne plafonne que le corps « hors fichiers »
(`DATA_UPLOAD_MAX_MEMORY_SIZE`), un fichier de n'importe quelle taille est
écrit en entier sur le disque du conteneur, puis les vues de dépôt le lisent en
entier en mémoire (`envoye.read()`) avant de constater qu'il dépasse 10 Mo.
Deux processus servent l'API : deux envois suffisaient à l'arrêter.

La borne est posée ici plutôt que dans chaque vue : une vue de dépôt ajoutée
demain en hérite sans y penser (règle 4).

Seul `Content-Length` est regardé, et c'est suffisant sous WSGI : un envoi
« par morceaux » qui ne l'annonce pas est lu par Django comme un corps de
zéro octet.
"""
from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse


class CorpsBorne:
    """Répond 413 à toute requête qui annonce plus que `EVKHA_TAILLE_MAX_REQUETE`."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            annonce = int(request.META.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            annonce = 0
        plafond = int(settings.EVKHA_TAILLE_MAX_REQUETE)
        if annonce > plafond:
            return JsonResponse(
                {
                    "error": (
                        f"Cet envoi dépasse {plafond // (1024 * 1024)} Mo. "
                        "Réduisez le fichier, puis réessayez."
                    ),
                    "code": "requete_trop_lourde",
                },
                status=413,
            )
        return self.get_response(request)
