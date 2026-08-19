"""Un meme nombre de concurrents du debut a la conclusion.

## Le defaut, releve par la cliente le 18/08/2026

Etude de concurrence `743e6a2b`. Dans le MEME document :

    chapitre 1 : « Onze acteurs : huit concurrents directs et trois indirects »
                 « figee pour la suite : aucun chapitre n'y ajoute ni n'y retire »
    ailleurs   : « Neuf acteurs identifies avec un site officiel verifiable »
    ailleurs   : « un marche a sept acteurs directs reellement actifs »

Onze, dix, sept. Son mot : « un meme scenario, un meme taux, un meme chiffre de
marche ou un meme nombre de concurrents doit rester identique du debut a la
conclusion ».

## La cause, et elle vient du correctif precedent

Deux regles justes avaient ete ajoutees le meme jour — une categorie n'est pas
une entreprise, deux offres d'un meme operateur comptent pour une — et chaque
chapitre en tirait SON total. Les trois comptes sont justes separement, et se
contredisent ensemble.

On ne demande donc plus au modele de compter : on lui DONNE les nombres.
"""
from __future__ import annotations

import pytest

from generation.chapitres.runner import _bloc_concurrents
from generation.socle.schema import Concurrent, Socle, Zone


def _socle(concurrents: list[Concurrent]) -> Socle:
    return Socle(secteur="conseil IA", zone=Zone(pays="France"),
                 date_socle="2026-08-19", concurrents=concurrents)


BASE = [
    Concurrent(nom="Croissance & Transitions", type="direct", site_web="ct.fr"),
    Concurrent(nom="Dust", type="direct", site_web="dust.tt"),
    Concurrent(nom="Findle", type="direct", site_web="findle.fr"),
    Concurrent(nom="Agences no-code + IA pour PME", type="direct", site_web=""),
    Concurrent(nom="Jedha", type="indirect", site_web="jedha.co"),
]


def test_le_bloc_donne_un_decompte_unique() -> None:
    """Echoue sur le code d'avant : aucun total n'etait fourni, seulement deux
    regles de comptage que chaque chapitre appliquait a sa facon."""
    bloc = _bloc_concurrents(_socle(BASE))
    assert "DÉCOMPTE DE RÉFÉRENCE" in bloc
    assert "5 acteurs au total" in bloc
    assert "4 directs et 1 indirects" in bloc
    assert "4 entreprises identifiées" in bloc
    assert "1 catégorie d'acteurs" in bloc


def test_le_bloc_interdit_tout_autre_compte() -> None:
    """Le « sept acteurs reellement actifs » qui contredisait le chapitre 1."""
    bloc = _bloc_concurrents(_socle(BASE))
    assert "N'en calcule aucun autre" in bloc
    assert "réellement actifs" in bloc
    assert "du premier chapitre à la conclusion" in bloc


def test_l_ancienne_consigne_ambigue_a_disparu() -> None:
    """Echoue sur le code d'avant.

    « Une phrase qui annonce un nombre de concurrents COMPTE les entreprises,
    pas les categories » : c'est cette phrase qui autorisait un chapitre a
    ecrire « neuf » quand le chapitre 1 avait ecrit « onze ».
    """
    bloc = _bloc_concurrents(_socle(BASE))
    assert "COMPTE les entreprises, pas les catégories" not in bloc


def test_une_base_sans_categorie_ne_recoit_pas_de_decompte() -> None:
    """Contre-epreuve : rien a desambiguier, donc pas de bloc en plus."""
    bloc = _bloc_concurrents(_socle([
        Concurrent(nom="Findle", type="direct", site_web="findle.fr"),
        Concurrent(nom="Jedha", type="indirect", site_web="jedha.co"),
    ]))
    assert "DÉCOMPTE DE RÉFÉRENCE" not in bloc


@pytest.mark.parametrize("nb_categories", [1, 2])
def test_l_accord_suit_le_nombre(nb_categories: int) -> None:
    """Contre-epreuve de forme : le livrable de la cliente parle francais."""
    extra = [Concurrent(nom=f"Categorie {i}", type="direct", site_web="")
             for i in range(nb_categories)]
    bloc = _bloc_concurrents(_socle(BASE[:3] + extra))
    attendu = "catégorie d'acteurs" if nb_categories == 1 else "catégories d'acteurs"
    assert attendu in bloc
