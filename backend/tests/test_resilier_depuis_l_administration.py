"""Un opérateur doit pouvoir retirer un abonnement sans ouvrir la base.

## Ce qui manquait

`organisations.services.resilier` existait, et il était juste. Mais il n'était
atteignable que par le traitement d'une DEMANDE venue de l'espace client. Un
abonnement posé par erreur, ou un compte d'essai, n'avait aucun geste : il
fallait ouvrir l'administration Django et changer un statut à la main.

Constaté le 09/08/2026. Le tableau de bord annonçait **189 € de revenu
récurrent** alors qu'aucun client ne payait. Le montant était juste — il
additionne les abonnements actifs — mais il venait d'un compte d'essai créé au
début du projet. **Le chiffre le plus regardé de l'écran était faux pour une
raison qu'aucun écran ne permettait de corriger.**

C'est le même manque que le bouton « Relancer » du même jour : l'action existe
en base, pas dans l'interface. Une fonctionnalité qu'on ne peut atteindre que
par la console n'est pas livrée.

## Ce que la résiliation ne fait pas

Elle ne reprend aucun crédit. Le mois en cours est payé ; les retirer au clic
serait prendre au client ce qu'il a acheté. La réserve expire à la bascule de
période, par `organisations.tasks.appliquer_echeances`.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from customers.models import Customer
from organisations import services
from organisations.models import (
    AbonnementOrganisation,
    Organisation,
    StatutAbonnement,
)

from .aides_abonnement import abonner, formule_de_test

JETON = "r" * 64


@pytest.fixture
def api(settings: Any) -> Client:
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON
    settings.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ""
    return Client(HTTP_AUTHORIZATION=f"Bearer {JETON}")


@pytest.fixture
def organisation(db: Any) -> Organisation:
    """Une organisation complète — contact, propriétaire, portefeuille.

    Passe par `services.creer_organisation` plutôt que par le modèle : les trois
    sont indissociables, et une doublure qui n'en pose qu'un décrit un état qui
    n'existe pas en production (règle 7).
    """
    contact = Customer.objects.create(email="essai@resiliation.test")
    return services.creer_organisation(
        raison_sociale="Compte d'essai", contact=contact
    )


@pytest.fixture
def abonnement(organisation: Organisation) -> AbonnementOrganisation:
    """Un abonnement ACTIF à 189 €, comme celui trouvé en production."""
    abonner(organisation, formule_de_test())
    actif = organisation.abonnements.filter(statut=StatutAbonnement.ACTIF).first()
    assert actif is not None
    return actif


def _resilier(api: Client, organisation: Organisation, **corps: Any) -> Any:
    return api.post(
        f"/api/dashboard/supervision/organisations/{organisation.id}/resilier/",
        data=json.dumps(corps),
        content_type="application/json",
    )


def test_un_abonnement_d_essai_se_resilie_depuis_l_ecran(
    api: Client, organisation: Organisation, abonnement: AbonnementOrganisation
) -> None:
    """Le cas exact des 189 €."""
    reponse = _resilier(api, organisation, motif="Compte d'essai du début du projet")

    assert reponse.status_code == 200, reponse.content
    assert json.loads(reponse.content)["abonnements_resilies"] == 1
    abonnement.refresh_from_db()
    assert abonnement.statut == StatutAbonnement.RESILIE
    assert abonnement.fin_le is not None


def test_le_motif_est_obligatoire(
    api: Client, organisation: Organisation, abonnement: AbonnementOrganisation
) -> None:
    """Une résiliation sans raison écrite ne s'explique plus trois mois après.

    Même exigence que pour la suspension — la règle ne change pas selon
    l'action, sinon elle n'est pas une règle.
    """
    reponse = _resilier(api, organisation, motif="   ")

    assert reponse.status_code == 400
    assert json.loads(reponse.content)["code"] == "motif_manquant"
    abonnement.refresh_from_db()
    assert abonnement.statut == StatutAbonnement.ACTIF


def test_sans_abonnement_actif_le_clic_le_DIT(
    api: Client, organisation: Organisation
) -> None:
    """Contre-épreuve, et c'est la règle 1 : ne pas rendre 200 sur un non-geste.

    Un succès sur une action qui n'a rien fait laisserait croire que le revenu
    récurrent va baisser. Il ne bougerait pas, et personne ne saurait pourquoi.
    """
    reponse = _resilier(api, organisation, motif="Rien à résilier ici")

    assert reponse.status_code == 409
    assert json.loads(reponse.content)["code"] == "aucun_abonnement_actif"


def test_resilier_deux_fois_ne_reussit_qu_une_fois(
    api: Client, organisation: Organisation, abonnement: AbonnementOrganisation
) -> None:
    """Le second clic doit être franc, pas silencieusement complaisant."""
    assert _resilier(api, organisation, motif="Essai").status_code == 200

    assert _resilier(api, organisation, motif="Essai").status_code == 409


def test_les_credits_deja_acquis_ne_sont_pas_repris(
    api: Client, organisation: Organisation, abonnement: AbonnementOrganisation
) -> None:
    """Le mois en cours est payé. Les reprendre au clic serait le lui voler.

    La réserve expire à la bascule de période, pas à la résiliation — c'est
    `organisations.tasks.appliquer_echeances` qui s'en charge.
    """
    from organisations import credits

    credits.crediter(organisation, 8, motif="Dotation d'essai")
    assert credits.solde(organisation) == 8

    _resilier(api, organisation, motif="Compte d'essai")

    assert credits.solde(organisation) == 8


def test_une_organisation_inconnue_rend_404(api: Client, db: Any) -> None:
    reponse = api.post(
        "/api/dashboard/supervision/organisations/"
        "00000000-0000-0000-0000-000000000000/resilier/",
        data=json.dumps({"motif": "Test"}),
        content_type="application/json",
    )

    assert reponse.status_code == 404


def test_la_route_est_protegee_par_le_jeton(
    settings: Any, organisation: Organisation
) -> None:
    """Résilier est une action ; elle ne s'ouvre pas plus que le reste."""
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON

    reponse = Client().post(
        f"/api/dashboard/supervision/organisations/{organisation.id}/resilier/",
        data=json.dumps({"motif": "Test"}),
        content_type="application/json",
    )

    assert reponse.status_code == 401
