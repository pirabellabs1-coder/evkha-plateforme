"""Trois plages que le contrôle des fourchettes prenait pour des estimations.

Corpus de production re-mesuré le 19/11/2026 (43 dossiers) : `fourchette_interdite`
retient 17 dossiers. La plupart de ses motifs sont justes — une estimation
laissée en plage, là où la cliente veut un chiffre décidé. Trois familles ne le
sont pas, et chacune retenait un document à elle seule :

1. la ZONE entre deux seuils d'un tableau de décision ;
2. la plage que publie une source, sur la ligne qui porte son adresse ;
3. la plage citée avec sa source, quand la source est nommée par son domaine.

Chaque test échoue sur le code d'avant, et chaque règle a sa contre-épreuve :
la plage voisine, non couverte, reste signalée.
"""
from __future__ import annotations

import pytest

from generation.checks_evangeline import detecter_fourchettes

BP = "business_plan"
STR = "business_strategy"


def _plages(texte: str, livrable: str) -> list[str]:
    return [f.extrait for f in detecter_fourchettes(17, texte, livrable)]


# ── 1. La zone entre deux seuils ────────────────────────────────────────────

DECISION = (
    "| Chantier | Indicateur | Échéance | Seuil GO | Zone d'attente | Seuil STOP |\n"
    "| --- | --- | --- | --- | --- | --- |\n"
    "| Script de conversion | Taux de proposition d'abonnement | 90 jours "
    "| Plus de 70 % des livraisons | Entre 40 % et 70 % | Moins de 40 % |\n"
)

LEVEE = (
    "| Chantier | Indicateur | Échéance | Atteint | Partiel | Manqué |\n"
    "| --- | --- | --- | --- | --- | --- |\n"
    "| Levée de fonds de 175 000 € | Montant sur le compte de la société | 6 mois "
    "| 175 000 € reçus | Entre 90 000 € et 175 000 € reçus | Moins de 90 000 € |\n"
)


def test_la_zone_entre_deux_seuils_d_un_tableau_de_decision_passe() -> None:
    """Stratégie `d319a9e5` : retenue sur ce seul motif."""
    assert _plages(DECISION, STR) == []


def test_la_zone_passe_aussi_en_euros() -> None:
    """Business plan `6c9dc734`."""
    assert _plages(LEVEE, BP) == []


def test_une_plage_dont_la_ligne_ne_pose_pas_les_seuils_reste_signalee() -> None:
    """Contre-épreuve : c'est la ligne qui décide, pas le mot « entre »."""
    ligne = (
        "| Chantier | Indicateur | Cible |\n| --- | --- | --- |\n"
        "| Script de conversion | Taux de proposition | Entre 40 % et 70 % |\n"
    )

    assert len(_plages(ligne, STR)) == 1


def test_un_seul_seuil_ecrit_ne_suffit_pas() -> None:
    """Contre-épreuve : « plus de 70 % » seul ne fait pas de « 40 » une décision."""
    ligne = (
        "| Chantier | Seuil GO | Zone d'attente |\n| --- | --- | --- |\n"
        "| Script de conversion | Plus de 70 % | Entre 40 % et 70 % |\n"
    )

    assert len(_plages(ligne, STR)) == 1


def test_la_meme_plage_en_prose_reste_signalee() -> None:
    """Contre-épreuve : hors tableau, rien ne dit que les bornes sont décidées."""
    prose = "Le taux de proposition devrait se situer entre 40 % et 70 % au premier trimestre."

    assert len(_plages(prose, STR)) == 1


def test_les_seuils_d_une_autre_ligne_ne_valent_pas_pour_celle_ci() -> None:
    """Contre-épreuve : la zone et ses seuils sont sur la MÊME ligne."""
    tableau = (
        "| Indicateur | Valeur |\n| --- | --- |\n"
        "| Seuil haut | 70 % |\n"
        "| Seuil bas | 40 % |\n"
        "| Taux attendu | Entre 40 % et 70 % |\n"
    )

    assert len(_plages(tableau, STR)) == 1


# ── 2. La ligne qui porte l'adresse de la source ────────────────────────────

SOURCES = (
    "| Organisme | Ce que la source étaye | Année | Adresse |\n"
    "| --- | --- | --- | --- |\n"
    "| Superprof.ch | Fourchette de prix des cours d'anglais particuliers en ligne "
    "en Suisse (25 à 40 CHF/heure en moyenne) | 2025 "
    "| https://www.superprof.ch/cours/anglais/online/ |\n"
)


def test_la_plage_publiee_par_une_source_passe_sur_la_ligne_de_son_adresse() -> None:
    """Business plan `6c794b18`, chapitre Sources : trois motifs de cette forme."""
    assert _plages(SOURCES, BP) == []


def test_une_source_seulement_nommee_dans_une_autre_case_ne_suffit_pas() -> None:
    """Contre-épreuve — la décision du 15/09/2026 tient : sans l'adresse, la
    source doit être dans la case de la plage."""
    ligne = (
        "| Repère | Valeur | Source |\n| --- | --- | --- |\n"
        "| Budget annuel moyen par animal | entre 1 200 € et 1 500 € | Goodflair |\n"
    )

    assert len(_plages(ligne, BP)) == 1


def test_l_adresse_d_une_ligne_ne_couvre_pas_la_ligne_suivante() -> None:
    """Contre-épreuve."""
    tableau = SOURCES + (
        "| Estimation du porteur | Prix d'un cours particulier (30 à 60 CHF) | 2026 | — |\n"
    )

    assert _plages(tableau, BP) == ["30 à 60 CHF"]


# ── 3. La source nommée par son domaine ─────────────────────────────────────


def test_une_source_nommee_par_son_domaine_est_une_source() -> None:
    """Business plan `cb59cede` : « (monatelier.app, 2026) » n'était pas lue,
    faute de majuscule."""
    case = (
        "| Coûts variables faibles | Fourchette de marché 25 € à 65 € selon la "
        "spécialité (monatelier.app, 2026) | Positionnement cohérent |\n"
    )

    assert _plages(case, BP) == []


def test_sans_source_la_meme_plage_reste_signalee() -> None:
    """Contre-épreuve."""
    case = (
        "| Coûts variables faibles | Fourchette de marché 25 € à 65 € selon la "
        "spécialité | Positionnement cohérent |\n"
    )

    assert len(_plages(case, BP)) == 1


def test_une_parenthese_sans_annee_ne_cite_rien() -> None:
    """Contre-épreuve : même exigence que pour un organisme nommé — une année."""
    phrase = "Le marché affiche 25 € à 65 € selon la spécialité (voir monatelier.app)."

    assert len(_plages(phrase, BP)) == 1


# ── Contre-épreuves de la porte finale : des lignes ORDINAIRES ──────────────
#
# La première écriture des deux exemptions passait ses douze tests et avalait
# douze plages courantes : nombres nus comparés sans unité ni position, toute
# adresse tenue pour une source. Ces lignes viennent du banc de la porte finale.



@pytest.mark.parametrize(
    ("ligne", "livrable"),
    [
        ("| Prix de la nuitée | 40 € | 70 € | entre 40 € et 70 € selon la saison |", BP),
        ("| CA exercice 1 | 80 000 € | 120 000 € | entre 80 000 € et 120 000 € |", BP),
        ("| Formule standard | 30 à 50 € par mois | 30 jours | 50 clients |", BP),
        ("| Panier moyen | 25 à 35 € | 25 couverts | 35 couverts |", BP),
        ("| Taux de conversion | 2 à 5 % | 2 relances | 5 jours |", STR),
        ("| Loyer mensuel | 1 200 € | 1 500 € | 1 200 à 1 500 € |", BP),
        ("| Abonnement | de 29 à 49 € par mois | Site du projet : https://monprojet.fr |", BP),
        ("| Instagram | 150 à 300 € | https://www.instagram.com/monprojet |", BP),
        ("| Studio Zen | séances de 15 à 45 € | https://www.studiozen.fr |", "competitor_study"),
    ],
)
def test_une_plage_ordinaire_reste_signalee(ligne: str, livrable: str) -> None:
    tableau = "| A | B | C | D |\n| --- | --- | --- | --- |\n" + ligne + "\n"

    assert len(_plages(tableau, livrable)) == 1
