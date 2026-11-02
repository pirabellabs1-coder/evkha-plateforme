"""Les figures : plus de quota, une complétion qui reste, un seul motif d'absence.

## L'histoire

06/08/2026, la cliente : « au moins 17 à 25 graphes par document, c'est une
obligation absolue ». Le quota a été demandé au modèle, complété depuis le
socle, puis vérifié sur le document livré.

15/09/2026, le client : « et si on enlève d'avoir un nombre exact de figures
tout simplement, c'est très bloquant ». Mesuré le même jour sur la génération
test `cd639627` : le socle de la stratégie ne permettait que quatre figures, la
consigne en réclamait vingt-deux, et le modèle en a inventé huit, toutes
abandonnées au rendu. Le quota ne produisait pas de figures, il produisait des
demandes impossibles.

## Ce que ces tests tiennent

1. **La consigne ne chiffre plus aucun objectif**, et dit qu'un chapitre sans
   figure est normal quand aucune donnée ne s'y prête.
2. **Le contrôle ne signale plus un plancher** ; il signale encore un document
   où AUCUNE figure n'a pu être dessinée.
3. **Plus de complétion** depuis le 02/11/2026 : elle ajoutait des figures hors
   sujet (« — repères chiffrés »), retirées sur retour d'Evangéline.
"""
from __future__ import annotations

import re

import pytest

from generation.prompts import PLANCHER_FIGURES
from generation.verification import controles
from generation.verification.rapport import Gravite

# ── 1. La consigne ───────────────────────────────────────────────────────────


def test_la_consigne_ne_chiffre_plus_aucun_objectif_de_figures() -> None:
    from generation.prompts import OBJECTIF_FIGURES_TEXTE

    assert not re.search(r"\d+\s+figures", OBJECTIF_FIGURES_TEXTE)
    assert "pas de nombre à atteindre" in OBJECTIF_FIGURES_TEXTE
    assert "Un chapitre sans figure est normal" in OBJECTIF_FIGURES_TEXTE


# ── 2. Le contrôle ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("rendues", [1, 4, PLANCHER_FIGURES - 1, PLANCHER_FIGURES])
def test_un_document_avec_peu_de_figures_n_est_plus_signale(rendues: int) -> None:
    """Sur le code d'avant : « 4 figures dans le document, pour un plancher de 17 »."""
    assert controles.controler_visuels(20, rendues, [], []) == []


def test_un_document_sans_aucune_figure_garde_son_motif_d_origine() -> None:
    """L'ancien cas reste distinct : « aucune n'a pu être dessinée ».

    C'est un autre défaut — le socle ne nourrit rien — et il mérite son propre
    motif. Le fondre dans le plancher ferait perdre l'information. Mesuré sur
    la stratégie Zenitek (12/09/2026) : 31 figures demandées, 31 refusées au
    dessin, zéro rendue. Le motif dit aussi ce qui a été fait de leurs données.
    """
    anomalies = controles.controler_visuels(20, 0, [], [])

    assert not [a for a in anomalies if a.gravite is Gravite.BLOQUANTE]
    signalees = [a for a in anomalies if a.gravite is Gravite.AVERTISSEMENT]
    assert len(signalees) == 1
    assert "Aucun des 20" in signalees[0].detail
    assert "tableau" in signalees[0].detail


# ── 3. Plus de complétion automatique (02/11/2026) ─────────────────────────


def test_l_assemblage_n_ajoute_plus_aucune_figure_de_lui_meme() -> None:
    """Evangéline, étude `a6947890` : des barres « — repères chiffrés » qui
    « ne traitent même pas le bon sujet ». Une figure n'existe plus que parce
    qu'un chapitre l'a demandée. Échoue sur le code d'avant, où la fonction
    existait et était appelée."""
    from generation.rendu_word import assemblage

    assert not hasattr(assemblage, "_completer_les_figures")
