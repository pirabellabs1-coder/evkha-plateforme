"""Un verdict doit pouvoir être rejoué quand le JUGE a changé.

Le 10/08/2026, `026fecea` — dix chapitres propres, 1,94 € — est bloqué par
trois contrôles qui jugeaient le contrat structuré avec les yeux de l'ancien
moteur (chapitre fermé sur sa figure « tronqué », cardinaux additionnés entre
chapitres, annexes numérotées comptées zéro). Les contrôles sont réparés le
soir même — mais le verdict reste écrit en base, et l'écran continue
d'afficher un blocage que plus rien ne justifie.

Sans recontrôle, deux issues, toutes deux mauvaises : livrer sous dérogation
en assumant un blocage FAUX, ou repayer 3,50 € une génération dont le
document existe déjà. Le recontrôle rejoue le gate — lecture seule, zéro
appel IA — et met l'étiquette à jour, dans les deux sens.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import Client, override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import GenerationJob, JobStatus, QAStatus
from monitoring.models import OperationalIncident
from orders.models import Order


def _job(statut: str = JobStatus.DONE, qa: str = QAStatus.BLOCKED) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="recontrole",
        defaults={"name": "Étude de la concurrence",
                  "deliverable_type": DeliverableType.COMPETITOR_STUDY},
    )
    client, _ = Customer.objects.get_or_create(email="recontrole@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"recontrole-{statut}-{qa}", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(order=commande, status=statut, qa_status=qa)


class _Rapport:
    def __init__(self, passed: bool) -> None:
        self.passed = passed
        self.failures = () if passed else ({"check": "x"},)

    def as_details(self) -> dict[str, object]:
        return {"passed": self.passed, "failures": list(self.failures)}


def _poster(job: GenerationJob) -> Any:
    with override_settings(DEBUG=True, EVKHA_DASHBOARD_AUTH_DISABLED=True):
        return Client().post(f"/api/dashboard/jobs/{job.id}/reverifier/")


@pytest.mark.django_db
def test_un_blocage_devenu_faux_est_efface(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le cas `026fecea` : contrôles réparés, verdict rejoué, étiquette juste."""
    import generation.gate as gate

    monkeypatch.setattr(gate, "run_delivery_gate", lambda _job: _Rapport(passed=True))
    job = _job()

    reponse = _poster(job)

    assert reponse.status_code == 200, reponse.content
    job.refresh_from_db()
    assert job.qa_status == QAStatus.PASSED


@pytest.mark.django_db
def test_un_blocage_toujours_justifie_est_confirme_avec_motifs_frais(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRE-ÉPREUVE : le recontrôle n'est pas un tampon.

    Un gate qui échoue encore laisse le blocage EN PLACE et ouvre un incident
    aux motifs frais — relire d'anciens échecs ferait chercher dans le
    document des défauts qui n'y sont plus (règle 2).
    """
    import generation.gate as gate

    monkeypatch.setattr(gate, "run_delivery_gate", lambda _job: _Rapport(passed=False))
    job = _job()

    reponse = _poster(job)

    assert reponse.status_code == 200, reponse.content
    job.refresh_from_db()
    assert job.qa_status == QAStatus.BLOCKED
    assert OperationalIncident.objects.filter(
        job=job, title__contains="recontrôle"
    ).exists()


@pytest.mark.django_db
def test_un_dossier_non_termine_ne_se_recontrole_pas() -> None:
    """Un gate sans document complet n'a rien à juger (règle 1)."""
    job = _job(statut=JobStatus.RUNNING)

    reponse = _poster(job)

    assert reponse.status_code == 400
