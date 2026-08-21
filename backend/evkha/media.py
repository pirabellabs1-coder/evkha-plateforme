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

from pathlib import PurePosixPath

from django.http import Http404, HttpRequest, HttpResponse
from django.views.static import serve as servir_statique

from . import signatures

#: Extensions rendues EN LIGNE sous un prefixe public. Liste FERMEE, et c'est
#: le point : la faille d'origine venait d'un fichier `.html` servi sur
#: l'origine qui porte `/admin/`. Interdire les extensions dangereuses une par
#: une aurait laisse passer la suivante (regle 4) — on autorise, au lieu
#: d'interdire.
#:
#: `.svg` en est ABSENT alors que c'est une image : un SVG peut porter un
#: `<script>`, et le servir en ligne rouvrirait exactement la faille que ce
#: module a fermee. Une couverture se depose en JPEG ou en PNG.
#:
#: Tout le reste, meme sous un prefixe public, retombe en piece jointe.
EXTENSIONS_EN_LIGNE: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".pdf"}
)


def _prefixes_publics() -> tuple[str, ...]:
    """Prefixes servis SANS signature et EN LIGNE.

    Un seul aujourd'hui : la vitrine de la boutique — couverture et extrait.
    Ce sont des supports de vente, et les deux protections qui couvrent les
    livrables les rendraient inutilisables : une image en
    `Content-Disposition: attachment` ne s'affiche pas dans une balise `<img>`,
    et une signature qui expire ferait disparaitre les couvertures d'un
    catalogue public au bout de quelques jours.

    Le prefixe est LU dans le modele qui y range les fichiers, jamais recopie :
    deux chaines identiques dans deux modules finissent par diverger, et le
    jour ou elles divergent les couvertures cessent de s'afficher sans que rien
    ne le dise (regle 5).

    Import differe : ce module est charge tot, et importer les modeles a son
    sommet imposerait l'ordre de chargement des applications.
    """
    from catalog.models import PREFIXE_VITRINE  # noqa: PLC0415

    return (f"{PREFIXE_VITRINE.strip('/')}/",)


def _est_une_vitrine(chemin: str) -> bool:
    """Ce fichier est-il un support de vente, servable tel quel ?"""
    propre = chemin.lstrip("/")
    if not propre.startswith(_prefixes_publics()):
        return False
    return PurePosixPath(propre).suffix.lower() in EXTENSIONS_EN_LIGNE


def servir_media(request: HttpRequest, path: str, **kwargs: object) -> HttpResponse:
    """Sert un fichier de `MEDIA_ROOT`, signature vérifiée, en téléchargement.

    Sauf sous un préfixe de vitrine, où le fichier est servi tel quel : ce sont
    les images et extraits de la boutique, dont le rôle EST d'être vus par des
    visiteurs sans compte.
    """
    if _est_une_vitrine(path):
        vitrine = servir_statique(request, path, **kwargs)  # type: ignore[arg-type]
        vitrine.headers["Content-Disposition"] = "inline"
        # `nosniff` reste : l'extension est deja restreinte, mais le navigateur
        # ne doit pas non plus « deviner » un type plus permissif que celui
        # qu'on annonce.
        vitrine.headers["X-Content-Type-Options"] = "nosniff"
        return vitrine

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
