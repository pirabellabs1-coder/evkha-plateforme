from __future__ import annotations

import pytest
from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.blueprints import BUSINESS_PLAN_CHAPTERS, BUSINESS_STRATEGY_CHAPTERS, SectionKind
from generation.models import ChapterStatus, JobStatus
from generation.rendering import render_client_document
from generation.runner import run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order


@pytest.fixture
def bp_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Business Plan",
        slug="business-plan",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email="client-bp@example.com")
    order = Order.objects.create(systeme_order_id="order_bp_1", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "restauration rapide halal",
            "PAYS": "France",
            "ZONE": "Ile-de-France",
            "PROJET": "chaine snacks halal premium",
            "FORME_JURIDIQUE": "SAS",
            "CAPITAL_INITIAL": "30000 EUR",
            "MODELE_REVENUS": "vente directe + catering",
            "EQUIPE": "2 associes, profils complementaires cuisine et gestion",
        },
    )


@pytest.fixture
def str_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Strategie Business",
        slug="strategie-business",
        deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )
    customer = Customer.objects.create(email="client-str@example.com")
    order = Order.objects.create(systeme_order_id="order_str_1", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "e-commerce mode africaine",
            "PAYS": "Benin",
            "ZONE": "Cotonou",
            "PROJET": "marketplace mode africaine premium",
            "OBJECTIF_STRATEGIQUE": "devenir le leader regional en 3 ans",
            "HORIZON_PLANIFICATION": "3 ans",
        },
    )


# --- Blueprint tests -------------------------------------------------------


def test_business_plan_blueprint_structure() -> None:
    assert len(BUSINESS_PLAN_CHAPTERS) == 14
    assert BUSINESS_PLAN_CHAPTERS[0].prompt_key == "bp.00.fiche_projet"
    assert BUSINESS_PLAN_CHAPTERS[0].section_kind == SectionKind.OPENING
    assert BUSINESS_PLAN_CHAPTERS[-1].section_kind == SectionKind.ANNEXE
    # Verifier que les chapitres financiers cles sont presents.
    keys = [c.prompt_key for c in BUSINESS_PLAN_CHAPTERS]
    assert "bp.09.previsions_financieres" in keys
    assert "bp.10.plan_financement" in keys


def test_business_strategy_blueprint_structure() -> None:
    assert len(BUSINESS_STRATEGY_CHAPTERS) == 13
    assert BUSINESS_STRATEGY_CHAPTERS[0].prompt_key == "str.00.fiche_projet"
    assert BUSINESS_STRATEGY_CHAPTERS[0].section_kind == SectionKind.OPENING
    keys = [c.prompt_key for c in BUSINESS_STRATEGY_CHAPTERS]
    assert "str.02.pestel" in keys
    assert "str.10.kpis" in keys
    assert "str.12.conclusion" in keys


# --- Bootstrap tests -------------------------------------------------------


@pytest.mark.django_db
def test_bootstrap_bp_job_creates_all_sections(bp_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(bp_submission)

    assert job.deliverable_type == DeliverableType.BUSINESS_PLAN
    assert job.chapters.count() == 14
    assert list(job.chapters.values_list("chapter_number", flat=True)) == list(range(0, 14))


@pytest.mark.django_db
def test_bootstrap_str_job_creates_all_sections(str_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(str_submission)

    assert job.deliverable_type == DeliverableType.BUSINESS_STRATEGY
    assert job.chapters.count() == 13
    assert list(job.chapters.values_list("chapter_number", flat=True)) == list(range(0, 13))


# --- Generation tests -------------------------------------------------------


@pytest.mark.django_db
def test_run_bp_job_completes_and_renders(bp_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(bp_submission)

    run_generation_job(job, client=StubClaudeClient())
    job.refresh_from_db()

    assert job.status == JobStatus.DONE
    assert job.chapters.filter(status=ChapterStatus.DONE).count() == 14
    assert job.total_cost_eur <= job.budget_eur

    document = render_client_document(job)
    assert document.title == "Business plan"
    assert document.sections[0].number == 0  # fiche projet
    markdown = document.to_markdown()
    assert "# Business plan" in markdown


@pytest.mark.django_db
def test_run_str_job_completes_and_renders(str_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(str_submission)

    run_generation_job(job, client=StubClaudeClient())
    job.refresh_from_db()

    assert job.status == JobStatus.DONE
    assert job.chapters.filter(status=ChapterStatus.DONE).count() == 13
    assert job.total_cost_eur <= job.budget_eur

    document = render_client_document(job)
    assert document.title == "Strategie business"
    markdown = document.to_markdown()
    assert "# Strategie business" in markdown


@pytest.mark.django_db
def test_bp_coherence_seeds_forme_juridique_and_capital(bp_submission: IntakeSubmission) -> None:
    from generation.coherence import locked_facts_as_context

    job = bootstrap_generation_job(bp_submission)
    run_generation_job(job, client=StubClaudeClient())

    facts = locked_facts_as_context(job)
    assert "forme_juridique = SAS" in facts
    assert "capital_initial = 30000 EUR" in facts
    # France -> EUR
    assert "currency = EUR" in facts
