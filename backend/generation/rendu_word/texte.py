"""Raccourcir un texte pour le lecteur : au mot, jamais au milieu d'un mot.

## Le défaut, mesuré

Business plan ÉCLORE, 29/09/2026 (107 pages, rendu Word puis PDF). Deux
familles de coupes dans le document livré, nées toutes deux dans notre rendu :

- les libellés des tableaux de repli étaient coupés net à 110 signes
  (`assemblage._tableau_de_repli`), sans points de suspension : le lecteur
  voyait un mot amputé et le prenait pour une faute de frappe ;
- l'en-tête courant et l'auteur du PDF recopiaient toute la raison sociale
  saisie dans « Ma marque » — « ÉCLORE (nom de projet provisoire), avec pour
  signature « … » » — sur 105 pages.

## Une seule façon de couper (règle 5)

Chaque endroit coupait à sa manière. Ils passent désormais tous par ici :
`couper_au_mot` borne une longueur sans jamais entamer un mot, et DIT la coupe
par « … » ; `nom_court` garde la tête d'une dénomination, avant toute
apposition ; `libelle_court` garde la première phrase d'une définition.
"""
from __future__ import annotations

import re

#: Au-delà, un nom ne tient plus sur la ligne d'en-tête à côté du titre du
#: document (« Stratégie d'entreprise », le plus long, fait 22 signes ; la ligne
#: utile d'une page A4 à 2 cm de marge en porte environ 95 en corps 9).
NOM_COURT_MAX = 40

#: Plafond d'un libellé dans une cellule de tableau. Même valeur que la coupe
#: dure qu'il remplace : seule la MANIÈRE de couper change.
LIBELLE_MAX = 110

#: Ce qui ouvre une apposition après un nom : « ÉCLORE (nom provisoire) »,
#: « ÉCLORE, avec pour signature… », « ÉCLORE — bien-être », « ÉCLORE « … » ».
#:
#: CLASSE, pas liste d'exemples (règle 4) : toute ponctuation qui ouvre une
#: précision — parenthèse ou crochet, virgule, point-virgule, deux-points, tiret
#: long ou moyen, trait d'union ENTOURÉ d'espaces, guillemet ouvrant. Un trait
#: d'union collé (« Saint-Étienne ») et un point (« Atelier S. Martin ») n'en
#: font pas partie : ils vivent à l'intérieur des noms.
_APPOSITION = re.compile(r"\s*(?:[(\[,;:—–«“\"]|\s-\s)")

#: Ce qui ne doit ni ouvrir ni fermer un nom ou une coupe.
_BORDS = " ,;:.-–—/«»“”\"'()[]"

#: Une fin de phrase : un point suivi d'une espace et d'une majuscule. Un point
#: décimal (« 2.5 ») ou une abréviation suivie d'une minuscule ne coupent pas.
_FIN_DE_PHRASE = re.compile(r"\.\s+(?=[A-ZÀ-Þ])")


def couper_au_mot(texte: str, plafond: int) -> str:
    """Le texte borné à `plafond` signes, coupé entre deux mots, suivi de « … ».

    Un texte déjà court traverse intact. Un seul mot plus long que le plafond
    n'est PAS entamé : la règle « jamais au milieu d'un mot » l'emporte sur la
    longueur — un mot coupé se lit comme une faute, un mot long se lit.
    """
    texte = " ".join(str(texte or "").split())
    if len(texte) <= plafond or " " not in texte:
        return texte
    limite = max(plafond - 1, 1)  # la place du « … »
    tete = texte[:limite]
    if texte[limite] != " ":
        # La coupe tombe dans un mot : on recule jusqu'à l'espace précédente.
        espace = tete.rfind(" ")
        tete = tete[:espace] if espace > 0 else texte.split(" ", 1)[0]
    tete = tete.rstrip(_BORDS)
    return f"{tete}…" if tete else texte


def nom_court(texte: str, plafond: int = NOM_COURT_MAX) -> str:
    """La tête d'une dénomination, avant toute apposition, bornée à `plafond`.

    « ÉCLORE (nom de projet provisoire), avec pour signature « … » » devient
    « ÉCLORE ». « Maison Lorel » traverse intact.
    """
    propre = " ".join(str(texte or "").split()).lstrip(_BORDS)
    tete = _APPOSITION.split(propre, maxsplit=1)[0].strip(_BORDS)
    return couper_au_mot(tete or propre.strip(_BORDS), plafond)


def est_coupe(texte: str) -> bool:
    """Vrai si `couper_au_mot` a dû raccourcir ce texte."""
    return texte.endswith("…")


def libelle_court(libelle: str, plafond: int = LIBELLE_MAX) -> str:
    """La première phrase d'un libellé, bornée à `plafond` et coupée au mot.

    Le libellé du socle est une DÉFINITION : il lève toute ambiguïté sur ce que
    le chiffre mesure, donc il est souvent long. Une cellule n'en garde que la
    première phrase, et, si elle dépasse encore, la coupe se voit.
    """
    phrase = _FIN_DE_PHRASE.split(" ".join(str(libelle or "").split()), maxsplit=1)[0]
    return couper_au_mot(phrase.rstrip(". "), plafond)
