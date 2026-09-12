"""Une figure que le rendu refuse laisse ses données, pas un trou.

Stratégie Zenitek, reprise `b098ded3` du 12/09/2026 : **31 figures demandées,
31 refusées, zéro rendue**. Le document est parti sans une seule figure, et le
contrôle l'a retenu pour cette raison — un dossier en attente d'une main qui ne
pouvait rien, puisque l'administrateur ne réécrit pas le document.

Les motifs de refus étaient tous de forme, jamais de fond : « unités
hétérogènes : EUR, unite » (le modèle mêle un montant et un effectif dans la
même figure), « le radar exige des notes », « un seul chiffre ». Les DONNÉES,
elles, venaient du socle et étaient justes.

On imprime donc ces données en tableau. Le lecteur garde l'information ; il ne
perd que le dessin. Ces tests échouent sur le code d'avant, où le bloc était
purement et simplement abandonné.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from generation.chapitres.schema import Graphique, TypeGraphique
from generation.rendu_word import assemblage, secteurs
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone


def _socle() -> Socle:
    return Socle(
        secteur="assistance informatique",
        zone=Zone(pays="France"),
        date_socle=date(2026, 9, 12),
        donnees=[
            DonneeSocle(
                id="ca_actuel", libelle="Chiffre d'affaires actuel", valeur=120000.0,
                unite="EUR", annee=2026, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.DECLAREE,
            ),
            DonneeSocle(
                id="abonnes", libelle="Abonnés actifs", valeur=14.0,
                unite="unite", annee=2026, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.DECLAREE,
            ),
        ],
    )


def _rendre(graphique: Graphique) -> tuple[list[dict[str, Any]], assemblage.RapportAssemblage]:
    socle = _socle()
    rapport = assemblage.RapportAssemblage()
    blocs = assemblage._blocs_graphique(
        socle, [graphique], secteurs.profil_du_secteur(socle.secteur), rapport, "Chapitre 5",
    )
    return blocs, rapport


def test_des_unites_heterogenes_donnent_un_tableau() -> None:
    """Le cas le plus fréquent : un montant et un effectif dans la même figure."""
    blocs, rapport = _rendre(Graphique(
        type_graphique=TypeGraphique.BARRES,
        titre="Repères économiques actuels",
        donnees_ids=["ca_actuel", "abonnes"],
    ))

    assert rapport.graphiques_rendus == 0
    assert len(rapport.graphiques_abandonnes) == 1
    assert len(rapport.graphiques_en_tableau) == 1
    assert [b["type"] for b in blocs] == ["tableau"]
    assert blocs[0]["entetes"] == ["Donnée", "Valeur", "Unité", "Année"]
    valeurs = {ligne[0] for ligne in blocs[0]["lignes"]}
    assert valeurs == {"Chiffre d'affaires actuel", "Abonnés actifs"}


def test_le_tableau_de_repli_porte_le_titre_de_la_figure() -> None:
    """Le lecteur doit savoir ce qu'il regarde : le titre demandé reste."""
    blocs, _ = _rendre(Graphique(
        type_graphique=TypeGraphique.RADAR,
        titre="Diagnostic de maturité",
        donnees_ids=["ca_actuel", "abonnes"],
    ))
    assert blocs[0]["source"] == "Diagnostic de maturité"


def test_une_figure_dont_le_socle_ignore_tout_ne_laisse_rien() -> None:
    """CONTRE-ÉPREUVE : un tableau vide serait pire que pas de tableau."""
    blocs, rapport = _rendre(Graphique(
        type_graphique=TypeGraphique.BARRES,
        titre="Chiffres que le socle ne porte pas",
        donnees_ids=["inconnu_1", "inconnu_2"],
    ))

    assert blocs == []
    assert rapport.graphiques_en_tableau == []
    assert len(rapport.graphiques_abandonnes) == 1
