"""Un dossier en attente finit par être produit — ou par se voir.

Audit du 19/11/2026. Le dossier `b57a4284` attendait depuis le 03/11, jour où la
file de tâches est tombée : sa tâche a disparu avec Redis, sa ligne est restée
« en attente », et aucun des deux gardiens ne regardait cet état-là. Seize
jours, sans incident ni reprise.

Le second constat est de la même famille : les gardiens eux-mêmes partaient
dans la file des générations, derrière des rédactions de quarante minutes.

Ces tests échouent sur le code d'avant : la tâche n'existait pas, et les routes
ne nommaient que `delivery.*`.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.utils import timezone

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation import tasks
from generation.models import ChapterStatus, GenerationJob, JobStatus
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from monitoring.models import IncidentSeverity, OperationalIncident
from orders.models import Order

pytestmark = pytest.mark.django_db


def _dossier(suffixe: str, *, en_attente_depuis: timedelta) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="ec-attente",
        defaults={
            "name": "Étude de la concurrence",
            "deliverable_type": DeliverableType.COMPETITOR_STUDY,
        },
    )
    client = Customer.objects.create(email=f"attente-{suffixe}@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-attente-{suffixe}", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "ateliers", "PAYS": "France", "PROJET": "Attente"},
    )
    job = bootstrap_generation_job(soumission)
    GenerationJob.objects.filter(pk=job.pk).update(
        updated_at=timezone.now() - en_attente_depuis
    )
    job.refresh_from_db()
    return job


@pytest.fixture
def file(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Ce qui part en file, sans ouvrier ni Redis."""
    partis: list[str] = []
    monkeypatch.setattr(
        tasks.run_generation_job_task, "delay", lambda job_id: partis.append(job_id),
    )
    return partis


# ── Le défaut ───────────────────────────────────────────────────────────────


def test_une_tache_perdue_est_remise_en_file(file: list[str]) -> None:
    job = _dossier("perdu", en_attente_depuis=timedelta(minutes=40))

    assert tasks.reprendre_les_dossiers_en_attente() == 1

    assert file == [str(job.id)]
    incident = OperationalIncident.objects.get(job=job)
    assert incident.details["type"] == "attente_sans_tache"


def test_le_meme_dossier_n_est_pas_remis_en_file_toutes_les_dix_minutes(
    file: list[str],
) -> None:
    """Une file longue n'est pas une panne : une remise par heure suffit."""
    _dossier("patient", en_attente_depuis=timedelta(minutes=40))

    tasks.reprendre_les_dossiers_en_attente()
    tasks.reprendre_les_dossiers_en_attente()

    assert len(file) == 1
    assert OperationalIncident.objects.count() == 1


def test_un_dossier_tres_ancien_se_signale_et_ne_se_produit_pas_seul(
    file: list[str],
) -> None:
    """Seize jours après, produire d'office dépenserait pour un document que
    plus personne n'attend peut-être. Quelqu'un décide."""
    job = _dossier("ancien", en_attente_depuis=timedelta(days=16))

    assert tasks.reprendre_les_dossiers_en_attente() == 0
    tasks.reprendre_les_dossiers_en_attente()

    assert file == []
    incidents = OperationalIncident.objects.filter(job=job)
    assert incidents.count() == 1, "un seul incident, pas un par passage"
    incident = incidents.get()
    assert incident.severity == IncidentSeverity.HIGH
    assert incident.details["jours_d_attente"] == 16


def test_une_file_encore_injoignable_n_use_pas_l_essai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La panne qui a perdu la tâche peut durer : l'essai suivant reste permis."""
    job = _dossier("panne", en_attente_depuis=timedelta(minutes=40))
    essais: list[str] = []

    def tomber(job_id: str) -> None:
        essais.append(job_id)
        raise ConnectionError("Redis ne répond pas")

    monkeypatch.setattr(tasks.run_generation_job_task, "delay", tomber)
    assert tasks.reprendre_les_dossiers_en_attente() == 0
    assert not OperationalIncident.objects.filter(job=job).exists()

    partis: list[str] = []
    monkeypatch.setattr(
        tasks.run_generation_job_task, "delay", lambda job_id: partis.append(job_id),
    )
    assert tasks.reprendre_les_dossiers_en_attente() == 1
    assert partis == [str(job.id)]


# ── Les contre-épreuves ─────────────────────────────────────────────────────


def test_un_dossier_qui_vient_d_etre_commande_attend_son_tour(file: list[str]) -> None:
    _dossier("frais", en_attente_depuis=timedelta(minutes=3))

    assert tasks.reprendre_les_dossiers_en_attente() == 0
    assert file == []


def test_un_dossier_qui_a_deja_produit_n_est_pas_relance_ici(file: list[str]) -> None:
    """« En attente » avec un chapitre écrit : une tâche travaille peut-être sous
    cette étiquette (dossier `256e63d8`, 17/08/2026). La relancer ferait tourner
    deux générations."""
    job = _dossier("engage", en_attente_depuis=timedelta(minutes=40))
    premier = job.chapters.order_by("chapter_number").first()
    assert premier is not None
    type(premier).objects.filter(pk=premier.pk).update(status=ChapterStatus.DONE)

    assert tasks.reprendre_les_dossiers_en_attente() == 0
    assert file == []


@pytest.mark.parametrize(
    "statut", [JobStatus.RUNNING, JobStatus.DONE, JobStatus.CANCELLED, JobStatus.FAILED]
)
def test_seul_un_dossier_en_attente_est_repris(file: list[str], statut: str) -> None:
    job = _dossier(f"statut-{statut}", en_attente_depuis=timedelta(minutes=40))
    GenerationJob.objects.filter(pk=job.pk).update(status=statut)

    assert tasks.reprendre_les_dossiers_en_attente() == 0
    assert file == []


def test_la_tache_remise_en_file_ne_double_pas_celle_qui_attendait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ce qui rend la reprise sans danger : deux tâches, un seul dossier produit."""
    job = _dossier("double", en_attente_depuis=timedelta(minutes=40))
    produits: list[str] = []
    monkeypatch.setattr(tasks, "run_generation_job", lambda j: produits.append(str(j.id)))

    tasks.run_generation_job_task(str(job.id))
    tasks.run_generation_job_task(str(job.id))

    assert produits == [str(job.id)]


# ── Les gardiens ne font pas la queue derrière ce qu'ils gardent ─────────────


def _file_de(tache: str) -> Any:
    return settings.CELERY_TASK_ROUTES.get(tache, {}).get("queue")


def test_toute_tache_d_entretien_part_dans_la_file_courte() -> None:
    """Dérivé du calendrier : une tâche périodique ajoutée demain est couverte."""
    longues = {"prospection.prospection_quotidienne"}
    periodiques = {str(e["task"]) for e in settings.CELERY_BEAT_SCHEDULE.values()}
    assert len(periodiques) >= 8, "le calendrier lu ici n'est pas celui du service"

    mal_rangees = sorted(
        t for t in periodiques - longues
        if _file_de(t) != "livraison" and not t.startswith("delivery.")
    )

    assert mal_rangees == []


def test_le_gardien_des_dossiers_en_attente_est_au_calendrier() -> None:
    """Une tâche écrite et jamais planifiée ne garde rien (règle 8)."""
    periodiques = {str(e["task"]) for e in settings.CELERY_BEAT_SCHEDULE.values()}

    assert "generation.reprendre_les_dossiers_en_attente" in periodiques
    assert tasks.reprendre_les_dossiers_en_attente.name in periodiques


def test_une_redaction_ne_part_pas_dans_la_file_courte() -> None:
    """Contre-épreuve : la file courte reste courte."""
    assert _file_de("generation.run_generation_job") is None
    assert _file_de("generation.controler_puis_livrer") is None
    assert _file_de("prospection.prospection_quotidienne") is None


def test_un_ouvrier_ne_reserve_pas_plus_qu_il_ne_peut_faire() -> None:
    """Une tâche réservée plus longtemps que le délai de visibilité s'exécute
    deux fois : le délai dépasse la plus longue tâche, et rien n'est réservé
    d'avance."""
    assert settings.CELERY_WORKER_PREFETCH_MULTIPLIER == 1
    visibilite = settings.CELERY_BROKER_TRANSPORT_OPTIONS["visibility_timeout"]
    assert visibilite > tasks._STUCK_JOB_TIMEOUT_HOURS * 3600
