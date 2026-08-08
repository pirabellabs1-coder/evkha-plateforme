"""Une génération qui s'arrête doit le DIRE, tout de suite.

Défaut vécu le 31/07/2026, sur le tout premier appel réel. L'API a refusé la
requête en 0,9 seconde — plafond de dépenses atteint sur le compte. La tâche
Celery a levé, l'exception est allée dans les journaux, et le job est resté
affiché `running` **quatorze minutes**, sans erreur, sans incident.

Le gardien `reset_stuck_generation_jobs` aurait fini par le requalifier — au
bout de DEUX HEURES. C'est le bon délai pour un worker mort, et absurde pour
un crash instantané. Entre les deux, l'admin et le client lisent « en cours »
sur quelque chose de terminé (règle 1).

Le correctif vise la CLASSE, pas l'erreur de plafond : n'importe quelle
exception traversant le pipeline doit produire le même résultat visible.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.echecs import motif_lisible

pytestmark = pytest.mark.django_db


# ── Le motif doit être actionnable par un humain ─────────────────────────────


def test_le_plafond_de_depenses_est_traduit_en_consigne() -> None:
    """Règle 2 : un motif qu'on ne retrouve pas dans la réalité fait corriger
    la mauvaise chose. Le message brut de l'API ne dit à personne qu'il faut
    relever un plafond dans une console.
    """
    brut = RuntimeError(
        "Error code: 400 - {'type': 'error', 'error': {'type': "
        "'invalid_request_error', 'message': 'You have reached your specified "
        "API usage limits. You will regain access on 2026-08-01 at 00:00 UTC.'}}"
    )
    motif = motif_lisible(brut)
    assert "Plafond de dépenses atteint" in motif
    assert "Settings" in motif and "Limits" in motif
    # Le message d'origine survit : une traduction qui efface la cause reelle
    # est pire que pas de traduction.
    assert "Error code: 400" in motif


def test_une_cle_refusee_nomme_la_variable_a_corriger() -> None:
    motif = motif_lisible(RuntimeError("authentication_error: invalid x-api-key"))
    assert "ANTHROPIC_API_KEY" in motif


def test_une_erreur_inconnue_n_est_jamais_avalee() -> None:
    """Contre-épreuve : ce que la liste ne connaît pas doit passer INTACT.

    Une traduction qui remplacerait l'inconnu par un message générique
    recréerait exactement le silence qu'on corrige.
    """
    motif = motif_lisible(ZeroDivisionError("division by zero"))
    assert "ZeroDivisionError" in motif
    assert "division by zero" in motif


# ── Le job doit être requalifié, et l'incident ouvert ────────────────────────


def _job_en_cours() -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob, JobStatus
    from orders.models import Order

    offre = Offer.objects.create(name="EM", slug="em-echec",
                                 deliverable_type=DeliverableType.MARKET_STUDY)
    client = Customer.objects.create(email="echec@example.com")
    commande = Order.objects.create(systeme_order_id="ord-echec-01",
                                    customer=client, offer=offre)
    return GenerationJob.objects.create(order=commande, status=JobStatus.RUNNING,
                                        deliverable_type=DeliverableType.MARKET_STUDY)


def test_une_exception_requalifie_le_job_et_ouvre_un_incident() -> None:
    """Le test qui échoue sur le code d'avant : le job y restait `running`."""
    from generation.echecs import marquer_echec
    from generation.models import GenerationJob, JobStatus
    from monitoring.models import OperationalIncident

    job = _job_en_cours()
    marquer_echec(job, RuntimeError("boum"), etape="socle")

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED
    assert "socle" in job.error_message
    assert "boum" in job.error_message

    incident = OperationalIncident.objects.filter(job=job).first()
    assert incident is not None
    assert incident.details["etape"] == "socle"
    assert "Aucun e-mail client" in incident.details["consigne"]
    assert GenerationJob.objects.filter(status=JobStatus.RUNNING).count() == 0


def test_un_statut_terminal_n_est_jamais_ecrase() -> None:
    """Un échec déjà raconté ailleurs l'est mieux que par ce dernier filet.

    Sans cette garde, l'annulation demandée par un client serait réécrite en
    « interrompu » par une exception survenue après coup.
    """
    from generation.echecs import marquer_echec
    from generation.models import GenerationJob, JobStatus
    from monitoring.models import OperationalIncident

    job = _job_en_cours()
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.CANCELLED, error_message="Annulé par le client.")
    job.refresh_from_db()

    marquer_echec(job, RuntimeError("boum"), etape="generation")

    job.refresh_from_db()
    assert job.status == JobStatus.CANCELLED
    assert job.error_message == "Annulé par le client."
    assert not OperationalIncident.objects.filter(job=job).exists()


# ── Le branchement, sur la chaîne réelle ─────────────────────────────────────


def test_la_tache_celery_requalifie_le_job_quand_le_runner_leve(
    monkeypatch: Any,
) -> None:
    """De bout en bout : c'est la tâche qui doit poser le filet.

    Les tests ci-dessus jugent `marquer_echec` isolément — ils resteraient
    verts si personne ne l'appelait, ce qui est exactement le défaut d'origine
    (règle 8 : intégré, testé, jamais exécuté).
    """
    from generation import tasks
    from generation.models import JobStatus
    from monitoring.models import OperationalIncident

    job = _job_en_cours()

    def leve(_job: Any) -> None:
        msg = ("Error code: 400 - You have reached your specified API usage "
               "limits. You will regain access on 2026-08-01 at 00:00 UTC.")
        raise RuntimeError(msg)

    monkeypatch.setattr(tasks, "run_generation_job", leve)

    with pytest.raises(RuntimeError):
        tasks.run_generation_job_task(str(job.id))

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED, "le job est reste en cours"
    assert "Plafond de dépenses atteint" in job.error_message
    assert OperationalIncident.objects.filter(job=job).exists()
