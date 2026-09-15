"""Un objectif de chiffre d'affaires du client ne s'invente pas dans le socle.

## Le défaut mesuré

Génération test `6c9dc734` (stratégie, reprise sans envoi de `f8a29b66`,
15/09/2026). Le brief donnait « CA an 1 = 51 030 € ; an 3 = 685 004 € ». Le socle
a produit `ca_objectif_horizon` = 1 070 000 €, et le chapitre 17 écrivait « la
trajectoire jusqu'à 1 070 000 € de chiffre d'affaires visé à horizon 2031 ».
Le gate l'a vu : « le document dit 1 070 000 €, le brief client dit 51 030 € /
685 004 € ». Un objectif que personne n'avait fixé, dans un dossier bancaire.

## La règle

Seul le client fixe ses objectifs. Un emplacement `du_client` ne se renseigne
que d'un montant que le brief ou ses documents écrivent ; sinon il est refusé,
puis retiré à la dernière tentative plutôt que de tuer le socle.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from generation.socle.builder import _analyser
from generation.socle.prompt import _ligne_referentiel
from generation.socle.referentiel import (
    Fiabilite,
    Perimetre,
    definitions_pour,
    identifiants_du_client,
)
from generation.socle.schema import DonneeSocle, Socle, Zone

STR = "business_strategy"
BRIEF = [51_030.0, 685_004.0, 226_500.0]


def _charge(**objectifs: float) -> dict[str, Any]:
    donnees = [
        DonneeSocle(
            id="marche_national_taille", libelle="Marché national de la legaltech",
            valeur=1.2, unite="MdEUR", annee=2025, perimetre=Perimetre.NATIONAL,
            fiabilite=Fiabilite.ESTIMEE, source="Institut Leges",
        ),
        *(
            DonneeSocle(
                id=identifiant, libelle=identifiant, valeur=valeur, unite="EUR",
                annee=2026, perimetre=Perimetre.ENTREPRISE, fiabilite=Fiabilite.DECLAREE,
            )
            for identifiant, valeur in objectifs.items()
        ),
    ]
    socle = Socle(
        secteur="legaltech", zone=Zone(pays="France"), date_socle=date(2026, 9, 15),
        donnees=donnees,
    )
    return socle.model_dump(mode="json")


def test_les_objectifs_de_chiffre_d_affaires_sont_du_client() -> None:
    objectifs = {"ca_objectif_horizon", "ca_objectif_an1", "ca_objectif_an3"}
    assert objectifs <= identifiants_du_client(STR)
    assert "marche_national_taille" not in identifiants_du_client(STR)


def test_un_objectif_que_le_brief_ne_chiffre_pas_est_refuse() -> None:
    """`6c9dc734` : 1 070 000 € « à horizon 2031 »."""
    socle, motifs = _analyser(
        _charge(ca_objectif_an1=51_030, ca_objectif_horizon=1_070_000), STR,
        montants_client=BRIEF,
    )
    assert socle is None
    assert any("ca_objectif_horizon" in m and "ne chiffre pas" in m for m in motifs)
    assert not any("ca_objectif_an1" in m for m in motifs)


def test_a_la_derniere_tentative_l_objectif_invente_est_retire_pas_le_socle() -> None:
    socle, motifs = _analyser(
        _charge(ca_objectif_an1=51_030, ca_objectif_horizon=1_070_000), STR,
        dernier_recours=True, montants_client=BRIEF,
    )
    assert socle is not None, motifs
    ids = socle.identifiants
    assert "ca_objectif_an1" in ids and "ca_objectif_horizon" not in ids


def test_les_objectifs_ecrits_par_le_client_passent() -> None:
    """CONTRE-ÉPREUVE : les deux montants du brief, recopiés."""
    socle, motifs = _analyser(
        _charge(ca_objectif_an1=51_030, ca_objectif_an3=685_004), STR,
        montants_client=BRIEF,
    )
    assert socle is not None, motifs


def test_une_interpolation_entre_deux_annees_n_est_pas_un_objectif_du_client() -> None:
    """CONTRE-ÉPREUVE : l'année 2 « au milieu » n'est écrite nulle part."""
    socle, motifs = _analyser(
        _charge(ca_objectif_an1=51_030, ca_objectif_an2=368_017, ca_objectif_an3=685_004),
        STR, montants_client=BRIEF,
    )
    assert socle is None
    assert any("ca_objectif_an2" in m for m in motifs)


def test_la_consigne_du_socle_dit_que_la_donnee_est_du_client() -> None:
    horizon = next(d for d in definitions_pour(STR) if d.identifiant == "ca_objectif_horizon")
    assert "DU CLIENT" in _ligne_referentiel(horizon)
    marche = next(d for d in definitions_pour(STR) if d.identifiant == "marche_national_taille")
    assert "DU CLIENT" not in _ligne_referentiel(marche)
