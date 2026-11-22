"""Le business plan validé par la cliente est à 93 % de prose. Le nôtre était à 31 %.

## La mesure qui a tranché

La cliente a transmis le 28/10/2026 « FINDRAX — Business Plan v3, octobre
2026 » : 59 pages, bâti sur une étude de marché et une étude de la concurrence
« déjà validées », avec un prévisionnel en version 8. Un document VALIDÉ et
écrit hors de notre chaîne — la règle 9 interdit de mesurer un modèle de forme
sur ce que notre moteur produit, puisqu'il se donnerait raison tout seul.

Passé par le même extracteur que nos livrables :

    référence Findrax v3 : prose 93 % | tableaux  6,9 % |  24 tableaux | longs 41 %
    produit par EVKHA    : prose 31 % | tableaux 68 %   | 157 tableaux | longs 19 %

## Le défaut que la mesure a révélé

Son cahier des charges semblait se contredire — « reprend la même charte
rédactionnelle » que l'étude de marché, ET « patte narrative EVKHA : écrit
comme si le porteur de projet en était lui-même l'auteur ». J'avais laissé le
dosage en suspens pour cette raison. La mesure tranche : c'est la patte
narrative, et de loin.

Pire : **confronté aux seuils d'alors — 40 % de tableaux minimum, 25 % de
paragraphes longs maximum — son propre business plan validé ÉCHOUAIT sur deux
critères sur trois.** Un contrôle qui refuse le document de référence est la
règle 2 dans sa forme la plus pure.

Et la consigne allait dans le même sens que le contrôle : « l'information vit
dans les TABLEAUX ». Le moteur était configuré pour produire l'inverse de ce
qu'elle valide.

Ces tests échouent sur le code d'avant : le business plan recevait le dosage
par défaut et les seuils de l'étude de marché.
"""
from __future__ import annotations

from pathlib import Path

from catalog.models import DeliverableType
from generation.chapitres.runner import _bloc_forme
from generation.verification import controles
from generation.verification.controles import seuils_de_densite
from generation.verification.lecture import DocumentLu

BP = DeliverableType.BUSINESS_PLAN

#: Mesuré sur « FINDRAX — Business Plan v3, octobre 2026 » par
#: `relecture.document_du_pdf`, le 28/10/2026.
FINDRAX_PROSE = 128_805
FINDRAX_CELLULES = 9_507
FINDRAX_PART_TABLEAUX = FINDRAX_CELLULES / (FINDRAX_PROSE + FINDRAX_CELLULES)
FINDRAX_MEDIANE_MOTS = 17
FINDRAX_PART_LONGS = 0.41


def test_le_business_plan_validee_passe_nos_seuils() -> None:
    """La contre-épreuve qui compte : notre contrôle ne refuse plus SA référence.

    C'est le test qui échoue sur le code d'avant, et il échoue deux fois : la
    part de tableaux (6,9 % contre 40 % exigés) et la part de paragraphes longs
    (41 % contre 25 % tolérés).
    """
    seuils = seuils_de_densite(BP)

    assert FINDRAX_PART_TABLEAUX >= seuils.part_tableaux_min, (
        f"son business plan validé porte {FINDRAX_PART_TABLEAUX:.1%} de tableaux, "
        f"et le contrôle en exige {seuils.part_tableaux_min:.0%}"
    )
    assert FINDRAX_PART_LONGS <= seuils.part_paragraphes_longs_max, (
        f"{FINDRAX_PART_LONGS:.0%} de ses paragraphes dépassent 25 mots, et le "
        f"contrôle en tolère {seuils.part_paragraphes_longs_max:.0%}"
    )
    assert FINDRAX_MEDIANE_MOTS <= seuils.mediane_paragraphe_max


#: Remesuré le 22/11/2026 par `lire_livrable` sur « FINDRAX BP FINAL OK.docx »
#: et sur les sept business plans livrés du 14 au 21/11. Sa médiane de 17
#: comptait ses titres : sa prose seule est à 69 mots, la nôtre à 31-40.
FINDRAX_MEDIANE_PROSE = 69
NOS_MEDIANES_TOUTES_LIGNES = (28, 28, 32, 28, 28, 28, 27)


def _document(longueurs: list[int], tableau_mots: int = 2_000) -> DocumentLu:
    paragraphes = [" ".join(["mot"] * n) + "." for n in longueurs]
    return DocumentLu(
        chemin=Path("bp.docx"),
        paragraphes=paragraphes,
        cellules=[" ".join(["case"] * tableau_mots)],
        chapitre_du_paragraphe=[1 + i % 3 for i in range(len(paragraphes))],
    )


def test_nos_business_plans_ne_sont_plus_refuses_pour_densite() -> None:
    """Échoue sur le code d'avant : plafond 25, les sept BP étaient refusés et
    trois chapitres par dossier partaient en réécriture payante."""
    assert all(m <= seuils_de_densite(BP).mediane_paragraphe_max
               for m in NOS_MEDIANES_TOUTES_LIGNES)
    # Une forme courante : des titres courts, une prose d'une ou deux phrases.
    document = _document([6, 9, 28, 31, 34, 27, 40, 8, 30, 33, 29, 45] * 8)
    assert controles.controler_densite(document, str(BP)) == []


def test_un_vrai_mur_de_texte_reste_signale() -> None:
    """Contre-épreuve : des paragraphes tous au-delà de soixante-dix mots."""
    document = _document([75, 80, 90, 72, 85] * 10)
    anomalies = controles.controler_densite(document, str(BP))
    assert any("médian" in a.detail for a in anomalies)
    par_chapitre = [a for a in anomalies if a.chapitre]
    assert par_chapitre
    # Ce texte part au modèle qui réécrit : plus la forme de l'étude de marché.
    assert not any("prose courte" in a.detail for a in par_chapitre)


def test_la_consigne_de_longueur_ne_renvoie_pas_au_tableau() -> None:
    """Échoue sur le code d'avant : la phrase de l'étude de marché partait au BP."""
    forme = _bloc_forme(BP)
    assert "Un bloc `paragraphe` tient en 60 mots au plus" in forme
    assert "il annonce ou commente un tableau" not in forme
    assert "il annonce ou commente un tableau" in _bloc_forme(DeliverableType.MARKET_STUDY)


def test_la_consigne_de_la_strategie_ne_se_contredit_pas() -> None:
    """Contre-épreuve : la stratégie reçoit le dosage tableaux par défaut ; la
    phrase « il ne passe pas dans un tableau » l'aurait contredit."""
    forme = _bloc_forme(DeliverableType.BUSINESS_STRATEGY)
    assert "vit dans les TABLEAUX" in forme
    assert "il ne passe pas dans un tableau" not in forme


def test_une_prose_developpee_sans_titres_passe() -> None:
    """Le haut de la plage visée : paragraphes de 50 à 58 mots, aucun titre."""
    document = _document([50, 54, 58, 52, 56, 55] * 10)
    assert controles.controler_densite(document, str(BP)) == []


def test_la_prose_validee_n_est_pas_un_mur_de_texte() -> None:
    """Sa prose (69 mots) dépasse ce seuil : il ne vaut que parce que la médiane
    compte aussi les titres. Le baisser sous 60 referait l'erreur du 18/11."""
    assert 60 <= seuils_de_densite(BP).mediane_paragraphe_max < FINDRAX_MEDIANE_PROSE


def test_un_business_plan_sans_aucun_tableau_echoue_toujours() -> None:
    """Contre-épreuve : un prévisionnel et un plan de financement SONT des tableaux.

    Abaisser le plancher ne doit pas autoriser un mur de texte.
    """
    assert seuils_de_densite(BP).part_tableaux_min > 0


def test_la_consigne_demande_un_document_raconte() -> None:
    forme = _bloc_forme(BP)

    assert "se RACONTE" in forme
    assert "L'information vit dans les TABLEAUX" not in forme
    # Les tableaux financiers restent nommés : ils ne doivent pas disparaître.
    assert "prévisionnel" in forme
    assert "plan de financement" in forme


def test_les_autres_livrables_ne_bougent_pas() -> None:
    """Contre-épreuve : chaque livrable garde le dosage de SA mesure.

    L'étude de marché porte la mesure d'origine (52 % de mots en tableaux sur
    `joalie_2026.docx`) ; l'étude de la concurrence celle de sa référence
    réécrite à la main (18 %). Aucune ne doit hériter de celle du business plan.
    """
    marche = _bloc_forme(DeliverableType.MARKET_STUDY)
    assert "L'information vit dans les TABLEAUX" in marche
    assert "se RACONTE" not in marche

    concurrence = _bloc_forme(DeliverableType.COMPETITOR_STUDY)
    assert "L'analyse est RÉDIGÉE" in concurrence
    assert "se RACONTE" not in concurrence

    # Et les seuils de l'étude de marché sont les SIENS — ni ceux du business
    # plan, ni ceux de la concurrence. Ils ont bougé le 31/10/2026, par une
    # décision propre à l'étude de marché (« beaucoup de tableaux, pas
    # beaucoup de textes ») : voir `PART_TABLEAUX_MIN_ETUDE_DE_MARCHE`.
    from generation.verification.controles import PART_TABLEAUX_MIN_ETUDE_DE_MARCHE

    assert (
        seuils_de_densite(DeliverableType.MARKET_STUDY).part_tableaux_min
        == PART_TABLEAUX_MIN_ETUDE_DE_MARCHE
    )


def test_chaque_livrable_a_desormais_ses_propres_seuils() -> None:
    """Trois mesures, trois jeux de seuils — plus un seul défaut partagé."""
    marche = seuils_de_densite(DeliverableType.MARKET_STUDY)
    concurrence = seuils_de_densite(DeliverableType.COMPETITOR_STUDY)
    plan = seuils_de_densite(BP)

    planchers = {
        marche.part_tableaux_min,
        concurrence.part_tableaux_min,
        plan.part_tableaux_min,
    }
    assert len(planchers) == 3, (
        "deux livrables partagent un plancher de tableaux : c'est ainsi que la "
        "mesure de l'étude de marché s'est retrouvée appliquée aux autres"
    )
