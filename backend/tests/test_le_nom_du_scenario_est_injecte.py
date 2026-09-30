"""Le nom du scénario de référence est injecté, jamais écrit en dur (point 6, cliente).

30/09/2026 : le prompt du chapitre 16 disait « scénario central » alors que le
dossier ÉCLORE repose sur le scénario prudent. Le nom vient désormais du brief
(ou d'un défaut NEUTRE), et le gabarit le porte comme variable.
"""
from __future__ import annotations

import pytest

from generation.chapitres.fichiers_prompts import charger_prompt, variables_attendues
from generation.chapitres.runner import _scenario_reference

pytestmark = pytest.mark.django_db


def test_le_defaut_est_neutre_jamais_central() -> None:
    assert _scenario_reference({}) == "scénario de référence"


def test_le_brief_impose_le_nom_du_scenario() -> None:
    assert _scenario_reference({"SCENARIO_REFERENCE": "scénario prudent"}) == "scénario prudent"
    assert _scenario_reference({"SCENARIO": "scénario prudent"}) == "scénario prudent"


def test_le_prompt_16_porte_la_variable_et_non_le_mot_en_dur() -> None:
    gabarit = charger_prompt("business_plan", 16)
    assert "scénario central" not in gabarit
    assert "scenario_reference" in variables_attendues(gabarit)


def test_le_nom_injecte_reste_reconnu_comme_le_previsionnel() -> None:
    """Le défaut et « prudent » sont dans la liste que la relecture n'a pas à juger."""
    from generation.relecture.valeurs import _SCENARIO

    for nom in ("scénario de référence", "scénario prudent"):
        assert not _SCENARIO.search(nom), nom
    assert _SCENARIO.search("scénario dégradé"), "un autre scénario reste jugé"
