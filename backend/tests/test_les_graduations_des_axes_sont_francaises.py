"""Un axe gradué « 0.5, 1.0, 1.5 » ou décalé « 1e6 » écrit un nombre à l'anglaise.

Les annotations des figures parlent français depuis le lot 87 (`_fmt`), les
graduations des axes non : `graphiques.py` ne posait aucun formateur, et
matplotlib applique le sien — point décimal, et notation scientifique avec
décalage dès le million. Relevé le 26/09/2026 en relisant les douze figures
d'un rendu : toutes juste parce que leurs graduations tombaient sur des entiers
ou que leurs valeurs étaient mises à l'échelle en amont. Un marché de 0 à 3 M€
sur une barre aurait donné « 0.5 ». Le formateur vit dans `_figure`, une fois
pour toutes les figures (règle 5).
"""
from __future__ import annotations

import re

import pytest

from generation.rendu_word.graphiques import _figure, _fmt
from generation.rendu_word.palette import Palette, construire_palette


@pytest.fixture
def palette() -> Palette:
    return construire_palette(primaire="", secondaire="", fond_clair="")


def _graduations(palette: Palette, bas: float, haut: float) -> list[str]:
    figure, axes = _figure(palette)
    axes.set_ylim(bas, haut)
    figure.canvas.draw()
    textes = [t.get_text() for t in axes.get_yticklabels() if t.get_text()]
    figure.clf()
    return textes


def test_les_decimales_sont_a_la_virgule(palette: Palette) -> None:
    textes = _graduations(palette, 0, 3)
    assert "0,5" in textes, textes
    assert not any("." in t for t in textes), textes


def test_pas_de_decalage_scientifique_au_dela_du_million(palette: Palette) -> None:
    textes = _graduations(palette, 0, 3_000_000)
    assert not any("e" in t.lower() for t in textes), textes
    assert any(re.fullmatch(r"\d{1,3}(?: \d{3})+", t) for t in textes), textes


def test_les_entiers_restent_des_entiers(palette: Palette) -> None:
    """Contre-épreuve : ce qui était juste le reste — « 100, 200, 300 »."""
    assert _graduations(palette, 0, 600)[:4] == ["0", "100", "200", "300"]


def test_le_formateur_est_celui_des_annotations() -> None:
    assert _fmt(0.5) == "0,5"
    assert _fmt(1_200_000.0) == "1 200 000"
