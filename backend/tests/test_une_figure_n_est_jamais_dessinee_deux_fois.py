"""Une figure n'est jamais dessinée deux fois, ni sous un titre qu'elle trahit.

29/09/2026, business plan ÉCLORE (§ 3.11 et § 3.12 du diagnostic) :

- **la même image deux fois.** `_blocs_graphique` ne gardait aucune mémoire des
  figures déjà dessinées ; les résolveurs qui ignorent les identifiants
  demandés — la frise, la carte des risques, le radar sans sélecteur — rendent
  la même image à chaque demande, et la passe de complétion redessinait des
  identifiants déjà tracés ;
- **un « rétroplanning » qui affichait des tendances de marché.** La frise
  dessine `socle.tendances`, quels que soient les identifiants : il n'existe
  aucune donnée « calendrier ».

Tenu ici : une même forme sur les mêmes données résolues n'est posée qu'une
fois dans le document, l'écart se dit au rapport, et une frise sous un titre de
calendrier n'est pas dessinée. Les contre-épreuves : deux figures différentes
passent toutes deux, et une frise titrée sur les tendances est dessinée.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from generation.chapitres.schema import ChapitrePayload
from generation.rendu_word.assemblage import assembler_etude
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Tendance, Zone


def _socle() -> Socle:
    def donnee(identifiant: str, libelle: str, valeur: float) -> DonneeSocle:
        return DonneeSocle(
            id=identifiant, libelle=libelle, valeur=valeur, unite="EUR", annee=2027,
            perimetre=Perimetre.ENTREPRISE, fiabilite=Fiabilite.DECLAREE,
            source="données du projet",
        )

    return Socle(
        secteur="bien-être", zone=Zone(pays="France"), date_socle=date(2026, 9, 29),
        donnees=[
            donnee("ca_sejours", "Chiffre d'affaires des séjours", 120_000.0),
            donnee("ca_ateliers", "Chiffre d'affaires des ateliers", 45_000.0),
            donnee("charges_fixes", "Charges fixes", 60_000.0),
        ],
        tendances=[
            Tendance(intitule="Tourisme de proximité", horizon="2027"),
            Tendance(intitule="Sylvothérapie", horizon="2028"),
            Tendance(intitule="Retraites bien-être", horizon="2030"),
        ],
    )


def _chapitre(
    numero: int, *figures: dict[str, Any], cites: list[str] | None = None,
) -> ChapitrePayload:
    return ChapitrePayload.model_validate({
        "chapitre": numero,
        "titre": f"Chapitre {numero}",
        "accroche": "Accroche.",
        "blocs": [
            {"type": "paragraphe", "texte": "Un paragraphe."},
            *({"type": "graphique", "graphique": figure} for figure in figures),
        ],
        "donnees_utilisees": cites or [],
        "resume": "Résumé.",
    })


def _figures(etude: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        bloc for chapitre in etude["chapitres"] for bloc in chapitre["blocs"]
        if bloc["type"] == "graphique"
    ]


def _signatures(etude: dict[str, Any]) -> list[str]:
    return [
        json.dumps([f["graphique"], f["donnees"]], sort_keys=True, default=str)
        for f in _figures(etude)
    ]


def test_la_frise_n_est_pas_redessinee_a_chaque_demande() -> None:
    """Elle ignore les identifiants : deux demandes, une seule image."""
    etude, rapport = assembler_etude(
        socle=_socle(),
        chapitres=[
            _chapitre(1, {"type": "chronologie", "titre": "Les tendances du secteur",
                          "donnees_ids": ["ca_sejours"]}),
            _chapitre(2, {"type": "chronologie", "titre": "Ce qui porte le marché",
                          "donnees_ids": ["ca_sejours"]}),
        ],
        titre="Business plan",
    )
    frises = [f for f in _figures(etude) if f["graphique"] == "chronologie"]
    assert len(frises) == 1, [f["titre"] for f in frises]
    assert len(rapport.graphiques_en_double) == 1
    assert "Chapitre 2" in rapport.graphiques_en_double[0]
    assert "en double" in rapport.resume()


def test_la_meme_figure_demandee_deux_fois_n_est_posee_qu_une_fois() -> None:
    figure = {"type": "barres", "titre": "Chiffre d'affaires par activité",
              "donnees_ids": ["ca_sejours", "ca_ateliers"]}
    etude, _ = assembler_etude(
        socle=_socle(),
        chapitres=[_chapitre(1, figure), _chapitre(2, {**figure, "titre": "Deux activités"})],
        titre="Business plan",
    )
    signatures = _signatures(etude)
    assert len(signatures) == len(set(signatures)), "une figure est dessinée deux fois"


def test_la_completion_ne_redessine_pas_une_figure_deja_posee() -> None:
    """La passe de complétion reprend ce que le chapitre cite — déjà tracé."""
    etude, rapport = assembler_etude(
        socle=_socle(),
        chapitres=[
            _chapitre(1, {"type": "barres_horizontales", "titre": "Deux activités",
                          "donnees_ids": ["ca_sejours", "ca_ateliers"]},
                      cites=["ca_sejours", "ca_ateliers"]),
            _chapitre(2, cites=["ca_sejours", "ca_ateliers"]),
            _chapitre(3, cites=["ca_sejours", "ca_ateliers"]),
        ],
        titre="Business plan",
    )
    signatures = _signatures(etude)
    assert len(signatures) == len(set(signatures)), rapport.graphiques_completes


def test_une_frise_sous_un_titre_de_calendrier_n_est_pas_dessinee() -> None:
    """Le « rétroplanning » d'ÉCLORE affichait des tendances de marché."""
    etude, rapport = assembler_etude(
        socle=_socle(),
        chapitres=[_chapitre(1, {"type": "chronologie", "titre": "Rétroplanning du lancement",
                                 "donnees_ids": ["ca_sejours"]})],
        titre="Business plan",
    )
    assert not [f for f in _figures(etude) if f["graphique"] == "chronologie"]
    # Ni sous forme de tableau : des chiffres qui ne sont pas un calendrier,
    # sous ce titre, mentiraient de la même façon.
    assert not [
        bloc for chapitre in etude["chapitres"] for bloc in chapitre["blocs"]
        if bloc.get("titre") == "Rétroplanning du lancement"
    ]
    assert any(
        "Rétroplanning du lancement" in motif and "calendrier" in motif
        for motif in rapport.graphiques_abandonnes
    ), rapport.graphiques_abandonnes


def test_deux_figures_differentes_passent_toutes_deux() -> None:
    """CONTRE-ÉPREUVE : la mémoire n'écarte que la même figure."""
    etude, rapport = assembler_etude(
        socle=_socle(),
        chapitres=[
            _chapitre(1, {"type": "barres", "titre": "Activités",
                          "donnees_ids": ["ca_sejours", "ca_ateliers"]}),
            _chapitre(2, {"type": "barres", "titre": "Séjours et charges",
                          "donnees_ids": ["ca_sejours", "charges_fixes"]}),
            _chapitre(3, {"type": "chronologie", "titre": "Tendances à l'horizon 2030",
                          "donnees_ids": ["ca_sejours"]}),
        ],
        titre="Business plan",
    )
    titres = {f["titre"] for f in _figures(etude)}
    assert {"Activités", "Séjours et charges", "Tendances à l'horizon 2030"} <= titres
    assert not rapport.graphiques_en_double
