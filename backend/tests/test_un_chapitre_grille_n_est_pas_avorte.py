"""Un chapitre n'est pas avorté parce qu'il tient le format qu'on lui a demandé.

26/10/2026, répétition à blanc d'une étude de marché. Le gate déclarait le
chapitre 9 (« Les 12 chiffres clés ») avorté : 124 mots pour un plancher de
135, soit 40 % de la médiane du document.

Or ce chapitre n'a **aucun bloc de paragraphe** au modèle de référence —
mesuré : `dosage_attendu(chapitre_du_modele(9)).signes == 0`. C'est une GRILLE
de douze chiffres. On lui reprochait de ne pas avoir écrit une prose que la
consigne ne lui demande pas, en le comparant à des chapitres d'analyse.

Deux contrôles du dépôt visaient deux cibles incompatibles sur le même
chapitre (règle 9). Le plancher relatif ne dépasse donc plus la part attendue
du volume PROPRE du chapitre ; le plancher absolu, lui, reste et tient le fond.
"""
from __future__ import annotations

from generation.checks_evangeline import (
    _PLANCHER_ABSOLU_MOTS,
    detecter_chapitres_avortes,
)

#: Des chapitres d'analyse, assez longs pour hisser la médiane.
_PROSE = "mot " * 400
#: Le chapitre de grille : court, et conforme à ce qu'on lui demande.
_GRILLE = "mot " * 124


def _document(grille: str) -> list[tuple[int, str, str, int]]:
    return [
        (1, "Analyse", _PROSE, 1800),
        (2, "Analyse", _PROSE, 1800),
        (9, "Les 12 chiffres clés", grille, 1200),
        (10, "Analyse", _PROSE, 1800),
    ]


def test_le_defaut_mesure_ne_se_produit_plus() -> None:
    """Le modèle ne demande aucune prose au chapitre 9 : il n'est pas avorté."""
    avortes = detecter_chapitres_avortes(_document(_GRILLE), {9: 0})
    assert avortes == [], [str(a) for a in avortes]


def test_sans_volume_de_reference_le_comportement_d_avant_tient() -> None:
    """Le contrôle qui échoue sur le code d'avant.

    Sans la table des volumes, le chapitre est comparé à ses voisins et
    déclaré avorté — c'est exactement ce que faisait le gate avant ce
    correctif, et ce que la répétition à blanc a refusé.
    """
    avortes = detecter_chapitres_avortes(_document(_GRILLE))
    assert [a.chapitre for a in avortes] == [9]


def test_une_grille_reellement_vide_reste_avortee() -> None:
    """Contre-épreuve (règle 1) : le plancher absolu tient toujours le fond.

    Un chapitre de grille qui ne porte presque rien reste signalé — sinon le
    correctif aurait ouvert un trou là où il fermait une fausse alerte.
    """
    presque_vide = "mot " * (_PLANCHER_ABSOLU_MOTS - 30)
    avortes = detecter_chapitres_avortes(_document(presque_vide), {9: 0})
    assert [a.chapitre for a in avortes] == [9]
    assert avortes[0].mots_attendus == _PLANCHER_ABSOLU_MOTS


def test_un_chapitre_de_prose_garde_son_plancher_de_voisinage() -> None:
    """Contre-épreuve : le correctif ne relâche rien sur les chapitres d'analyse.

    Un chapitre dont le modèle attend une vraie prose, rendu très court, reste
    avorté — le plancher des voisins continue de s'appliquer.
    """
    document = _document(_GRILLE)
    document[1] = (2, "Analyse", "mot " * 130, 1800)
    # 2 400 signes attendus ≈ 400 mots : sa part propre (160) dépasse le
    # plancher des voisins, qui reste donc la référence.
    avortes = detecter_chapitres_avortes(document, {9: 0, 2: 2400})
    assert [a.chapitre for a in avortes] == [2]


def test_le_modele_de_reference_ne_demande_aucune_prose_au_chapitre_9() -> None:
    """La prémisse du correctif, verrouillée sur le VRAI fichier de référence.

    Tout tient à ce zéro : si un jour le modèle donne des paragraphes au
    chapitre 9, le traitement d'exception ci-dessus n'a plus lieu d'être et
    doit tomber avec lui. Un commentaire ne l'aurait pas dit (règle 6).
    """
    from generation.modele.chargement import chapitre_du_modele, dosage_attendu

    chapitre = chapitre_du_modele(9)
    assert chapitre is not None
    assert dosage_attendu(chapitre).signes == 0


def test_les_chapitres_d_analyse_gardent_un_volume_attendu() -> None:
    """Contre-épreuve : le zéro du chapitre 9 est une EXCEPTION, pas la règle.

    Si `signes_comparables` rendait zéro partout — fichier manquant, API
    changée —, le plancher tomberait au plancher absolu sur toute l'étude et le
    contrôle serait désarmé en silence. Ce test l'interdit.
    """
    from generation.modele.chargement import chapitre_du_modele, dosage_attendu

    volumes = [
        dosage_attendu(c).signes
        for numero in (1, 2, 6, 18)
        if (c := chapitre_du_modele(numero)) is not None
    ]
    assert len(volumes) == 4, volumes
    assert all(v > 500 for v in volumes), volumes


def test_les_volumes_du_modele_ne_couvrent_que_les_livrables_connus() -> None:
    """`_volumes_du_modele` rend la table pour une EM, et vide pour le reste.

    Le chemin de production n'était couvert par aucun test : son `except`
    rend un dictionnaire vide, donc l'ancien comportement, sans que rien ne le
    dise (règle 1).
    """
    from types import SimpleNamespace
    from typing import Any, cast

    from catalog.models import DeliverableType
    from generation.gate import _volumes_du_modele

    # `_volumes_du_modele` ne lit que `deliverable_type`, `id` et `number` :
    # une doublure suffit, et évite de monter une base pour un calcul pur.
    sections = tuple(SimpleNamespace(number=n) for n in (1, 9, 18))
    em = SimpleNamespace(deliverable_type=DeliverableType.MARKET_STUDY, id="x")
    volumes = _volumes_du_modele(cast("Any", em), cast("Any", sections))
    assert volumes.get(9) == 0, volumes
    assert volumes.get(1, 0) > 500, volumes
