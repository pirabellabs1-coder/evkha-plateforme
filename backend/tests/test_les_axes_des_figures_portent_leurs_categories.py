"""Une figure gradue ses catégories par leur NOM — « 2027 », jamais « 0 ».

29/09/2026, business plan ÉCLORE : les courbes, les aires et les barres empilées
portaient « 0, 1, 2 » sous l'axe des abscisses au lieu des années (§ 3.13 du
diagnostic). `graphiques._figure` posait un formateur de nombres sur les DEUX
axes ; matplotlib n'installe son formateur de catégories que si celui de l'axe
est encore le défaut — les années, écrites en texte, s'affichaient donc par
leur rang. Les barres simples y échappaient grâce à `set_xticklabels`.

Le test existant des graduations (`test_les_graduations_des_axes_sont_francaises`)
ne lisait que l'axe des ORDONNÉES. Celui-ci lit les étiquettes réellement
dessinées, sur l'axe qui porte les catégories, pour CHAQUE forme du catalogue
qui en a (règle 4 : la classe, pas les trois formes relevées).
"""
from __future__ import annotations

from typing import Any

import pytest
from matplotlib.figure import Figure

from generation.rendu_word import graphiques
from generation.rendu_word.palette import Palette, construire_palette

ANNEES = ["2027", "2028", "2029"]
NOMS = ["Accueil", "Ateliers", "Séjours"]

#: Forme → (données, axe qui porte les catégories, catégories attendues).
_CAS: dict[str, tuple[dict[str, Any], str, list[str]]] = {
    "courbes": ({"abscisses": ANNEES, "series": [("CA", [1.0, 2.0, 3.0])]}, "x", ANNEES),
    "aires": (
        {"abscisses": ANNEES,
         "series": [("A", [1.0, 2.0, 3.0]), ("B", [2.0, 2.0, 1.0])]},
        "x", ANNEES,
    ),
    "barres_empilees": (
        {"etiquettes": ANNEES,
         "series": [("A", [1.0, 2.0, 3.0]), ("B", [2.0, 2.0, 1.0])]},
        "x", ANNEES,
    ),
    "barres_groupees": (
        {"etiquettes": ANNEES,
         "series": [("A", [1.0, 2.0, 3.0]), ("B", [2.0, 2.0, 1.0])]},
        "x", ANNEES,
    ),
    "barres": ({"etiquettes": ANNEES, "valeurs": [1.0, 2.0, 3.0]}, "x", ANNEES),
    "barres_horizontales": ({"etiquettes": NOMS, "valeurs": [1.0, 2.0, 3.0]}, "y", NOMS),
    "jauges": ({"notes": list(zip(NOMS, [4.0, 3.0, 2.5], strict=True))}, "y", NOMS),
    "pyramide_ages": (
        {"tranches": NOMS, "gauche": [1.0, 2.0, 3.0], "droite": [2.0, 1.0, 3.0]},
        "y", NOMS,
    ),
    "carte_chaleur": (
        {"lignes": NOMS, "colonnes": ANNEES,
         "valeurs": [[1.0, 2.0, 3.0], [2.0, 3.0, 1.0], [3.0, 1.0, 2.0]]},
        "x", ANNEES,
    ),
    "radar": (
        {"axes_noms": NOMS, "series": [("Projet", [4.0, 3.0, 2.0])]}, "x", NOMS,
    ),
}


@pytest.fixture
def palette() -> Palette:
    return construire_palette(primaire="", secondaire="", fond_clair="")


@pytest.fixture
def etiquettes_dessinees(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Les étiquettes des deux axes, lues sur la figure au moment de l'export."""
    lues: dict[str, list[str]] = {}

    def exporter(figure: Figure, _palette: Palette) -> bytes:
        figure.canvas.draw()
        axes = figure.axes[0]
        lues["x"] = [t.get_text() for t in axes.get_xticklabels() if t.get_text()]
        lues["y"] = [t.get_text() for t in axes.get_yticklabels() if t.get_text()]
        figure.clf()
        return b""

    monkeypatch.setattr(graphiques, "_exporter", exporter)
    return lues


@pytest.mark.parametrize("forme", sorted(_CAS))
def test_l_axe_des_categories_porte_leurs_noms(
    forme: str, palette: Palette, etiquettes_dessinees: dict[str, list[str]],
) -> None:
    donnees, axe, attendues = _CAS[forme]
    graphiques.rendre(palette, forme, donnees, titre="Figure d'essai")
    assert etiquettes_dessinees[axe] == attendues, (
        f"{forme} : l'axe {axe} porte {etiquettes_dessinees[axe]} au lieu de {attendues}"
    )


def test_l_axe_des_valeurs_reste_francais(
    palette: Palette, etiquettes_dessinees: dict[str, list[str]],
) -> None:
    """CONTRE-ÉPREUVE : rendre ses catégories à l'axe des x ne rend pas
    l'anglais à l'axe des y — « 0,5 », jamais « 0.5 »."""
    graphiques.rendre(
        palette, "courbes", {"abscisses": ANNEES, "series": [("CA", [0.5, 1.0, 2.5])]},
    )
    ordonnees = etiquettes_dessinees["y"]
    assert "0,5" in ordonnees, ordonnees
    assert not any("." in texte for texte in ordonnees), ordonnees


def test_toutes_les_formes_a_categories_sont_couvertes() -> None:
    """Une forme ajoutée au catalogue ne doit pas échapper à ce test en silence.

    Les formes SANS axe de catégories — parts d'un tout, entonnoir, frise,
    nuage de points — n'ont rien à y lire.
    """
    sans_categories = {
        "camembert", "anneau", "entonnoir", "chronologie", "matrice_positionnement",
    }
    assert set(graphiques.RENDU_PAR_TYPE) - sans_categories == set(_CAS)
