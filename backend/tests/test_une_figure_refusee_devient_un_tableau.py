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
    """Le lecteur doit savoir ce qu'il regarde : le titre demandé reste.

    En LÉGENDE, au-dessus du tableau, depuis le 29/09/2026 : passé comme source,
    il se serait lu « Source : Diagnostic de maturité » une fois les sources
    annoncées comme telles.
    """
    blocs, _ = _rendre(Graphique(
        type_graphique=TypeGraphique.RADAR,
        titre="Diagnostic de maturité",
        donnees_ids=["ca_actuel", "abonnes"],
    ))
    assert blocs[0]["titre"] == "Diagnostic de maturité"
    assert blocs[0]["source"] != "Diagnostic de maturité"


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


# ── Business plan `29d59ae9` (19/11/2026) : un repli qui ne fait que répéter ─


def _refusee() -> Graphique:
    return Graphique(
        type_graphique=TypeGraphique.BARRES,
        titre="Repères économiques actuels",
        donnees_ids=["ca_actuel", "abonnes"],
    )


def _rendre_avec(
    *lignes_du_chapitre: str, abonnes: float = 14.0,
) -> tuple[list[dict[str, Any]], assemblage.RapportAssemblage]:
    """Les données : 120 000 € et `abonnes`, toutes deux de 2026."""
    socle = _socle()
    socle.donnees[1] = socle.donnees[1].model_copy(update={"valeur": abonnes})
    rapport = assemblage.RapportAssemblage()
    blocs = assemblage._blocs_graphique(
        socle, [_refusee()], secteurs.profil_du_secteur(socle.secteur), rapport,
        "Chapitre 5",
        lignes_ecrites=[assemblage.nombres_ecrits(ligne) for ligne in lignes_du_chapitre],
    )
    return blocs, rapport


def test_un_repli_entierement_repete_sur_une_meme_ligne_n_est_pas_imprime() -> None:
    blocs, rapport = _rendre_avec("2026 | 120 000 € | 1 400", abonnes=1_400.0)
    assert blocs == []
    assert rapport.graphiques_en_double
    assert "déjà dans un tableau" in rapport.graphiques_en_double[0]


def test_un_petit_nombre_retrouve_ne_suffit_pas() -> None:
    """« 14 » se retrouve par hasard : le repli reste imprimé."""
    blocs, _ = _rendre_avec("2026 | 120 000 € | 14")
    assert [b["type"] for b in blocs] == ["tableau"]


def test_un_montant_retrouve_sans_son_annee_ne_suffit_pas() -> None:
    """Contre-épreuve : les mêmes montants, sur une ligne d'un autre exercice."""
    blocs, rapport = _rendre_avec("2028 | 120 000 € | 1 400", abonnes=1_400.0)
    assert [b["type"] for b in blocs] == ["tableau"]
    assert len(rapport.graphiques_en_tableau) == 1


def test_un_repli_qui_apporte_un_chiffre_reste_imprime() -> None:
    """Contre-épreuve : une seule valeur absente des tableaux suffit."""
    blocs, _ = _rendre_avec("2026 | 120 000 €", abonnes=1_400.0)
    assert [b["type"] for b in blocs] == ["tableau"]


# ── Même dossier : un tableau du chapitre, deux arrondis ────────────────────


def test_les_montants_d_un_tableau_du_chapitre_prennent_le_meme_arrondi() -> None:
    lignes = [
        ["Vin de vigneron", "22,60 €", "Prix observé"],
        ["Champagne de vigneron", "39 €", "Prix observé"],
        ["Cidre fermier", "19 €", "Prix observé"],
    ]
    sortie = assemblage.lignes_au_meme_arrondi(lignes)
    assert [ligne[1] for ligne in sortie] == ["22,60 €", "39,00 €", "19,00 €"]
    assert [ligne[2] for ligne in sortie] == ["Prix observé"] * 3


def test_une_phrase_dans_une_cellule_ne_change_pas() -> None:
    """Contre-épreuve : une cellule qui est une phrase, et un tableau homogène."""
    phrase = "Campagne de lancement 6 000 € + charges fixes 9 433 €"
    lignes = [["Janvier", phrase, "12 300,50 €"], ["Février", "x", "13 200 €"]]
    sortie = assemblage.lignes_au_meme_arrondi(lignes)
    assert sortie[0][1] == phrase
    assert sortie[1][2] == "13 200,00 €"
    homogene = [["A", "19 €"], ["B", "39 €"]]
    assert assemblage.lignes_au_meme_arrondi(homogene) == homogene
