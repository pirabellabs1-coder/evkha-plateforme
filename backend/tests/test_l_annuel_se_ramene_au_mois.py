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


# ── Revue du 29/09/2026 : une partie de l'année n'est pas l'année ───────────


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param(
            "90 000 € par an, soit 15 000 € par mois d'ouverture sur la saison de 6 mois.",
            id="mois-d-ouverture",
        ),
        pytest.param("48 000 € par an, soit 12 000 € par mois d'été.", id="mois-d-ete"),
        pytest.param("36 000 € par an, soit 2 769 € par mois sur 13 mois.", id="treize-mois"),
        pytest.param(
            "2 500 € par mois d'ouverture, soit 15 000 € par an.", id="dans-l-autre-sens",
        ),
    ],
)
def test_une_periode_restreinte_ne_se_juge_pas_au_calendrier(texte: str) -> None:
    """AVANT : « calcul faux » sur une saison de six mois divisée par douze."""
    assert verifier(texte) == []


def test_douze_mois_dits_en_clair_se_jugent_encore() -> None:
    """Contre-épreuve : « sur 12 mois » est l'année entière — 36 000 ÷ 12 = 3 000."""
    assert [f.nature for f in verifier("36 000 € par an, soit 2 000 € par mois sur 12 mois.")] == [
        "Projection",
    ]
