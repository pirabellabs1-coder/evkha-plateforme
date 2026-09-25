"""« CA An1 250 272 € » se lisait « 1 250 272 € » — et ce montant faux était
verrouillé comme fait client, puis opposé au document.

Mesuré le 26/09/2026 en appelant l'extracteur du brief sur la forme exacte
citée par son propre commentaire (`intake/financials.py`). `MONEY` et
`MONEY_CAPTURED` n'avaient pas le garde `_NUMBER_START` que
`AMOUNT_WITH_UNIT_RE` porte depuis le début : le « 1 » de « An1 » était pris
pour un chiffre de millions.

C'est la règle 2 à l'état pur : un contrôle qui compare à une donnée mal
extraite envoie corriger un chiffre qui n'était pas faux.
"""
from __future__ import annotations

import re

import pytest

from core.numbers import MONEY, MONEY_CAPTURED
from intake.financials import extract_financials_from_text


def test_l_indice_d_exercice_ne_fait_pas_partie_du_montant() -> None:
    lu = extract_financials_from_text("CA An1 250 272 €, An2 296 000 €")
    assert lu["CA_PREVISIONNEL"] == "250 272 € / 296 000 €"


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        pytest.param("An1 250 272 €", "250 272", id="indice-colle"),
        pytest.param("S1 2027 : 20 000 €", "20 000", id="semestre-puis-annee"),
        pytest.param("Investissement : 1 250 000 €", "1 250 000", id="millions-intacts"),
        pytest.param("**320 000 €** en An3", "320 000", id="gras-markdown"),
        pytest.param("apport de -20 000 €", "-20 000", id="negatif"),
    ],
)
def test_money_capture_le_bon_nombre(texte: str, attendu: str) -> None:
    trouve = re.search(MONEY_CAPTURED, texte)
    assert trouve is not None
    assert trouve.group(1) == attendu
    assert re.search(MONEY, texte) is not None
