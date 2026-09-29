"""Une ligne d'un tableau financier collé sur une ligne n'avale pas la suivante.

29/09/2026, business plan `cb59cede` (ÉCLORE). La réponse « Tableaux
financiers » de la cliente est son compte de résultat, aplati sur UNE ligne :

    … EBE 782 € 8 772 € 23 956 € 23 956 € 23 956 € Dotations aux
    amortissements 612 € 612 € 612 € 612 € 612 € Résultat net comptable 50 €
    8 040 € 23 224 € 23 224 € 23 224 € Capacité d'autofinancement 662 €
    8 652 € 23 836 € 23 836 € 23 836 € …

`_LIBELLES_FRONTIERE` ne connaissait ni la CAF ni les dotations. Le fait
CLIENT `resultat_net_previsionnel` est devenu « 50 € / 8 040 € / 23 224 € /
662 € / 8 652 € / 23 836 € » — résultat net ET capacité d'autofinancement —,
imposé à chaque chapitre comme source unique. Le document a imprimé le
résultat net 2029 à 23 223,86 € sur seize pages et à 23 835,86 € (la CAF) sur
dix, et le gate a jugé les deux conformes.

La classe visée (règle 4) : une trajectoire ne prend JAMAIS les valeurs d'une
autre ligne du même tableau, quel que soit le libellé de cette ligne — pas
seulement la CAF.
"""
from __future__ import annotations

import pytest

from core.numbers import amounts_in
from intake.financials import enrich_variables_from_free_text, extract_financials_from_text

#: La forme de la réponse réelle : les lignes du compte de résultat bout à bout.
#: Les montants de la CAF, des dotations et de l'EBE sont ceux du dossier.
TABLEAU_APLATI = (
    "Compte de résultat prévisionnel 2027 2028 2029 2030 2031 "
    "Chiffre d'affaires 19 674 € 54 276 € 90 000 € 90 000 € 90 000 € "
    "Charges externes 10 000 € 20 000 € 30 000 € 30 000 € 30 000 € "
    "EBE 782 € 8 772 € 23 956 € 23 956 € 23 956 € "
    "Dotations aux amortissements 612 € 612 € 612 € 612 € 612 € "
    "Résultat net comptable 50 € 8 040 € 23 224 € 23 224 € 23 224 € "
    "Capacité d'autofinancement 662 € 8 652 € 23 836 € 23 836 € 23 836 € "
    "Trésorerie fin d'exercice 1 000 € 2 000 € 3 000 € 4 000 € 5 000 €"
)

RESULTAT_NET = [50.0, 8_040.0, 23_224.0, 23_224.0, 23_224.0]
CAF = {662.0, 8_652.0, 23_836.0}


def test_le_resultat_net_est_exactement_sa_ligne() -> None:
    """AVANT : « 50 € / 8 040 € / 23 224 € / 662 € / 8 652 € / 23 836 € / … »."""
    lu = extract_financials_from_text(TABLEAU_APLATI)

    assert amounts_in(lu["RESULTAT_NET_PREVISIONNEL"]) == RESULTAT_NET
    assert not CAF & set(amounts_in(lu["RESULTAT_NET_PREVISIONNEL"]))


def test_l_ebe_n_avale_pas_les_dotations() -> None:
    """AVANT : l'EBE finissait par « 612 € », la dotation de la ligne suivante."""
    lu = extract_financials_from_text(TABLEAU_APLATI)

    assert amounts_in(lu["EBE_PREVISIONNEL"]) == [782.0, 8_772.0, 23_956.0, 23_956.0, 23_956.0]


def test_le_ca_n_avale_pas_les_charges() -> None:
    """Un libellé qu'aucune liste ne connaît (« Charges externes ») ferme aussi.

    C'est la CLASSE : ajouter « CAF » à `_LIBELLES_FRONTIERE` aurait réparé le
    résultat net, et laissé le chiffre d'affaires avaler les charges.
    """
    lu = extract_financials_from_text(TABLEAU_APLATI)

    assert amounts_in(lu["CA_PREVISIONNEL"]) == [19_674.0, 54_276.0, 90_000.0, 90_000.0, 90_000.0]


def test_un_tableau_colle_en_minuscules_se_lit_aussi() -> None:
    """Sans majuscule pour annoncer la ligne suivante, le nom du poste suffit."""
    lu = extract_financials_from_text(TABLEAU_APLATI.lower())

    assert amounts_in(lu["RESULTAT_NET_PREVISIONNEL"]) == RESULTAT_NET
    assert amounts_in(lu["EBE_PREVISIONNEL"]) == [782.0, 8_772.0, 23_956.0, 23_956.0, 23_956.0]


def test_la_ligne_suivante_inconnue_ferme_le_segment() -> None:
    """Un libellé qu'aucune liste ne nomme : « Prélèvements de l'exploitant »."""
    lu = extract_financials_from_text(
        "Résultat net 50 € 8 040 € 23 224 € Prélèvements de l'exploitant 12 000 € 12 000 €"
    )

    assert amounts_in(lu["RESULTAT_NET_PREVISIONNEL"]) == [50.0, 8_040.0, 23_224.0]


def test_la_meme_ligne_citee_dans_deux_champs_ne_compte_pas_double() -> None:
    """Le tableau collé dans « Tableaux financiers » et repris ailleurs."""
    variables: dict[str, object] = {
        "TABLEAUX_FINANCIERS": TABLEAU_APLATI,
        "ELEMENTS_A_RETENIR": "Résultat net comptable 50 € 8 040 € 23 224 € 23 224 € 23 224 €",
    }

    ajoutees = enrich_variables_from_free_text(variables)

    assert amounts_in(ajoutees["RESULTAT_NET_PREVISIONNEL"]) == RESULTAT_NET


# ── Contre-épreuve : la prose d'une trajectoire reste lue en entier ─────────


@pytest.mark.parametrize(
    ("texte", "cle", "attendu"),
    [
        pytest.param(
            "CA previsionnel : 250 272 € en An1, 296 000 € en An2, 318 400 € en An3.",
            "CA_PREVISIONNEL", [250_272.0, 296_000.0, 318_400.0], id="prose-en-an",
        ),
        pytest.param(
            "CA prévisionnel An1 : 250 272 €, An2 : 296 000 €, An3 : 318 400 €",
            "CA_PREVISIONNEL", [250_272.0, 296_000.0, 318_400.0], id="an-avant-montant",
        ),
        pytest.param(
            "Résultat net : 44 245 € la première année, puis 60 000 € la deuxième année",
            "RESULTAT_NET_PREVISIONNEL", [44_245.0, 60_000.0], id="premiere-puis-deuxieme",
        ),
        pytest.param(
            "Résultat net 50 € (Année 1), 8 040 € (Année 2), 23 224 € (Année 3)",
            "RESULTAT_NET_PREVISIONNEL", [50.0, 8_040.0, 23_224.0], id="annee-en-majuscule",
        ),
        pytest.param(
            "Chiffre d'affaires 250 000 € HT 300 000 € HT 350 000 € HT",
            "CA_PREVISIONNEL", [250_000.0, 300_000.0, 350_000.0], id="hors-taxes",
        ),
        pytest.param(
            "Résultat net après amortissements : 50 €",
            "RESULTAT_NET_PREVISIONNEL", [50.0], id="qualificatif-avant-la-valeur",
        ),
    ],
)
def test_une_trajectoire_ecrite_en_prose_reste_complete(
    texte: str, cle: str, attendu: list[float]
) -> None:
    assert amounts_in(extract_financials_from_text(texte)[cle]) == attendu


def test_une_autre_grandeur_citee_apres_la_valeur_n_est_pas_une_annee() -> None:
    """« … avant remboursement de l'emprunt de 920 000 € » : pas un résultat net."""
    lu = extract_financials_from_text(
        "Résultat net : 44 245 € en An1 avant remboursement de l'emprunt de 920 000 €"
    )

    assert amounts_in(lu["RESULTAT_NET_PREVISIONNEL"]) == [44_245.0]
