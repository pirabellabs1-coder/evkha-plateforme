"""Le modèle ne demande plus de figures impossibles : il choisit dans un catalogue.

Stratégie Zenitek, reprise `b098ded3` du 12/09/2026 : **31 figures demandées,
31 impossibles, zéro dessinée**. Le document est parti sans un seul graphique.
Les motifs se rangeaient en deux familles, toujours les mêmes :

    « unités hétérogènes : EUR, unite »     — un montant et un effectif ensemble
    « le radar exige des notes »            — un radar sur des montants

Le modèle ne pouvait pas faire mieux : on lui donnait les identifiants du socle
avec leurs unités, et la charge de deviner ce que le moteur de rendu
accepterait. Il choisit désormais dans une liste que ce moteur a lui-même
validée — et c'est ce qui rend l'erreur impossible plutôt que rattrapable.

Ces tests échouent sur le code d'avant : le catalogue n'existait pas et le
prompt n'en portait rien.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from generation.rendu_word.catalogue_figures import (
    bloc_figures_possibles,
    figures_possibles,
)
from generation.rendu_word.donnees_graphiques import resoudre
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone


def _donnee(identifiant: str, valeur: float, unite: str) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=identifiant.replace("_", " ").capitalize(),
        valeur=valeur, unite=unite, annee=2026, perimetre=Perimetre.NATIONAL,
        fiabilite=Fiabilite.DECLAREE,
    )


def _socle_zenitek() -> Socle:
    """Le socle d'une stratégie réelle : des euros, des effectifs, des taux."""
    return Socle(
        secteur="assistance informatique", zone=Zone(pays="France"),
        date_socle=date(2026, 9, 12),
        donnees=[
            _donnee("ca_actuel", 120000, "EUR"),
            _donnee("ca_objectif_horizon", 250000, "EUR"),
            _donnee("panier_moyen", 17.9, "EUR"),
            _donnee("abonnes", 14, "unite"),
            _donnee("abonnes_cible", 250, "unite"),
            _donnee("taux_marge", 38, "%"),
            _donnee("taux_attrition", 12, "%"),
        ],
    )


def test_toute_figure_du_catalogue_se_dessine_vraiment() -> None:
    """LE test : le catalogue est vérifié par le moteur qui dessine, pas décrit.

    Une liste écrite à la main aurait vieilli à la première règle changée
    (règle 5). Ici, chaque ligne est passée par `resoudre`.
    """
    socle = _socle_zenitek()
    propositions = figures_possibles(socle)

    assert propositions, "un socle ordinaire doit permettre des figures"
    for proposition in propositions:
        resolution = resoudre(
            socle, proposition.type_graphique, list(proposition.identifiants)
        )
        assert resolution.retenu, f"{proposition.type_graphique} {proposition.identifiants}"


def test_le_catalogue_ne_melange_jamais_deux_natures() -> None:
    """La cause n°1 des 31 abandons : un montant et un effectif ensemble."""
    socle = _socle_zenitek()
    unites = {d.id: d.unite for d in socle.donnees}

    for proposition in figures_possibles(socle):
        natures = {unites[identifiant] for identifiant in proposition.identifiants}
        assert len(natures) == 1, f"{proposition.identifiants} mêle {natures}"


def test_aucun_radar_sans_grille_de_notes() -> None:
    """La cause n°2 : un radar demandé sur des montants."""
    propositions = figures_possibles(_socle_zenitek())
    assert not [p for p in propositions if p.type_graphique == "radar"]


def test_le_catalogue_dit_la_regle_et_l_alternative() -> None:
    """Un modèle guidé écrit mieux qu'un modèle repris : la consigne explique."""
    bloc = bloc_figures_possibles(_socle_zenitek())

    assert "FIGURES RÉALISABLES" in bloc
    assert "MÊME NATURE" in bloc
    assert "au moins deux valeurs" in bloc
    # L'alternative compte autant que l'interdit : sans elle, le modèle
    # renoncerait à porter son propos.
    assert "écris le tableau qui le porte" in bloc


def test_un_socle_sans_figure_possible_ne_dit_rien() -> None:
    """CONTRE-ÉPREUVE : annoncer « aucune figure possible » ferait écrire au
    modèle que le document n'en aura pas — ce qui n'a rien à faire dans un
    livrable remis au client."""
    maigre = Socle(
        secteur="x", zone=Zone(pays="France"), date_socle=date(2026, 9, 12),
        donnees=[_donnee("ca_actuel", 120000, "EUR")],
    )
    assert bloc_figures_possibles(maigre) == ""


@pytest.mark.django_db
def test_le_prompt_du_chapitre_porte_le_catalogue_et_la_coherence() -> None:
    """Les deux vivent dans la partie du prompt mise en CACHE : quasi gratuites."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.chapitres.configuration import type_document
    from generation.chapitres.runner import (
        COHERENCE_DES_CHIFFRES,
        construire_prompt_chapitre,
    )
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    livrable = DeliverableType.BUSINESS_STRATEGY
    offre = Offer.objects.create(name="S", slug="s-figures", deliverable_type=livrable)
    client = Customer.objects.create(email="figures@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-figures", customer=client, offer=offre
    )
    variables: dict[str, Any] = {"SECTEUR": "assistance informatique", "PAYS": "France"}
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=variables,
    )
    job = bootstrap_generation_job(soumission)
    chapitre = job.chapters.order_by("chapter_number").first()
    assert chapitre is not None

    prompt, _ = construire_prompt_chapitre(
        chapitre, socle=_socle_zenitek(), variables=variables,
        document=type_document(livrable),
    )

    assert "FIGURES RÉALISABLES" in prompt.par_job
    assert "ca_actuel" in prompt.par_job
    # La cohérence chiffrée, elle, vit dans le prompt système — commun à tous
    # les chapitres et mis en cache une seule fois.
    for attendu in ("UN CHIFFRE, UNE SOURCE", "JAMAIS DE ZÉRO NU", "UN CALCUL SE MONTRE"):
        assert attendu in COHERENCE_DES_CHIFFRES


def test_le_prompt_systeme_porte_les_regles_de_sources() -> None:
    """Trois défauts mesurés, une seule réponse : les sources sont enseignées.

    Étude WAOME (la moitié des sources non vérifiables, deux URL inventées),
    stratégie Zenitek du 12/09/2026 (« 0 URL vérifiable pour 3 sources
    extérieures »), et le marché « 900 M€ » sans source alors que l'étude du
    client portait le chiffre.
    """
    from generation.chapitres.runner import SOURCES_ET_TRACABILITE

    for attendu in (
        "N'INVENTE JAMAIS UNE ADRESSE",
        "LA SOURCE DOIT PORTER CE CHIFFRE-LÀ",
        "données du projet",
        "UN CHIFFRE DU CLIENT PRIME",
        "UNE ANNÉE EST CELLE DE LA MESURE",
    ):
        assert attendu in SOURCES_ET_TRACABILITE, attendu
    # Et la leçon de WAOME v4 : des règles récitées DANS le document sont un
    # défaut de plus. Elles se suivent, elles ne se citent pas.
    assert "CES RÈGLES NE SE CITENT PAS DANS LE TEXTE" in SOURCES_ET_TRACABILITE
