"""Une reprise à l'identique peut passer par la mémoire de l'étude — sur demande.

29/09/2026 : la mémoire de l'étude reste coupée pour les commandes des clients
(`EVKHA_MEMOIRE_ETUDE`) tant qu'elle n'a pas été éprouvée sur une génération
réelle. La console peut refaire UN dossier avec elle (`{"memoire": true}`), à
nos frais et sans envoi : c'est l'épreuve, sans toucher aux clients.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import GenerationJob
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _sans_generation_reelle(monkeypatch: pytest.MonkeyPatch) -> None:
    from generation.tasks import run_generation_job_task

    monkeypatch.setattr(run_generation_job_task, "delay", lambda *_a, **_k: None)


def _origine() -> GenerationJob:
    offre = Offer.objects.create(
        name="BP", slug="bp-reprise-memoire", deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email="reprise-memoire@exemple.fr")
    commande = Order.objects.create(systeme_order_id="cmd-origine", customer=client, offer=offre)
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "x", "PAYS": "France", "ZONE": "Lyon", "PROJET": "T"},
    )
    with override_settings(EVKHA_MEMOIRE_ETUDE=False):
        return bootstrap_generation_job(soumission)


def _refaire(client_admin: Any, job: GenerationJob, corps: dict[str, Any]) -> Any:
    return client_admin.post(
        f"/api/dashboard/jobs/{job.id}/regenerer/", data=corps, content_type="application/json",
    )


@override_settings(EVKHA_MEMOIRE_ETUDE=False)
def test_la_reprise_demandee_avec_la_memoire_la_porte(client_admin: Any) -> None:
    reponse = _refaire(client_admin, _origine(), {"sans_envoi": True, "memoire": True})
    assert reponse.status_code == 202, reponse.content
    assert reponse.json()["memoire"] is True
    assert GenerationJob.objects.get(id=reponse.json()["job_id"]).memoire_active is True


@override_settings(EVKHA_MEMOIRE_ETUDE=False)
def test_sans_la_demande_la_reprise_garde_le_reglage(client_admin: Any) -> None:
    """Contre-épreuve : le réglage global, coupé, s'applique."""
    reponse = _refaire(client_admin, _origine(), {"sans_envoi": True})
    assert reponse.json()["memoire"] is False
    assert GenerationJob.objects.get(id=reponse.json()["job_id"]).memoire_active is False
