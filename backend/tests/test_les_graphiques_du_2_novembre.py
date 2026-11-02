"""Les graphiques de l'étude `a6947890`, relevés par Evangéline le 02/11/2026.

« Il y a plusieurs graphiques qui ressortent comme des gros pavés noirs […]
ça met la figure présentée au chapitre 0 ou au chapitre 7, alors qu'en fait ce
n'est pas du tout le cas […] c'est tout le temps les mêmes […] le graphique, il
est un peu automatique et il prend n'importe quoi. »

Trois causes, mesurées sur le PDF livré :

1. **Le noir comme aplat.** Sa couleur secondaire est `#000000`, et toute
   figure à une seule série la prend : une barre pleine noire.
2. **Deux grandeurs incomparables sur un même axe.** 3,5 Md€ face à 176 Md€ :
   la petite barre disparaît, la grande devient un pavé plein cadre.
3. **La complétion automatique et ses renvois** — retirées, voir
   `test_plancher_de_figures` et `test_une_figure_n_est_jamais_dessinee_deux_fois`.

Chaque test échoue sur le code d'avant (règle 6), sauf les contre-épreuves.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.rendu_word.donnees_graphiques import Resolution
from generation.rendu_word.palette import REF_OR_BRONZE, construire_palette, luminance

JAUNE_EVANGELINE = "#EEBA2B"
NOIR = "#000000"


# ── 1. Le noir n'est pas une surface ─────────────────────────────────────────


def test_une_serie_seule_ne_sort_plus_en_noir() -> None:
    from generation.rendu_word.graphiques import _couleurs

    palette = construire_palette(primaire=JAUNE_EVANGELINE, secondaire=NOIR)

    assert _couleurs(palette, 1) == [JAUNE_EVANGELINE]


def test_plusieurs_series_ne_portent_pas_de_barre_noire() -> None:
    from generation.rendu_word.graphiques import _couleurs

    palette = construire_palette(primaire=JAUNE_EVANGELINE, secondaire=NOIR)

    couleurs = _couleurs(palette, 3)
    assert NOIR not in couleurs
    assert couleurs[1] == REF_OR_BRONZE, "le bronze, pas une seconde fois la principale"


def test_contre_epreuve_une_secondaire_qui_fait_un_aplat_reste_la_sienne() -> None:
    """La charte du client tient dès que sa couleur fait une surface."""
    from generation.rendu_word.graphiques import _couleurs

    palette = construire_palette(primaire=JAUNE_EVANGELINE, secondaire="#1F6FB2")

    assert _couleurs(palette, 1) == ["#1F6FB2"]
    assert _couleurs(palette, 2)[1] == "#1F6FB2"


def test_contre_epreuve_la_charte_de_reference_ne_bouge_pas() -> None:
    from generation.rendu_word.graphiques import _couleurs

    palette = construire_palette()

    assert _couleurs(palette, 1) == [REF_OR_BRONZE]
    assert luminance(_couleurs(palette, 3)[0]) < 0.05, "la série 1 reste la prune sombre"


# ── 2. Des barres que l'œil ne peut pas comparer ─────────────────────────────


def _barres(*valeurs: float, forme: str = "barres") -> Any:
    return Resolution(
        donnees={"etiquettes": [f"x{i}" for i in range(len(valeurs))], "valeurs": list(valeurs)},
        type_graphique=forme,
    )


def _ecarts(resolution: Any) -> list[str]:
    from generation.rendu_word.specification_figures import _ecarts_d_echelle

    return [ecart.regle for ecart in _ecarts_d_echelle(resolution)]


def test_3_5_face_a_176_ne_se_dessine_pas_en_barres() -> None:
    """LE cas du chapitre 2 de `a6947890` : un rapport de 50."""
    assert _ecarts(_barres(3.5, 176.0)) == ["echelle"]
    assert _ecarts(_barres(3.5, 176.0, forme="barres_horizontales")) == ["echelle"]


@pytest.mark.parametrize("valeurs", [(3.5, 7.0, 16.8), (10.0, 200.0), (1.0, 1.0)])
def test_contre_epreuve_des_barres_comparables_passent(valeurs: tuple[float, ...]) -> None:
    assert _ecarts(_barres(*valeurs)) == []


def test_contre_epreuve_l_entonnoir_garde_ses_ordres_de_grandeur() -> None:
    """Marché total, accessible, visé : l'écart d'échelle EST son propos."""
    assert _ecarts(_barres(4000.0, 760.0, 0.03, forme="entonnoir")) == []


def test_la_regle_est_branchee_dans_la_specification() -> None:
    """Écrite mais pas appelée, c'est le défaut de Gamma (règle 8)."""
    import inspect

    from generation.rendu_word import specification_figures

    source = inspect.getsource(specification_figures.ecarts_de_specification)
    assert "_ecarts_d_echelle(resolution)" in source
