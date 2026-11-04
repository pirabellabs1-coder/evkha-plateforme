"""« Ajouter un client » rendait « Erreur 500 », et rien ne disait pourquoi.

04/11/2026 : deux fois de suite en production. La création d'une fiche
n'appliquait pas la garde de longueur que sa correction appliquait déjà — une
valeur plus longue que sa colonne passe sous SQLite et tombe sous PostgreSQL.
Et les journaux de Coolify ne montraient que « POST … 500 ».
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client, RequestFactory

from monitoring.middleware import IncidentSurErreur500
from monitoring.models import OperationalIncident
from organisations.models import ClientFinal
from tests.test_lot4_commander import Abonne

pytestmark = pytest.mark.django_db

URL = "/api/espace/clients-finaux/"


def _creer(abonne: Abonne, corps: dict[str, Any]) -> Any:
    return Client().post(
        URL, data=json.dumps(corps, ensure_ascii=False),
        content_type="application/json", headers=abonne.entetes,
    )


@pytest.fixture
def abonne() -> Abonne:
    return Abonne("Agence Sun", "sun-clients@example.com")


def test_un_secteur_trop_long_est_refuse_clairement(abonne: Abonne) -> None:
    reponse = _creer(abonne, {"raison_sociale": "SUN TZU", "secteur": "terroir " * 40})

    assert reponse.status_code == 400
    assert "Secteur" in json.loads(reponse.content)["error"]
    assert not ClientFinal.objects.exists()


def test_une_fiche_ordinaire_se_cree(abonne: Abonne) -> None:
    """Contre-épreuve : la garde ne bloque pas une saisie normale."""
    reponse = _creer(abonne, {
        "raison_sociale": "SUN TZU ORGANISATION", "secteur": "Produits du terroir",
        "pays": "France", "ville": "Lyon",
    })

    assert reponse.status_code == 201
    client = ClientFinal.objects.get()
    assert (client.secteur, client.pays, client.ville) == ("Produits du terroir", "France", "Lyon")


def test_un_doublon_rend_409(abonne: Abonne) -> None:
    _creer(abonne, {"raison_sociale": "SUN TZU"})
    assert _creer(abonne, {"raison_sociale": "SUN TZU"}).status_code == 409


def test_une_erreur_500_laisse_un_incident_qui_dit_sa_cause() -> None:
    requete = RequestFactory().post("/api/espace/clients-finaux/")
    intergiciel = IncidentSurErreur500(lambda r: None)  # type: ignore[arg-type,return-value]

    try:
        raise ValueError("value too long for type character varying(200)")
    except ValueError as erreur:
        intergiciel.process_exception(requete, erreur)
        intergiciel.process_exception(requete, erreur)

    incident = OperationalIncident.objects.get()
    assert "POST /api/espace/clients-finaux/" in incident.title
    assert "character varying(200)" in incident.details["exception"]
    assert incident.details["pile"]
