"""Les deux dernières familles de calculs que la cliente avait nommées.

Sa liste, mot pour mot : « vérifier automatiquement tous les calculs simples :
pourcentages, ratios, taux de conversion, marges, évolutions, parts de marché,
additions, moyennes et projections ». Les six premières étaient couvertes.
Restaient la **moyenne** — un total rapporté à un effectif — et la
**projection** — un montant de période extrapolé à une période plus longue.

## Ce que ce fichier verrouille surtout : la contre-épreuve

Six des douze défauts trouvés en production sur ce projet venaient de mes
propres contrôles, pas des documents. Un motif faux coûte plus cher qu'un
contrôle absent : il déclenche une réécriture payante sur une phrase juste, et
il envoie la cliente relire un défaut qui n'existe pas.

La moitié « doit passer » de ce fichier pèse donc autant que l'autre. Elle
contient trois pièges qui ont vraiment failli être écrits :

- **le changement d'unité** — « 320 k€ pour 40 000 clients, soit 8 € ». Sans
  conversion, le code calcule 0,008 et crie faux. Ce serait commettre en le
  cherchant exactement le défaut qui a motivé le module ;
- **le jour et la semaine** — « 1 000 € par jour, soit 300 000 € par an » est
  JUSTE pour un commerce fermé le dimanche et en août. Multiplier par 365
  serait imposer une hypothèse d'exploitation au rédacteur ;
- **la phrase qui ne pose aucune opération** — « la part de marché atteint
  0,2 % » n'a pas de termes à recouper. On s'abstient.

Et une leçon de méthode, payée en écrivant ce fichier : la première version de
la contre-épreuve écrivait « reparti sur » sans accent. Le motif ne
reconnaissait donc rien, et les deux moitiés du test passaient — celle qui
devait tomber comme celle qui devait passer. Un test vert qui ne compare rien
est un échec déguisé, c'est la règle 1 du dépôt appliquée à sa propre suite.
Chaque cas « doit tomber » ci-dessous est là pour prouver que le motif MORD.
"""
from __future__ import annotations

import pytest

from generation.arithmetique import verifier

# ── Ce que le contrôle doit trouver ──────────────────────────────────────────

FAUTES = [
    pytest.param(
        "Un chiffre d'affaires de 320 000 euros pour 40 000 clients, "
        "soit un panier moyen de 12 euros.",
        "Moyenne",
        id="panier-moyen-faux",
    ),
    pytest.param(
        "Le total de 90 000 euros réparti sur 300 adhérents, "
        "soit une cotisation moyenne de 250 euros.",
        "Moyenne",
        id="cotisation-moyenne-fausse",
    ),
    pytest.param(
        "Un loyer de 2 500 euros par mois, soit 25 000 euros par an.",
        "Projection",
        id="mois-vers-an",
    ),
    pytest.param(
        "Une marge de 12 000 euros par trimestre, soit 60 000 euros par an.",
        "Projection",
        id="trimestre-vers-an",
    ),
    pytest.param(
        "Une charge de 8 000 euros par mois sur 18 mois, soit 200 000 euros.",
        "Projection",
        id="duree-dite-en-clair",
    ),
]


@pytest.mark.parametrize(("phrase", "nature"), FAUTES)
def test_une_operation_fausse_est_trouvee(phrase: str, nature: str) -> None:
    """Le motif doit MORDRE : sans ça, la moitié « doit passer » ne prouve rien."""
    fautes = verifier(phrase)
    assert [f.nature for f in fautes] == [nature], (
        f"« {phrase} » pose une opération fausse et rien ne l'a vue"
    )


# ── Ce que le contrôle ne doit PAS trouver ───────────────────────────────────

CORRECTES = [
    pytest.param(
        "Un chiffre d'affaires de 320 000 euros pour 40 000 clients, "
        "soit un panier moyen de 8 euros.",
        id="panier-moyen-juste",
    ),
    pytest.param(
        "Un chiffre d'affaires de 320 k€ pour 40 000 clients, "
        "soit un panier moyen de 8 €.",
        id="unites-differentes-le-calcul-tient",
    ),
    pytest.param(
        "Le total de 90 000 euros réparti sur 300 adhérents, "
        "soit une cotisation moyenne de 300 euros.",
        id="cotisation-moyenne-juste",
    ),
    pytest.param(
        "Un loyer de 2 500 euros par mois, soit 30 000 euros par an.",
        id="mois-vers-an-juste",
    ),
    pytest.param(
        "Un loyer de 2,5 k€ par mois, soit 30 000 € par an.",
        id="projection-a-unites-differentes",
    ),
    pytest.param(
        "Une marge de 12 000 euros par trimestre, soit 48 000 euros par an.",
        id="trimestre-vers-an-juste",
    ),
    pytest.param(
        "Une charge de 8 000 euros par mois sur 18 mois, soit 144 000 euros.",
        id="duree-juste",
    ),
    pytest.param(
        "Une recette de 1 000 euros par jour, soit 300 000 euros par an.",
        id="le-jour-cache-une-hypothese-on-ne-juge-pas",
    ),
    pytest.param(
        "Un flux de 500 euros par semaine, soit 24 000 euros par an.",
        id="la-semaine-aussi",
    ),
    pytest.param(
        "Le chiffre d'affaires de 320 000 euros pour 40 000 clients est stable.",
        id="aucune-operation-posee",
    ),
    pytest.param(
        "La part de marché atteint 0,2 %.",
        id="un-resultat-sans-ses-termes",
    ),
]


@pytest.mark.parametrize("phrase", CORRECTES)
def test_une_phrase_juste_traverse_le_controle(phrase: str) -> None:
    """Un motif sur une phrase correcte coûte une réécriture payante."""
    fautes = verifier(phrase)
    assert not fautes, (
        f"« {phrase} » est juste, et le contrôle a pourtant écrit : {fautes[0]}"
    )


def test_le_motif_de_projection_ouvre_la_porte_a_la_saisonnalite() -> None:
    """Un glacier ne tourne pas douze mois — le motif lui demande de l'écrire.

    Sans cette phrase, la seule issue offerte au rédacteur serait de changer un
    chiffre exact. Le motif doit demander la précision manquante, pas un faux.
    """
    fautes = verifier("Un loyer de 2 500 euros par mois, soit 25 000 euros par an.")
    assert fautes
    assert "ne tourne pas sur toute la période" in str(fautes[0])
