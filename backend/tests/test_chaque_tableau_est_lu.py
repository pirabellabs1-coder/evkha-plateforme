"""Après chaque tableau de l'étude de marché, un paragraphe qui le lit.

Cliente, 29/10/2026, sur les deux études de marché de la boutique : « il y
avait beaucoup de tableaux, mais pas beaucoup de textes […] c'est bien aussi
qu'il y ait des paragraphes écrits ». Son cahier des charges : « Les
paragraphes doivent être rédigés ».

Mesuré au même extracteur le 31/10/2026 : Joalie, le modèle validé, 61,6 % de
mots en tableaux ; l'étude IA `e30fce14`, 61,7 %. Le moteur reproduisait le
modèle, et le validateur de conformité plafonnait la prose au volume de
Joalie : une consigne « écris plus » aurait été refusée. Et 18 % de nos
cellules faisaient douze mots ou plus, portant 52 % des mots de tableau.

Le modèle est ajusté AU CHARGEMENT, seule source du plan envoyé et du
validateur (règle 5). Ces tests échouent sur le code d'avant.
"""
from __future__ import annotations

import json
from typing import Any

from generation.chapitres.schema import Tableau
from generation.modele.chargement import (
    CELLULES_COURTES,
    CHEMIN_MODELE,
    LECTURE_DE_TABLEAU_SIGNES,
    chapitre_du_modele,
    dosage_attendu,
)
from generation.modele.consigne import plan_du_chapitre


def _brut(numero: int) -> dict[str, Any]:
    """Le chapitre tel que MESURÉ sur Joalie, sans l'ajustement."""
    modele = json.loads(CHEMIN_MODELE.read_text(encoding="utf-8"))
    attendu = f"CHAPITRE {numero:02d}"
    return next(c for c in modele["chapitres"] if c.get("numero") == attendu)


def _tableaux_sans_lecture(chapitre: dict[str, Any]) -> int:
    blocs = chapitre.get("blocs") or []
    return sum(
        1
        for rang, bloc in enumerate(blocs)
        if bloc.get("type") == "tableau"
        and (rang + 1 >= len(blocs) or blocs[rang + 1].get("type") != "paragraphe")
    )


def test_chaque_tableau_est_suivi_d_un_paragraphe_dans_tout_le_modele() -> None:
    """LE test : plus aucun tableau seul, sur les vingt et un chapitres."""
    for numero in range(1, 22):
        chapitre = chapitre_du_modele(numero)
        if chapitre is None:
            continue
        assert _tableaux_sans_lecture(chapitre) == 0, numero


def test_le_chapitre_4_recoit_ses_deux_paragraphes_de_lecture() -> None:
    """Le chapitre 4 de Joalie ouvre et ferme sur un tableau seul."""
    assert _tableaux_sans_lecture(_brut(4)) == 2

    ajuste = dosage_attendu(chapitre_du_modele(4) or {})
    brut = dosage_attendu(_brut(4))

    assert ajuste.paragraphes == brut.paragraphes + 2
    assert ajuste.tableaux == brut.tableaux, "aucun tableau ajouté ni retiré"
    assert ajuste.signes == brut.signes + 2 * LECTURE_DE_TABLEAU_SIGNES


def test_le_validateur_et_le_plan_lisent_le_meme_dosage() -> None:
    """Le plan envoyé demande ce que le validateur attend (règle 5)."""
    plan = plan_du_chapitre(4)

    assert plan.count("`paragraphe`") == dosage_attendu(chapitre_du_modele(4) or {}).paragraphes
    assert "Lecture du tableau qui précède" in plan


def test_chaque_tableau_demande_des_cellules_courtes() -> None:
    plan = plan_du_chapitre(4)

    assert plan.count("Cellules COURTES") == plan.count("`tableau`")
    assert CELLULES_COURTES in plan


def test_un_tableau_deja_lu_ne_recoit_pas_de_second_paragraphe() -> None:
    """CONTRE-ÉPREUVE : le modèle lisait déjà certains tableaux ; on n'en double
    pas la lecture."""
    for numero in range(1, 22):
        brut = chapitre_du_modele(numero)
        if brut is None:
            continue
        mesure = _brut(numero)
        ajoutes = dosage_attendu(brut).paragraphes - dosage_attendu(mesure).paragraphes
        assert ajoutes == _tableaux_sans_lecture(mesure), numero


def test_le_fichier_mesure_reste_intact() -> None:
    """Le modèle mesuré sur Joalie ne change pas : l'ajustement est au chargement."""
    assert _tableaux_sans_lecture(_brut(4)) == 2


def test_le_schema_dit_ce_qu_une_cellule_porte() -> None:
    """La seule consigne que le modèle lise sur le champ `lignes`."""
    description = Tableau.model_json_schema()["properties"]["lignes"]["description"]

    assert "douze mots au plus" in description
    assert "paragraphe rédigé qui suit le tableau" in description


def test_le_controle_de_densite_ne_punit_pas_le_document_qui_obeit() -> None:
    """Moins de mots en tableaux et des paragraphes de lecture : le contrôle
    ne doit pas les faire réécrire à nos frais."""
    from catalog.models import DeliverableType
    from generation.verification.controles import seuils_de_densite

    seuils = seuils_de_densite(DeliverableType.MARKET_STUDY)

    assert seuils.part_tableaux_min <= 0.25
    # La médiane porte sur TOUS les paragraphes du document (20 mots sur
    # `e30fce14`, plafond d'alors 25) : une cinquantaine de paragraphes de
    # lecture d'une cinquantaine de mots la font monter, elle ne doit pas
    # déclencher de réécriture.
    from generation.verification.controles import MEDIANE_PARAGRAPHE_MAX

    assert seuils.mediane_paragraphe_max > MEDIANE_PARAGRAPHE_MAX
