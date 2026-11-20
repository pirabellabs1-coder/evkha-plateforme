"""Les fiches de la boutique, telles qu'un ROBOT les lit.

## Pourquoi

Les pages publiques du site sont ecrites a la construction du front
(`frontend/scripts/prerendre.mjs`). Les fiches de la boutique ne peuvent pas
l'etre : leur contenu est en base, et la gerante ajoute ou retire une etude
sans mise en ligne. Mesure le 20/11/2026 : `/boutique/<etude>` rendait a un
robot sans JavaScript la coquille vide de l'application — titre « Espace
client », aucun texte — et toute adresse inventee sous `/boutique/` repondait
200.

Or ce sont les pages « par secteur », celles que la concurrence aligne en
serie.

## Comment

nginx (`frontend/nginx.conf`) confie `/boutique/<slug>` a `page`, et
`/sitemap-boutique.xml` a `plan`.

`page` prend la COQUILLE de l'application la ou elle est servie (le conteneur
du front, par le reseau interne) et y ecrit :

  - dans l'en-tete : le titre, la description, l'adresse canonique, les
    balises de partage et le bloc `Product` de l'etude ;
  - dans le corps : le texte de la fiche, dans un `<noscript>`.

La coquille n'est PAS recopiee ici : elle porte le nom des fichiers de
l'application, qui change a chaque construction. La lire a la demande, sans
cache, garantit que la page servie cite toujours des fichiers qui existent —
un cache de trente secondes aurait servi, apres chaque mise en ligne, des
fiches dont le script n'existe plus.

### Pourquoi `<noscript>`, et pas la racine de l'application

Un navigateur monte l'application dans `#root` et y affiche la vraie fiche.
Ecrire le texte dans cette racine le ferait apparaitre SANS sa mise en forme
(la feuille de style de la fiche est chargee a la demande), puis disparaitre
pendant que la fiche charge ses donnees, puis revenir : trois etats pour une
personne venue acheter. `<noscript>` ne s'affiche que sans JavaScript : le
visiteur ne voit aucun changement, et un robot qui n'execute pas de scripts
lit le texte.

Limite, dite : Google execute les scripts et lit la fiche montee par
l'application ; il ne s'appuie pas sur `<noscript>`. Ce bloc sert les robots
qui n'executent rien — ceux des moteurs de reponse, les apercus de partage.
L'en-tete, lui, sert tout le monde.

### Les marques de l'en-tete

Chaque balise ajoutee porte `data-prerendu`, chaque balise changee porte
`data-origine` avec sa valeur d'avant : ce sont les marques du pre-rendu, que
`frontend/src/enTetePrerendu.ts` defait avant de monter l'application. Sans
elles, la page porterait deux adresses canoniques, et le titre de l'etude
suivrait le visiteur sur la page suivante.

## Ce qui echoue, echoue bruyamment (regle 1)

Si la coquille ne peut pas etre lue, ou si elle n'a plus la forme attendue
(un titre, une description, une racine vide), la vue repond 503 — et nginx
sert alors la coquille seule, comme avant : le visiteur a sa fiche, le robot
n'a rien, et personne ne recoit une page a moitie ecrite.
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import re
from typing import Any
from urllib.parse import quote
from xml.sax.saxutils import escape as xml

import httpx
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.html import escape
from django.views.decorators.http import require_safe

from catalog.models import ProduitBoutique

from . import vues_boutique

_log = logging.getLogger(__name__)

#: Les memes noms que `frontend/src/enTetePrerendu.ts`. Ce fichier n'est pas
#: du TypeScript et ne peut pas les importer : `test_pages_boutique` les
#: compare (regle 5 — a defaut d'une source unique, un controle).
MARQUE_AJOUTEE = "data-prerendu"
MARQUE_CHANGEE = "data-origine"

#: Le temps laisse au conteneur du front pour rendre la coquille : un fichier
#: de quatre kilo-octets sur le reseau interne. Au-dela, quelque chose ne va
#: pas, et la personne n'attend pas.
DELAI_COQUILLE_S = 3.0

SUFFIXE_DU_TITRE = " — EVKHA"
LONGUEUR_DU_RESUME = 160


class CoquilleIllisible(Exception):
    """La coquille n'a pas pu etre lue, ou n'a plus la forme attendue."""


def _coquille() -> str:
    """Le `index.html` de l'application, lu dans le conteneur qui le sert."""
    base = str(getattr(settings, "EVKHA_FRONT_INTERNE", "") or "").rstrip("/")
    if not base:
        raise CoquilleIllisible("EVKHA_FRONT_INTERNE n'est pas defini")
    try:
        reponse = httpx.get(
            f"{base}/index.html",
            timeout=httpx.Timeout(DELAI_COQUILLE_S),
            follow_redirects=False,
        )
        reponse.raise_for_status()
    except httpx.HTTPError as erreur:
        raise CoquilleIllisible(type(erreur).__name__) from erreur
    return reponse.text


# ── Ecrire dans la coquille ─────────────────────────────────────────────────

_TITRE = re.compile(r"<title>([^<]*)</title>")
_RACINE = '<div id="root"></div>'
_FIN_D_EN_TETE = "</head>"


def _meta(attribut: str, nom: str) -> re.Pattern[str]:
    """La balise `<meta attribut="nom" content="...">` de la coquille, dont la
    valeur est capturee. `\\s+` : la source l'ecrit sur plusieurs lignes."""
    return re.compile(
        rf'<meta\s+{attribut}="{re.escape(nom)}"\s+content="([^"]*)"\s*/?>'
    )


def _remplacer_une_fois(
    motif: re.Pattern[str], texte: str, ecrire: Any, quoi: str
) -> str:
    """Remplace l'UNIQUE occurrence de `motif`. Zero ou deux : la coquille a
    change de forme, et ecrire quand meme rendrait une page fausse."""
    trouvees = motif.findall(texte)
    if len(trouvees) != 1:
        raise CoquilleIllisible(f"{quoi} : {len(trouvees)} occurrence(s)")
    return motif.sub(ecrire, texte, count=1)


def composer(
    coquille: str,
    *,
    titre: str | None,
    description: str | None,
    en_tete: list[str],
    corps: str,
) -> str:
    """La coquille, avec l'en-tete et le corps de la page.

    `titre` et `description` a `None` : la page garde ceux de la coquille.
    """
    html = coquille

    if titre is not None:
        html = _remplacer_une_fois(
            _TITRE,
            html,
            lambda m: (
                f'<title {MARQUE_CHANGEE}="{escape(html_lib.unescape(m.group(1)))}">'
                f"{escape(titre)}</title>"
            ),
            "titre",
        )
        for attribut, nom in (("property", "og:title"), ("name", "twitter:title")):
            html = _changer_la_meta(html, attribut, nom, titre)
    if description is not None:
        html = _changer_la_meta(html, "name", "description", description)
        html = _changer_la_meta(html, "property", "og:description", description)

    if html.count(_FIN_D_EN_TETE) != 1:
        raise CoquilleIllisible("fin d'en-tete introuvable")
    html = html.replace(_FIN_D_EN_TETE, "".join(en_tete) + _FIN_D_EN_TETE)

    if html.count(_RACINE) != 1:
        raise CoquilleIllisible("racine de l'application introuvable")
    return html.replace(_RACINE, f"{_RACINE}<noscript>{corps}</noscript>")


def _changer_la_meta(html: str, attribut: str, nom: str, valeur: str) -> str:
    return _remplacer_une_fois(
        _meta(attribut, nom),
        html,
        lambda m: (
            f'<meta {attribut}="{nom}" content="{escape(valeur)}" '
            f'{MARQUE_CHANGEE}="{m.group(1)}" />'
        ),
        nom,
    )


# ── Ce que la page dit ──────────────────────────────────────────────────────


def _origine(request: HttpRequest) -> str:
    """L'adresse publique du site, sans barre finale.

    `EVKHA_APP_URL` d'abord : c'est l'adresse CANONIQUE, la meme quel que soit
    le nom par lequel la requete est arrivee. A defaut (developpement), celle
    de la requete.
    """
    base = str(getattr(settings, "EVKHA_APP_URL", "") or "").rstrip("/")
    return base or request.build_absolute_uri("/").rstrip("/")


def _adresse(request: HttpRequest, slug: str) -> str:
    return f"{_origine(request)}/boutique/{quote(slug)}"


def _paragraphes(description: str) -> list[str]:
    """Les paragraphes de la description : ceux de la gerante, separes par une
    ligne vide — la meme coupe que `FicheProduit.paragraphes`."""
    return [p.strip() for p in re.split(r"\n\s*\n", description) if p.strip()]


def _resume(description: str) -> str:
    """Le debut du premier paragraphe, coupe entre deux mots — la description
    de la page pour les moteurs, comme `FicheProduit.resume`."""
    paragraphes = _paragraphes(description)
    premier = " ".join(paragraphes[0].split()) if paragraphes else ""
    if len(premier) <= LONGUEUR_DU_RESUME:
        return premier
    coupe = premier[: LONGUEUR_DU_RESUME - 3]
    return re.sub(r"\s+\S*$", "", coupe) + "…"


def _prix(cents: int, devise: str) -> str:
    """« 89 € », « 89,50 € » ; hors euro, le code de la devise."""
    euros, centimes = divmod(cents, 100)
    montant = str(euros) if centimes == 0 else f"{euros},{centimes:02d}"
    return f"{montant} €" if devise.upper() == "EUR" else f"{montant} {devise.upper()}"


def _json_pour_script(donnees: dict[str, Any]) -> str:
    """Du JSON qui ne peut pas refermer sa balise `<script>`."""
    return (
        json.dumps(donnees, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def donnees_structurees(fiche: dict[str, Any], adresse: str) -> dict[str, Any]:
    """Le bloc `Product` de l'etude — les memes regles que
    `FicheProduit.donneesStructurees` : un champ que la fiche ne porte pas
    n'est pas declare. Ni note sans avis publie, ni offre sans prix, ni
    disponibilite, ni marque : ce serait declarer un fait que personne n'a
    etabli."""
    bloc: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": fiche["titre"],
        "url": adresse,
    }
    if fiche["description"]:
        bloc["description"] = fiche["description"]
    if fiche["theme"]:
        bloc["category"] = fiche["theme"]
    if fiche["image"]:
        bloc["image"] = fiche["image"]
    if fiche["prix_cents"] > 0 and fiche["devise"]:
        bloc["offers"] = {
            "@type": "Offer",
            "price": f"{fiche['prix_cents'] / 100:.2f}",
            "priceCurrency": fiche["devise"],
            "url": adresse,
        }
    if fiche["avis"] and fiche["note"] > 0:
        bloc["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": fiche["note"],
            "reviewCount": len(fiche["avis"]),
        }
    return bloc


def _corps(fiche: dict[str, Any], proches: list[dict[str, Any]]) -> str:
    """Le texte de la fiche. Tout ce qui vient de la base est echappe."""
    morceaux = ['<article><p><a href="/boutique">Toutes les études</a></p>']
    if fiche["theme"]:
        morceaux.append(f"<p>{escape(fiche['theme'])}</p>")
    morceaux.append(f"<h1>{escape(fiche['titre'])}</h1>")
    formats = "PDF et Word" if fiche["editable"] else "PDF"
    morceaux.append(
        f"<p>{escape(_prix(fiche['prix_cents'], fiche['devise']))} TTC, "
        f"paiement unique. {formats}, téléchargement immédiat après paiement.</p>"
    )
    if fiche["description"]:
        morceaux.append("<h2>Ce que vous achetez</h2>")
        morceaux.extend(f"<p>{escape(p)}</p>" for p in _paragraphes(fiche["description"]))
    if fiche["sommaire"]:
        morceaux.append("<h2>Le sommaire</h2><ol>")
        morceaux.extend(f"<li>{escape(ligne)}</li>" for ligne in fiche["sommaire"])
        morceaux.append("</ol>")
    if fiche["apercu"]:
        morceaux.append(
            f'<p><a href="{escape(fiche["apercu"]["adresse"])}">Feuilleter les '
            f'{int(fiche["apercu"]["pages"])} premières pages</a></p>'
        )
    if fiche["avis"]:
        morceaux.append("<h2>Ce qu'en disent les lectrices</h2><ul>")
        for avis in fiche["avis"]:
            signature = str(escape(avis["auteur"]))
            if avis["qualite"]:
                signature += f", {escape(avis['qualite'])}"
            texte = f"<blockquote>{escape(avis['texte'])}</blockquote>" if avis["texte"] else ""
            morceaux.append(
                f"<li>Note : {int(avis['note'])} sur 5. {texte}<p>{signature}</p></li>"
            )
        morceaux.append("</ul>")
    morceaux.append("</article>")
    if proches:
        morceaux.append("<h2>Ces études peuvent aussi vous intéresser</h2><ul>")
        morceaux.extend(
            f'<li><a href="/boutique/{quote(p["slug"])}">{escape(p["titre"])}</a></li>'
            for p in proches
        )
        morceaux.append("</ul>")
    morceaux.append(
        '<p>Pour une étude bâtie sur votre propre projet : '
        '<a href="/etudes">les études sur mesure</a>.</p>'
    )
    return "".join(morceaux)


def _html(corps: str, statut: int = 200) -> HttpResponse:
    reponse = HttpResponse(corps, status=statut, content_type="text/html; charset=utf-8")
    # Le prix et la liste des etudes proches changent sans prevenir : la page
    # se revalide a chaque visite.
    reponse["Cache-Control"] = "no-cache"
    return reponse


@require_safe
def page(request: HttpRequest, slug: str) -> HttpResponse:
    """La fiche d'une etude, en HTML complet. 404 si elle n'est pas en vente."""
    produit: ProduitBoutique | None = (
        vues_boutique._en_ligne().filter(slug=slug).first()
    )
    if produit is None:
        # 404 SANS corps, et sans lire la coquille : nginx la sert lui-meme
        # avec ce code (`error_page 404` du bloc des fiches). Une adresse
        # inventee sous `/boutique/` ne coute ainsi qu'une requete en base —
        # la lire ici aurait permis d'occuper les ouvriers de l'API en
        # enchainant des adresses qui n'existent pas.
        return HttpResponse(status=404)
    try:
        coquille = _coquille()
        fiche = vues_boutique._fiche(produit)
        proches = [
            vues_boutique._resume(p) for p in vues_boutique.etudes_proches(produit)
        ]
        adresse = _adresse(request, produit.slug)
        description = _resume(fiche["description"]) or (
            "Une étude de marché déjà rédigée, à télécharger tout de suite : "
            "son sommaire, un aperçu de ses premières pages et son prix."
        )
        en_tete = [
            f'<link rel="canonical" href="{escape(adresse)}" {MARQUE_AJOUTEE}="" />',
            f'<meta property="og:url" content="{escape(adresse)}" {MARQUE_AJOUTEE}="" />',
            f'<meta name="twitter:description" content="{escape(description)}" '
            f'{MARQUE_AJOUTEE}="" />',
            f'<script type="application/ld+json" {MARQUE_AJOUTEE}="">'
            f"{_json_pour_script(donnees_structurees(fiche, adresse))}</script>",
        ]
        return _html(
            composer(
                coquille,
                titre=f"{fiche['titre']}{SUFFIXE_DU_TITRE}",
                description=description,
                en_tete=en_tete,
                corps=_corps(fiche, proches),
            )
        )
    except CoquilleIllisible as erreur:
        # 503 : nginx sert alors la coquille seule. Le visiteur a sa fiche par
        # l'application ; le journal dit pourquoi le robot n'a rien eu.
        _log.error("fiche de boutique non ecrite : %s", erreur)
        return HttpResponse(status=503)


@require_safe
def plan(request: HttpRequest) -> HttpResponse:
    """Le plan du site des fiches en vente (`/sitemap-boutique.xml`).

    Ecrit a la demande : une etude mise en ligne par la gerante y figure sans
    mise en production, une etude retiree en sort.
    """
    lignes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for produit in vues_boutique._en_ligne():
        date = (
            f"<lastmod>{produit.mise_a_jour_le.isoformat()}</lastmod>"
            if produit.mise_a_jour_le
            else ""
        )
        lignes.append(
            f"  <url><loc>{xml(_adresse(request, produit.slug))}</loc>{date}</url>"
        )
    lignes.append("</urlset>\n")
    return HttpResponse("\n".join(lignes), content_type="text/xml; charset=utf-8")
