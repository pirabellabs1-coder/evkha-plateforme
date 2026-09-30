"""Une reprise faite depuis la console se range dans l'espace de la cliente, sur demande.

## Le cas réel

30/09/2026, business plan ÉCLORE `28a257bf` : reprise « sans envoi » de
`cb59cede`, faite à nos frais. Le document était prêt, mais l'espace de la
cliente ne le montrait pas : la bibliothèque ne liste que les commandes
rattachées à l'organisation, et `job_regenerer` crée une commande neuve sans
rattachement. L'utilisateur : « ce qui est déjà généré, il faut juste le
rendre visible », sans nouvelle génération.

## Ce que ce fichier verrouille

1. `POST jobs/<id>/rendre-visible/` range la reprise dans l'espace de
   l'organisation de la commande d'origine, et la bibliothèque la montre avec
   ses fichiers ;
2. rien d'autre : aucun courriel, aucune génération, aucun crédit ;
3. contre-épreuves (règle 6) : un dossier qui n'est pas une reprise, une
   reprise non terminée, une commande d'origine sans organisation ne se
   rangent pas ; les AUTRES reprises restent cachées ; deux appels valent un ;
   la route exige le jeton.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.core import mail
from django.test import Client
from django.utils import timezone

from catalog.models import DeliverableType, Offer
from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact
from generation.models import GenerationJob, JobStatus
from orders.models import Order
from organisations import credits
from tests.test_lot4_espace_client import Agence, charge

pytestmark = pytest.mark.django_db


@pytest.fixture
def agence() -> Agence:
    return Agence("Éclore Conseil", "reprise-visible@exemple.fr")


def _offre() -> Offer:
    offre, _ = Offer.objects.get_or_create(
        slug="bp-reprise-visible",
        defaults={"name": "Business plan", "deliverable_type": DeliverableType.BUSINESS_PLAN},
    )
    return offre


def _origine(agence: Agence, *, rattachee: bool = True) -> GenerationJob:
    commande = Order.objects.create(
        systeme_order_id=f"espace-origine-{Order.objects.count()}",
        customer=agence.contact,
        offer=_offre(),
        organisation=agence.organisation if rattachee else None,
    )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN, status=JobStatus.DONE,
    )


def _reprise(origine: GenerationJob, *, statut: str = JobStatus.DONE) -> GenerationJob:
    """La commande que `job_regenerer` crée : identifiant préfixé, sans organisation."""
    commande = Order.objects.create(
        systeme_order_id=f"reprise-{str(origine.id)[:8]}-{Order.objects.count():08d}",
        customer=origine.order.customer,
        offer=_offre(),
        raw_payload={"reprise_de": str(origine.id), "sans_envoi": True},
    )
    job = GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN, status=statut,
    )
    DocumentArtifact.objects.create(
        job=job, kind=ArtifactKind.PDF, status=ArtifactStatus.READY,
        storage_key=f"livrables/{job.id}/etude.pdf",
        download_url=f"https://api.exemple/media/livrables/{job.id}/etude.pdf?s=x",
        expires_at=timezone.now() + timedelta(days=300),
    )
    return job


def _bibliotheque(agence: Agence) -> dict[str, Any]:
    corps = charge(Client().get("/api/espace/livrables/", headers=agence.entetes))
    return {ligne["id"]: ligne for ligne in corps["livrables"]}


def test_la_reprise_apparait_dans_l_espace_avec_ses_fichiers(
    client_admin: Any, agence: Agence,
) -> None:
    reprise = _reprise(_origine(agence))
    assert str(reprise.id) not in _bibliotheque(agence), "le défaut du 30/09/2026"

    reponse = client_admin.post(f"/api/dashboard/jobs/{reprise.id}/rendre-visible/")

    assert reponse.status_code == 200 and reponse.json()["visible"] is True
    ligne = _bibliotheque(agence)[str(reprise.id)]
    assert [f["kind"] for f in ligne["fichiers"]] == [ArtifactKind.PDF]


def test_ranger_n_envoie_rien_ne_genere_rien_ne_debite_rien(
    client_admin: Any, agence: Agence,
) -> None:
    reprise = _reprise(_origine(agence))
    dossiers = GenerationJob.objects.count()
    solde = credits.solde(agence.organisation)

    client_admin.post(f"/api/dashboard/jobs/{reprise.id}/rendre-visible/")

    assert mail.outbox == []
    assert GenerationJob.objects.count() == dossiers
    assert credits.solde(agence.organisation) == solde
    reprise.refresh_from_db()
    assert reprise.status == JobStatus.DONE


def test_les_autres_reprises_restent_cachees(client_admin: Any, agence: Agence) -> None:
    origine = _origine(agence)
    rangee, cachee = _reprise(origine), _reprise(origine)

    client_admin.post(f"/api/dashboard/jobs/{rangee.id}/rendre-visible/")

    bibliotheque = _bibliotheque(agence)
    assert str(rangee.id) in bibliotheque and str(cachee.id) not in bibliotheque


def test_deux_appels_valent_un(client_admin: Any, agence: Agence) -> None:
    reprise = _reprise(_origine(agence))
    client_admin.post(f"/api/dashboard/jobs/{reprise.id}/rendre-visible/")

    reponse = client_admin.post(f"/api/dashboard/jobs/{reprise.id}/rendre-visible/")

    assert reponse.status_code == 200 and "Déjà visible" in reponse.json()["message"]


def test_un_dossier_qui_n_est_pas_une_reprise_ne_se_range_pas(
    client_admin: Any, agence: Agence,
) -> None:
    """Rattacher une commande quelconque, c'est deviner son organisation."""
    commande = Order.objects.create(
        systeme_order_id="systeme-io-123", customer=agence.contact, offer=_offre(),
    )
    job = GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN, status=JobStatus.DONE,
    )

    reponse = client_admin.post(f"/api/dashboard/jobs/{job.id}/rendre-visible/")

    assert reponse.status_code == 409
    commande.refresh_from_db()
    assert commande.organisation_id is None


def test_une_reprise_non_terminee_ne_se_range_pas(client_admin: Any, agence: Agence) -> None:
    reprise = _reprise(_origine(agence), statut=JobStatus.RUNNING)

    reponse = client_admin.post(f"/api/dashboard/jobs/{reprise.id}/rendre-visible/")

    assert reponse.status_code == 409
    assert str(reprise.id) not in _bibliotheque(agence)


def test_sans_organisation_d_origine_rien_ne_se_devine(
    client_admin: Any, agence: Agence,
) -> None:
    reprise = _reprise(_origine(agence, rattachee=False))

    reponse = client_admin.post(f"/api/dashboard/jobs/{reprise.id}/rendre-visible/")

    assert reponse.status_code == 409
    reprise.order.refresh_from_db()
    assert reprise.order.organisation_id is None


def test_la_route_exige_le_jeton(client: Any, agence: Agence) -> None:
    reprise = _reprise(_origine(agence))

    reponse = client.post(f"/api/dashboard/jobs/{reprise.id}/rendre-visible/")

    assert reponse.status_code in (401, 403)
    assert str(reprise.id) not in _bibliotheque(agence)
