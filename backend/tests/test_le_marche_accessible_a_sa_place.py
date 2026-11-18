"""Le marché accessible que le client déclare a une place hors de l'étude de marché.

Business plan de test `9e38eb81` (18/11/2026). Le brief donnait deux chiffres :
176 Md€ d'importations alimentaires chinoises, et 42,5 M€ de marché « réellement
accessible à une plateforme de petits producteurs » en Chine. Le référentiel du
business plan n'avait qu'une place, `marche_national_taille` : elle a reçu le
total, et le chiffre que le client retient pour son projet n'en avait aucune.
La fiche projet a présenté 176 000 M€ comme « marché d'accueil », et la
relecture a bloqué le document.
"""
from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType
from generation.chapitres.runner import REGLES_DE_FOND
from generation.memoire.faits import faits_de_l_etude
from generation.socle.prompt import construire_prompt_socle
from generation.socle.referentiel import definition, identifiants_obligatoires
from generation.socle.schema import Socle, _controler_emboitement_marche
from generation.socle.stub import socle_de_demonstration

BP = DeliverableType.BUSINESS_PLAN
STR = DeliverableType.BUSINESS_STRATEGY
EM = DeliverableType.MARKET_STUDY
BRIEF = {
    "SECTEUR": "Place de marché en ligne, produits du terroir",
    "PAYS": "France (siège social). Marchés de vente : Chine continentale dès 2027.",
    "PROJET": "Terroir en Asie",
}


def _socle(valeurs: dict[str, float], livrable: DeliverableType = BP) -> Socle:
    charge: dict[str, Any] = socle_de_demonstration(
        construire_prompt_socle(deliverable_type=livrable, variables=BRIEF)
    )
    for donnee in charge["donnees"]:
        if donnee["id"] in valeurs:
            donnee["valeur"], donnee["unite"] = valeurs[donnee["id"]], "EUR"
    return Socle.model_validate(charge)


@pytest.mark.parametrize("livrable", [BP, STR])
def test_le_referentiel_a_une_place_pour_le_marche_accessible(
    livrable: DeliverableType,
) -> None:
    place = definition(livrable, "sam")

    assert place is not None, "le marché accessible du client n'a aucune place"
    assert "accessible" in place.libelle
    # Facultatif : sans chiffre établi, il reste absent — jamais estimé.
    assert "sam" not in identifiants_obligatoires(livrable)
    assert "omets-la" in place.commentaire


@pytest.mark.parametrize("livrable", [BP, STR])
def test_le_socle_demande_le_marche_accessible_sur_le_pays_de_vente(
    livrable: DeliverableType,
) -> None:
    prompt = construire_prompt_socle(deliverable_type=livrable, variables=BRIEF)

    assert "`sam` — Marché réellement accessible au projet" in prompt
    assert "MÊME pays que `marche_national_taille`" in prompt


def test_l_etude_de_marche_garde_son_entonnoir() -> None:
    """Contre-épreuve : dans l'étude de marché, `sam` reste obligatoire."""
    assert "sam" in identifiants_obligatoires(EM)
    place = definition(EM, "sam")
    assert place is not None and "SAM" in place.libelle


def test_la_part_de_marche_se_calcule_sur_l_accessible_pas_sur_le_total() -> None:
    """Les chiffres du dossier : 8 000 commandes × 35 € sur 42,5 M€, soit 0,66 %."""
    socle = _socle({
        "marche_national_taille": 176_000_000_000.0, "sam": 42_500_000.0,
        "panier_moyen": 35.0,
    })
    assert socle.donnee("sam") is not None, "la doublure ne porte pas le marché accessible"
    # La doublure ne chiffre pas les commandes : on les pose comme le client.
    modele = next(d for d in socle.donnees if d.id == "ca_previsionnel_an1")
    socle.donnees.append(
        type(modele).model_validate({
            **modele.model_dump(),
            "id": "nombre_commandes_an1", "valeur": 8_000.0, "unite": "unite",
            "libelle": "Nombre de commandes — exercice 1",
        })
    )

    faits = faits_de_l_etude(socle)

    assert faits["part_de_marche_an1"].valeur == pytest.approx(0.659, abs=0.001)
    assert "sam" in faits["part_de_marche_an1"].formule


def test_un_marche_accessible_plus_grand_que_le_marche_national_est_refuse() -> None:
    socle = _socle({"marche_national_taille": 42_500_000.0, "sam": 176_000_000_000.0})

    motifs = _controler_emboitement_marche(socle)

    assert any("`sam`" in m and "`marche_national_taille`" in m for m in motifs), motifs


def test_un_marche_accessible_plus_petit_passe() -> None:
    """Contre-épreuve : le cas du dossier, 42,5 M€ dans 176 Md€."""
    socle = _socle({"marche_national_taille": 176_000_000_000.0, "sam": 42_500_000.0})

    assert _controler_emboitement_marche(socle) == []


def test_l_etude_de_marche_n_est_pas_jugee_sur_le_marche_national() -> None:
    """Contre-épreuve : avec un TAM, c'est le couple TAM/SAM qui porte l'emboîtement.

    Le TAM d'une étude à l'export couvre plusieurs pays ; son SAM peut dépasser
    le marché d'un seul d'entre eux sans rien avoir de faux.
    """
    socle = _socle(
        {
            "tam": 500_000_000.0, "sam": 127_000_000.0, "som": 280_000.0,
            "marche_national_taille": 100_000_000.0,
        },
        livrable=EM,
    )

    motifs = _controler_emboitement_marche(socle)

    assert not any("`marche_national_taille`" in m for m in motifs), motifs


def test_le_redacteur_rapporte_le_projet_au_marche_accessible() -> None:
    assert "le marché du projet est l'ACCESSIBLE" in REGLES_DE_FOND
    assert "Le marché total ne se cite jamais seul" in REGLES_DE_FOND
