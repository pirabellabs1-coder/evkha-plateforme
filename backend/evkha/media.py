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

Ce que cette couche ne fait PAS, et qu'il faut savoir en la lisant : elle ne
contrôle **aucun droit d'accès**. Qui détient l'URL télécharge. Les liens de
livraison sont récupérés par Brevo depuis Internet, sans session — les protéger
demande des URL signées à durée limitée, pas une authentification de session.
C'est un chantier distinct, et il reste ouvert.
"""
from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.views.static import serve as servir_statique


def servir_media(request: HttpRequest, path: str, **kwargs: object) -> HttpResponse:
    """Sert un fichier de `MEDIA_ROOT` en imposant qu'il soit téléchargé."""
    reponse = servir_statique(request, path, **kwargs)  # type: ignore[arg-type]

    # `filename` n'est volontairement pas renseigne : le nom stocke suffit, et
    # le repeter ici ajouterait une seconde source de verite sur le nom du
    # fichier (regle 5).
    reponse.headers["Content-Disposition"] = "attachment"
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    return reponse
