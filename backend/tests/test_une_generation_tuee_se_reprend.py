"""Un dossier tué en cours de route ne doit pas rester « en cours » pour toujours.

## Ce qui est arrivé, le 09/08/2026

Une cliente lance une étude de marché depuis son espace à 06:22:59. Trois
minutes plus tard, un déploiement redémarre les conteneurs et tue le processus
qui produisait ses chapitres. Deux autres déploiements suivent, à 06:43 et 07:27.

Le dossier reste `running` pendant **soixante-seize minutes** : deux chapitres
sur vingt-trois, 0,3562 € dépensés, et pas un centime de mouvement en cent
secondes de mesure. Aucun incident ouvert. Aucun délai de garde. Aucune reprise.
Les journaux du serveur ne montrent qu'une chose : la cliente qui rafraîchit sa
page, devant un document que plus rien ne fabrique.

## Trois défauts, pas un

1. **Le déploiement tue les générations en cours**, et rien ne le rattrape.
2. **Le dossier garde son statut**, donc se déclare vivant sans l'être — le
   silence que la règle 1 condamne, appliqué à un dossier entier.
3. **La relance refusait `running`.** Elle acceptait `failed` et `cancelled`,
   c'est-à-dire tous les états SAUF celui dans lequel on se retrouve. Le seul
   recours était d'annuler — ce qui REMBOURSE, et un dossier remboursé ne
   repart plus. La cliente aurait dû recommander.

## Ce que ce fichier verrouille, et la contre-épreuve qui compte

Relancer un dossier qui travaille vraiment ferait tourner DEUX générations sur
le même dossier : payer deux fois, écrire deux fois les mêmes chapitres. Le
refus reste donc la règle, et l'exception se **mesure** au lieu de se décréter.
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
from generation.services import (
    DELAI_SANS_PROGRESSION,
    duree_sans_progression,
    generation_interrompue,
)
from orders.models import Order

JETON = "j" * 64


@pytest.fixture
def job(db: Any) -> GenerationJob:
    offre = Offer.objects.create(
        name="EM", slug="reprise", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="reprise@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-reprise", customer=client, offer=offre,
    )
    dossier = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        status=JobStatus.RUNNING,
        started_at=timezone.now() - timedelta(minutes=76),
    )
    for numero in (1, 2, 3):
        ChapterGeneration.objects.create(
            job=dossier,
            chapter_number=numero,
            chapter_title=f"Chapitre {numero}",
            prompt_key=f"em.{numero:02d}",
            status=ChapterStatus.DONE if numero < 3 else ChapterStatus.RUNNING,
        )
    return dossier


def _vieillir(job: GenerationJob, minutes: int) -> None:
    """Recule la dernière trace d'activité, comme le ferait le temps."""
    instant = timezone.now() - timedelta(minutes=minutes)
    job.chapters.all().update(updated_at=instant)


def test_un_dossier_qui_progresse_n_est_pas_interrompu(job: GenerationJob) -> None:
    """Contre-épreuve : la lenteur n'est pas une panne."""
    _vieillir(job, 5)

    assert not generation_interrompue(job)


def test_un_dossier_silencieux_depuis_76_minutes_est_interrompu(
    job: GenerationJob,
) -> None:
    """Le cas réel, à sa durée réelle."""
    _vieillir(job, 76)

    assert generation_interrompue(job)
    silence = duree_sans_progression(job)
    assert silence is not None
    assert silence > DELAI_SANS_PROGRESSION


def test_le_seuil_laisse_passer_le_chapitre_le_plus_lent_jamais_mesure(
    job: GenerationJob,
) -> None:
    """10,2 min sur `b561c2d6`. Un seuil sous cette valeur créerait de faux morts.

    C'est la règle 2 : un contrôle qui se déclenche à tort envoie corriger ce
    qui n'était pas cassé — ici, il relancerait une génération vivante.
    """
    _vieillir(job, 11)

    assert not generation_interrompue(job)
    assert DELAI_SANS_PROGRESSION >= timedelta(minutes=20)


@pytest.mark.parametrize(
    "statut",
    [JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED],
)
def test_la_question_ne_se_pose_que_pour_un_dossier_en_cours(
    job: GenerationJob, statut: str
) -> None:
    """Un dossier terminé n'est pas « interrompu » : il est fini."""
    job.status = statut
    job.save(update_fields=["status"])
    _vieillir(job, 300)

    assert duree_sans_progression(job) is None
    assert not generation_interrompue(job)


def test_un_dossier_en_attente_qui_a_DEJA_produit_est_bien_interrompu(
    job: GenerationJob,
) -> None:
    """`pending` était dans la liste ci-dessus. Il en sort, et volontairement.

    Le raisonnement d'origine — « la question ne se pose pas pour un dossier en
    attente » — vaut pour une étude qui attend son tour sans avoir rien produit.
    Il ne vaut pas pour celle-ci : deux chapitres écrits, plus une trace depuis
    cinq heures, et l'étiquette « en attente ». Ce dossier ne démarre pas, il
    est ORPHELIN.

    Mesuré le 17/08/2026 sur le business plan `256e63d8`, qui a écrit
    dix-sept chapitres en portant ce statut. Tant qu'il l'a porté, ni ce
    gardien-ci ni `reset_stuck_generation_jobs` ne pouvaient le voir : tous
    deux ne regardent que `running`. C'est le silence de la règle 1, et il a
    déjà coûté soixante-seize minutes à une cliente le 09/08/2026.

    La contre-épreuve d'à côté — une étude qui attend VRAIMENT — reste dans
    `test_dossier_qui_ecrit_le_dit`.
    """
    job.status = JobStatus.PENDING
    job.save(update_fields=["status"])
    _vieillir(job, 300)

    assert duree_sans_progression(job) is not None
    assert generation_interrompue(job)


@pytest.fixture
def api(settings: Any) -> Client:
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON
    settings.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ""
    return Client(HTTP_AUTHORIZATION=f"Bearer {JETON}")


def test_la_relance_accepte_un_dossier_interrompu(
    api: Client, job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le défaut exact : cet état était le seul que la relance ne prévoyait pas."""
    _vieillir(job, 76)
    envoyes: list[str] = []
    monkeypatch.setattr(
        "dashboard.views.run_generation_job_task",
        type("T", (), {"delay": staticmethod(envoyes.append)}),
    )

    reponse = api.post(f"/api/dashboard/jobs/{job.id}/relaunch/")

    assert reponse.status_code == 202, reponse.content
    assert envoyes == [str(job.id)]
    job.refresh_from_db()
    assert job.status == JobStatus.PENDING


def test_la_relance_refuse_un_dossier_qui_travaille(
    api: Client, job: GenerationJob
) -> None:
    """LA contre-épreuve : deux générations sur un dossier, c'est payer deux fois."""
    _vieillir(job, 3)

    reponse = api.post(f"/api/dashboard/jobs/{job.id}/relaunch/")

    assert reponse.status_code == 400
    assert "progresse encore" in json.loads(reponse.content)["error"]


def test_les_chapitres_deja_ecrits_survivent_a_la_reprise(
    api: Client, job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reprendre au chapitre 3, pas à zéro — 0,3562 € étaient déjà dépensés."""
    _vieillir(job, 76)
    monkeypatch.setattr(
        "dashboard.views.run_generation_job_task",
        type("T", (), {"delay": staticmethod(lambda _: None)}),
    )

    api.post(f"/api/dashboard/jobs/{job.id}/relaunch/")

    assert job.chapters.filter(status=ChapterStatus.DONE).count() == 2
