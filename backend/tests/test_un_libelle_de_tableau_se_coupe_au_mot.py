"""Un libellé de tableau se coupe entre deux mots, et la coupe se voit.

29/09/2026, business plan ÉCLORE : des cellules coupées au milieu d'un mot,
sans points de suspension (§ 3.14 du diagnostic). Deux coupes dans notre code :

- le tableau de repli d'une figure refusée tranchait le libellé à 110 signes
  (`assemblage._tableau_de_repli`, `[:110]`) ;
- l'annexe des chiffres gardait ce qui précède le premier POINT
  (`split(".")[0]`) : « Taux de marge brute (env. 62 %) » devenait « Taux de
  marge brute (env ».

Une seule manière de couper désormais (`texte.libelle_court`) : la première
phrase, bornée au mot, suivie de « … » quand elle a été raccourcie.

## Plus aucune coupe dans une cellule (30/09/2026)

Business plan ÉCLORE `28a257bf`, annexe des chiffres : « … les coûts de
session… ». La cliente : « aucune ligne de tableau tronquée par "…" ». La
première phrase du libellé s'écrit désormais ENTIÈRE ; la cellule passe à la
ligne. Ni mot tranché (29/09), ni points de suspension (30/09).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from docx import Document

from generation.chapitres.schema import Graphique, TypeGraphique
from generation.rendu_word import assemblage, secteurs
from generation.rendu_word.depuis_json import rendre_etude
from generation.rendu_word.texte import couper_au_mot, libelle_court
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone

#: 142 signes : la coupe dure à 110 laissait « … corrigé de l » — un mot
#: tranché, sans suspension.
LONG = (
    "Chiffre d'affaires prévisionnel des séjours bien-être en pleine nature, "
    "hors taxe et hors option, corrigé de la saisonnalité estivale observée"
)
ABREGE = "Taux de marge brute (env. 62 % du chiffre d'affaires)"


def _socle() -> Socle:
    def donnee(identifiant: str, libelle: str, valeur: float, unite: str) -> DonneeSocle:
        return DonneeSocle(
            id=identifiant, libelle=libelle, valeur=valeur, unite=unite, annee=2027,
            perimetre=Perimetre.ENTREPRISE, fiabilite=Fiabilite.DECLAREE,
        )

    return Socle(
        secteur="bien-être", zone=Zone(pays="France"), date_socle=date(2026, 9, 29),
        donnees=[
            donnee("ca_sejours", LONG, 180_000.0, "EUR"),
            donnee("taux_marge", ABREGE, 62.0, "%"),
            donnee("clients", "Clients accueillis", 1_200.0, "unite"),
        ],
    )


def test_le_tableau_de_repli_ne_coupe_plus_le_libelle() -> None:
    """Le défaut du 29/09 : « … corrigé de l » — un mot tranché, sans suspension.
    Celui du 30/09 : la coupe au mot, suivie de « … ». La cellule porte désormais
    le libellé entier."""
    assert LONG[:110].endswith("corrigé de l"), "le libellé d'essai doit dépasser 110 signes"
    socle = _socle()
    blocs = assemblage._blocs_graphique(
        socle,
        [Graphique(type_graphique=TypeGraphique.BARRES, titre="Repères du projet",
                   donnees_ids=["ca_sejours", "clients"])],
        secteurs.profil_du_secteur(socle.secteur),
        assemblage.RapportAssemblage(),
        "Chapitre 5",
    )
    tableau = next(b for b in blocs if b["type"] == "tableau")
    cellule = next(ligne[0] for ligne in tableau["lignes"] if ligne[0].startswith("Chiffre"))
    assert cellule == LONG, cellule
    assert not cellule.endswith("…"), cellule


def test_l_annexe_ne_coupe_pas_a_un_point_d_abreviation(tmp_path: Path) -> None:
    """« Taux de marge brute (env » : un point n'est pas une fin de phrase."""
    etude, _ = assemblage.assembler_etude(
        socle=_socle(), chapitres=[], titre="Business plan", marque={"nom": "ÉCLORE"},
    )
    document = Document(str(rendre_etude(etude, tmp_path / "annexe.docx")))
    donnees = [
        ligne.cells[0].text for table in document.tables
        if table.rows[0].cells[0].text == "Donnée" and len(table.columns) == 4
        for ligne in table.rows[1:]
    ]
    assert ABREGE in donnees, donnees
    longue = next(d for d in donnees if d.startswith("Chiffre"))
    assert longue == LONG, longue
    assert not any(d.endswith("…") for d in donnees), donnees


@pytest.mark.parametrize(
    ("texte", "plafond", "attendu"),
    [
        ("abc def ghi", 8, "abc def…"),
        ("abc def ghi", 6, "abc…"),
        ("abc def", 20, "abc def"),
        ("anticonstitutionnellement", 10, "anticonstitutionnellement"),
        ("Marché national, hors taxes", 20, "Marché national…"),
    ],
)
def test_couper_au_mot(texte: str, plafond: int, attendu: str) -> None:
    """Jamais un mot entamé — un seul mot trop long reste entier."""
    assert couper_au_mot(texte, plafond) == attendu


def test_un_libelle_court_traverse_intact() -> None:
    """CONTRE-ÉPREUVE : ni coupe, ni « … » sur ce qui tient déjà."""
    assert libelle_court("Chiffre d'affaires actuel.") == "Chiffre d'affaires actuel"
    assert libelle_court("Marché national. Source : Insee.") == "Marché national"


def test_un_libelle_long_garde_sa_premiere_phrase_entiere() -> None:
    """Le cas du 30/09 : la phrase dépasse 110 signes, elle reste entière."""
    assert libelle_court(f"{LONG}. Seconde phrase.") == LONG
