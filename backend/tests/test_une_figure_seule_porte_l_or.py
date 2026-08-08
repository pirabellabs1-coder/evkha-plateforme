"""Une figure à série unique porte l'or de la charte, pas le noir du rang 0.

**Décision de la cliente du 08/08/2026**, prise sur une mesure et non sur une
impression. Le dossier réel `b561c2d6` — l'étude de marché validée — contient
dix-sept figures. En comptant les pixels de chacune : **onze portaient l'or,
six étaient en noir et blanc intégral**. Aucune règle ne demandait cela. C'était
mécanique : l'ordre des séries est `primaire, or, crème, rosé`, donc toute
figure n'ayant qu'UNE série s'arrêtait au rang 0, le sombre.

## Ce que ce test ne verrouille PAS, exprès

L'ordre du lot 0 pour les figures à plusieurs séries. Il vient du document de
référence, et une figure à trois séries doit rester comparable à sa voisine :
si la première série changeait de couleur selon le nombre de séries, deux
graphiques côte à côte ne se liraient plus ensemble. La contre-épreuve ci-dessous
le garde (règle 6).

## Le trait épaissi n'est pas une coquetterie

Contrastes mesurés sur la palette réelle, avant livraison :

    couleur principale sur le fond des figures : 15,51
    or                 sur le fond des figures :  2,96

Sur un aplat — barre, part de camembert, aire — l'écart ne se voit pas : la
surface porte la couleur. Sur un trait de deux points, il se voit, et 2,96 passe
sous le seuil de 3:1 admis pour un objet graphique. On rend donc au trait en
épaisseur ce qu'il perd en contraste. Livrer une courbe délavée en la déclarant
« conforme à la charte » aurait été un contrôle qui ne regarde pas ce que le
lecteur voit (règle 9).
"""
from __future__ import annotations

import pytest

from generation.rendu_word.graphiques import (
    EPAISSEUR_TRAIT,
    EPAISSEUR_TRAIT_SOLO,
    _couleurs,
    _epaisseur,
)
from generation.rendu_word.palette import Palette, construire_palette, contraste


@pytest.fixture
def palette() -> Palette:
    return construire_palette(primaire="", secondaire="", fond_clair="")


def test_une_serie_seule_sort_en_or(palette: Palette) -> None:
    """Le défaut exact des six figures monochromes de `b561c2d6`."""
    assert _couleurs(palette, 1) == [palette.or_bronze]


def test_une_serie_seule_n_est_plus_la_couleur_principale(palette: Palette) -> None:
    """Formulé en négatif : c'est CE choix-là qui rendait les figures grises."""
    assert _couleurs(palette, 1) != [palette.primaire]


@pytest.mark.parametrize("nombre", [2, 3, 4, 5, 9])
def test_l_ordre_du_lot_0_survit_des_deux_series(
    palette: Palette, nombre: int
) -> None:
    """Contre-épreuve : ne pas casser ce qui allait bien.

    Deux figures voisines doivent rester comparables ; la première série d'une
    figure multiple reste donc sombre, quel que soit le nombre de séries.
    """
    couleurs = _couleurs(palette, nombre)

    assert couleurs[0] == palette.primaire
    assert couleurs[1] == palette.or_bronze
    assert len(couleurs) == nombre


def test_le_cycle_reboucle_au_dela_de_la_charte(palette: Palette) -> None:
    """Neuf séries ne doivent pas lever : la charte en compte quatre."""
    couleurs = _couleurs(palette, 9)

    assert couleurs[4] == couleurs[0]
    assert set(couleurs) == set(palette.series_graphique)


def test_le_trait_seul_est_plus_epais() -> None:
    assert _epaisseur(1) == EPAISSEUR_TRAIT_SOLO
    assert _epaisseur(3) == EPAISSEUR_TRAIT
    assert EPAISSEUR_TRAIT_SOLO > EPAISSEUR_TRAIT


def test_l_or_est_bien_le_moins_contraste_des_deux(palette: Palette) -> None:
    """La raison d'être du trait épaissi, vérifiée et non recopiée.

    Si un jour l'or est assombri au point de valoir la couleur principale, ce
    test tombe et le compromis est à réexaminer — plutôt que de survivre en
    commentaire longtemps après avoir cessé d'être vrai (règle 8).
    """
    sur_le_fond = contraste(palette.or_bronze, palette.fond_graphique)
    principale = contraste(palette.primaire, palette.fond_graphique)

    assert sur_le_fond < principale
    assert sur_le_fond < 3.0, (
        "L'or dépasse désormais le seuil de 3:1 : le trait épaissi n'a plus "
        f"lieu d'être ({sur_le_fond:.2f})."
    )
