"""« Non traitée à ce jour » dit l'état de l'affaire, pas celui du document.

Stratégie `d667fbb4`, corpus du 15/09/2026. Au chapitre 5, le tableau des
fragilités porte une colonne d'état :

    | Relation avec les prestataires techniques, comptables, juridiques |
    Ralentissement du développement du CRM et des obligations légales |
    Non traitée à ce jour |

Le contrôle des demandes contredites y lisait une demande abandonnée, puis
retrouvait « comptables, juridiques, prestataires, techniques » ailleurs dans le
document — forcément : le document ANALYSE ce point que l'entreprise n'a pas
encore réglé. Aucune contradiction, un motif faux routé vers une réécriture
payée (règle 2).

Le statut d'une demande dans l'annexe de validation ne se date pas : il dit ce
que le document a fait. Un repère de temps dit ce que l'entreprise a fait.
"""
from __future__ import annotations

import pytest

from generation.checks_post_rendu import detecter_demandes_contredites


def _chapitres(ligne: str) -> list[tuple[int, str, str]]:
    return [
        (
            3,
            "Organisation",
            "La relation avec les prestataires techniques reste informelle ; "
            "les obligations comptables et juridiques sont suivies au fil de l'eau.",
        ),
        (5, "Fragilités", ligne),
    ]


@pytest.mark.parametrize("ligne", [
    "| Relation avec les prestataires techniques, comptables, juridiques | "
    "Ralentissement du développement | Non traitée à ce jour |",
    "| Relation avec les prestataires techniques | Retards | Non traitée pour l'instant |",
    "La relation avec les prestataires techniques, encore non traitée, freine le projet.",
    "| Relation avec les prestataires techniques | Retards | Actuellement non traitée |",
])
def test_un_etat_de_l_affaire_n_est_pas_une_demande_abandonnee(ligne: str) -> None:
    assert detecter_demandes_contredites(_chapitres(ligne)) == []


def test_une_demande_declaree_non_traitee_reste_signalee() -> None:
    """CONTRE-ÉPREUVE : sans repère de temps, c'est le statut du document."""
    ligne = "| Analyser la relation avec les prestataires techniques | Non traitée |"
    assert len(detecter_demandes_contredites(_chapitres(ligne))) == 1
