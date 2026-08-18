"""Une trajectoire ne change pas d'arrivee en cours de document.

## Le defaut, releve par la cliente le 18/08/2026

Etude de marche `f0064333` : « il y a une incoherence importante entre 600 et
800 adherents en annee 3. Il faut choisir une seule trajectoire et la reprendre
partout de maniere identique. »

Mesure : « 400 puis 600 adherents » huit fois, « 400 puis 800 adherents » UNE
fois, dans un encadre LECTURE. Un intrus isole contre une trajectoire coherente
partout ailleurs.

## Ce qui a ete essaye avant, et pourquoi c'etait faux

Reperer une valeur RARE contre une valeur dominante pour un meme nom. Mesuree
sur les quatre livrables, cette approche rendait TROIS faux pour un vrai :

    « Moins de 300 adherents actifs au bout de neuf mois »
    « 100 a 150 adherents recrutes sur ce segment en annee 1 »
    « Au-dela de 500 avocats actifs »

Des seuils et des fourchettes, pas des trajectoires. Les distinguer d'une
affirmation demandait une analyse grammaticale hors de portee d'une expression
reguliere ; un filtre sur les comparateurs n'en rattrapait qu'un.

## Ce qui marche

On oppose une PAIRE a une paire, pas un nombre a un nombre. Un seuil n'a pas de
paire ; une fourchette n'a pas le mot « puis ». Aucun des deux ne peut entrer,
sans qu'on ait eu a les reconnaitre.
"""
from __future__ import annotations

import pytest

from generation.arithmetique import trajectoires_divergentes


def test_les_deux_trajectoires_du_dossier_sont_signalees() -> None:
    """Les phrases EXACTES de l'etude de marche livree.

    Echoue sur le code d'avant : aucun controle ne comparait deux trajectoires.
    """
    document = [
        "La trajectoire du centre pilote — 400 puis 600 adhérents en année 3 — "
        "dépend d'un taux de capture de 0,02 %.",
        "Le scénario central reste atteignable avec un objectif de 400 puis "
        "600 adhérents en année 3.",
        "La croissance de 6 % par an et la marge de progression rendent "
        "l'objectif de 400 puis 800 adhérents statistiquement crédible.",
    ]
    motifs = trajectoires_divergentes(document)
    assert len(motifs) == 1
    m = motifs[0]
    assert (m.depart, m.dominante, m.intruse) == (400, 600, 800)
    assert m.quoi == "adhérents"
    assert m.chapitre == 2, "le motif doit designer le chapitre de l'INTRUS"
    assert "800" in str(m) and "600" in str(m)


def test_une_trajectoire_coherente_ne_declenche_rien() -> None:
    """Contre-epreuve : le meme document, sans l'intrus."""
    assert trajectoires_divergentes([
        "Trajectoire de 400 puis 600 adhérents en année 3.",
        "L'objectif reste 400 puis 600 adhérents.",
        "Le plan vise 400 puis 600 adhérents à trois ans.",
    ]) == []


@pytest.mark.parametrize("phrase", [
    "Moins de 300 adhérents actifs au bout de neuf mois déclenchent l'alerte.",
    "100 à 150 adhérents recrutés sur ce segment en année 1.",
    "Au-delà de 500 avocats actifs, le suivi individuel sature.",
    "Le panier moyen annuel de 1 200 euros par adhérent reste la référence.",
])
def test_un_seuil_ou_une_fourchette_n_est_pas_une_trajectoire(phrase: str) -> None:
    """Contre-epreuve, et c'est elle qui a fait ecarter la premiere version.

    Ces quatre phrases viennent des livrables reels. La version « valeur rare
    contre valeur dominante » en signalait trois.
    """
    document = [
        "Trajectoire de 400 puis 600 adhérents en année 3.",
        "L'objectif reste 400 puis 600 adhérents.",
        phrase,
    ]
    assert trajectoires_divergentes(document) == []


def test_deux_trajectoires_de_departs_differents_coexistent() -> None:
    """Contre-epreuve : un document peut porter plusieurs trajectoires.

    « 400 puis 600 adhérents » et « 15 puis 90 avocats » ne se contredisent
    pas — elles ne parlent ni de la meme chose ni du meme depart.
    """
    assert trajectoires_divergentes([
        "Trajectoire de 400 puis 600 adhérents en année 3.",
        "Montée de 15 puis 90 avocats actifs en fin d'année 1.",
    ]) == []


def test_le_motif_est_reparable_par_la_boucle() -> None:
    from generation.correction import _CHAPTER_LEVEL_CHECKS, _CHECK_LABELS

    assert "trajectoire_divergente" in _CHAPTER_LEVEL_CHECKS
    assert "trajectoire_divergente" in _CHECK_LABELS
