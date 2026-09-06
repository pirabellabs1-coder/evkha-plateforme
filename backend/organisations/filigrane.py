"""Le filigrane posé sur les pages d'aperçu de la boutique.

## Pourquoi il existe

L'aperçu montre les premières pages d'une étude vendue. Sans marque, ces pages
sont un extrait propre, indiscernable du document acheté : elles se transmettent,
se recopient, et rien n'y dit d'où elles viennent ni qu'il en manque le reste.
Le filigrane ne rend pas l'extrait inutilisable — il le rend *reconnaissable*,
et il porte l'adresse où l'étude complète s'achète.

## Ce qu'il ne fait pas, et il faut le dire

Ce n'est pas une protection. Un calque vectoriel s'enlève avec les bons outils,
et le prétendre inviolable serait le genre de fausse garantie qui fait baisser
la garde ailleurs. Ce qui protège vraiment l'étude, c'est le découpage : dix
pages au plus, et jamais plus de quatre dixièmes du document
(`vues_boutique.APERCU_PAGES_MAX` et `APERCU_PART_MAX`). Le filigrane dissuade
la reprise distraite et signe la provenance ; c'est tout ce qu'on lui demande.

## Le calque est posé PAR-DESSUS, et l'échec est fermé

`merge_page` dépose le calque après le contenu de la page : rien ne peut le
masquer en dessinant par-dessus. Et si la composition échoue, l'appelant doit
refuser l'aperçu plutôt que de servir des pages nues — c'est la règle du
fichier voisin, qui refuse déjà de rendre le document entier « faute de
mieux ».
"""
from __future__ import annotations

import math
from io import BytesIO
from typing import Any

#: Le texte répété en diagonale.
#:
#: Court, et il porte l'adresse : une page d'extrait qui circule doit dire où
#: se trouve l'étude entière. « EXTRAIT » plutôt que « CONFIDENTIEL » ou
#: « COPIE » — le document n'est ni l'un ni l'autre, il est incomplet, et c'est
#: exactement ce qu'il faut annoncer à qui le lit.
TEXTE = "EXTRAIT · EVKHA · evkha.fr"

#: Gris moyen. Ni noir, qui masquerait le texte, ni très clair, qui
#: disparaîtrait à l'impression en niveaux de gris.
GRIS = (0.42, 0.42, 0.45)

#: Opacité du calque. Mesurée sur une page d'étude réelle : à 0,16 le texte
#: sous-jacent reste parfaitement lisible, et le filigrane se voit sur une
#: capture d'écran comme sur une impression.
OPACITE = 0.16

#: Inclinaison, en degrés. La diagonale traverse les colonnes et les tableaux
#: au lieu de se confondre avec une ligne de texte.
ANGLE = 30

#: Taille de police rapportée à la largeur de page, et son plancher. Une taille
#: fixe donnerait un timbre-poste sur un A3 et un pavé sur un A5.
PART_DE_LA_LARGEUR = 26
TAILLE_MINIMALE = 13.0


class FiligraneImpossible(RuntimeError):
    """La composition du calque a échoué.

    Type propre plutôt qu'une exception générique : l'appelant doit pouvoir
    distinguer « je ne sais pas filigraner » de « je ne sais pas lire ce PDF »,
    et refuser dans les deux cas — mais en le disant juste dans les journaux.
    """


def _calque(largeur: float, hauteur: float, texte: str) -> Any:
    """Une page transparente de la taille demandée, couverte du texte incliné.

    Le texte est répété en lignes qui couvrent la DIAGONALE de la page et non
    sa largeur : une fois incliné, un pavé de la largeur de la page laisse deux
    coins nus, et ce sont précisément les coins qu'on recadre pour faire
    disparaître une marque.
    """
    try:
        from pypdf import PdfReader  # noqa: PLC0415
        from reportlab.pdfgen import canvas as toile_pdf  # noqa: PLC0415
    except ImportError as manque:  # pragma: no cover — dépendances déclarées
        raise FiligraneImpossible(str(manque)) from manque

    taille = max(TAILLE_MINIMALE, largeur / PART_DE_LA_LARGEUR)
    diagonale = math.hypot(largeur, hauteur)

    tampon = BytesIO()
    toile = toile_pdf.Canvas(tampon, pagesize=(largeur, hauteur))
    toile.saveState()
    toile.setFillColorRGB(*GRIS, alpha=OPACITE)
    toile.setFont("Helvetica-Bold", taille)

    # On tourne autour du CENTRE de la page : après rotation, l'origine reste
    # au milieu, et les lignes se répartissent symétriquement de part et
    # d'autre. Tourner autour du coin obligerait à corriger le décalage à la
    # main, pour le même résultat.
    toile.translate(largeur / 2, hauteur / 2)
    toile.rotate(ANGLE)

    # Une ligne assez longue pour dépasser la diagonale des deux côtés.
    motif = texte + "     "
    largeur_motif = toile.stringWidth(motif, "Helvetica-Bold", taille)
    repetitions = max(1, int(diagonale / max(largeur_motif, 1)) + 2)
    ligne = motif * repetitions

    # L'ecart entre deux lignes. Mesure a l'ecran sur une page d'etude reelle :
    # a 4,5 fois la police, la grille couvre bien mais la page a l'air brouillee
    # — pour un document de VENTE, c'est un defaut. A 6,5, la marque se voit
    # partout et la page respire.
    pas = taille * 6.5
    lignes = int(diagonale / pas) + 2
    for index in range(-lignes, lignes + 1):
        toile.drawCentredString(0, index * pas, ligne)

    toile.restoreState()
    toile.save()
    tampon.seek(0)
    return PdfReader(tampon).pages[0]


def poser(pages: list[Any], *, texte: str = TEXTE) -> None:
    """Pose le filigrane sur chaque page, EN PLACE.

    Les calques sont mis en cache par taille de page : une étude de dix pages
    au même format ne compose qu'un seul calque, là où une composition par page
    ferait dix fois le même travail à chaque consultation d'une fiche.

    Lève `FiligraneImpossible` plutôt que de rendre les pages inchangées. Une
    fonction qui échouerait en silence livrerait des pages nues à un appelant
    persuadé de les avoir marquées — et personne ne s'en apercevrait avant de
    voir l'extrait circuler.
    """
    if not pages:
        return
    cache: dict[tuple[int, int], Any] = {}
    try:
        for page in pages:
            boite = page.mediabox
            largeur = float(boite.width)
            hauteur = float(boite.height)
            cle = (round(largeur), round(hauteur))
            if cle not in cache:
                cache[cle] = _calque(largeur, hauteur, texte)
            # `merge_page` dépose le calque APRÈS le contenu : il est au-dessus,
            # et rien de la page ne peut le recouvrir.
            page.merge_page(cache[cle])
    except FiligraneImpossible:
        raise
    except Exception as echec:  # noqa: BLE001 — converti, jamais avalé
        raise FiligraneImpossible(str(echec)) from echec
