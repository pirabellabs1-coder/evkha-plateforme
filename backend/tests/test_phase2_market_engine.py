from __future__ import annotations

from decimal import Decimal

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.blueprints import MARKET_STUDY_CHAPTERS, SectionKind
from generation.coherence import CoherenceConflictError, locked_facts_as_context, upsert_locked_fact
from generation.context import build_context
from generation.cost import (
    CostBudgetExceededError,
    estimate_call_cost_eur,
    record_chapter_cost,
)
from generation.models import FactKind
from generation.services import GenerationBootstrapError, bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order


@pytest.fixture
def normalized_market_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="client@example.com")
    order = Order.objects.create(systeme_order_id="order_123", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "beaute",
            "PAYS": "Benin",
            "ZONE": "Cotonou",
            "PROJET": "concept store beaute",
        },
    )


@pytest.mark.django_db
def test_market_study_blueprint_matches_evkha_method() -> None:
    # Fiche projet en ouverture + 20 chapitres + annexe brief + sources = 23 unites.
    assert len(MARKET_STUDY_CHAPTERS) == 23
    assert MARKET_STUDY_CHAPTERS[0].prompt_key == "em.00.fiche_projet"
    assert MARKET_STUDY_CHAPTERS[0].section_kind == SectionKind.OPENING
    assert MARKET_STUDY_CHAPTERS[1].title.startswith("Analyse chiffree du marche mondial")
    assert MARKET_STUDY_CHAPTERS[-2].section_kind == SectionKind.ANNEXE
    assert MARKET_STUDY_CHAPTERS[-1].prompt_key == "em.22.sources"
    assert MARKET_STUDY_CHAPTERS[-1].section_kind == SectionKind.SOURCES


@pytest.mark.django_db
def test_bootstrap_generation_job_creates_all_sections(
    normalized_market_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(normalized_market_submission)

    assert job.deliverable_type == DeliverableType.MARKET_STUDY
    assert job.chapters.count() == 23
    assert list(job.chapters.values_list("chapter_number", flat=True)) == list(range(0, 23))


@pytest.mark.django_db
def test_bootstrap_generation_job_requires_normalized_submission(
    normalized_market_submission: IntakeSubmission,
) -> None:
    normalized_market_submission.status = IntakeStatus.INCOMPLETE
    normalized_market_submission.save(update_fields=["status", "updated_at"])

    with pytest.raises(GenerationBootstrapError):
        bootstrap_generation_job(normalized_market_submission)


@pytest.mark.django_db
def test_context_builder_includes_variables_summaries_and_locked_facts(
    normalized_market_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(normalized_market_submission)
    first = job.chapters.get(chapter_number=1)
    second = job.chapters.get(chapter_number=2)
    first.operational_summary = "Le projet vise les clientes urbaines actives."
    first.save(update_fields=["operational_summary", "updated_at"])
    upsert_locked_fact(
        job=job,
        kind=FactKind.CURRENCY,
        key="currency",
        value="XOF",
        source_chapter_number=1,
    )

    context = build_context(second)

    assert "SECTEUR" in context
    assert "beaute" in context
    assert "clientes urbaines actives" in context
    assert "currency = XOF" in context
    assert "CHAPITRE_CIBLE: 2. Analyse chiffree du marche national et local" in context


@pytest.mark.django_db
def test_coherence_facts_refuse_locked_contradictions(
    normalized_market_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(normalized_market_submission)
    upsert_locked_fact(job=job, kind=FactKind.CURRENCY, key="currency", value="XOF")

    with pytest.raises(CoherenceConflictError):
        upsert_locked_fact(job=job, kind=FactKind.CURRENCY, key="currency", value="EUR")

    assert "currency = XOF" in locked_facts_as_context(job)


@pytest.mark.django_db
def test_cost_engine_records_chapter_and_job_total(
    normalized_market_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(normalized_market_submission)
    chapter = job.chapters.get(chapter_number=1)

    cost = record_chapter_cost(chapter=chapter, input_tokens=1000, output_tokens=2000)
    job.refresh_from_db()
    chapter.refresh_from_db()

    assert cost == estimate_call_cost_eur(1000, 2000)
    assert chapter.cost_eur == cost
    assert job.total_cost_eur == Decimal("0.0297")


@pytest.mark.django_db
def test_cost_engine_enforces_budget_and_raises(
    normalized_market_submission: IntakeSubmission,
) -> None:
    from monitoring.models import OperationalIncident

    job = bootstrap_generation_job(normalized_market_submission)
    chapter = job.chapters.get(chapter_number=1)

    # Cout volontairement enorme pour franchir le plafond de 2 EUR.
    with pytest.raises(CostBudgetExceededError):
        record_chapter_cost(chapter=chapter, input_tokens=10_000_000, output_tokens=10_000_000)

    job.refresh_from_db()
    assert job.total_cost_eur > job.budget_eur
    assert OperationalIncident.objects.filter(job=job, severity="high").exists()
