"""« un investissement de 1,2 million d'euros » est un montant, et il se lit.

Relevé le 26/09/2026 par appel direct sur l'extracteur du brief : cette forme
— la plus naturelle en prose — ne rendait RIEN. `MONEY` exigeait la devise
collée au nombre ; « million » n'en est pas une, et « d'euros » venait trop
tard. Deux conséquences, mesurées :

- l'intake ne verrouillait aucun fait client pour ce champ ;
- si le fait existait par une autre voie, le gate le déclarait « illisible —
  réponse en texte libre » et réclamait le chiffre au client, qui l'avait
  écrit (règle 2 : un motif introuvable dans le texte est pire qu'absent).

La contre-épreuve tient la ligne : « 3 millions de clients » n'est pas un
montant, et ce qui se lisait avant se lit toujours pareil.
"""
from __future__ import annotations

import re

import pytest

from core.numbers import MONEY, MONEY_CAPTURED, amounts_in, parse_amount
from intake.financials import extract_financials_from_text


@pytest.mark.parametrize(
    ("texte", "nombre", "unite", "base"),
    [
        pytest.param("1,2 million d'euros", "1,2", "million", 1_200_000.0, id="million-d-euros"),
        pytest.param("420 millions d'euros", "420", "millions", 420_000_000.0, id="millions"),
        pytest.param(
            "1,5 milliard d’euros", "1,5", "milliard", 1_500_000_000.0, id="apostrophe-typo",
        ),
        pytest.param("2 millions €", "2", "millions", 2_000_000.0, id="millions-symbole"),
        pytest.param("1,25 M€", "1,25", "M€", 1_250_000.0, id="inchange-M-euro"),
        pytest.param("320 000 €", "320 000", "€", 320_000.0, id="inchange-euros"),
        pytest.param("50 000 FCFA", "50 000", "FCFA", 50_000.0, id="inchange-fcfa"),
    ],
)
def test_le_groupe_2_porte_l_echelle(texte: str, nombre: str, unite: str, base: float) -> None:
    trouve = re.search(MONEY_CAPTURED, texte, re.IGNORECASE)
    assert trouve is not None, texte
    assert trouve.group(1) == nombre
    assert trouve.group(2) == unite
    assert parse_amount(trouve.group(1), trouve.group(2)) == base
    assert re.search(MONEY, texte, re.IGNORECASE) is not None


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("3 millions de clients", id="magnitude-sans-devise"),
        pytest.param("420 millions d'habitants", id="magnitude-puis-autre-chose"),
        pytest.param("1,2 million", id="magnitude-nue"),
    ],
)
def test_une_magnitude_sans_devise_n_est_pas_un_montant(texte: str) -> None:
    assert re.search(MONEY, texte, re.IGNORECASE) is None, texte
    assert re.search(MONEY_CAPTURED, texte, re.IGNORECASE) is None, texte


def test_le_brief_en_prose_verrouille_son_investissement() -> None:
    lu = extract_financials_from_text(
        "Investissement total : 1,2 million d'euros, dont un apport de 250 000 €."
    )
    assert lu["INVESTISSEMENT_TOTAL"] == "1,2 million d'euros"
    assert lu["APPORT"] == "250 000 €"
    assert amounts_in(lu["INVESTISSEMENT_TOTAL"]) == [1_200_000.0]
