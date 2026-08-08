"""Service des fichiers de `MEDIA_ROOT`, en refusant qu'ils soient *rendus*.

`/media/` était branché sur `django.views.static.serve` sans rien autour.
Django choisit alors le `Content-Type` d'après **l'extension**, et le navigateur
rend le fichier. Un document déposé sous un nom en `.html` s'exécutait donc sur
l'origine qui héberge `/admin/` et `/api/dashboard/` — c'est-à-dire avec accès
aux cookies de session de cette origine.

La cause première est corrigée à la source : `organisations.fichiers.nom_sur`
impose désormais une extension prise dans une liste fermée. Cette couche-ci est
la seconde ligne, et elle est délibérée : le stockage contient déjà des
fichiers déposés **avant** ce correctif, et la génération y écrit par d'autres
chemins que le téléversement client.

Deux en-têtes suffisent, et ils visent la classe du défaut plutôt que les
extensions dangereuses une par une :

- `Content-Disposition: attachment` — le fichier est téléchargé, jamais rendu,
  quel que soit son type ;
- `X-Content-Type-Options: nosniff` — le navigateur ne « devine » pas un type
  plus permissif que celui annoncé, ce qu'il fait volontiers sinon.

**Le contrôle d'accès est désormais là.** Chaque lien porte une signature
horodatée liée au chemin (`evkha/signatures.py`). Un nom de fichier deviné ne
suffit plus, et un lien ne vaut plus éternellement.

Il ne s'agit pas d'une authentification, et c'est délibéré : ni Brevo, qui
récupère les pièces jointes depuis Internet, ni le client final de l'abonné,
qui n'a pas de compte chez nous, ne peuvent présenter de session. Un lien
transmis reste donc utilisable jusqu'à son expiration — ce qui disparaît, c'est
l'énumération et la validité sans fin.
"""
from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.views.static import serve as servir_statique

from . import signatures


def servir_media(request: HttpRequest, path: str, **kwargs: object) -> HttpResponse:
    """Sert un fichier de `MEDIA_ROOT`, signature vérifiée, en téléchargement."""
    if not signatures.signature_valable(path, request.GET.get(signatures.PARAMETRE, "")):
        # Réponse volontairement identique à celle d'un fichier absent : dire
        # « signature invalide » confirmerait au passage que le fichier existe,
        # et transformerait cette route en oracle d'énumération.
        raise Http404

    reponse = servir_statique(request, path, **kwargs)  # type: ignore[arg-type]

    # `filename` n'est volontairement pas renseigne : le nom stocke suffit, et
    # le repeter ici ajouterait une seconde source de verite sur le nom du
    # fichier (regle 5).
    reponse.headers["Content-Disposition"] = "attachment"
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    return reponse
