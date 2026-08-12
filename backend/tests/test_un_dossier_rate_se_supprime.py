"""Faire le ménage dans les dossiers ratés, sans pouvoir effacer un livrable payé.

Demande cliente du 12/08/2026 : cinq dossiers en échec traînaient au tableau de
bord — deux socles morts, un plafond dépassé, un CHECK INITIAL, un contrôle
hors socle.

## Les deux garde-fous, et pourquoi ils ne sont pas décoratifs

1. SEULS les dossiers en échec. Un dossier abouti porte le livrable qu'un
   client a payé ; la commodité de faire le ménage ne justifie pas de pouvoir
   l'effacer d'un appel.

2. Le coût part au JOURNAL avant de disparaître. `total_cost_eur` est la
   comptabilité de ce projet — il n'existe aucun registre séparé. Effacer un
   dossier qui a dépensé 4,29 € fait disparaître ces 4,29 € de partout.

## Ce que la suppression n'emporte pas

La commande et le brief du client : ils ne dépendent pas du dossier, c'est lui
qui pointe vers eux. Les incidents non plus — ils se détachent (`SET_NULL`) au
lieu de disparaître. On peut donc nettoyer sans perdre ni les réponses du
client ni la trace de ce qui a échoué.
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest


def _dossier(statut: str, cout: str = "4.2873"):  # type: ignore[no-untyped-def]
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
    from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="BP", slug=f"test-suppr-{statut}",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email=f"suppr-{statut}@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-suppr-{statut}", customer=client, offer=offre,
    )
    IntakeSubmission.objects.create(
        order=commande, source=IntakeSource.MANUAL, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "joaillerie", "PAYS": "France"},
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        status=statut,
        total_cost_eur=Decimal(cout),
    )
    ChapterGeneration.objects.create(
        job=job, chapter_number=0, chapter_title="Fiche projet",
        prompt_key="bp.00", status=ChapterStatus.DONE, content="x",
    )
    return job


@pytest.mark.django_db
def test_un_dossier_en_echec_s_efface(client_admin) -> None:  # type: ignore[no-untyped-def]
    """Avec le compte rendu de ce qu'il emportait."""
    from generation.models import GenerationJob, JobStatus

    job = _dossier(JobStatus.FAILED)
    reponse = client_admin.post(f"/api/dashboard/jobs/{job.id}/supprimer/")

    assert reponse.status_code == 200
    trace = json.loads(reponse.content)["supprime"]
    assert trace["total_cost_eur"] == "4.2873"
    assert trace["chapitres"] == 1
    assert not GenerationJob.objects.filter(id=job.id).exists()


@pytest.mark.django_db
def test_le_brief_du_client_survit(client_admin) -> None:  # type: ignore[no-untyped-def]
    """LE point qui rend le ménage acceptable.

    Sans lui, supprimer un dossier raté ferait perdre les réponses du client —
    et refaire son livrable demanderait de tout ressaisir à la main.
    """
    from generation.models import JobStatus
    from intake.models import IntakeSubmission
    from orders.models import Order

    job = _dossier(JobStatus.FAILED)
    commande_id = job.order_id

    client_admin.post(f"/api/dashboard/jobs/{job.id}/supprimer/")

    assert Order.objects.filter(id=commande_id).exists()
    soumission = IntakeSubmission.objects.get(order_id=commande_id)
    assert soumission.normalized_variables["SECTEUR"] == "joaillerie"


@pytest.mark.django_db
def test_l_incident_se_detache_au_lieu_de_disparaitre(client_admin) -> None:  # type: ignore[no-untyped-def]
    """La trace de ce qui a échoué survit au dossier qui a échoué."""
    from generation.models import JobStatus
    from monitoring.models import IncidentSeverity, OperationalIncident

    job = _dossier(JobStatus.FAILED)
    OperationalIncident.objects.create(
        title="Socle non etabli", severity=IncidentSeverity.HIGH, job=job,
    )

    client_admin.post(f"/api/dashboard/jobs/{job.id}/supprimer/")

    incident = OperationalIncident.objects.get(title="Socle non etabli")
    assert incident.job_id is None


@pytest.mark.django_db
@pytest.mark.parametrize("statut", ["done", "running", "pending"])
def test_un_dossier_qui_n_a_pas_echoue_est_refuse(client_admin, statut: str) -> None:  # type: ignore[no-untyped-def]
    """CONTRE-ÉPREUVE : un livrable payé ne s'efface pas d'un appel."""
    from generation.models import GenerationJob

    job = _dossier(statut)
    reponse = client_admin.post(f"/api/dashboard/jobs/{job.id}/supprimer/")

    assert reponse.status_code == 409
    assert GenerationJob.objects.filter(id=job.id).exists()


@pytest.mark.django_db
def test_la_lecture_seule_n_efface_rien(client_admin) -> None:  # type: ignore[no-untyped-def]
    """Une suppression est définitive : elle ne part JAMAIS sur un GET.

    Un lien visité par erreur, un préchargement de navigateur, un robot — et un
    dossier disparaît.
    """
    from generation.models import GenerationJob, JobStatus

    job = _dossier(JobStatus.FAILED)

    assert client_admin.get(
        f"/api/dashboard/jobs/{job.id}/supprimer/"
    ).status_code == 405
    assert GenerationJob.objects.filter(id=job.id).exists()


@pytest.mark.django_db
def test_le_cout_est_journalise_avant_l_effacement(client_admin, caplog) -> None:  # type: ignore[no-untyped-def]
    """La dépense a eu lieu : elle doit rester lisible quelque part."""
    import logging

    from generation.models import JobStatus

    job = _dossier(JobStatus.FAILED)
    with caplog.at_level(logging.WARNING):
        client_admin.post(f"/api/dashboard/jobs/{job.id}/supprimer/")

    trace = "\n".join(caplog.messages)
    assert "4.2873" in trace
    assert str(job.id) in trace
