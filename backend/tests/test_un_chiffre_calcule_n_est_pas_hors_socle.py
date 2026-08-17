"""Un chiffre CALCULÉ à partir du socle n'est pas un chiffre hors socle.

## Ce qui n'allait pas, et pourquoi ce n'était pas un bug

`controler_chiffres_hors_socle` était volontairement un simple avertissement, et
sa docstring disait pourquoi : « le contrôle ne recalcule pas l'arithmétique
interne des chapitres, si bien qu'une somme légitime de deux valeurs du socle
apparaît ici comme hors socle. Bloquer sur cette base arrêterait des livrables
corrects, et une barrière qui crie à tort finit débranchée. »

C'était juste. Mais cela laissait le contrôle incapable de séparer les deux
seules choses qui comptent :

    « SOM = 1,0 Md€ × 0,05 % = 0,5 M€ »   un calcul, parfaitement légitime
    « 26,3 millions de chiens et chats »  un chiffre de marché INVENTÉ

Les deux sortaient pareil. Sur le dossier réel `c8b4e60a`, quatorze réserves
mélangeaient les unes et les autres, et il fallait les relire à la main.

## La bonne façon de durcir un contrôle

Non pas relever la sanction, mais **retirer la cause des faux positifs**. Une
barrière qui crie à tort ne devient pas utile en criant plus fort : elle devient
débranchée. Ce fichier vérifie donc les deux moitiés — le calcul passe, et
l'invention ne passe pas.

## Pourquoi on s'arrête à deux termes

À trois termes, le nombre de combinaisons explose et la probabilité qu'un
chiffre inventé tombe par hasard sur l'une d'elles devient réelle. Un contrôle
qui justifie tout ne justifie plus rien — ce serait échanger un bruit contre un
silence, et le silence est le défaut que ce dépôt combat depuis le début
(règle 1).
"""
from __future__ import annotations

from datetime import date

import pytest

from generation.socle.schema import (
    DonneeSocle,
    Fiabilite,
    Perimetre,
    Socle,
    Zone,
)
from generation.verification.controles import controler_chiffres_hors_socle
from generation.verification.lecture import DocumentLu, Mesure


def _socle() -> Socle:
    """TAM 1,0 Md€ et un taux de capture de 0,05 % — le cas du dossier réel."""
    return Socle(
        secteur="e-commerce animalier",
        zone=Zone(pays="France"),
        date_socle=date(2026, 8, 9),
        donnees=[
            DonneeSocle(
                id="sam", libelle="Marché adressable", valeur=1.0, unite="MdEUR",
                annee=2025, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.OBSERVEE, source="Fevad, 2025",
            ),
            DonneeSocle(
                id="taux_capture", libelle="Taux de capture", valeur=0.05, unite="%",
                annee=2025, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.ESTIMEE,
            ),
        ],
    )


def _document(*mesures: Mesure) -> DocumentLu:
    from pathlib import Path

    return DocumentLu(
        chemin=Path("essai.docx"),
        paragraphes=["Un paragraphe d'essai."],
        cellules=[],
        tableaux=4,
        tableaux_vides=0,
        images=2,
        mesures=list(mesures),
    )


def _mesure(valeur: float, texte: str, *, unite: str = "MdEUR") -> Mesure:
    """Une grandeur relevée dans le document.

    `unite` vide = grandeur non monétaire (un décompte), qui se compare aux
    valeurs BRUTES du socle. Une unité monétaire déclenche en plus la
    comparaison en unités de base.
    """
    return Mesure(
        valeur=valeur, unite=unite, texte=texte, contexte=texte, dans_un_tableau=False
    )


def _regles(anomalies: list) -> list[str]:
    return [a.detail for a in anomalies]


def test_une_valeur_du_socle_passe() -> None:
    """Le cas de base, qui marchait déjà."""
    anomalies = controler_chiffres_hors_socle(
        _document(_mesure(1_000_000_000.0, "1,0 Md€")), _socle()
    )

    assert anomalies == []


def test_un_SOM_calcule_depuis_le_socle_passe_desormais() -> None:
    """« SOM = 1,0 Md€ × 0,05 % = 0,5 M€ » — le faux positif qui bridait tout.

    Ce test échouerait sur le code d'avant : le produit n'était comparé à rien.
    """
    anomalies = controler_chiffres_hors_socle(
        _document(_mesure(500_000.0, "0,5 M€")), _socle()
    )

    assert anomalies == [], _regles(anomalies)


def test_une_part_calculee_en_pourcentage_passe() -> None:
    """0,05 / 1,0 x 100 = 5 % — une part tiree du socle, pas une invention."""
    anomalies = controler_chiffres_hors_socle(
        _document(_mesure(5.0, "5 %", unite="%")), _socle()
    )

    assert anomalies == [], _regles(anomalies)


def test_un_produit_passe() -> None:
    """1 Md EUR x 0,05 = 50 M EUR."""
    anomalies = controler_chiffres_hors_socle(
        _document(_mesure(50_000_000.0, "50 M€")), _socle()
    )

    assert anomalies == [], _regles(anomalies)


def test_un_chiffre_INVENTE_ne_passe_toujours_pas() -> None:
    """LA contre-épreuve. Sans elle, le correctif justifierait tout.

    « 26,3 millions de chiens et chats » vient du dossier réel : aucun calcul
    depuis ce socle ne le produit, et il ne doit pas passer.
    """
    anomalies = controler_chiffres_hors_socle(
        _document(_mesure(26_300_000, "26,3 millions", unite="")), _socle()
    )

    assert len(anomalies) == 1
    assert "26,3 millions" in anomalies[0].detail


@pytest.mark.parametrize(
    ("valeur", "texte"),
    [
        (3.7, "3,7 Md€"),
        (42.0, "42 M€"),
        (0.123, "0,123 Md€"),
    ],
)
def test_plusieurs_inventions_restent_signalees(valeur: float, texte: str) -> None:
    anomalies = controler_chiffres_hors_socle(
        _document(_mesure(valeur, texte)), _socle()
    )

    assert anomalies, f"« {texte} » devrait rester hors socle"


def test_une_derivation_APPROCHANTE_ne_justifie_pas() -> None:
    """La contre-épreuve la plus importante du fichier, et elle vient d'un échec.

    Première version : les dérivations partageaient la tolérance de 1 % des
    valeurs recopiées. Un test qui existait déjà — « la passe voit un chiffre
    inventé dans un vrai fichier » — s'est mis à échouer : « 777 M€ » cessait
    d'être détecté parce qu'une dérivation valait 781 250 000, soit 0,55 % de
    lui.

    Vingt-neuf données au socle produisent près de trois mille combinaisons ;
    à ±1 % chacune, elles couvrent presque tout l'espace des nombres
    plausibles. Le contrôle ne mesurait plus rien.

    Un chiffre CALCULÉ n'est pas approché — il EST le résultat. D'où une
    tolérance cent fois plus serrée, et ce test qui la verrouille : une valeur à
    0,5 % d'une dérivation doit rester signalée.
    """
    # 1 Md€ × 0,05 = 50 M€ exactement. À 0,5 % près, ce n'est plus le calcul.
    presque = 50_000_000.0 * 1.005

    anomalies = controler_chiffres_hors_socle(
        _document(_mesure(presque, "50,25 M€")), _socle()
    )

    assert anomalies, "une valeur seulement PROCHE d'une dérivation n'est pas dérivée"


def test_un_socle_vide_reste_bloquant() -> None:
    """Règle 1 : sans socle, il n'y a rien à comparer — et ce n'est pas un succès."""
    vide = Socle(
        secteur="mode", zone=Zone(pays="France"),
        date_socle=date(2026, 8, 9), donnees=[],
    )

    anomalies = controler_chiffres_hors_socle(_document(_mesure(1_000_000_000.0, "1 Md€")), vide)

    assert anomalies
    assert anomalies[0].gravite.value == "bloquante"


def test_un_document_sans_aucun_chiffre_reste_bloquant() -> None:
    """« Une étude de marché sans un seul chiffre n'est pas une étude de marché. »"""
    anomalies = controler_chiffres_hors_socle(_document(), _socle())

    assert anomalies
    assert anomalies[0].gravite.value == "bloquante"
