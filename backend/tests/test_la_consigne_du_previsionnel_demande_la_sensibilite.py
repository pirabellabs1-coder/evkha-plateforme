"""La consigne du prévisionnel demande la sensibilité à −10 % ET −20 %, sans échappatoire.

Business plan ÉCLORE `28a257bf` (30/09/2026) : la consigne ne demandait que
−10 %, recalculé par le modèle ; le chapitre a écrit que la colonne
« exigerait de redistribuer charges variables et fixes selon des hypothèses
que le client n'a pas arbitrées ». La mémoire calcule désormais les deux
scénarios (`memoire.faits.faits_de_sensibilite`) ; la consigne les demande.
"""
from __future__ import annotations

from generation.chapitres.fichiers_prompts import charger_prompt


def test_la_consigne_demande_les_deux_baisses() -> None:
    consigne = charger_prompt("business_plan", 16)
    assert "inférieur de 10 %" in consigne and "inférieur de 20 %" in consigne


def test_la_consigne_interdit_de_dire_que_c_est_impossible() -> None:
    consigne = charger_prompt("business_plan", 16)
    assert "n'écris jamais qu'il ne peut pas l'être" in consigne
