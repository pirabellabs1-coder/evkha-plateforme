"""« 7 369 320,354 CHF » n'est pas un montant : c'est un calcul recopié brut.

Business plan `6c794b18`, rejeu du gate du 26/09/2026, chapitre 16 : « un seuil
de rentabilité de 7 369 320,354 CHF dépassé de 235 429,65 CHF ». Le format
français des nombres est imposé au modèle depuis le lot 88 — et rien ne le
vérifiait sur le document livré. Un banquier lit là un chiffre que personne
n'a arrondi, donc que personne n'a relu.

Ce que le contrôle ne juge PAS, exprès :
- une unité à échelle (« 1,234 M€ » vaut 1 234 000 €) ;
- un pourcentage (« 0,204 % » n'est pas une monnaie) ;
- le point (« 250.000 € » est un point de milliers mal formé, un autre défaut :
  le motif doit décrire le vrai, règle 2).
"""
from __future__ import annotations

import pytest

from generation.checks_post_rendu import detecter_montants_non_arrondis
from generation.gate import _check_montants_non_arrondis
from generation.rendering import RenderedSection


def _section(numero: int, corps: str) -> RenderedSection:
    return RenderedSection(number=numero, title=f"Chapitre {numero}", kind="chapitre", body=corps)


def test_le_cas_mesure_est_vu() -> None:
    (trouve,) = detecter_montants_non_arrondis([_section(
        16, "avec un seuil de rentabilité de 7 369 320,354 CHF dépassé de 235 429,65 CHF",
    )])
    assert trouve.montant == "7 369 320,354 CHF"
    assert trouve.decimales == 3
    assert trouve.chapitre == 16


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("un résultat net de 127 950,8 CHF", id="une-decimale"),
        pytest.param("un panier de 1 250,50 €", id="deux-decimales"),
        pytest.param("un marché de 1,234 M€", id="unite-a-echelle"),
        pytest.param("un marché de 1,234 milliard d'euros", id="magnitude-en-lettres"),
        pytest.param("une part de 0,204 %", id="pourcentage"),
        pytest.param("un budget de 250.000 €", id="point-de-milliers-autre-defaut"),
        pytest.param("un investissement de 1 250 000 €", id="entier"),
    ],
)
def test_ce_qui_est_correct_n_est_pas_signale(texte: str) -> None:
    assert detecter_montants_non_arrondis([_section(3, texte)]) == [], texte


def test_un_montant_repete_est_un_seul_defaut() -> None:
    """Rejeu du 26/09/2026 : « 7 369 320,354 CHF » cinq fois = cinq motifs.

    Un motif par défaut, avec le nombre d'occurrences ; un autre montant
    dans le même chapitre reste un autre défaut."""
    trouves = detecter_montants_non_arrondis([_section(
        16,
        "un seuil de 7 369 320,354 CHF, soit 7 369 320,354 CHF ; le seuil de "
        "7 369 320,354 CHF est dépassé de 235 429,646 CHF.",
    )])
    assert [(t.montant, t.occurrences) for t in trouves] == [
        ("7 369 320,354 CHF", 3), ("235 429,646 CHF", 1),
    ]
    assert "3 occurrences" in str(trouves[0])
    assert "occurrences" not in str(trouves[1])


def test_la_boucle_de_correction_sait_le_reparer() -> None:
    """Un motif que la boucle ne sait pas traiter part chez le client tel quel."""
    from generation.correction import _CHECK_LABELS, _is_regenerable

    assert _is_regenerable("montant_non_arrondi")
    assert "montant_non_arrondi" in _CHECK_LABELS


def test_le_gate_porte_le_motif_au_bon_chapitre() -> None:
    echecs = _check_montants_non_arrondis((
        _section(3, "un panier de 1 250,50 €"),
        _section(16, "un seuil de 7 369 320,354 CHF"),
    ))
    assert [(e.check, e.chapter_number) for e in echecs] == [("montant_non_arrondi", 16)]
    assert "3 décimales" in echecs[0].detail
