"""Deux tableaux qui donnent deux seuils de rentabilité sont une divergence.

`collecter_mentions` exigeait un CONNECTEUR entre le libellé et sa valeur
(« : », « de », « s'élève à »…) et la barre de cellule n'en était pas un.
Vérifié le 26/09/2026 : « | Seuil de rentabilité | 90 000 € | » contre
« | … | 120 000 € | » dans deux chapitres ne rendait aucun motif. Les tableaux
financiers du business plan — l'endroit où les chiffres se contredisent le
plus — étaient invisibles au contrôle chiffre contre chiffre.

Même relecture, dans l'autre sens : « seuil de rentabilité mensuel : 7 500 € »
était opposé au seuil de l'exercice (90 000 €) parce que la périodicité
n'était lue qu'APRÈS le montant. Un faux motif fait réécrire un chapitre
juste, et c'est payant.
"""
from __future__ import annotations

from generation.checks_evangeline import collecter_mentions, detecter_divergences


def _mentions(*chapitres: tuple[int, str]) -> list:  # type: ignore[type-arg]
    return [m for numero, texte in chapitres for m in collecter_mentions(numero, texte)]


def test_deux_tableaux_deux_seuils_une_divergence() -> None:
    mentions = _mentions(
        (3, "| Indicateur | Valeur |\n| Seuil de rentabilité | 90 000 € |\n"),
        (12, "| Indicateur | Valeur |\n| Seuil de rentabilité | 120 000 € |\n"),
    )
    divergences = detecter_divergences(mentions)
    assert len(divergences) == 1
    assert {m.montant_base for m in divergences[0].mentions} == {90_000.0, 120_000.0}


def test_la_barre_lie_un_libelle_a_sa_seule_cellule() -> None:
    """Contre-épreuve : sur une ligne à deux couples, chacun garde sa valeur."""
    mentions = collecter_mentions(
        3, "| Apport personnel | 20 000 € | Emprunt bancaire | 80 000 € |\n"
    )
    par_libelle = {m.libelle: m.montant_base for m in mentions}
    assert any("apport" in cle for cle in par_libelle), par_libelle
    assert all(
        montant == 20_000.0 for cle, montant in par_libelle.items() if "apport" in cle
    ), par_libelle


def test_un_seuil_mensuel_n_est_pas_le_seuil_de_l_exercice() -> None:
    mentions = _mentions(
        (3, "Le seuil de rentabilité s'établit à 90 000 € sur l'exercice."),
        (12, "Le seuil de rentabilité mensuel : 7 500 €, soit 90 000 € par an."),
    )
    assert detecter_divergences(mentions) == []


def test_le_seuil_annuel_reste_surveille() -> None:
    """« annuel » n'est pas une rupture : c'est la grandeur par défaut."""
    mentions = _mentions(
        (3, "Le seuil de rentabilité annuel s'établit à 90 000 €."),
        (12, "Le seuil de rentabilité annuel s'établit à 120 000 €."),
    )
    assert len(detecter_divergences(mentions)) == 1
