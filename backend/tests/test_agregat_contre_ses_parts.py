"""Un agregat enonce doit egaler la somme de ses parts.

## Le defaut, releve par la cliente le 18/08/2026

Etude de concurrence `3a4df56c`. Le document ecrit :

    Marché national estimé à 850 000 000 € en 2025, avec seulement 2,7 %
    capté par les onze concurrents recensés

et detaille ailleurs les onze parts :

    0,065 + 0,065 + 0,082 + 0,047 + 0,071 + 0,015 + 0,029 + 0,024 + 0,008
    + 0,032 + 0,041 = 0,479 %

Elle a refait l'addition au millieme pres : « la somme donne environ 0,479 %,
donc ≈ 0,48 % ». Et elle ajoute : « c'est exactement le type de contradiction
interchapitres que le controle final devait desormais empecher ».

## Pourquoi `totaux_faux` ne pouvait pas le voir

Ce n'est PAS une ligne « Total » de tableau. C'est une phrase de synthese, dans
un chapitre, a distance de la colonne qu'elle contredit. Le controle des totaux
ne juge que ce qu'un tableau annonce dans sa derniere ligne.
"""
from __future__ import annotations

from generation.arithmetique import agregats_faux

#: La colonne reelle du chapitre 6, aux valeurs exactes.
PARTS = ["0,065", "0,065", "0,082", "0,047", "0,071",
         "0,015", "0,029", "0,024", "0,008", "0,032", "0,041"]

TABLEAU = (
    "| Concurrent | Chiffre d'affaires | Part de marché |\n"
    "| --- | --- | --- |\n"
    + "".join(
        f"| Acteur {i + 1} | {550 + i * 10} 000 € | {p} % |\n"
        for i, p in enumerate(PARTS)
    )
)


def test_le_2_7_pour_cent_est_signale() -> None:
    """La phrase EXACTE du document livre.

    Echoue sur le code d'avant : aucun controle ne confrontait un agregat de
    prose a la colonne qui le compose.
    """
    fautes = agregats_faux([
        TABLEAU,
        "Marché national estimé à 850 000 000 € en 2025, avec seulement "
        "2,7 % capté par les onze concurrents recensés.",
    ])
    assert len(fautes) == 1
    assert fautes[0].annonce == 2.7
    assert round(fautes[0].somme, 3) == 0.479
    assert fautes[0].lignes == 11


def test_un_agregat_juste_ne_declenche_rien() -> None:
    """Contre-epreuve : le meme document, avec le bon chiffre."""
    assert agregats_faux([
        TABLEAU,
        "Marché national estimé à 850 000 000 € en 2025, avec seulement "
        "0,48 % capté par les onze concurrents recensés.",
    ]) == []


def test_sans_agregat_enonce_aucune_colonne_n_est_jugee() -> None:
    """Contre-epreuve, et c'est la plus importante.

    Le controle ne cherche PAS les colonnes qui « devraient » faire 100 %. Le
    business plan du 17/08 porte trois colonnes de pourcentages sommant a
    339 %, 264 % et 480 % — toutes legitimes, puisqu'il n'en tire aucun total.
    Un controle qui les jugerait produirait trois motifs faux sur un document
    correct (regle 2).
    """
    assert agregats_faux([
        TABLEAU,
        "Les onze concurrents recensés couvrent des segments distincts du "
        "marché national, sans recouvrement notable entre leurs offres.",
    ]) == []


def test_un_agregat_sans_colonne_de_parts_ne_declenche_rien() -> None:
    """Contre-epreuve : rien a comparer, donc rien a dire.

    Le document peut affirmer une part globale sans detailler acteur par
    acteur : c'est une affirmation, pas une contradiction.
    """
    assert agregats_faux([
        "Le marché national est capté à 2,7 % par les onze concurrents "
        "recensés, selon notre estimation.",
    ]) == []
