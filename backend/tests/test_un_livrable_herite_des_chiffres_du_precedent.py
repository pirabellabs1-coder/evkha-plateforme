"""Deux livrables du même client ne donnent pas deux totaux pour le même marché.

## Le défaut, mesuré

Étude de la concurrence `e150aade` (27/10/2026) : marché total de la zone
**1 588,6 M€**. La référence que la cliente a réécrite à la main pour le même
dossier : **1 902 M€**. Son premier grief du 28/10/2026 :

    Reprendre le périmètre validé et rester cohérent avec l'étude de marché :
    mêmes pays, mêmes hypothèses, mêmes chiffres, car ce n'était pas le cas.

## Pourquoi c'était inévitable, vérifié dans le code

Le cahier des charges de l'étude de la concurrence l'exige depuis le
18/05/2026 (« une cohérence systématique avec l'étude de marché lorsque
celle-ci existe ») et aucun mécanisme ne l'assurait : `SocleDonnees` est en
`OneToOneField` sur le job, `socle.services` ne lit que le socle du dossier
courant, et `fact_store.load_facts_block` — qui ferait ce travail — n'est
appelé que depuis `context.build_context`, l'ancienne chaîne que la production
n'emprunte pas.

Ces tests échouent sur le code d'avant : `socle.heritage` n'existait pas, et
`construire_prompt_socle` n'avait pas de paramètre où le recevoir.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.utils import timezone

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import GenerationJob, JobStatus, SocleDonnees, SocleStatut
from generation.socle.heritage import (
    MAX_CHIFFRES_HERITES,
    chiffres_du_livrable_precedent,
)
from orders.models import Order

EM = DeliverableType.MARKET_STUDY
EC = DeliverableType.COMPETITOR_STUDY

#: Le chiffre qui diverge dans le dossier réel.
MARCHE_DE_LA_ZONE = {
    "donnees": [
        {
            "id": "marche_zone_total",
            "libelle": "Marché total de la zone (vins, spiritueux, fromages)",
            "valeur": 1902.0,
            "unite": "MEUR",
            "annee": 2025,
            "perimetre": "continent",
        },
        {
            "id": "part_france",
            "libelle": "Part de la France dans la zone",
            "valeur": 34.0,
            "unite": "pourcent",
            "annee": 2025,
            "perimetre": "continent",
        },
    ],
}


@pytest.fixture
def client_avec_deux_commandes(db: Any) -> Customer:
    return Customer.objects.create(email="heritage@test.local")


def _job(
    customer: Customer,
    livrable: str,
    *,
    reference: str,
    statut: str = JobStatus.DONE,
) -> GenerationJob:
    offre = Offer.objects.create(
        name=f"offre {reference}", slug=f"heritage-{reference}", deliverable_type=livrable,
    )
    commande = Order.objects.create(
        systeme_order_id=f"cmd-{reference}", customer=customer, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande,
        deliverable_type=livrable,
        budget_eur=Decimal("8.0000"),
        status=statut,
        completed_at=timezone.now(),
    )


def test_l_etude_de_la_concurrence_herite_du_marche(
    client_avec_deux_commandes: Customer,
) -> None:
    """Le test qui échoue sur le code d'avant : rien ne traversait les dossiers."""
    marche = _job(client_avec_deux_commandes, EM, reference="em")
    SocleDonnees.objects.create(
        job=marche, statut=SocleStatut.VALIDE, contenu=MARCHE_DE_LA_ZONE,
    )
    concurrence = _job(client_avec_deux_commandes, EC, reference="ec")

    bloc = chiffres_du_livrable_precedent(concurrence)

    assert "1902" in bloc.replace(" ", "").replace(" ", "")
    assert "Marché total de la zone" in bloc
    assert "2025" in bloc
    # La consigne, pas seulement les chiffres : c'est elle qui fait le travail.
    assert "À L'IDENTIQUE" in bloc
    # Et le droit de s'en écarter, à condition de le DIRE.
    assert "NOMME l'écart" in bloc


def test_le_dossier_courant_ne_s_herite_pas_de_lui_meme(
    client_avec_deux_commandes: Customer,
) -> None:
    """Contre-épreuve : un seul dossier, rien à hériter."""
    seul = _job(client_avec_deux_commandes, EC, reference="seul")
    SocleDonnees.objects.create(
        job=seul, statut=SocleStatut.VALIDE, contenu=MARCHE_DE_LA_ZONE,
    )
    assert chiffres_du_livrable_precedent(seul) == ""


def test_un_socle_refuse_ne_s_herite_pas(
    client_avec_deux_commandes: Customer,
) -> None:
    """Contre-épreuve : s'aligner sur des chiffres refusés propagerait la faute."""
    marche = _job(client_avec_deux_commandes, EM, reference="em-rate")
    SocleDonnees.objects.create(
        job=marche, statut=SocleStatut.INVALIDE, contenu=MARCHE_DE_LA_ZONE,
    )
    concurrence = _job(client_avec_deux_commandes, EC, reference="ec-rate")

    assert chiffres_du_livrable_precedent(concurrence) == ""


def test_un_dossier_d_un_AUTRE_client_ne_s_herite_pas(db: Any) -> None:
    """Contre-épreuve capitale : les chiffres d'un client ne passent pas chez un autre."""
    premier = Customer.objects.create(email="un@test.local")
    second = Customer.objects.create(email="deux@test.local")
    marche = _job(premier, EM, reference="autre-em")
    SocleDonnees.objects.create(
        job=marche, statut=SocleStatut.VALIDE, contenu=MARCHE_DE_LA_ZONE,
    )
    concurrence = _job(second, EC, reference="autre-ec")

    assert chiffres_du_livrable_precedent(concurrence) == ""


def test_un_dossier_en_cours_ne_s_herite_pas(
    client_avec_deux_commandes: Customer,
) -> None:
    """Contre-épreuve : un dossier qui n'a pas abouti n'a rien de validé."""
    marche = _job(
        client_avec_deux_commandes, EM, reference="em-cours", statut=JobStatus.RUNNING,
    )
    SocleDonnees.objects.create(
        job=marche, statut=SocleStatut.VALIDE, contenu=MARCHE_DE_LA_ZONE,
    )
    concurrence = _job(client_avec_deux_commandes, EC, reference="ec-cours")

    assert chiffres_du_livrable_precedent(concurrence) == ""


def test_un_socle_vide_ne_produit_pas_un_bloc_vide(
    client_avec_deux_commandes: Customer,
) -> None:
    """Règle 1 : sans chiffre à transmettre, pas de bloc — et pas de faux bloc."""
    marche = _job(client_avec_deux_commandes, EM, reference="em-vide")
    SocleDonnees.objects.create(job=marche, statut=SocleStatut.VALIDE, contenu={})
    concurrence = _job(client_avec_deux_commandes, EC, reference="ec-vide")

    assert chiffres_du_livrable_precedent(concurrence) == ""


def test_le_nombre_de_chiffres_transmis_est_borne(
    client_avec_deux_commandes: Customer,
) -> None:
    """Chaque ligne coûte des jetons : au-delà, c'est le document recopié."""
    marche = _job(client_avec_deux_commandes, EM, reference="em-long")
    SocleDonnees.objects.create(
        job=marche, statut=SocleStatut.VALIDE,
        contenu={"donnees": [
            {"id": f"d{n}", "libelle": f"Donnée {n}", "valeur": float(n),
             "unite": "MEUR", "annee": 2025, "perimetre": "national"}
            for n in range(MAX_CHIFFRES_HERITES + 20)
        ]},
    )
    concurrence = _job(client_avec_deux_commandes, EC, reference="ec-long")

    bloc = chiffres_du_livrable_precedent(concurrence)
    assert bloc.count("\n- ") == MAX_CHIFFRES_HERITES


def test_le_prompt_du_socle_porte_le_bloc() -> None:
    """Écrit mais pas branché, c'est le défaut de Gamma : on vérifie le câble."""
    from generation.socle.prompt import construire_prompt_socle

    herite = "CHIFFRES DÉJÀ POSÉS POUR CE CLIENT — marché total 1 902 M€."
    prompt = construire_prompt_socle(
        deliverable_type=EC,
        variables={"SECTEUR": "vins"},
        chiffres_herites=herite,
    )
    assert herite in prompt
    # Contre-épreuve : sans héritage, le prompt ne porte aucun bloc vide.
    assert "CHIFFRES DÉJÀ POSÉS" not in construire_prompt_socle(
        deliverable_type=EC, variables={"SECTEUR": "vins"},
    )
