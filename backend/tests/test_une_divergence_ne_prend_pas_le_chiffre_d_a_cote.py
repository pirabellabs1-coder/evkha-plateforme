"""Une valeur divergente est celle du libellé, pas celle d'à côté.

## Les motifs, lus pour la première fois avec leur phrase (corpus du 14/09/2026)

Le motif `coherence_chiffree` montre depuis `fad39d3` la phrase de la valeur
minoritaire. Relus, douze des seize étaient des lectures fausses :

- une grille « **27 600 €** — Investissement total *(données du projet)*
  **1 600 €** — Apport personnel » : la valeur précède son libellé, et le
  libellé prenait celle de la ligne suivante ;
- « dépasse le seuil de rentabilité de 35 609 € », « ne dépasse le seuil de
  rentabilité que de 4 000 € » : un ÉCART au seuil, pas le seuil ;
- « 34,4 % du chiffre d'affaires prévisionnel de l'année 1 (18 667 €/54 276 €) » :
  un opérande de la division ;
- « le résultat net de la première année, 9 000 euros » : « première année »
  n'était pas lue comme l'année 1 ;
- « résultat net de 9 000 à 45 000 euros entre l'année 1 et l'année 3 » : la
  fin d'une trajectoire, rangée dans l'année 1.

Contre-épreuve : la vraie divergence de la cliente (SYNAPSES — trois seuils de
rentabilité concurrents) reste attrapée.
"""
from __future__ import annotations

from generation.checks_evangeline import (
    DivergenceChiffree,
    collecter_mentions,
    detecter_divergences,
)


def _divergences(chapitres: dict[int, str]) -> list[DivergenceChiffree]:
    mentions = []
    for numero, texte in chapitres.items():
        mentions.extend(collecter_mentions(numero, texte))
    return detecter_divergences(mentions)


def test_une_grille_valeur_puis_libelle_ne_donne_pas_la_valeur_suivante() -> None:
    assert _divergences({
        13: "L'investissement total est de 27 600 €.",
        20: (
            "**27 600 €** — Investissement total de lancement *(données du projet)*\n"
            "**1 600 €** — Apport personnel déjà investi dans le projet"
        ),
    }) == []


def test_un_ecart_au_seuil_n_est_pas_le_seuil() -> None:
    assert _divergences({
        9: "Le seuil de rentabilité est de 18 667 €.",
        14: "Le chiffre d'affaires dépasse le seuil de rentabilité de 35 609 € dès l'année 1.",
        19: "L'exercice 1 ne dépasse le seuil de rentabilité que de 4 000 €.",
    }) == []


def test_un_operande_entre_parentheses_n_est_pas_la_valeur() -> None:
    assert _divergences({
        4: "Le chiffre d'affaires prévisionnel de l'année 1 est de 54 276 €.",
        9: (
            "Ce montant représente 34,4 % du chiffre d'affaires prévisionnel de "
            "l'année 1 (18 667 €/54 276 €)."
        ),
    }) == []


def test_la_premiere_annee_est_l_annee_1() -> None:
    assert _divergences({
        0: "Le résultat net de la première année est de 9 000 euros.",
        13: "Le résultat net de l'année 1 est de 9 000 euros.",
        17: "Le résultat net de l'année 3 atteint 45 000 euros.",
    }) == []
    divs = _divergences({
        0: "Le résultat net de la première année est de 12 000 euros.",
        13: "Le résultat net de l'année 1 est de 9 000 euros.",
    })
    assert len(divs) == 1, "CONTRE-ÉPREUVE : deux valeurs pour l'année 1 restent opposées"


def test_la_fin_d_une_trajectoire_n_est_pas_rangee_dans_l_annee_1() -> None:
    assert _divergences({
        13: "Le résultat net de l'année 1 est de 9 000 euros.",
        17: (
            "La montée en charge (résultat net de 9 000 à 45 000 euros entre "
            "l'année 1 et l'année 3)."
        ),
    }) == []


def test_la_divergence_synapses_reste_attrapee() -> None:
    """CONTRE-ÉPREUVE : trois seuils de rentabilité concurrents."""
    divs = _divergences({
        8: "Le seuil de rentabilité est de 163 672 €.",
        12: "Le seuil de rentabilité s'établit à 168 622 €.",
        15: "Le seuil de rentabilité atteint 180 000 €.",
    })
    assert len(divs) == 1


# ── Relecture des sept motifs restants (mesure `corpus-20260914-1502`) ───────


def test_une_composante_du_chiffre_d_affaires_n_est_pas_le_chiffre_d_affaires() -> None:
    assert _divergences({
        3: "Le chiffre d'affaires prévisionnel de l'année 1 est de 54 276 euros.",
        4: (
            "Le chiffre d'affaires prévisionnel de l'année 1 se décompose en 40 716 € "
            "issus des abonnements B2B et 13 560 € issus des ventes."
        ),
    }) == []


def test_un_seuil_legal_n_est_pas_le_chiffre_d_affaires_du_projet() -> None:
    assert _divergences({
        7: "Le chiffre d'affaires de l'année 1 est de 54 276 €.",
        13: (
            "Le taux réduit s'applique aux petites entreprises dont le chiffre "
            "d'affaires ne dépasse pas 10 millions d'euros, ce qui reste le cas avec "
            "269 721 € en année 1."
        ),
    }) == []


def test_un_montant_suivi_d_un_autre_libelle_est_le_sien() -> None:
    assert _divergences({
        2: "Le seuil de rentabilité est de 18 667 euros.",
        15: (
            "L'emprunt s'apprécie au regard du seuil de rentabilité déjà établi : "
            "54 276 euros de chiffre d'affaires en année 1."
        ),
    }) == []


def test_une_vraie_divergence_de_chiffre_d_affaires_reste_attrapee() -> None:
    """CONTRE-ÉPREUVE : sans composante ni seuil, deux CA de l'année 1 s'opposent."""
    divs = _divergences({
        3: "Le chiffre d'affaires prévisionnel de l'année 1 est de 54 276 euros.",
        4: "Le chiffre d'affaires prévisionnel de l'année 1 atteint 40 716 €.",
    })
    assert len(divs) == 1


# ── Les quatre motifs restants (mesure `corpus-20260914-1518`) ───────────────


def test_une_valeur_ecrite_avant_son_libelle_ne_prend_pas_la_suivante() -> None:
    assert _divergences({
        7: "Le chiffre d'affaires prévisionnel de l'année 1 est de 54 276 €.",
        13: (
            "Le plafond couvre largement les 54 276 € de chiffre d'affaires prévisionnel "
            "de l'année 1 et même les 269 721 € projetés en année 3."
        ),
    }) == []


def test_un_montant_coordonne_appartient_au_dernier_terme() -> None:
    assert _divergences({
        9: "Le seuil de rentabilité est de 18 667 €.",
        18: (
            "Elle est déjà intégrée au calcul du seuil de rentabilité et au compte de "
            "résultat prévisionnel du chapitre 16 : 12 000 euros annuels."
        ),
    }) == []


_TRAJECTOIRE = (
    "La trajectoire devient positive dès l'année 2 et solide en année 3 "
    "(résultat net de 42 000 euros)."
)


def test_l_annee_retenue_est_la_plus_proche_du_montant() -> None:
    assert _divergences({
        1: "Le résultat net de l'année 2 est de 8 000 €.",
        21: _TRAJECTOIRE,
    }) == []
    divs = _divergences({
        1: "Le résultat net de l'année 3 est de 8 000 €.",
        21: _TRAJECTOIRE,
    })
    assert len(divs) == 1, "CONTRE-ÉPREUVE : deux résultats nets de l'année 3 s'opposent"
