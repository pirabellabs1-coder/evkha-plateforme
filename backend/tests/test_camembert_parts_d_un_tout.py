"""Un camembert dont les parts ne font pas 100 % n'est pas un camembert.

## Le defaut, releve par la cliente le 18/08/2026

Strategie `f8a29b66`, page 59. Le camembert reunit DEUX indicateurs sans
rapport : un taux d'activation des avocats (45 %) et une part de chiffre
d'affaires recurrent (65 %). Le lecteur y voit 41 % et 59 %.

Sa lecture technique etait juste au premier coup :

    45 / (45 + 65) ≈ 41 %
    65 / (45 + 65) ≈ 59 %

`matplotlib.pie` NORMALISE : son `autopct` calcule chaque part sur la somme des
valeurs. La figure affiche donc deux chiffres qui n'existent nulle part dans le
dossier — alors que 45 % et 65 % y figurent des dizaines de fois.

## Pourquoi aucun controle ne pouvait le voir

Une figure normalisee est TOUJOURS coherente en apparence : rien ne depasse,
rien ne manque, le total fait 100 par construction. Le controle ne pouvait donc
pas venir du dessin ; il vient d'avant, la ou les donnees rencontrent le type
de figure demande.

## Ce qu'on en fait

Pas un abandon : une CONVERSION. Les chiffres sont bons, c'est la forme qui
ment, et le module convertit deja plutot que d'abandonner quand les memes
donnees alimentent honnetement un autre type. Deux indicateurs distincts font
des barres parfaitement lisibles.
"""
from __future__ import annotations

import pytest

from generation.rendu_word.donnees_graphiques import _scalaires
from generation.socle.schema import DonneeSocle, Socle, Zone


def _donnee(identifiant: str, valeur: float, unite: str, libelle: str) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, valeur=valeur, unite=unite, libelle=libelle,
        annee=2026, perimetre="entreprise", source="données du projet",
        fiabilite="observee",
    )


def _socle(*donnees: DonneeSocle) -> Socle:
    return Socle(
        secteur="conseil juridique", zone=Zone(pays="France"),
        date_socle="2026-08-18", donnees=list(donnees),
    )


@pytest.mark.parametrize("type_demande", ["camembert", "anneau"])
def test_deux_indicateurs_sans_rapport_deviennent_des_barres(
    type_demande: str,
) -> None:
    """Les valeurs EXACTES de la page 59.

    Echoue sur le code d'avant : le seul garde-fou etait « aucune valeur
    negative », et 45 comme 65 sont positifs.
    """
    resolution = _scalaires(
        _socle(
            _donnee("taux_activation", 45.0, "%", "Taux d'activation des avocats"),
            _donnee("part_ca_recurrent", 65.0, "%",
                    "Part de chiffre d'affaires récurrent"),
        ),
        type_demande,
        ["taux_activation", "part_ca_recurrent"],
    )

    assert resolution.retenu, "la figure ne doit pas être perdue"
    assert resolution.type_graphique == "barres"
    assert resolution.converti
    assert "110 %" in resolution.motif
    # Et surtout : les valeurs du dossier, pas celles que la normalisation
    # aurait fabriquees.
    assert resolution.donnees is not None
    assert resolution.donnees["valeurs"] == [45.0, 65.0]


def test_de_vraies_parts_d_un_tout_restent_un_camembert() -> None:
    """Contre-epreuve : le correctif ne doit pas supprimer les camemberts."""
    resolution = _scalaires(
        _socle(
            _donnee("part_b2b", 40.0, "%", "Part du chiffre d'affaires B2B"),
            _donnee("part_b2c", 35.0, "%", "Part du chiffre d'affaires B2C"),
            _donnee("part_public", 25.0, "%", "Part du secteur public"),
        ),
        "camembert",
        ["part_b2b", "part_b2c", "part_public"],
    )
    assert resolution.type_graphique == "camembert"
    assert not resolution.converti


def test_l_arrondi_d_un_document_ne_declenche_rien() -> None:
    """Contre-epreuve : trois parts ecrites 33 % font 99, et c'est normal."""
    resolution = _scalaires(
        _socle(
            _donnee("a", 33.0, "%", "Segment A"),
            _donnee("b", 33.0, "%", "Segment B"),
            _donnee("c", 33.0, "%", "Segment C"),
        ),
        "camembert", ["a", "b", "c"],
    )
    assert resolution.type_graphique == "camembert"


def test_des_montants_restent_un_camembert_quelle_que_soit_leur_somme() -> None:
    """Contre-epreuve : le tout d'une repartition en euros EST sa somme.

    Exiger 100 sur des montants n'aurait aucun sens et condamnerait toute
    repartition monetaire — le camembert le plus courant d'un business plan.
    """
    resolution = _scalaires(
        _socle(
            _donnee("ca_produit", 120000.0, "EUR", "Chiffre d'affaires produit"),
            _donnee("ca_service", 80000.0, "EUR", "Chiffre d'affaires service"),
        ),
        "camembert", ["ca_produit", "ca_service"],
    )
    assert resolution.type_graphique == "camembert"
    assert not resolution.converti


def test_une_valeur_negative_reste_refusee() -> None:
    """Contre-epreuve : le garde-fou d'origine tient toujours."""
    resolution = _scalaires(
        _socle(
            _donnee("marge", 70.0, "%", "Marge"),
            _donnee("perte", -30.0, "%", "Perte"),
        ),
        "camembert", ["marge", "perte"],
    )
    assert not resolution.retenu
    assert "négative" in resolution.motif
