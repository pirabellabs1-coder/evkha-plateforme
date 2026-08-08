"""La consigne doit nommer chaque forme de refus que le rendu applique.

Mesure du 08/08/2026, business plan réel `09f32041` : **32 figures rendues sur
48 demandées**. Les seize refus se rangent en cinq motifs, et chacun est une
règle du moteur de rendu (`rendu_word/donnees_graphiques.py`).

Neuf de ces refus tombaient sur une règle DÉJÀ écrite dans la consigne — au
moins deux identifiants, des grandeurs de même nature. Six tombaient sur une
règle que la consigne ne disait **nulle part** : radar et jauges exigent des
notes, un radar veut trois axes, une série temporelle couvre toutes les
périodes.

Une règle appliquée au rendu mais tue dans la consigne fabrique un travail
perdu : le modèle demande une figure impossible, le moteur la refuse, et le
client reçoit un chapitre en moins. Ce test relie les deux bouts.

Il ne vérifie PAS que le modèle obéit — aucun test ne peut le faire sans
appeler l'API. Il vérifie que la règle lui a été DITE, ce qui est le préalable.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType
from generation.prompts import build_system_prompt

#: Les cinq motifs observés, et ce que la consigne doit contenir pour chacun.
#: Les fragments sont volontairement courts : viser une phrase entière ferait
#: tomber ce test à la première reformulation, sans qu'aucune règle ait changé.
MOTIFS_OBSERVES = {
    "radar sans notes (4 refus)": ("radar", "notes"),
    "jauges sans notes (2 refus)": ("jauge", "notes"),
    "radar a moins de 3 axes (1 refus)": ("trois axes",),
    "serie temporelle trouee (1 refus)": ("toutes les periodes",),
    "un seul identifiant (4 refus)": ("DEUX identifiants",),
    "unites heterogenes (5 refus)": ("MEME NATURE",),
}


def _consigne(livrable: str) -> str:
    return build_system_prompt(livrable, country="France", plan="Plan de test.")


def test_la_consigne_est_bien_construite() -> None:
    """Garde-fou : sans lui, une consigne vide ferait passer tout le reste.

    Si `build_system_prompt` cessait d'injecter le bloc graphique, les
    assertions suivantes chercheraient des fragments dans une chaîne vide et
    échoueraient — mais pour une raison qu'on mettrait longtemps à trouver.
    """
    consigne = _consigne(DeliverableType.MARKET_STUDY)

    assert "GRAPHIQUES" in consigne
    assert len(consigne) > 2000


@pytest.mark.parametrize(("motif", "fragments"), sorted(MOTIFS_OBSERVES.items()))
def test_chaque_motif_de_refus_est_annonce(motif: str, fragments: tuple[str, ...]) -> None:
    """Le modèle doit connaître la règle avant qu'on lui reproche de l'enfreindre."""
    consigne = _consigne(DeliverableType.MARKET_STUDY)
    manquants = [f for f in fragments if f.lower() not in consigne.lower()]

    assert not manquants, (
        f"La consigne ne dit rien de : {motif}. Fragments absents : {manquants}. "
        "Le rendu refusera pourtant ces figures — voir donnees_graphiques.py."
    )


def test_les_quatre_livrables_recoivent_la_consigne() -> None:
    """Les quatre passent par le moteur structuré depuis le 06/08/2026.

    Le business plan a longtemps reçu la consigne du moteur hérité, qui
    n'annonce que quatre types. Vérifier le seul livrable phare laisserait ce
    trou ouvert sur les trois autres.
    """
    sans_regle = [
        str(livrable)
        for livrable in (
            DeliverableType.MARKET_STUDY,
            DeliverableType.BUSINESS_PLAN,
            DeliverableType.BUSINESS_STRATEGY,
            DeliverableType.COMPETITOR_STUDY,
        )
        if "notes" not in _consigne(str(livrable)).lower()
    ]

    assert not sans_regle, (
        f"Ces livrables ne reçoivent pas la règle des notes : {sans_regle}."
    )
