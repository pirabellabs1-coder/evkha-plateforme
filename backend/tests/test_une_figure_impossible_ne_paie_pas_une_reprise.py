"""Une figure impossible est JUGÉE à l'acceptation — mais ne paie jamais une reprise.

## Première décision (12/09/2026)

Stratégie Zenitek `b098ded3` : 31 figures demandées, 31 impossibles, toutes
découvertes à l'assemblage. On a donc jugé chaque figure à l'acceptation du
chapitre, par le moteur qui dessine, et fait REFAIRE le chapitre au moindre
refus.

## Ce que la mesure a dit (13/09/2026)

Même stratégie, même socle, mêmes documents déposés :

    655b0908  avant    4 reprises   4,33 €   10/32 figures dessinées
    db0d9508  après   34 reprises   6,51 €   11/18
    db228221  après   34 reprises   6,52 €    7/17

Huit fois plus de reprises, près de quatre euros jetés par dossier — et au
dernier essai la figure passait quand même. Le budget vidé, la relecture finale
s'arrêtait sans corriger un seul défaut réparable.

## La décision actuelle

Le motif de figure VOYAGE avec une reprise déjà décidée pour une autre raison
(il ne coûte alors rien). Seul, il ne relance rien : le chapitre est accepté et
l'assemblage imprime les données en tableau.

Le premier test ci-dessous échoue sur le code d'avant : le chapitre y était
refusé et redemandé.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres import produire_chapitre
from generation.chapitres.runner import _motifs_de_figure
from generation.chapitres.schema import (
    BlocGraphique,
    ChapitrePayload,
    Graphique,
    TypeGraphique,
)
from generation.models import ChapterStatus
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StructuredResult, StubClaudeClient
from orders.models import Order


def _socle() -> Socle:
    def donnee(identifiant: str, valeur: float, unite: str) -> DonneeSocle:
        return DonneeSocle(
            id=identifiant, libelle=identifiant.replace("_", " "), valeur=valeur,
            unite=unite, annee=2026, perimetre=Perimetre.NATIONAL,
            fiabilite=Fiabilite.DECLAREE,
        )

    return Socle(
        secteur="assistance informatique", zone=Zone(pays="France"),
        date_socle=date(2026, 9, 12),
        donnees=[
            donnee("ca_actuel", 120000, "EUR"),
            donnee("ca_cible", 250000, "EUR"),
            donnee("abonnes", 14, "unite"),
        ],
    )


def _payload(*identifiants: str, titre: str = "Repères économiques") -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=5, titre="Lecture économique", accroche="",
        blocs=[
            BlocGraphique(
                graphique=Graphique(
                    type_graphique=TypeGraphique.BARRES,
                    titre=titre,
                    donnees_ids=list(identifiants),
                )
            )
        ],
        donnees_utilisees=list(identifiants),
        resume="Résumé du chapitre, assez long pour tenir le contrat de forme.",
    )


def test_une_figure_aux_unites_melangees_est_jugee() -> None:
    """LE cas : un montant et un effectif dans la même figure — 14 fois sur 31."""
    motifs = _motifs_de_figure(_payload("ca_actuel", "abonnes"), _socle())

    assert len(motifs) == 1
    assert "impossible à dessiner" in motifs[0]
    # Règle 2 : le motif doit être actionnable par qui doit corriger.
    assert "unités hétérogènes" in motifs[0]
    assert "figures réalisables" in motifs[0]


def test_une_figure_realisable_ne_reproche_rien() -> None:
    """CONTRE-ÉPREUVE : le contrôle ne doit pas renvoyer un chapitre correct."""
    assert _motifs_de_figure(_payload("ca_actuel", "ca_cible"), _socle()) == []


def test_au_dernier_essai_le_chapitre_n_est_pas_perdu() -> None:
    """Un chapitre juste ne se perd pas pour une figure : ses données iront en tableau.

    C'est l'arbitrage déjà retenu ailleurs dans ce moteur — le texte du
    chapitre vaut plus que sa mise en forme.
    """
    motifs = _motifs_de_figure(
        _payload("ca_actuel", "abonnes"), _socle(), derniere_tentative=True
    )
    assert motifs == []


class _Compteur(StubClaudeClient):
    """La doublure, qui compte ses appels."""

    def __init__(self) -> None:
        super().__init__()
        self.appels = 0

    def complete_structured(self, **kwargs: Any) -> StructuredResult:
        self.appels += 1
        return super().complete_structured(**kwargs)


@pytest.mark.django_db
def test_un_chapitre_dont_le_seul_defaut_est_une_figure_n_est_pas_redemande() -> None:
    """LE test du coût : un appel, un chapitre accepté, zéro reprise.

    La doublure écrit un chapitre correct dont UNE figure est impossible (un
    radar à moins de trois axes). C'est exactement la situation qui, sur
    `db228221`, a coûté 34 reprises.
    """
    variables = {"SECTEUR": "assistance informatique", "PAYS": "France", "ZONE": "Paris"}
    offre = Offer.objects.create(
        name="EM", slug="em-figure-reprise", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="figure-reprise@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-figure-reprise", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=variables,
    )
    job = bootstrap_generation_job(soumission)
    etablir_socle(job, client=StubClaudeClient(), variables=variables)

    compteur = _Compteur()
    chapitre = produire_chapitre(job, 1, client=compteur)

    assert chapitre.status == ChapterStatus.DONE
    assert compteur.appels == 1, f"{compteur.appels} appels : la figure a payé une reprise"
