from __future__ import annotations

import pytest
from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.blueprints import COMPETITOR_STUDY_CHAPTERS, SectionKind
from generation.models import ChapterStatus, JobStatus
from generation.rendering import render_client_document
from generation.runner import run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order


@pytest.fixture
def competitor_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Etude de concurrence",
        slug="etude-concurrence",
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
    )
    customer = Customer.objects.create(email="client-ec@example.com")
    order = Order.objects.create(systeme_order_id="order_ec_1", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "CBD indoor premium",
            "PAYS": "France",
            "ZONE": "Rhone-Alpes",
            "PROJET": "production indoor premium",
            "CONCURRENTS": "La Tete Francaise, Loud Co.",
        },
    )


def test_competitor_blueprint_matches_evkha_method() -> None:
    # Fiche projet en ouverture + 8 chapitres canoniques (sommaire EC) = 9 unites.
    assert len(COMPETITOR_STUDY_CHAPTERS) == 9
    assert COMPETITOR_STUDY_CHAPTERS[0].prompt_key == "ec.00.fiche_projet"
    assert COMPETITOR_STUDY_CHAPTERS[0].section_kind == SectionKind.OPENING
    assert COMPETITOR_STUDY_CHAPTERS[1].title == "Identification des concurrents"
    assert COMPETITOR_STUDY_CHAPTERS[-1].prompt_key == "ec.08.annexe_brief"
    assert COMPETITOR_STUDY_CHAPTERS[-1].section_kind == SectionKind.ANNEXE


@pytest.mark.django_db
def test_bootstrap_competitor_job_creates_all_sections(
    competitor_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(competitor_submission)

    assert job.deliverable_type == DeliverableType.COMPETITOR_STUDY
    assert job.chapters.count() == 9
    assert list(job.chapters.values_list("chapter_number", flat=True)) == list(range(0, 9))


@pytest.mark.django_db
def test_run_competitor_job_completes_and_renders(
    competitor_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(competitor_submission)

    run_generation_job(job, client=StubClaudeClient())
    job.refresh_from_db()

    assert job.status == JobStatus.DONE
    assert job.chapters.filter(status=ChapterStatus.DONE).count() == 9
    assert job.total_cost_eur <= job.budget_eur

    document = render_client_document(job)
    assert document.title == "Etude de la concurrence"
    assert document.sections[0].number == 0
    assert document.sections[-1].number == 8  # annexe en fin
