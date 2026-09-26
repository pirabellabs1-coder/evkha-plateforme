"""« CHF 6'000'000 » est un montant, et le Bénin paie en XOF même écrit « Cotonou, Bénin ».

## Le dossier réel

Business plan `6c794b18` (26/09/2026, société suisse) : trois motifs
`reference_client_illisible` — investissement, apport, CA prévisionnel —
« le brief client ne donne aucun montant exploitable », avec sous les yeux
« Seed de CHF 6'000'000 », « CHF 325'000 en 2027, CHF 7'604'750 en 2028 ».
Le parseur canonique ne connaissait ni CHF, ni l'apostrophe comme séparateur
de milliers, ni la devise placée AVANT le nombre — pendant que
`_COUNTRY_CURRENCY` savait très bien que la Suisse paie en CHF. Deux modules
en désaccord sur la même vérité (règle 5), et un motif faux (règle 2) sur un
dossier que la cliente jugeait « vraiment solide ».

## La devise du pays

`_COUNTRY_CURRENCY.get(pays)` exigeait l'égalité stricte : « Cotonou, Bénin »
ou « Côte d’Ivoire » (apostrophe typographique) ne verrouillaient aucune
devise, et les montants en € d'un dossier ouest-africain n'étaient jamais
confrontés. On cherche désormais le pays comme mot entier, le plus long
d'abord — la RDC (CDF) doit gagner sur « congo » (XAF).
"""
from __future__ import annotations

import re

import pytest

from core.numbers import MONEY, MONEY_CAPTURED, amounts_in, parse_number
from generation.checks_evangeline import detecter_fourchettes
from generation.coherence import devise_du_pays
from intake.financials import extract_financials_from_text


def test_l_apostrophe_separe_les_milliers() -> None:
    assert parse_number("6'000'000") == 6_000_000.0
    assert parse_number("7’604’750") == 7_604_750.0
    assert parse_number("325'000,50") == 325_000.5


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("CHF 6'000'000", id="devise-avant-apostrophes"),
        pytest.param("6'000'000 CHF", id="devise-apres-apostrophes"),
        pytest.param("10 000 francs suisses", id="en-toutes-lettres"),
        pytest.param("€ 320 000", id="euro-avant"),
        pytest.param("50 000 MAD", id="dirham"),
    ],
)
def test_money_reconnait_le_montant(texte: str) -> None:
    assert re.search(MONEY, texte, re.IGNORECASE) is not None, texte


def test_money_capture_garde_l_ordre_francais() -> None:
    trouve = re.search(MONEY_CAPTURED, "un CA de 6'000'000 CHF", re.IGNORECASE)
    assert trouve is not None
    assert trouve.group(1) == "6'000'000"
    assert trouve.group(2) == "CHF"


def test_la_trajectoire_suisse_se_lit_en_base() -> None:
    """`amounts_in` ramasse aussi les années (c'est son contrat) : on vérifie
    que les trois montants y sont, lus en base malgré les apostrophes."""
    lus = amounts_in("CHF 325'000 en 2027, CHF 7'604'750 en 2028, CHF 18'893'227 en 2029")
    assert {325_000.0, 7_604_750.0, 18_893_227.0} <= set(lus)


def test_le_brief_suisse_verrouille_son_investissement() -> None:
    lu = extract_financials_from_text("Investissement total : CHF 6'000'000")
    assert lu["INVESTISSEMENT_TOTAL"] == "CHF 6'000'000"
    lu = extract_financials_from_text("Investissement total : 6'000'000 CHF")
    assert lu["INVESTISSEMENT_TOTAL"] == "6'000'000 CHF"


def test_l_apostrophe_d_un_mot_n_est_pas_un_separateur() -> None:
    """Contre-épreuve : « d'euros », « l'an 1 » gardent leur apostrophe à eux."""
    assert 1_200_000.0 in amounts_in("1,2 million d'euros sur l'an 1")
    assert parse_number("d'euros") is None


def test_une_fourchette_en_francs_suisses_est_vue() -> None:
    trouvees = detecter_fourchettes(3, "un loyer de 5'000 CHF à 8'000 CHF", "business_strategy")
    assert len(trouvees) == 1


@pytest.mark.parametrize(
    ("pays", "devise"),
    [
        pytest.param("Cotonou, Bénin", "XOF", id="ville-virgule-pays"),
        pytest.param("République du Sénégal", "XOF", id="forme-longue"),
        pytest.param("Côte d’Ivoire", "XOF", id="apostrophe-typographique"),
        pytest.param("République démocratique du Congo", "CDF", id="rdc-avant-congo"),
        pytest.param("Congo-Brazzaville", "XAF", id="congo-brazzaville"),
        pytest.param("Suisse", "CHF", id="suisse"),
        pytest.param("France métropolitaine", "EUR", id="france"),
        pytest.param("Guinée équatoriale", "XAF", id="guinee-equatoriale-pas-gnf"),
        pytest.param("Atlantide", None, id="inconnu"),
    ],
)
def test_la_devise_se_lit_dans_le_champ_pays(pays: str, devise: str | None) -> None:
    assert devise_du_pays(pays) == devise
