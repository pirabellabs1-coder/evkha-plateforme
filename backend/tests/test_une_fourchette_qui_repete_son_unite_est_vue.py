"""« entre 120 000 € et 150 000 € » est une fourchette — la plus courante.

Le motif n'attendait l'unité qu'après la borne HAUTE : « entre 120 000 et
150 000 € » était vu, « entre 120 000 € et 150 000 € » ne l'était pas, ni
« de 15 % à 20 % ». Vérifié le 26/09/2026 par appel direct : zéro trouvaille
sur les deux, dans tous les livrables. La règle de la cliente du 23/07/2026
(« les TAUX sont TOUJOURS une valeur fixe unique ») n'était donc appliquée
qu'à la moitié des façons de l'enfreindre.

La contre-épreuve garde les gardes existantes : une TRAJECTOIRE qui répète
son unité (« passe de 120 000 € à 180 000 € ») n'est toujours pas une plage.
"""
from __future__ import annotations

import pytest

from generation.checks_evangeline import detecter_fourchettes

STRICT = "business_strategy"

PLAGES = [
    pytest.param("un budget compris entre 120 000 € et 150 000 €", id="entre-euros-repetes"),
    pytest.param("une marge de 15 % à 20 % selon les canaux", id="de-pourcent-a-pourcent"),
    pytest.param("un panier de 49 € à 59 €", id="de-euros-a-euros"),
    pytest.param("un budget compris entre 120 000 et 150 000 €", id="forme-deja-vue"),
]

PAS_DES_PLAGES = [
    pytest.param(
        "le chiffre d'affaires passe de 120 000 € à 180 000 € entre 2026 et 2027",
        id="trajectoire-unite-repetee",
    ),
    pytest.param("le saut de 19 € à 29 € a été absorbé", id="mouvement-unite-repetee"),
    pytest.param("une hausse de 3 points, de 2026 à 2027", id="dates"),
]


@pytest.mark.parametrize("texte", PLAGES)
def test_l_unite_repetee_apres_la_borne_basse_est_une_plage(texte: str) -> None:
    assert len(detecter_fourchettes(3, texte, STRICT)) == 1, texte


@pytest.mark.parametrize("texte", PAS_DES_PLAGES)
def test_une_trajectoire_reste_une_trajectoire(texte: str) -> None:
    """Contre-épreuve : le correctif ne doit pas bloquer ce qui est correct."""
    assert detecter_fourchettes(3, texte, STRICT) == [], texte


def test_les_bornes_lues_sont_les_nombres_pas_les_unites() -> None:
    (trouvee,) = detecter_fourchettes(3, "entre 120 000 € et 150 000 €", STRICT)
    assert trouvee.borne_basse.strip() == "120 000"
    assert trouvee.borne_haute.strip() == "150 000"
    assert trouvee.unite == "€"
