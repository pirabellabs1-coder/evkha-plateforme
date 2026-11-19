"""Un incident de gravité haute doit être une panne, et un incident par dossier un seul.

Mesuré en production le 19/11/2026 : 433 incidents ouverts, dont 98 de gravité
haute ou critique. Parmi eux, des réponses normales du serveur comptées comme
des erreurs 500, et le même constat ouvert deux fois pour le même dossier. Un
tableau d'incidents où les vraies pannes sont noyées ne sert plus à rien.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from documents.livrable_word import (
    INCIDENT_TYPE_VISUELS_ABANDONNES,
    _consigner_les_visuels_abandonnes,
)
from generation.models import GenerationJob
from generation.rendu_word.assemblage import RapportAssemblage
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from monitoring.middleware import IncidentSurErreur500
from monitoring.models import OperationalIncident
from orders.models import Order

pytestmark = pytest.mark.django_db


def make_job() -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="bp-incidents",
        defaults={"name": "Business plan", "deliverable_type": DeliverableType.BUSINESS_PLAN},
    )
    client = Customer.objects.create(email="incidents@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-incidents", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "ateliers", "PAYS": "France", "PROJET": "Test"},
    )
    return bootstrap_generation_job(soumission)


def _intergiciel() -> IncidentSurErreur500:
    return IncidentSurErreur500(lambda r: None)  # type: ignore[arg-type,return-value]


@pytest.mark.parametrize("exception", [
    Http404("« /app/staticfiles/admin/js/nav_sidebar.js.map » n'existe pas"),
    PermissionDenied("réservé à l'administration"),
])
def test_une_reponse_introuvable_ou_interdite_n_est_pas_une_erreur_500(
    exception: Exception,
) -> None:
    requete = RequestFactory().get("/static/admin/js/nav_sidebar.js.map")

    _intergiciel().process_exception(requete, exception)

    assert not OperationalIncident.objects.exists()


def test_une_vraie_exception_laisse_toujours_son_incident() -> None:
    """Contre-épreuve : ce pour quoi le middleware existe."""
    requete = RequestFactory().post("/api/espace/clients-finaux/")

    try:
        raise ValueError("value too long for type character varying(200)")
    except ValueError as erreur:
        _intergiciel().process_exception(requete, erreur)

    assert OperationalIncident.objects.get().details["type"] == "erreur_500"


def _rapport(rendus: int, abandonnes: list[str]) -> Any:
    rapport = RapportAssemblage()
    rapport.graphiques_demandes = rendus + len(abandonnes)
    rapport.graphiques_rendus = rendus
    rapport.graphiques_abandonnes = list(abandonnes)
    return rapport


def test_l_incident_des_figures_compte_ce_qui_manque_et_reste_unique() -> None:
    """Le dossier `68b6ab61` : « (15/17) » lu comme quinze figures abandonnées, et
    deux incidents pour deux assemblages du même dossier."""
    job = make_job()

    _consigner_les_visuels_abandonnes(job, _rapport(14, ["ch. 2 · frise", "ch. 14 · barres"]))
    _consigner_les_visuels_abandonnes(job, _rapport(15, ["ch. 2 · frise", "ch. 14 · barres"]))

    incident = OperationalIncident.objects.get(
        details__type=INCIDENT_TYPE_VISUELS_ABANDONNES,
    )
    assert incident.title.startswith("2 figure(s) abandonnée(s) sur 17")
    assert incident.details["rendus"] == 15


def test_un_assemblage_sans_figure_abandonnee_ne_cree_rien() -> None:
    """Contre-épreuve."""
    _consigner_les_visuels_abandonnes(make_job(), _rapport(12, []))

    assert not OperationalIncident.objects.exists()
