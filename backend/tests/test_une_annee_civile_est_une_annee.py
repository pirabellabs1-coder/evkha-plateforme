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


# ── Revue du 29/09/2026 : l'année d'une mention est la SIENNE ───────────────
#
# La fenêtre de ±40 signes franchissait lignes et propositions. Chaque cas
# ci-dessous produisait une divergence sur un document juste, et le motif
# poussait le modèle à « corriger » un chiffre qui ne l'était pas (règle 2).

TABLEAU_2027_2029 = (
    "| Indicateur | 2027 | 2028 | 2029 |\n"
    "|---|---|---|---|\n"
    "| Résultat net | 50 € | 8 040 € | 23 224 € |\n"
)


def test_une_cellule_prend_l_annee_de_sa_colonne() -> None:
    """AVANT : 50 € rangé en 2029 — l'en-tête était à moins de 40 signes."""
    assert _divergences({
        16: TABLEAU_2027_2029,
        2: "Le résultat net 2029 atteint 23 224 €.",
    }) == []
    # Et la colonne 2027 est bien 2027 : un autre chiffre pour 2027 diverge.
    assert _divergences({
        16: TABLEAU_2027_2029,
        2: "Le résultat net 2027 atteint 5 000 €.",
    }) == [("resultat_net", 2027)]


def test_une_colonne_sans_annee_ne_date_rien() -> None:
    """Un titre au-dessus du tableau n'est pas l'en-tête de la colonne."""
    assert _divergences({
        16: "Prévisionnel 2029\n| Indicateur | Valeur |\n|---|---|\n| Résultat net | 50 € |\n",
        2: "Le résultat net 2029 atteint 23 224 €.",
    }) == []


def test_l_annee_de_la_phrase_suivante_n_est_pas_la_sienne() -> None:
    assert _divergences({
        3: "Le résultat net atteint 8 040 €.\nEn 2029, l'activité se stabilise.",
        2: "Résultat net 2029 : 23 224 €.",
    }) == []


@pytest.mark.parametrize(
    ("premiere", "seconde"),
    [
        pytest.param(
            "La trésorerie de départ s'élève à 5 000 € en 2027.",
            "La trésorerie atteint 12 000 € fin 2027.",
            id="depart-et-fin",
        ),
        pytest.param(
            "Trésorerie au point bas : 1 200 € en 2027.",
            "Trésorerie à la clôture 2027 : 9 800 €.",
            id="point-bas-et-cloture",
        ),
    ],
)
def test_un_stock_a_plusieurs_moments_dans_l_annee(premiere: str, seconde: str) -> None:
    """La trésorerie de départ et celle de fin 2027 ne se contredisent pas."""
    assert _divergences({3: premiere, 9: seconde}) == []


def test_un_stock_au_meme_moment_diverge_encore() -> None:
    """Contre-épreuve : deux trésoreries de fin 2027 différentes restent vues."""
    assert _divergences({
        3: "Trésorerie fin 2027 : 12 000 €.",
        9: "La trésorerie atteint 9 800 € fin 2027.",
    }) == [("tresorerie", 2027)]


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("Le résultat net cumulé 2027-2029 : 31 314 €.", id="cumul"),
        pytest.param("Le résultat net moyen sur 2027-2029 : 10 438 €.", id="plage"),
        pytest.param("Le résultat net de 2027 à 2029 : 31 314 €.", id="de-a"),
    ],
)
def test_une_plage_d_annees_ne_date_rien(texte: str) -> None:
    """AVANT : « 2027-2029 » rangeait le montant en 2027."""
    assert _divergences({4: texte, 2: "Résultat net 2027 : 50 €."}) == []


def test_une_variante_chiffree_n_est_pas_la_valeur_retenue() -> None:
    """La lecture de sensibilité que la consigne du prévisionnel exige."""
    assert _divergences({
        16: "Avec un chiffre d'affaires inférieur de 10 %, le résultat net de "
            "15 900 € en 2029 reste positif.",
        2: "Le résultat net 2029 atteint 23 224 €.",
    }) == []


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("résultat net cumulé 2027-2029", id="tiret"),
        pytest.param("de 2027 à 2029", id="de-a"),
        pytest.param("entre 2027 et 2029", id="entre-et"),
        pytest.param("des années 1 à 3", id="rangs"),
        pytest.param("en moyenne sur 2027-20", id="plage-coupee"),
    ],
)
def test_une_plage_n_est_pas_une_annee(texte: str) -> None:
    from generation.checks_evangeline import annee_proche

    assert annee_proche(texte) is None
