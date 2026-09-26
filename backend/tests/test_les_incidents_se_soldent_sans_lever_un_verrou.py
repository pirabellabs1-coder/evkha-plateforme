"""Les incidents se soldent d'un coup, sans lever un verrou de livraison.

Le 26/09/2026, le tableau de bord comptait 477 incidents ouverts (195
graves), essentiellement des traces de rejeux de contrôle : un compteur qui
ne redescend jamais ne signale plus rien. La résolution unitaire ne
suffisait pas — la liste ne montre que les 50 derniers.

Mais un incident `check_bloc_non_resolu` OUVERT bloque la livraison de son
dossier (`gate._check_blocs_evangeline`) : le résoudre, c'est l'autoriser.
Le solde groupé doit donc le conserver tant que le dossier n'est pas livré —
et la contre-épreuve : le résoudre quand le dossier l'est déjà (règle 6).
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client, override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from delivery.models import DeliveryBatch, DeliveryStatus
from generation.checks_blocs import INCIDENT_TYPE_CHECK_BLOC
from generation.models import GenerationJob, JobStatus
from monitoring.models import IncidentSeverity, IncidentStatus, OperationalIncident
from orders.models import Order

URL = "/api/dashboard/incidents/resoudre-tout/"


def _dossier(suffixe: str, *, livre: bool) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="etude-marche-incidents",
        defaults={"name": "Etude de marche", "deliverable_type": DeliverableType.MARKET_STUDY},
    )
    client = Customer.objects.create(email=f"client-{suffixe}@example.com")
    commande = Order.objects.create(
        systeme_order_id=f"commande-incidents-{suffixe}", customer=client, offer=offre
    )
    if livre:
        DeliveryBatch.objects.create(
            order=commande, status=DeliveryStatus.SENT, recipient_email=client.email
        )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.MARKET_STUDY, status=JobStatus.DONE
    )


def _incident(
    titre: str,
    *,
    statut: str = IncidentStatus.OPEN,
    gravite: str = IncidentSeverity.HIGH,
    dossier: GenerationJob | None = None,
    verrou: bool = False,
) -> OperationalIncident:
    return OperationalIncident.objects.create(
        title=titre,
        severity=gravite,
        status=statut,
        job=dossier,
        order=dossier.order if dossier else None,
        details={"type": INCIDENT_TYPE_CHECK_BLOC, "bloc": "B1"} if verrou else {},
    )


@pytest.mark.django_db
def test_solde_tout_sauf_le_verrou_d_un_dossier_non_livre(client_admin: Any) -> None:
    non_livre = _dossier("non-livre", livre=False)
    livre = _dossier("livre", livre=True)
    bruit = _incident("Gate qualité (recontrôle) : toujours bloqué", dossier=livre)
    pris = _incident(
        "Pris en compte", statut=IncidentStatus.ACKNOWLEDGED, gravite=IncidentSeverity.LOW
    )
    verrou_garde = _incident("CHECK B1 non validé", dossier=non_livre, verrou=True)
    verrou_leve = _incident("CHECK B1 non validé (livré)", dossier=livre, verrou=True)
    deja = _incident("Déjà résolu", statut=IncidentStatus.RESOLVED)

    reponse = client_admin.post(URL, data={}, content_type="application/json")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["simulation"] is False
    assert corps["resolus"] == 3
    assert sorted(corps["identifiants"]) == sorted(
        str(i.id) for i in (bruit, pris, verrou_leve)
    )
    assert [v["id"] for v in corps["verrous_conserves"]] == [str(verrou_garde.id)]

    for resolu in (bruit, pris, verrou_leve):
        resolu.refresh_from_db()
        assert resolu.status == IncidentStatus.RESOLVED
        assert resolu.resolved_at is not None
    verrou_garde.refresh_from_db()
    assert verrou_garde.status == IncidentStatus.OPEN, "le verrou de livraison a été levé"
    deja.refresh_from_db()
    assert deja.status == IncidentStatus.RESOLVED

    # Les compteurs du tableau de bord ne voient plus que le verrou conservé.
    apercu = client_admin.get("/api/dashboard/overview/").json()
    assert apercu["incidents"]["open"] == 1


@pytest.mark.django_db
def test_la_simulation_compte_sans_rien_ecrire(client_admin: Any) -> None:
    ouvert = _incident("Ouvert")
    reponse = client_admin.post(URL, data={"simulation": True}, content_type="application/json")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["simulation"] is True
    assert corps["a_resoudre"] == 1
    assert corps["resolus"] == 0
    assert corps["par_gravite"] == {IncidentSeverity.HIGH: 1}
    ouvert.refresh_from_db()
    assert ouvert.status == IncidentStatus.OPEN


@pytest.mark.django_db
def test_sans_rien_a_solder_rien_ne_bouge(client_admin: Any) -> None:
    reponse = client_admin.post(URL, data={}, content_type="application/json")
    assert reponse.status_code == 200
    assert reponse.json()["resolus"] == 0


@pytest.mark.django_db
def test_un_verrou_sans_dossier_ne_verrouille_plus_rien(client_admin: Any) -> None:
    """Le dossier supprimé laisse un incident `job` nul : le gate filtre
    `job=job`, il ne bloque plus rien — il est soldé comme le reste."""
    orphelin = _incident("CHECK B1 non validé (dossier supprimé)", verrou=True)

    corps = client_admin.post(URL, data={}, content_type="application/json").json()

    assert corps["verrous_conserves"] == []
    orphelin.refresh_from_db()
    assert orphelin.status == IncidentStatus.RESOLVED


@pytest.mark.django_db
@pytest.mark.parametrize("corps", ["[]", "null", "123", "{pas du json"])
def test_un_corps_qui_n_est_pas_un_objet_est_refuse(client_admin: Any, corps: str) -> None:
    ouvert = _incident("Ouvert")
    reponse = client_admin.post(URL, data=corps, content_type="application/json")
    assert reponse.status_code == 400
    ouvert.refresh_from_db()
    assert ouvert.status == IncidentStatus.OPEN


@pytest.mark.django_db
def test_seul_un_post_authentifie_solde(client_admin: Any) -> None:
    _incident("Ouvert")
    assert client_admin.get(URL).status_code == 405
    with override_settings(
        EVKHA_DASHBOARD_AUTH_DISABLED=False,
        EVKHA_DASHBOARD_TOKEN="un-autre-jeton-de-trente-deux-signes",
    ):
        refus = Client().post(URL, data={}, content_type="application/json")
    assert refus.status_code == 401
    assert OperationalIncident.objects.filter(status=IncidentStatus.OPEN).count() == 1
