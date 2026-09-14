"""Une donnée inconnue se tait au socle ; elle ne s'y écrit pas 0.

## Le défaut mesuré

Corpus du 14/09/2026, contrôle des valeurs nulles sur les documents livrés :

    Valeur : Coût d'acquisition d'un abonné Zenitek — non mesuré à ce jour :
             aucun budget commercial dédié… | 0 EUR | 2026 | Estimée
                                              (stratégies b098ded3, 655b0908, c9aec835)
    Année 1 : Masse salariale | 0 € | à préciser selon décision ultérieure
                                              (business plan 9f8f144a)

Le socle acceptait une donnée à 0 dont le propre libellé disait qu'elle
manque ; le zéro partait dans le livrable, et le contrôle ne le voyait qu'au
bout de la chaîne. On le refuse à la source — et, en dernier recours, on retire
la donnée facultative plutôt que de perdre l'étude.
"""
from __future__ import annotations

import datetime as dt

from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import (
    DonneeSocle,
    Socle,
    Zone,
    retirer_les_zeros_qui_manquent,
    valider_socle,
)


def _donnee(identifiant: str, libelle: str, valeur: float) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=libelle, valeur=valeur, unite="EUR", annee=2026,
        perimetre=Perimetre.ENTREPRISE, fiabilite=Fiabilite.ESTIMEE,
    )


def _socle(*donnees: DonneeSocle) -> Socle:
    return Socle(
        secteur="assistance informatique", zone=Zone(pays="France"),
        date_socle=dt.date(2026, 9, 14), donnees=list(donnees),
    )


def _motifs_de_zero(socle: Socle) -> list[str]:
    return [m for m in valider_socle(socle, "business_plan") if "vaut 0" in m]


def test_une_donnee_a_zero_qui_se_dit_manquante_est_refusee() -> None:
    socle = _socle(_donnee("masse_salariale_an1", "Masse salariale — à préciser selon décision", 0))
    assert _motifs_de_zero(socle)


def test_un_vrai_zero_ou_une_valeur_non_nulle_passent() -> None:
    """CONTRE-ÉPREUVES : un zéro décidé, et une estimation « à confirmer » chiffrée."""
    socle = _socle(
        _donnee("emprunt", "Emprunt bancaire sollicité — aucun emprunt retenu", 0),
        _donnee("masse_salariale_an1", "Masse salariale — à confirmer", 24000),
    )
    assert _motifs_de_zero(socle) == []


def test_en_dernier_recours_la_donnee_facultative_est_retiree() -> None:
    socle = _socle(
        _donnee("masse_salariale_an1", "Masse salariale — non mesurée", 0),
        _donnee("emprunt", "Emprunt bancaire sollicité", 120000),
    )
    assert retirer_les_zeros_qui_manquent(socle, "business_plan") == ["masse_salariale_an1"]
    assert [d.id for d in socle.donnees] == ["emprunt"]
