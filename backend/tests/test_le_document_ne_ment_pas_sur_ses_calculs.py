"""Quand le document POSE une opération, le code la refait.

Demande de la cliente, 13/08/2026 : « vérifier automatiquement tous les calculs
simples : pourcentages, ratios, taux de conversion, marges, évolutions, parts
de marché, additions, moyennes et projections ».

Le déclencheur est mesuré : « 102 / 50 000 000 = 0,000204 % », écrit DOUZE fois
dans un business plan remis à un financeur. L'unité fautive — « 50 000
milliers » — est réparée à la source ; ce contrôle attrape la classe entière,
un résultat qui ne découle pas de ses propres termes, quelle qu'en soit la
cause.
"""
from __future__ import annotations

import pytest

from generation.arithmetique import verifier


@pytest.mark.parametrize(("texte", "attendu"), [
    # Le cas réel, une fois l'unité corrigée : 102 / 50 000 = 0,204 %.
    ("La cible représente 102 sur 50 000, soit 0,2 %.", 0),
    ("La cible représente 102 sur 50 000, soit 2,4 %.", 1),
    # Le pourcentage appliqué.
    ("Soit 12 % de 50 000, soit 6 000 euros.", 0),
    ("Soit 12 % de 50 000, soit 12 000 euros.", 1),
    # L'évolution entre deux exercices.
    ("Le CA passe de 40 000 à 50 000 euros, soit une hausse de 25 %.", 0),
    ("Le CA passe de 40 000 à 50 000 euros, soit une hausse de 40 %.", 1),
])
def test_une_operation_posee_est_refaite(texte: str, attendu: int) -> None:
    """Les trois formes que le contrôle sait relire."""
    assert len(verifier(texte)) == attendu


@pytest.mark.parametrize("arrondi", [
    "On compte 102 sur 50 000, soit 0,2 %.",      # 0,204 arrondi au dixième
    "On compte 102 sur 50 000, soit 0,20 %.",     # au centième
    "On compte 102 sur 50 000, soit 0,204 %.",    # exact
    "On compte 1 sur 3, soit 33 %.",              # 33,33 arrondi à l'unité
])
def test_un_arrondi_legitime_ne_declenche_rien(arrondi: str) -> None:
    """LE piège de ce contrôle, et ce qui le rend utilisable.

    Un document qui écrit « 0,2 % » pour 0,204 % ne se trompe pas : il arrondit
    au dixième, et c'est ce qu'un lecteur attend. Un écart RELATIF crierait ici
    — 2 % — sur une phrase juste.

    On compare donc à la précision que le rédacteur a choisie. Sans cette
    règle, ce contrôle produirait un motif par page et coûterait des
    réécritures pour rien : ce projet a mesuré, le jour même, ce qu'un contrôle
    qui crie faux coûte en euros.
    """
    assert verifier(arrondi) == []


def test_une_affirmation_sans_ses_termes_n_est_pas_jugee() -> None:
    """LIMITE ASSUMÉE, et elle est la contrepartie de la précédente.

    « La part de marché atteint 0,2 % » ne donne ni numérateur ni
    dénominateur : il n'y a rien à recouper. Deviner les termes manquants
    produirait des motifs faux — pire qu'un contrôle absent (règle 2).
    """
    assert verifier("La part de marché atteint 0,2 % du total national.") == []


def test_le_motif_montre_l_extrait_et_les_deux_valeurs() -> None:
    """Un motif qu'on ne peut pas corriger sans relire tout le chapitre est du bruit."""
    faute = verifier("On compte 102 sur 50 000, soit 2,4 %.")[0]
    message = str(faute)

    assert "102 sur 50 000" in message      # où regarder
    assert "0.204" in message.replace(",", ".")  # ce que le calcul donne
    assert "2.4" in message.replace(",", ".")    # ce que le document dit


def test_le_gate_execute_ce_controle() -> None:
    """Un contrôle jamais appelé est un contrôle qui n'existe pas.

    Ce dépôt a déjà connu six fois le défaut « écrit, testé, jamais exécuté »
    (règle 8). On vérifie donc le branchement, pas seulement la fonction.
    """
    from pathlib import Path

    import generation.gate as gate

    source = Path(gate.__file__).read_text(encoding="utf-8")

    assert "failures.extend(_check_arithmetique(sections))" in source


def test_un_calcul_faux_se_corrige_tout_seul() -> None:
    """Il doit être RÉPARABLE, sinon il bloque sans jamais aboutir.

    Depuis que la livraison ne s'arrête plus, un motif que la boucle ne sait
    pas corriger part chez le client sans avoir été retenté. Un calcul faux se
    corrige dans le chapitre qui l'a écrit : il suffit de refaire l'opération.
    """
    from generation.correction import _CHAPTER_LEVEL_CHECKS, _CHECK_LABELS

    assert "calcul_faux" in _CHAPTER_LEVEL_CHECKS
    assert "calcul_faux" in _CHECK_LABELS
