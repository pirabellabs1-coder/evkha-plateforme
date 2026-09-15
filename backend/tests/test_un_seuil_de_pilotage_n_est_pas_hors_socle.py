"""Le seuil d'une règle de pilotage est choisi par le document, pas avancé comme un fait.

## Le défaut mesuré

Corpus du 15/09/2026, études de marché :

- `2cef0cbd` : « Ralentir si… : Marché adressable | La part de 8 % du marché
  national se maintient ou progresse | Elle recule sous 6 % du marché national » ;
- `f0064333` : « Situation : Panier moyen sous 1 000 € par adhérent trois mois
  de suite | Revoir le mix abonnement/prestations avant tout nouvel
  investissement ».

6 % et 1 000 € disent QUAND agir. Ils étaient comptés comme des chiffres
inventés, alors que l'en-tête « Seuil STOP » d'un tableau de décision est admis
pour la même raison.

## Ce qui reste signalé

Un franchissement sans règle (« le marché recule sous 6 % de croissance »), une
règle sans franchissement juste avant la valeur, et « au-dessus du seuil de
rentabilité » — un calcul du prévisionnel, que le contrôle doit juger.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone
from generation.verification.controles import controler_chiffres_hors_socle
from generation.verification.lecture import DocumentLu, _dans_son_tableau, mesures_dans


def _socle() -> Socle:
    return Socle(
        secteur="bien-être", zone=Zone(pays="France"), date_socle=date(2026, 9, 15),
        donnees=[
            DonneeSocle(
                id="marche_national_taille", libelle="Marché national", valeur=30,
                unite="MdEUR", annee=2026, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.DECLAREE,
            ),
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


def _signales_en_tableau(ligne: str, case: str) -> set[str]:
    """La case telle que la lecture du Word la rend : « en-tête : ligne entière »."""
    document = DocumentLu(chemin=Path("corpus.docx"), paragraphes=[])
    document.mesures.extend(
        _dans_son_tableau(m, ligne, case) for m in mesures_dans(case, dans_un_tableau=True)
    )
    return {
        a.detail.split("»")[0].strip("« ").strip()
        for a in controler_chiffres_hors_socle(document, _socle())
        if a.controle == "chiffres_hors_socle"
    }


@pytest.mark.parametrize(("ligne", "case", "valeur"), [
    # `2cef0cbd` : l'action est dans l'en-tête de la colonne.
    ("Ralentir si… : Marché adressable | La part se maintient ou progresse | "
     "Elle recule sous 6 % du marché national",
     "Elle recule sous 6 % du marché national", "6 %"),
    # `f0064333` : l'action est la case de réponse de la ligne.
    ("Situation : Panier moyen sous 1 000 € par adhérent trois mois de suite | "
     "Revoir le mix abonnement/prestations avant tout nouvel investissement",
     "Panier moyen sous 1 000 € par adhérent trois mois de suite", "1 000 €"),
])
def test_le_seuil_d_une_ligne_de_pilotage_est_admis(ligne: str, case: str, valeur: str) -> None:
    assert valeur not in _signales_en_tableau(ligne, case)


@pytest.mark.parametrize(("ligne", "case", "valeur"), [
    # Relecture du 15/09/2026 : une case voisine ne qualifie pas celle-ci.
    ("Concurrents : Keep Cool | CA passé sous 25 000 € en 2024 | Réseau qui a décidé "
     "d'arrêter la franchise", "CA passé sous 25 000 € en 2024", "25 000 €"),
    ("Indicateurs : Taux de chômage | Au-dessus de 7 % depuis 2023 | Signal d'alerte "
     "pour la demande", "Au-dessus de 7 % depuis 2023", "7 %"),
])
def test_une_case_voisine_ne_fait_pas_d_un_fait_un_seuil(
    ligne: str, case: str, valeur: str,
) -> None:
    assert valeur in _signales_en_tableau(ligne, case)


@pytest.mark.parametrize(("phrase", "valeur"), [
    ("Ralentir si la part du marché national recule sous 6 % deux trimestres de suite.",
     "6 %"),
    ("Si le panier moyen passe sous 1 000 € par adhérent trois mois de suite, revoir le "
     "mix abonnement/prestations.", "1 000 €"),
    ("Seuil d'alerte : panier moyen en dessous de 550 € sur un trimestre.", "550 €"),
    ("Accélérer dès que le taux de réachat se maintient au-dessus de 40 %.", "40 %"),
])
def test_le_seuil_d_une_regle_est_admis(phrase: str, valeur: str) -> None:
    assert valeur not in _signales(phrase)


@pytest.mark.parametrize(("phrase", "valeur"), [
    # CONTRE-ÉPREUVE : un franchissement sans règle est un fait avancé.
    ("Le marché national recule sous 6 % de croissance annuelle.", "6 %"),
    # Une règle, mais la valeur n'est pas le seuil franchi.
    ("Si la fréquentation baisse, le panier moyen atteindra 1 000 € par adhérent.",
     "1 000 €"),
    # Le seuil de rentabilité est un calcul du prévisionnel.
    ("Le chiffre d'affaires passe au-dessus du seuil de rentabilité de 18 667 € en "
     "année 2.", "18 667 €"),
    # Relecture du 15/09/2026 : une condition sans action raconte un fait.
    ("Si l'on en croit Xerfi, le prix moyen est passé sous 49 € en 2025.", "49 €"),
    ("Quand le chômage est au-dessus de 7 %, la demande recule.", "7 %"),
    ("Le résultat net passe au-dessus de 12 400 € dès que l'activité atteint son rythme.",
     "12 400 €"),
    # Le verbe conjugué raconte, l'infinitif décide.
    ("Le prix moyen est passé sous 49 € en 2025, ce qui déclenche une guerre des prix.",
     "49 €"),
    # Un fait de croissance, même suivi d'une action, reste un fait.
    ("Si la croissance ralentit sous 5 %, il faut revoir les prix.", "5 %"),
    # Une taille de marché aussi.
    ("Si le marché national passe sous 25 000 000 €, revoir la cible.", "25 000 000 €"),
    # « Plus de » n'est pas un franchissement de règle.
    ("Si l'on regarde la clientèle, plus de 80 % des adhérents ont 45 ans et plus.",
     "80 %"),
])
def test_ce_qui_n_est_pas_un_seuil_reste_signale(phrase: str, valeur: str) -> None:
    assert valeur in _signales(phrase)
