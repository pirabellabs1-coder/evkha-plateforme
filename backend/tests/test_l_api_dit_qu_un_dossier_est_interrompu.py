"""L'API dit elle-même qu'un dossier est interrompu ; le front ne le redéduit pas.

## Pourquoi ce champ existe

Le bouton « Relancer la génération » existait déjà sur la fiche d'un dossier.
Sa condition d'affichage était écrite en TypeScript :

    const canRelaunch = data.status === "failed" || data.status === "cancelled";

Plus stricte que ce que le serveur accepte. Le bouton était donc caché
**exactement dans le cas qui l'a fait écrire** : le 09/08/2026, la génération
d'une cliente est tuée par un déploiement, son dossier reste `running`
soixante-seize minutes, et la relancer a demandé une requête HTTP à la main.

Deux endroits décidaient de la même chose et n'étaient pas d'accord — le défaut
que la règle 5 condamne, ici entre deux langages.

La règle vit désormais dans `generation.services`, l'API la publie
(`interrompue`), et le front la relit. Une seule source.

## Ce que le test vérifie, et qui n'est pas évident

Que la valeur publiée SUIT la règle, dans les deux sens. Un champ toujours vrai
ou toujours faux satisferait un test d'existence et ne dirait rien.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import ChapterGeneration, ChapterStatus, GenerationJob, JobStatus
from orders.models import Order

JETON = "k" * 64


@pytest.fixture
def job(db: Any) -> GenerationJob:
    offre = Offer.objects.create(
        name="EM", slug="api-interrompu", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="api-interrompu@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-api-interrompu", customer=client, offer=offre,
    )
    dossier = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        status=JobStatus.RUNNING,
        started_at=timezone.now() - timedelta(minutes=76),
    )
    ChapterGeneration.objects.create(
        job=dossier, chapter_number=1, chapter_title="Un", prompt_key="em.01",
        status=ChapterStatus.DONE,
    )
    return dossier


@pytest.fixture
def api(settings: Any) -> Client:
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON
    settings.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ""
    return Client(HTTP_AUTHORIZATION=f"Bearer {JETON}")


def _vieillir(job: GenerationJob, minutes: int) -> None:
    job.chapters.all().update(updated_at=timezone.now() - timedelta(minutes=minutes))


def _liste(api: Client) -> dict[str, Any]:
    reponse = api.get("/api/dashboard/jobs/")
    assert reponse.status_code == 200, reponse.content
    return json.loads(reponse.content)[0]  # type: ignore[no-any-return]


def test_un_dossier_fige_est_annonce_interrompu(api: Client, job: GenerationJob) -> None:
    _vieillir(job, 76)

    item = _liste(api)

    assert item["interrompue"] is True
    assert item["minutes_sans_progression"] >= 76


def test_un_dossier_qui_progresse_ne_l_est_pas(api: Client, job: GenerationJob) -> None:
    """Contre-épreuve : un champ toujours vrai ne mesurerait rien."""
    _vieillir(job, 4)

    item = _liste(api)

    assert item["interrompue"] is False
    assert item["minutes_sans_progression"] == 4


def test_un_dossier_termine_n_a_pas_de_silence(api: Client, job: GenerationJob) -> None:
    """La question ne se pose pas hors « en cours » : `null`, pas zéro.

    Zéro se lirait « il vient de produire quelque chose », ce qui est faux.
    """
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])
    _vieillir(job, 300)

    item = _liste(api)

    assert item["interrompue"] is False
    assert item["minutes_sans_progression"] is None


def test_la_fiche_publie_les_memes_champs_que_la_liste(
    api: Client, job: GenerationJob
) -> None:
    """Deux écrans, une seule vérité — sinon le bouton diffère selon la page."""
    _vieillir(job, 76)

    reponse = api.get(f"/api/dashboard/jobs/{job.id}/")

    assert reponse.status_code == 200, reponse.content
    fiche = json.loads(reponse.content)
    assert fiche["interrompue"] is True
    assert fiche["minutes_sans_progression"] >= 76
