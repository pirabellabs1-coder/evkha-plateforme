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
apposition ; `libelle_court` garde la première phrase d'une définition —
entière depuis le 30/09/2026 : une cellule de tableau ne se coupe plus
(« aucune ligne de tableau tronquée par "…" », cliente, business plan ÉCLORE
`28a257bf`).
"""
from __future__ import annotations

import re

#: Au-delà, un nom ne tient plus sur la ligne d'en-tête à côté du titre du
#: document (« Stratégie d'entreprise », le plus long, fait 22 signes ; la ligne
#: utile d'une page A4 à 2 cm de marge en porte environ 95 en corps 9).
NOM_COURT_MAX = 40

#: Ce qui OUVRE une apposition après un nom : « ÉCLORE (nom provisoire) »,
#: « ÉCLORE — bien-être », « ÉCLORE, avec pour signature… », « ÉCLORE avec
#: pour signature « … » ».
#:
#: La première version coupait à TOUTE ponctuation, et mutilait des raisons
#: sociales parfaitement normales (revue du 29/09/2026) : « Martin, Durand &
#: Associés » devenait « Martin », « SAS « Les Délices » » devenait « SAS ».
#: Une virgule, un point-virgule, un deux-points ou un trait d'union espacé
#: appartiennent à un nom quand la suite commence par une CAPITALE (d'autres
#: noms) ; ils ouvrent une apposition quand elle commence par une minuscule
#: (« , expériences bien-être », « , situé à Lyon »). Un guillemet appartient
#: au nom ; une parenthèse, un crochet, un tiret long ou moyen et « avec
#: pour » ouvrent toujours une précision.
_APPOSITION = re.compile(
    r"\s*[(\[—–]"
    r"|\s*[,;:]\s+(?=[a-zà-ÿœ])"
    r"|\s+-\s+(?=[a-zà-ÿœ])"
    r"|\s+avec\s+pour\b"
)

#: Ce qui ne doit ni ouvrir ni fermer une COUPE, qu'on signale par « … ».
_BORDS = " ,;:.-–—/«»“”\"'()[]"

#: Ce qui ne doit ni ouvrir ni fermer un NOM. Ni le point (« Dupont & Fils
#: S.A. »), ni les guillemets (« SAS « Les Délices » »), ni les parenthèses :
#: ils font partie du nom quand ils y sont.
_SEPARATEURS = " ,;:-–—/"

#: Guillemets qui enveloppent un nom ENTIER : « « ÉCLORE » » s'écrit ÉCLORE.
_ENVELOPPE = re.compile(r"^[«“\"]\s*([^«»“”\"]+?)\s*[»”\"]$")

#: Mots-outils du français : ils s'écrivent en minuscules DANS un nom propre
#: (« Boulangerie du Parc », « L'Atelier de Saint-Étienne », « Dupont & Fils »).
#: Classe grammaticale fermée — articles, prépositions, conjonctions —, pas une
#: liste de cas.
_MOTS_OUTILS = frozenset({
    "à", "au", "aux", "chez", "d", "de", "des", "du", "en", "et", "l", "la",
    "le", "les", "par", "pour", "sous", "sur", "y",
})

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
    « ÉCLORE ». « Maison Lorel », « Martin, Durand & Associés », « SAS « Les
    Délices » » et « Dupont & Fils S.A. » traversent intacts.
    """
    propre = " ".join(str(texte or "").split()).strip(_SEPARATEURS)
    tete = _APPOSITION.split(propre, maxsplit=1)[0].strip(_SEPARATEURS) or propre
    enveloppe = _ENVELOPPE.match(tete)
    if enveloppe:
        tete = enveloppe.group(1)
    return couper_au_mot(tete, plafond)


def est_coupe(texte: str) -> bool:
    """Vrai si `couper_au_mot` a dû raccourcir ce texte."""
    return texte.endswith("…")


def ressemble_a_un_nom(texte: str) -> bool:
    """Ce texte est-il un NOM, et pas la description d'une activité ?

    `PROJET` porte « le nom du projet ou de l'entreprise » dans le formulaire
    de l'espace, mais le formulaire Tally y range la « description du projet ».
    La première version prenait tout ce qui tenait sur la ligne : « Salon de
    coiffure mixte, situé à Lyon… » donnait l'en-tête « Salon de coiffure
    mixte » (revue du 29/09/2026).

    La règle est celle de la typographie des noms propres : hors mots-outils,
    chaque mot d'un nom commence par une capitale (« Boulangerie du Parc »,
    « Éclore Nature », « Dupont & Fils »). Un nom commun en minuscules après le
    premier mot — « coiffure », « torréfaction », « ouvrir » — dit une
    description. Un nom trop long pour la ligne n'en est pas un non plus.
    """
    tete = nom_court(texte)
    if not tete or est_coupe(tete):
        return False
    mots = re.findall(r"[^\W\d_]+", tete)
    return all(
        mot[0].isupper() or mot.casefold() in _MOTS_OUTILS for mot in mots[1:]
    )


def libelle_court(libelle: str) -> str:
    """La première phrase d'un libellé, ENTIÈRE.

    Le libellé du socle est une DÉFINITION : il lève toute ambiguïté sur ce que
    le chiffre mesure, donc il est souvent long. Une cellule n'en garde que la
    première phrase.

    ## Plus de coupe « … » (30/09/2026)

    La première phrase était encore bornée à 110 signes, coupée au mot et
    suivie de « … ». Business plan ÉCLORE `28a257bf`, annexe des chiffres :
    la définition d'un taux de marge s'arrêtait au milieu de sa phrase, sur
    « … ». La cliente : « aucune ligne de tableau tronquée par "…" ». Une
    cellule passe à la ligne ; le lecteur lit la phrase jusqu'au bout. Le
    contrôle `relecture.mise_en_page` signale toute cellule qui finirait encore
    ainsi.
    """
    phrase = _FIN_DE_PHRASE.split(" ".join(str(libelle or "").split()), maxsplit=1)[0]
    return phrase.rstrip(". ")
