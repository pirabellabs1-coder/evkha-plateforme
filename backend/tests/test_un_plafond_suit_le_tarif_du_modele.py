"""Un plafond de dépense calibré sur un modèle devient faux quand le modèle change.

26/10/2026, passage de la génération en Opus. Les quatre plafonds avaient été
calibrés sur `claude-sonnet-5` (2 $ / 10 $ par Mtok) à partir de coûts
RÉELLEMENT mesurés. Opus 5.5 est facturé 4 $ / 20 $ : le double. À jetons
égaux, les quatre plafonds devenaient donc insuffisants le jour de la bascule,
sans qu'une ligne de code ne change et sans que rien ne le signale.

L'historique de `cost.py` est déjà celui-là, trois fois : plafond relevé le
08/08, le 13/08, le 18/08, chaque fois APRÈS qu'un dossier réel se soit fait
couper à un chapitre de la fin, après avoir engagé la dépense. Le défaut n'est
pas la valeur d'un plafond — c'est qu'aucun contrôle ne reliait un plafond au
tarif pour lequel il avait été posé (règle 4 : la classe, pas l'exemple).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import override_settings

from generation.cost import (
    COUT_OBSERVE_MAX_EUR,
    MODELE_DE_CALIBRAGE,
    PLAFOND_PAR_LIVRABLE,
    plafonds_sous_calibres,
)

#: Le modèle que la production appelle depuis le 26/10/2026.
OPUS = "claude-opus-5-5"


def test_les_plafonds_couvrent_le_cout_en_opus() -> None:
    """Le contrôle qui échoue sur les plafonds d'avant.

    Avec les anciennes valeurs — étude de marché 8,00 €, business plan 8,00 €,
    stratégie 6,50 €, concurrence 4,50 € — ce test échoue sur les QUATRE
    livrables : au tarif d'Opus, le coût attendu d'une étude de marché est de
    7,72 × 2 = 15,44 €, et le plafond l'aurait coupée vers le 20e chapitre.
    """
    with override_settings(EVKHA_ANTHROPIC_MODEL_ID=OPUS):
        assert plafonds_sous_calibres() == []


def test_au_tarif_de_calibrage_rien_n_est_signale() -> None:
    """Contre-épreuve : le contrôle ne crie pas sur ce pour quoi il a été posé."""
    with override_settings(EVKHA_ANTHROPIC_MODEL_ID=MODELE_DE_CALIBRAGE):
        assert plafonds_sous_calibres() == []


def test_un_plafond_trop_bas_est_bien_signale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contre-épreuve de la règle 1 : un contrôle qui ne refuse jamais ne contrôle rien.

    On repose les plafonds d'avant la bascule. Le contrôle doit les refuser au
    tarif d'Opus, et nommer le livrable, son plafond et le coût attendu — un
    motif que le lecteur peut vérifier lui-même (règle 2).
    """
    anciens = {livrable: Decimal("8.0000") for livrable in PLAFOND_PAR_LIVRABLE}
    monkeypatch.setattr("generation.cost.PLAFOND_PAR_LIVRABLE", anciens)

    with override_settings(EVKHA_ANTHROPIC_MODEL_ID=OPUS):
        motifs = plafonds_sous_calibres()

    assert motifs, "un plafond de 8 € ne couvre pas une étude de marché en Opus"
    joints = " ".join(motifs)
    assert "15.44" in joints, joints
    assert "8.00" in joints, joints


def test_chaque_plafond_declare_son_cout_observe() -> None:
    """Un plafond sans mesure n'est pas calibré : il est deviné.

    Sans cette correspondance, `plafonds_sous_calibres` se tairait sur un
    livrable ajouté plus tard — un contrôle qui n'a rien à comparer rend un
    succès (règle 1). Ce test ferme la porte à l'oubli.
    """
    assert set(PLAFOND_PAR_LIVRABLE) == set(COUT_OBSERVE_MAX_EUR)


def test_un_plafond_reste_au_dessus_de_son_cout_observe() -> None:
    """Au tarif de calibrage, chaque plafond garde une marge sur ce qui a été mesuré."""
    for livrable, observe in COUT_OBSERVE_MAX_EUR.items():
        assert PLAFOND_PAR_LIVRABLE[livrable] > observe, livrable
