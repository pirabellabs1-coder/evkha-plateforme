"""Une note de provenance fausse ne doit pas coûter tout un livrable.

## Le défaut, mesuré

17/08/2026, étude de concurrence `8cc1be56` :

    Socle non établi : Socle non recevable après 3 tentative(s) :
    `marche_regional_taille` déclare dériver de `ca_moyen_concurrent`,
    absent du socle.

Zéro chapitre, zéro centime, un livrable perdu avant d'exister. Les deux
données sont FACULTATIVES au référentiel : le modèle a produit la première en
annotant sa provenance, sans fournir la seconde — et il a refait exactement le
même geste aux trois tentatives, la reprise ne le corrigeant pas.

## L'arbitrage

`derivee_de` est une annotation de PROVENANCE, pas une valeur. Quand elle
pointe vers rien, c'est l'annotation qui est fausse, pas le chiffre. Refuser
revient à jeter un socle entier pour une note de bas de page.

Le dépôt avait déjà tranché ce dilemme pour la grille de notation : sur les
premières tentatives le refus fait corriger le modèle, mais à la dernière il
tue l'étude — c'est arrivé à `6a44baff` le 10/08/2026. La filiation n'avait
jamais été branchée sur ce même `dernier_recours`.

## Ce que le test verrouille

Que la réparation retire le lien invérifiable ET conserve les liens valides.
Une réparation qui viderait `derivee_de` d'un coup passerait le premier test
et perdrait toute la traçabilité du socle — c'est la manière discrète de
casser une réparation.
"""
from __future__ import annotations

from generation.socle.schema import reparer_les_filiations


class _Donnee:
    """Le strict nécessaire : un identifiant et ses parents déclarés."""

    def __init__(self, identifiant: str, derivee_de: list[str]) -> None:
        self.id = identifiant
        self.derivee_de = derivee_de


class _Socle:
    def __init__(self, donnees: list[_Donnee]) -> None:
        self.donnees = donnees

    @property
    def identifiants(self) -> set[str]:
        return {d.id for d in self.donnees}


def test_le_lien_vers_une_donnee_absente_est_retire() -> None:
    """Le cas exact de l'étude 8cc1be56."""
    socle = _Socle([
        _Donnee("marche_national_taille", []),
        _Donnee("marche_regional_taille", ["ca_moyen_concurrent"]),
    ])
    orphelines = reparer_les_filiations(socle)  # type: ignore[arg-type]
    assert orphelines == ["marche_regional_taille ← ca_moyen_concurrent"]
    assert socle.donnees[1].derivee_de == []


def test_la_donnee_elle_meme_reste_debout() -> None:
    """Retirer la provenance, pas le chiffre : le socle garde ses données."""
    socle = _Socle([
        _Donnee("marche_national_taille", []),
        _Donnee("marche_regional_taille", ["ca_moyen_concurrent"]),
    ])
    reparer_les_filiations(socle)  # type: ignore[arg-type]
    assert socle.identifiants == {"marche_national_taille", "marche_regional_taille"}


def test_les_filiations_valides_survivent() -> None:
    """Sans ce test, vider `derivee_de` passerait pour un correctif.

    Ce serait perdre toute la traçabilité du socle en réparant un lien.
    """
    socle = _Socle([
        _Donnee("nb_concurrents_directs", []),
        _Donnee("nb_acteurs_zone", []),
        _Donnee("part_marche_leader", ["nb_acteurs_zone", "ca_moyen_concurrent"]),
    ])
    orphelines = reparer_les_filiations(socle)  # type: ignore[arg-type]
    assert orphelines == ["part_marche_leader ← ca_moyen_concurrent"]
    assert socle.donnees[2].derivee_de == ["nb_acteurs_zone"]


def test_un_socle_sain_n_est_pas_touche() -> None:
    socle = _Socle([
        _Donnee("nb_acteurs_zone", []),
        _Donnee("part_marche_leader", ["nb_acteurs_zone"]),
    ])
    assert reparer_les_filiations(socle) == []  # type: ignore[arg-type]
    assert socle.donnees[1].derivee_de == ["nb_acteurs_zone"]
