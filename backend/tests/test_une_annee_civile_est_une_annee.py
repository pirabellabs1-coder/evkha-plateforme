"""« 2029 » est une année pour le contrôle inter-chapitres.

29/09/2026, business plan `cb59cede` (ÉCLORE) : le résultat net 2029 est
imprimé 23 223,86 € sur seize pages et 23 835,86 € (la CAF) sur dix. Le
contrôle « chiffre contre chiffre » (`checks_evangeline.collecter_mentions`)
écarte une mention annuelle sans année — et `_ANNEE_RE` ne connaissait que
« an N / année N / exercice N ». Le document datait ses exercices en années
civiles : toutes les mentions étaient écartées, la divergence n'a jamais été
vue.

L'année d'une mention se lit désormais à un seul endroit
(`checks_evangeline.annee_proche`), que le gate importe aussi (règle 5).
"""
from __future__ import annotations

import pytest

# `annee_proche` et `rang_d_exercice` sont nés avec le correctif : importés
# dans leurs tests, pour que le rejeu contre l'ancien code fasse tomber les
# tests de comportement sur leur assertion, pas sur un import (règle 6).
from generation.checks_evangeline import collecter_mentions, detecter_divergences


def _divergences(chapitres: dict[int, str]) -> list[tuple[str, int | None]]:
    mentions = []
    for numero, texte in chapitres.items():
        mentions.extend(collecter_mentions(numero, texte))
    return [(d.libelle, d.annee) for d in detecter_divergences(mentions)]


def test_deux_resultats_nets_2029_differents_divergent() -> None:
    """AVANT : aucune divergence — « 2029 » n'était pas une année."""
    assert _divergences({
        2: "Résultat net 2029 : 23 223,86 €.",
        11: "Le résultat net 2029 : 23 835,86 €.",
    }) == [("resultat_net", 2029)]


def test_la_meme_valeur_en_2029_ne_diverge_pas() -> None:
    """Contre-épreuve : deux mentions justes, deux années différentes."""
    assert _divergences({
        2: "Résultat net 2029 : 23 223,86 €.",
        11: "Résultat net 2028 : 8 040 €.",
        16: "Le résultat net 2029 : 23 223,86 €.",
    }) == []


@pytest.mark.parametrize(
    ("texte", "annee"),
    [
        pytest.param("Résultat net 2029 : 23 223,86 €", 2029, id="civile"),
        pytest.param("le résultat net atteint 23 223,86 € en 2029", 2029, id="apres"),
        pytest.param("résultat net de l'année 3", 3, id="rang"),
        pytest.param("la troisième année", 3, id="ordinal"),
        pytest.param("un résultat net de 2029 €", None, id="un-montant"),
        pytest.param("une marge de 2029,5 %", None, id="un-pourcentage"),
        pytest.param("trésorerie au 31/12/2029", None, id="date-chiffree"),
        pytest.param("trésorerie au 31 décembre 2029", None, id="date-en-lettres"),
    ],
)
def test_ce_qui_est_une_annee(texte: str, annee: int | None) -> None:
    from generation.checks_evangeline import annee_proche

    assert annee_proche(texte) == annee


def test_le_rang_d_exercice() -> None:
    from generation.checks_evangeline import rang_d_exercice

    assert rang_d_exercice(3, None) == 3
    assert rang_d_exercice(2029, 2027) == 3
    # Sans premier exercice connu, une année civile ne devient pas un rang.
    assert rang_d_exercice(2029, None) is None
