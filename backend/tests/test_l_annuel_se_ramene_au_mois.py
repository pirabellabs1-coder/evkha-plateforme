"""« X € par an, soit Y € par mois » : la division se refait aussi.

29/09/2026, business plan `cb59cede` (ÉCLORE), p. 52 : un « revenu mensuel »
de 1 986,32 €, soit 23 835,86 € ÷ 12 — la CAF annuelle, présentée à côté du
résultat net. `_PERIODES` (`generation/arithmetique.py`) ne connaissait que le
passage mois → an ; l'annuel → mensuel, la même année de douze mois lue à
l'envers, n'était jamais refait.

Le contrôle ne dit pas si l'opérande est le bon (résultat net ou CAF) : il dit
si la division posée est juste. C'est sa limite, et elle est assumée.
"""
from __future__ import annotations

import pytest

from generation.arithmetique import verifier


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param(
            "Le résultat net de 23 223,86 € par an, soit 1 986,32 € par mois.",
            id="la-caf-divisee-a-la-place-du-resultat",
        ),
        pytest.param(
            "Un loyer de 30 000 € par an, soit 3 000 € par mois.",
            id="an-vers-mois-faux",
        ),
        pytest.param(
            "Un budget de 12 000 € par an, soit 4 000 € par trimestre.",
            id="an-vers-trimestre-faux",
        ),
    ],
)
def test_une_division_fausse_est_signalee(texte: str) -> None:
    """AVANT : aucune de ces divisions n'était refaite."""
    assert [f.nature for f in verifier(texte)] == ["Projection"]


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param(
            "La capacité d'autofinancement de 23 835,86 € par an, soit 1 986,32 € par mois.",
            id="division-juste-au-centime",
        ),
        pytest.param(
            "Un loyer de 30 000 € par an, soit 2 500 € par mois.",
            id="an-vers-mois-juste",
        ),
        pytest.param(
            "Un budget de 12 000 € par an, soit 3 000 € par trimestre.",
            id="an-vers-trimestre-juste",
        ),
        pytest.param(
            "Un résultat de 60 000 € par an à partager entre 2 associés, "
            "soit 2 500 € par mois.",
            id="partage-entre-associes",
        ),
        pytest.param(
            "Un loyer de 2 500 € par mois, soit 30 000 € par an.",
            id="mois-vers-an-inchange",
        ),
    ],
)
def test_une_division_juste_passe(texte: str) -> None:
    """Contre-épreuve : le correctif ne bloque pas ce qui est correct."""
    assert verifier(texte) == []
