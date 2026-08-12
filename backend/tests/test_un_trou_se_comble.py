"""Un dossier terminé avec un chapitre en échec doit pouvoir être relancé.

## Le cas réel

Stratégie `0f9fb13a` (11/08/2026, cliente EVKHA) : le chapitre 0 — la fiche
projet — perdu sur un encadré d'une ligne de trop, vingt chapitres livrés, et
**aucun moyen de récupérer le vingt-et-unième**.

## Deux règles qui ne se parlaient pas

`run_generation_job` ne marque plus FAILED un dossier dont un chapitre a
coincé : il livre le reste avec un trou nommé, ce qui vaut infiniment mieux
que de perdre vingt-deux chapitres corrects.

Mais la relance n'a jamais appris cette nuance. Elle n'acceptait que `failed`
et `cancelled` — donc le trou devenait DÉFINITIF. Deux moitiés d'une même
décision, écrites à deux endroits, qui ont fini par se contredire (règle 5).

La relance ne réécrit que les chapitres FAILED ou SKIPPED : les vingt autres
sont conservés, et la dépense se limite au trou.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import Client, override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import (
    ChapterGeneration,
    ChapterStatus,
    GenerationJob,
    JobStatus,
)
from orders.models import Order


def _job_avec(statuts: list[str], job_status: str = JobStatus.DONE) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="trou", defaults={"name": "Stratégie",
                               "deliverable_type": DeliverableType.BUSINESS_STRATEGY},
    )
    client, _ = Customer.objects.get_or_create(email="trou@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"trou-{job_status}-{'-'.join(statuts)}",
        customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande,
        status=job_status,
        deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )
    for numero, statut in enumerate(statuts):
        ChapterGeneration.objects.create(
            job=job, chapter_number=numero,
            chapter_title=f"Chapitre {numero}", status=statut,
        )
    return job


@pytest.fixture(autouse=True)
def _sans_generation_reelle(monkeypatch: pytest.MonkeyPatch) -> None:
    """La tâche de génération est neutralisée : on éprouve le GARDE-FOU.

    La laisser partir ferait tourner une vraie chaîne de production dans un
    test — lente, et qui échouerait sur une commande minimale sans mesurer
    quoi que ce soit de la question posée ici.
    """
    import dashboard.views as vues

    monkeypatch.setattr(
        vues.run_generation_job_task, "delay", lambda *_a, **_k: None
    )


def _relancer(job: GenerationJob) -> Any:
    with override_settings(DEBUG=True, EVKHA_DASHBOARD_AUTH_DISABLED=True):
        return Client().post(f"/api/dashboard/jobs/{job.id}/relaunch/")


@pytest.mark.django_db
def test_un_dossier_termine_avec_un_trou_se_relance() -> None:
    """Le défaut exact : vingt chapitres livrés, le vingt-et-unième perdu."""
    job = _job_avec([ChapterStatus.FAILED] + [ChapterStatus.DONE] * 20)

    reponse = _relancer(job)

    assert reponse.status_code in (200, 202), reponse.content
    job.refresh_from_db()
    assert job.status == JobStatus.PENDING


@pytest.mark.django_db
def test_seul_le_chapitre_en_echec_est_remis_a_produire() -> None:
    """La dépense se limite au trou : les vingt autres sont conservés."""
    job = _job_avec([ChapterStatus.FAILED] + [ChapterStatus.DONE] * 20)

    _relancer(job)

    a_refaire = job.chapters.filter(status=ChapterStatus.PENDING)
    assert [c.chapter_number for c in a_refaire] == [0]
    assert job.chapters.filter(status=ChapterStatus.DONE).count() == 20


@pytest.mark.django_db
def test_un_dossier_complet_ne_se_relance_pas() -> None:
    """CONTRE-ÉPREUVE : sans trou, relancer ferait repayer pour rien.

    C'est la raison d'être du refus : une relance sur un dossier complet
    n'aurait rien à réécrire et coûterait une génération entière.
    """
    job = _job_avec([ChapterStatus.DONE] * 21)

    reponse = _relancer(job)

    assert reponse.status_code == 400
    assert "chapitre en échec" in reponse.json()["error"]


@pytest.mark.django_db
def test_un_dossier_qui_progresse_encore_reste_protege() -> None:
    """CONTRE-ÉPREUVE : relancer un dossier vivant paierait deux fois."""
    job = _job_avec(
        [ChapterStatus.DONE, ChapterStatus.RUNNING], job_status=JobStatus.RUNNING
    )

    reponse = _relancer(job)

    assert reponse.status_code == 400
