"""Le rappel de fin de consigne ne cite que des repères de CETTE étude.

29/09/2026 : le rappel des repères (`eab7535`) donnait deux exemples écrits en
dur, dont `{{resultat_net_mensuel_an3}}`. Une étude de marché n'a pas de
résultat net : le modèle aurait recopié un repère absent de sa mémoire, et le
contrôle l'aurait puni comme repère inconnu — une reprise payée pour une
consigne fausse.
"""
from __future__ import annotations

from generation.chapitres.runner import rappel_des_reperes
from generation.memoire.etude import MemoireEtude
from generation.memoire.faits import Fait
from generation.memoire.reperes import REPERE


def _fait(identifiant: str) -> Fait:
    return Fait(id=identifiant, valeur=1000.0, unite="EUR", libelle=identifiant, origine="sourcee")


def _memoire(*identifiants: str) -> MemoireEtude:
    return MemoireEtude(faits={i: _fait(i) for i in identifiants})


def test_une_etude_sans_resultat_net_ne_se_le_voit_pas_proposer() -> None:
    memoire = _memoire("taille_marche_france", "panier_moyen")
    rappel = rappel_des_reperes(memoire)
    cites = REPERE.findall(rappel)
    assert cites, "le rappel donne des exemples"
    assert set(cites) <= set(memoire.faits), cites
    assert "CAF" not in rappel


def test_un_business_plan_voit_ses_propres_reperes() -> None:
    """Contre-épreuve : les exemples d'un business plan restent ceux du chiffre d'affaires."""
    memoire = _memoire(
        "ca_previsionnel_an1", "resultat_net_an1", "caf_an1", "resultat_net_mensuel_an1",
    )
    rappel = rappel_des_reperes(memoire)
    assert set(REPERE.findall(rappel)) == {"ca_previsionnel_an1", "resultat_net_mensuel_an1"}
    assert "le résultat net n'est pas la CAF" in rappel


def test_une_memoire_vide_ne_cite_aucun_repere() -> None:
    assert REPERE.findall(rappel_des_reperes(_memoire())) == []
