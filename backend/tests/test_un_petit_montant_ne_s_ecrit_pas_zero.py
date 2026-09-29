"""Un petit montant stocké à une grande échelle ne s'écrit jamais « 0 ».

29/09/2026, rendu du business plan ÉCLORE : `montant_lisible(0.0003, "MdEUR")`
rendait « 0 Md€ » (le formateur garde trois décimales). Le modèle lisait
« SOM = 0 Md€ » dans son prompt, l'annexe imprimait un faux zéro, et les
repères de la mémoire de l'étude — qui passent par ce formateur — l'auraient
hérité. Corrigé à la source (règle 5) : un seul formateur, pour tous.
"""
from __future__ import annotations

import pytest

from generation.socle.schema import montant_lisible


def _plat(texte: str) -> str:
    return texte.replace("\u00a0", " ").replace("\u202f", " ")


@pytest.mark.parametrize(("valeur", "unite", "attendu"), [
    (0.0003, "MdEUR", "300 000 €"),
    (0.25, "MdEUR", "250 M€"),
    (0.5, "MEUR", "500 000 €"),
    (1.2345, "MdEUR", "1 234,5 M€"),
])
def test_un_petit_montant_passe_a_l_echelle_qui_ne_perd_rien(
    valeur: float, unite: str, attendu: str
) -> None:
    assert _plat(montant_lisible(valeur, unite)) == attendu


@pytest.mark.parametrize(("valeur", "unite", "attendu"), [
    (1.2, "MdEUR", "1,2 Md€"),
    (37.3, "MdEUR", "37,3 Md€"),
    (0.0, "MdEUR", "0 Md€"),
    (320_000.0, "EUR", "320 000 €"),
])
def test_un_montant_a_son_echelle_reste_tel_quel(valeur: float, unite: str, attendu: str) -> None:
    """Contre-épreuve : ce qui s'écrivait juste ne bouge pas."""
    assert _plat(montant_lisible(valeur, unite)) == attendu
