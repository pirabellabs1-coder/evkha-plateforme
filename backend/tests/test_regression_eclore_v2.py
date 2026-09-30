"""Régression sur le business plan ÉCLORE `28a257bf` : chaque erreur attendue est DÉTECTÉE.

Le document, sa mémoire de référence et la liste des erreurs attendues sont
des données de cliente : ils vivent dans `tests/fixtures/eclore_*`, jamais
versionnés. Sans eux, ce test se saute — il ne se fait pas passer pour vert
(règle 1) : le saut est dit, avec sa raison.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from generation.relecture import document_du_pdf, relire
from generation.relecture.regression import (
    charger_la_reference,
    charger_les_attendus,
    evaluer,
    rapport,
)

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
PDF = FIXTURES / "eclore_v2.pdf"
REFERENCE = FIXTURES / "eclore_v2_reference.json"
ATTENDUS = FIXTURES / "eclore_v2_attendus.json"

pytestmark = [
    pytest.mark.skipif(
        not (PDF.exists() and REFERENCE.exists() and ATTENDUS.exists()),
        reason="document de cliente absent (tests/fixtures/eclore_*, jamais versionné)",
    ),
    pytest.mark.django_db,
]


def test_chaque_erreur_attendue_est_detectee() -> None:
    constats = relire(document_du_pdf(PDF), charger_la_reference(REFERENCE))
    resultats = evaluer(constats, charger_les_attendus(ATTENDUS))
    manquees = [r.attendu.exemple for r in resultats if r.trouve is None]
    assert not manquees, rapport(resultats, constats)
