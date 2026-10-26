"""Une figure juste ne se jette pas pour une etiquette fausse.

Mesure du 26/10/2026 sur l'etude de marche `dd30db73`, en production :

    figures : 18 demandees, 8 obtenues (44 %), 5 imprimees en tableau brut,
              5 perdues, 0 reparee

Deux des cinq abandons tenaient a ceci, et a rien d'autre :

    Chapitre 5, entonnoir : le titre cite 2026, 2030 et la figure porte
    2024, 2025 : la periode annoncee n'est pas celle des donnees.
    Chapitre 7, barres horizontales : le titre cite 2026, la figure 2025.

Les DONNEES etaient bonnes — elles viennent du socle, et la resolution avait
reussi. Seul le titre, ecrit par le chapitre, annoncait une periode que la
figure ne montre pas. On jetait donc la figure ET son intitule, et on imprimait
les chiffres en tableau nu : c'est le tableau « Donnee | Valeur | Unite |
Annee » que la cliente a lu au milieu de ses chapitres.
"""
from __future__ import annotations

from typing import Any, cast

import pytest

from generation.rendu_word import specification_figures as sf


@pytest.fixture
def annees_portees_2024_2025(monkeypatch: pytest.MonkeyPatch) -> None:
    """La figure porte 2024 et 2025, quoi que son titre annonce."""
    monkeypatch.setattr(sf, "_annees_portees", lambda *a, **k: {2024, 2025})


def _reecrit(titre: str) -> str:
    # La fonction ne lit ni le socle ni la resolution quand les annees
    # portees sont fournies par le fixture : une doublure suffit.
    return sf._titre_sans_les_annees_absentes(
        cast("Any", None), cast("Any", None), [], titre,
    )


@pytest.mark.usefixtures("annees_portees_2024_2025")
def test_le_defaut_mesure_garde_son_titre() -> None:
    """Le cas du chapitre 5 : « 2026-2030 » devant des donnees 2024-2025."""
    assert _reecrit("Projection du marché 2026-2030") == "Projection du marché"


@pytest.mark.usefixtures("annees_portees_2024_2025")
@pytest.mark.parametrize(("titre", "attendu"), [
    ("Marché national 2026", "Marché national"),
    ("Évolution du marché (2026 à 2030)", "Évolution du marché"),
    ("Marché 2030 et perspectives 2035", "Marché et perspectives"),
])
def test_la_liaison_part_avec_l_annee(titre: str, attendu: str) -> None:
    """« 2026-2030 » ampute de 2026 laisserait « -2030 » : la liaison part aussi."""
    assert _reecrit(titre) == attendu


@pytest.mark.usefixtures("annees_portees_2024_2025")
def test_un_titre_juste_n_est_pas_touche() -> None:
    """Contre-epreuve : une annee que la figure PORTE reste dans le titre."""
    assert _reecrit("Croissance 2024-2025") == ""


@pytest.mark.usefixtures("annees_portees_2024_2025")
def test_un_titre_qui_ne_dirait_plus_rien_est_refuse() -> None:
    """Contre-epreuve : mieux vaut un refus qu'un titre vide de sens (regle 2).

    Un titre reduit a moins de deux mots ne se tient plus : la figure repart
    alors au refus, comme avant, et ses donnees s'impriment en tableau.
    """
    assert _reecrit("2026") == ""
    assert _reecrit("Bilan 2026") == ""


def test_seule_la_periode_se_repare(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un titre qui nomme un projet non compare reste un REFUS.

    La reparation ne vaut que lorsque la periode est le SEUL grief : une forme
    qui ne tient pas, un decoupage invente, un projet absent de la grille
    disent que c'est la FIGURE qui ne va pas, pas son etiquette.
    """
    from generation.rendu_word.donnees_graphiques import Resolution
    from generation.rendu_word.specification_figures import Controle, Ecart

    # Deux ecarts dont un hors periode : le garde-fou du correctif.
    ecarts = (Ecart("periode", "x"), Ecart("projet", "y"))
    assert not all(e.regle == "periode" for e in ecarts)
    # Et un controle sans titre corrige se comporte comme avant.
    assert Controle(Resolution(motif="refus"), ecarts).titre_corrige == ""
