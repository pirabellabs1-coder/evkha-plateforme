"""« Europe » n'est pas un montant en euros.

Mesure sur le livrable reel `4b827759` du 05/08/2026, dans les reserves de la
passe de verification — devenues lisibles le matin meme :

    « 1.2 Euro » n'a pas d'equivalent dans le socle ni dans le brief client.
    extrait : « 1.2 Europe et France : une base culturelle et productive… »

Le sous-titre « 1.2 Europe et France » etait lu comme le montant « 1,2 euro ».
L'alternation des devises reconnaissait `euros?` sans exiger de fin de mot, si
bien qu'elle mordait au debut d'« Europe ».

Un motif d'echec introuvable dans le document par le lecteur est PIRE qu'absent
(regle 2) : il envoie corriger un chiffre qui n'existe pas. Et ce motif-la
touchait tout ce qui lit des montants — la passe de verification, le gate, le
socle — puisque tous partagent cette alternation.
"""
from __future__ import annotations

import pytest

from core.numbers import AMOUNT_WITH_UNIT_RE, amounts_in
from generation.verification.lecture import mesures_dans


@pytest.mark.parametrize(
    "texte",
    [
        "1.2 Europe et France : une base culturelle cohérente",
        "2 Europeens sur trois declarent acheter en ligne",
        "3 Eurostat publie ces series",
    ],
)
def test_un_mot_qui_commence_par_une_devise_n_est_pas_un_montant(texte: str) -> None:
    """Ce test echoue sur le code d'avant : « 1.2 Euro » y etait un montant."""
    assert mesures_dans(texte) == []


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("le panier moyen atteint 164 EUR", 164.0),
        ("un investissement de 1,25 M€", 1_250_000.0),
        ("le marche pese 4,2 Md€", 4_200_000_000.0),
        ("une enveloppe de 250 000 euros", 250_000.0),
        ("un apport de 90 kEUR", 90_000.0),
    ],
)
def test_un_vrai_montant_reste_lu(texte: str, attendu: float) -> None:
    """Contre-epreuve : la fin de mot ne doit rien casser de ce qui marchait.

    Une unite suivie d'une ponctuation, d'un espace ou d'une fin de ligne reste
    une unite — c'est le cas de tous les montants d'un livrable.
    """
    mesures = mesures_dans(texte)
    assert mesures, texte
    assert mesures[0].valeur == pytest.approx(attendu)


def test_une_unite_suivie_d_une_ponctuation_reste_lue() -> None:
    """« 250 EUR. » en fin de phrase, ou « (90 kEUR) » entre parentheses."""
    for texte in ("le total atteint 250 EUR.", "un apport (90 kEUR) suffit",
                  "cout : 4,2 M€, hors taxes"):
        assert mesures_dans(texte), texte


def test_les_millions_en_toutes_lettres_gardent_leur_frontiere() -> None:
    """« 420 millions d'euros » se lit ; « 3 millionaires » ne se lit pas.

    Meme classe de defaut que la devise, sur l'autre liste d'unites : la
    corriger d'un cote seulement l'aurait laissee vivre de l'autre (regle 4).
    """
    assert amounts_in("un marche de 420 millions d'euros")
    assert AMOUNT_WITH_UNIT_RE.search("420 millions")
    trouve = AMOUNT_WITH_UNIT_RE.search("3 millionaires du secteur")
    # Le nombre est bien vu, mais SANS unite : ce n'est pas 3 millions.
    assert trouve is not None
    assert not trouve.group(2)
