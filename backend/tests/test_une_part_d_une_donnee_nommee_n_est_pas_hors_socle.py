"""Un montant rapporté à une donnée du socle que la phrase NOMME n'est pas inventé.

## Le défaut mesuré

Corpus du 15/09/2026, business plans :

- `256e63d8` : « le seuil de rentabilité (19 674 euros, 36,3 % du chiffre
  d'affaires de l'année 1) » — 19 674 / 54 276 € ;
- `73dde3ab` : « une marge de sécurité de 55 000 euros représente environ
  20,8 % du seuil de rentabilité annuel » — 55 000 / 265 000 €.

Le dénominateur n'est pas écrit : il est nommé, et le socle le porte. Les
dérivations comparent au bit près, la part est arrondie à l'écriture : la part
juste était comptée comme un chiffre inventé.

## Ce qui reste signalé

- un rapport faux : « 28 000 euros, soit 8,7 % du chiffre d'affaires de
  385 000 euros » fait 7,3 % (`73dde3ab`) ;
- une part dont la grandeur n'est pas nommée (« 23 % du total ») ;
- une part sans montant dans sa phrase.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone
from generation.verification.controles import controler_chiffres_hors_socle
from generation.verification.lecture import DocumentLu, mesures_dans


def _donnee(identifiant: str, libelle: str, valeur: float) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=libelle, valeur=valeur, unite="EUR", annee=2026,
        perimetre=Perimetre.ENTREPRISE, fiabilite=Fiabilite.DECLAREE,
    )


def _socle() -> Socle:
    return Socle(
        secteur="boulangerie", zone=Zone(pays="France"), date_socle=date(2026, 9, 15),
        donnees=[
            _donnee("ca_previsionnel_an1", "Chiffre d'affaires prévisionnel — exercice 1", 54_276),
            _donnee("ca_previsionnel_an2", "Chiffre d'affaires prévisionnel — exercice 2", 385_000),
            _donnee("seuil_rentabilite", "Seuil de rentabilité annuel", 265_000),
            _donnee("besoin_total", "Besoin total de financement", 195_000),
            _donnee("seuil_an1", "Point mort de l'exercice 1", 19_674),
            _donnee("marge_securite", "Marge de sécurité", 55_000),
            _donnee("resultat_net_an2", "Résultat net — exercice 2", 28_000),
            _donnee("apport", "Apport personnel", 45_000),
        ],
    )


def _signales(phrase: str) -> set[str]:
    document = DocumentLu(chemin=Path("corpus.docx"), paragraphes=[phrase])
    document.mesures.extend(mesures_dans(phrase))
    return {
        a.detail.split("»")[0].strip("« ").strip()
        for a in controler_chiffres_hors_socle(document, _socle())
        if a.controle == "chiffres_hors_socle"
    }


@pytest.mark.parametrize(("phrase", "part"), [
    (
        "Un projet dont le seuil de rentabilité (19 674 euros, 36,3 % du chiffre "
        "d'affaires de l'année 1) est atteignable rapidement.",
        "36,3 %",
    ),
    (
        "Une marge de sécurité de 55 000 euros représente environ 20,8 % du seuil "
        "de rentabilité annuel.",
        "20,8 %",
    ),
    (
        "Apport personnel de 45 000 euros représentant 23 % du besoin total de "
        "financement.",
        "23 %",
    ),
])
def test_une_part_d_une_donnee_nommee_est_justifiee(phrase: str, part: str) -> None:
    assert part not in _signales(phrase)


@pytest.mark.parametrize(("phrase", "part"), [
    # CONTRE-ÉPREUVE du corpus : le rapport est faux.
    (
        "Le résultat net double presque en exercice 2 (28 000 euros, soit 8,7 % du "
        "chiffre d'affaires de 385 000 euros).",
        "8,7 %",
    ),
    # La grandeur n'est pas nommée : « total » seul ne désigne rien.
    ("Apport personnel de 45 000 euros, soit 23 % du total.", "23 %"),
    # Aucun montant dans la phrase.
    ("Le point mort représente 36,3 % du chiffre d'affaires de l'année 1.", "36,3 %"),
    # Relecture du 15/09/2026 : les bornes que la première version n'avait pas.
    # L'exercice nommé n'est pas celui de la donnée (28 000 / 54 276 € = 51,6 %).
    ("Le résultat net de 28 000 euros atteint 51,6 % du chiffre d'affaires de l'année 2.",
     "51,6 %"),
    # Le dénominateur est ÉCRIT : c'est lui qui juge, pas le socle.
    ("Le résultat net de 28 000 euros, soit 51,6 % du chiffre d'affaires de 385 000 euros.",
     "51,6 %"),
    # Le nom s'arrête à la virgule : ce sont des clients.
    ("Avec 36,2 % des clients fidélisés, le chiffre d'affaires couvre le point mort de "
     "19 674 euros.", "36,2 %"),
    # En tableau, le nom s'arrête à la case.
    ("Poids dans le budget : Loyer | 19 674 € | 36,2 % du total | Chiffre d'affaires "
     "prévisionnel", "36,2 %"),
    # Un seul chiffre significatif : trop de rapports tombent juste.
    ("Une dépense de 1 600 euros, soit 3 % du chiffre d'affaires de l'année 1.", "3 %"),
    # Une autre devise ne se rapporte pas à des euros.
    ("Un coût de 19 674 dollars, soit 36,2 % du chiffre d'affaires de l'année 1.", "36,2 %"),
])
def test_ce_qui_ne_se_rapporte_pas_reste_signale(phrase: str, part: str) -> None:
    assert part in _signales(phrase)
