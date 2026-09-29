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

Et sa contre-épreuve, apprise le jour même (revue du 29/09/2026) : le premier
correctif coupait au premier mot à majuscule ou au premier nom de poste après
une valeur, et amputait sept formes courantes d'une trajectoire en prose
(« 45 000 € hors taxes en 2027, 60 000 € … »). Un mot qui QUALIFIE une valeur
n'ouvre pas une ligne.
"""
from __future__ import annotations

import pytest

from core.numbers import amounts_in
from intake.financials import (
    enrich_variables_from_free_text,
    extract_financials_from_text,
    raffiner_champs_financiers,
)

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


# ── Revue du 29/09/2026 : un qualificatif n'ouvre pas une ligne ─────────────
#
# Mesurées avant le premier correctif (5d1161c) et après : chacune de ces
# formes perdait toutes ses valeurs sauf la première — la dernière, TOUTES.

QUALIFICATIFS = [
    pytest.param(
        "Chiffre d'affaires prévisionnel : 45 000 € hors taxes en 2027, "
        "60 000 € hors taxes en 2028, 80 000 € hors taxes en 2029",
        "CA_PREVISIONNEL", [45_000.0, 60_000.0, 80_000.0], id="hors-taxes",
    ),
    pytest.param(
        "CA prévisionnel : 45 000 € hors TVA en 2027, 60 000 € hors TVA en 2028",
        "CA_PREVISIONNEL", [45_000.0, 60_000.0], id="hors-tva",
    ),
    pytest.param(
        "Résultat net : 12 000 € avant impôts en 2027, 18 000 € avant impôts en 2028",
        "RESULTAT_NET_PREVISIONNEL", [12_000.0, 18_000.0], id="avant-impots",
    ),
    pytest.param(
        "Résultat net : 5 000 € en année 1 (après rémunération du dirigeant), "
        "15 000 € en année 2",
        "RESULTAT_NET_PREVISIONNEL", [5_000.0, 15_000.0], id="apres-remuneration",
    ),
    pytest.param(
        # Le formulaire du business plan demande lui-même les majuscules.
        "RÉSULTAT NET PRÉVISIONNEL : 12 000 € LA PREMIÈRE ANNÉE, 25 000 € LA DEUXIÈME ANNÉE",
        "RESULTAT_NET_PREVISIONNEL", [12_000.0, 25_000.0], id="tout-en-majuscules",
    ),
    pytest.param(
        "CA : 45 000 € en 2027 (Lancement), 60 000 € en 2028 (Développement)",
        "CA_PREVISIONNEL", [45_000.0, 60_000.0], id="phase-entre-parentheses",
    ),
    pytest.param(
        # Micro-crèche : la CAF finance le chiffre d'affaires.
        "Chiffre d'affaires (financement CAF + familles) : 150 000 € en An1, "
        "180 000 € en An2",
        "CA_PREVISIONNEL", [150_000.0, 180_000.0], id="caf-avant-la-valeur",
    ),
]


@pytest.mark.parametrize(("texte", "cle", "attendu"), QUALIFICATIFS)
def test_un_qualificatif_n_ouvre_pas_une_ligne(
    texte: str, cle: str, attendu: list[float]
) -> None:
    assert amounts_in(extract_financials_from_text(texte).get(cle, "")) == attendu


def test_le_champ_structure_n_est_pas_ampute_a_la_relecture() -> None:
    """`raffiner_champs_financiers` remplaçait le champ par la lecture amputée."""
    variables: dict[str, object] = {
        "CA_PREVISIONNEL": (
            "Chiffre d'affaires prévisionnel : 45 000 € hors taxes en 2027, "
            "60 000 € hors taxes en 2028, 80 000 € hors taxes en 2029"
        ),
    }

    raffiner_champs_financiers(variables)

    assert amounts_in(str(variables["CA_PREVISIONNEL"])) == [45_000.0, 60_000.0, 80_000.0]


def test_la_caf_ferme_encore_apres_une_valeur() -> None:
    """Contre-épreuve : la CAF qui SUIT les valeurs reste une autre ligne."""
    lu = extract_financials_from_text("Résultat net 50 € 8 040 € CAF 662 € 8 652 €")

    assert amounts_in(lu["RESULTAT_NET_PREVISIONNEL"]) == [50.0, 8_040.0]


def test_une_perte_de_premiere_annee_garde_son_signe() -> None:
    """« -3 000 € » se verrouillait « 3 000 € » : le gate refusait la vraie perte."""
    lu = extract_financials_from_text(
        "Résultat net : -3 000 € en 2027, 8 000 € en 2028, 15 000 € en 2029"
    )

    assert lu["RESULTAT_NET_PREVISIONNEL"] == "-3 000 € / 8 000 € / 15 000 €"


def test_le_tiret_du_formulaire_n_est_pas_un_signe() -> None:
    """Contre-épreuve : « 145 000 €- EBE … » garde son montant positif."""
    lu = extract_financials_from_text(
        "Résultat net prévisionnel 145 000 €- EBE prévisionnel 310 000 €"
    )

    assert lu["RESULTAT_NET_PREVISIONNEL"] == "145 000 €"


# ── Revue du 29/09/2026 : chaque exercice nommé garde sa place ──────────────


def test_deux_exercices_de_meme_valeur_en_puces_restent_deux() -> None:
    """AVANT : « An3 : 8 040 € » disparaissait, 8 040 € étant déjà l'An2."""
    lu = extract_financials_from_text(
        "- Résultat net An1 : 50 €\n"
        "- Résultat net An2 : 8 040 €\n"
        "- Résultat net An3 : 8 040 €"
    )

    assert amounts_in(lu["RESULTAT_NET_PREVISIONNEL"]) == [50.0, 8_040.0, 8_040.0]


def test_les_puces_recopiees_dans_un_autre_champ_ne_comptent_pas_double() -> None:
    puces = "- Résultat net An1 : 50 €\n- Résultat net An2 : 8 040 €\n- Résultat net An3 : 8 040 €"
    variables: dict[str, object] = {"PROJET": puces, "TABLEAUX_FINANCIERS": puces}

    ajoutees = enrich_variables_from_free_text(variables)

    assert amounts_in(ajoutees["RESULTAT_NET_PREVISIONNEL"]) == [50.0, 8_040.0, 8_040.0]


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param(
            "Le projet vise un CA prévisionnel de 250 272 € la première année.\n"
            "Chiffre d'affaires 250 272 € 296 000 € 318 400 €",
            id="resume-puis-tableau",
        ),
        pytest.param(
            "Chiffre d'affaires 250 272 € 296 000 € 318 400 €\n"
            "Le projet vise un CA prévisionnel de 250 272 € la première année.",
            id="tableau-puis-resume",
        ),
    ],
)
def test_le_resume_du_projet_n_ajoute_pas_un_exercice(texte: str) -> None:
    """Contre-épreuve : trois exercices, pas quatre.

    Un quatrième exercice inventé (250 272 € répété) ferait juger « CA 2030 »
    contre une valeur que la cliente n'a jamais donnée.
    """
    lu = extract_financials_from_text(texte)

    assert amounts_in(lu["CA_PREVISIONNEL"]) == [250_272.0, 296_000.0, 318_400.0]
