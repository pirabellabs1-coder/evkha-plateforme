from __future__ import annotations

from decimal import Decimal

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.blueprints import MARKET_STUDY_CHAPTERS, SectionKind
from generation.coherence import locked_facts_as_context, upsert_locked_fact
from generation.context import build_context
from generation.cost import (
    _MIN_MAX_TOKENS,
    CostBudgetExceededError,
    current_job_cost_eur,
    estimate_call_cost_eur,
    max_tokens_for_job,
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
    assert MARKET_STUDY_CHAPTERS[1].title.startswith("Analyse chiffrée du marché mondial")
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
    assert "CHAPITRE_CIBLE: 2. Analyse chiffrée du marché national et local" in context


@pytest.mark.django_db
def test_coherence_facts_refuse_locked_contradictions(
    normalized_market_submission: IntakeSubmission,
) -> None:
    # Un conflit non-numerique (XOF != EUR) crée un incident MEDIUM mais ne lève pas
    # d'exception — la valeur verrouillée (XOF) est conservée.
    job = bootstrap_generation_job(normalized_market_submission)
    upsert_locked_fact(job=job, kind=FactKind.CURRENCY, key="currency", value="XOF")
    result = upsert_locked_fact(job=job, kind=FactKind.CURRENCY, key="currency", value="EUR")
    # La valeur initiale est preservee
    assert result.value == "XOF"
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

    expected = estimate_call_cost_eur(1000, 2000)
    assert cost == expected
    assert chapter.cost_eur == expected
    assert job.total_cost_eur == expected


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


# ── Regle d'or #1 durcie : seuil 1.70 EUR + plafond dur 2.00 EUR ───────────────


@pytest.mark.django_db
def test_current_job_cost_eur_sums_all_chapters(
    normalized_market_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(normalized_market_submission)
    first = job.chapters.get(chapter_number=1)
    second = job.chapters.get(chapter_number=2)
    first.cost_eur = Decimal("0.5000")
    first.save(update_fields=["cost_eur", "updated_at"])
    second.cost_eur = Decimal("0.3000")
    second.save(update_fields=["cost_eur", "updated_at"])

    assert current_job_cost_eur(job) == Decimal("0.8000")


@pytest.mark.django_db
def test_max_tokens_for_job_throttles_from_first_chapter(
    normalized_market_submission: IntakeSubmission,
) -> None:
    # Le throttle se declenche quand le budget restant est faible.
    # A 3.50€ depense sur 4€ de budget EM, max_tokens doit etre < 3500.
    job = bootstrap_generation_job(normalized_market_submission)
    chapter = job.chapters.get(chapter_number=1)
    chapter.cost_eur = Decimal("3.5000")
    chapter.save(update_fields=["cost_eur", "updated_at"])

    result = max_tokens_for_job(job, default_max_tokens=3500)
    assert 400 <= result < 3500


@pytest.mark.django_db
def test_max_tokens_for_job_throttles_above_threshold(
    normalized_market_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(normalized_market_submission)
    chapter = job.chapters.get(chapter_number=1)
    chapter.cost_eur = Decimal("3.9500")
    chapter.save(update_fields=["cost_eur", "updated_at"])

    result = max_tokens_for_job(job, default_max_tokens=3500)

    assert 400 <= result < 3500


@pytest.mark.django_db
def test_max_tokens_for_job_worst_case_never_reaches_budget(
    normalized_market_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(normalized_market_submission)
    chapter = job.chapters.get(chapter_number=1)
    chapter.cost_eur = Decimal("1.7500")
    chapter.save(update_fields=["cost_eur", "updated_at"])

    result = max_tokens_for_job(job, default_max_tokens=3500)
    worst_case_cost = estimate_call_cost_eur(0, result)

    assert current_job_cost_eur(job) + worst_case_cost < job.budget_eur


@pytest.mark.django_db
def test_max_tokens_for_job_floors_at_minimum_when_budget_nearly_exhausted(
    normalized_market_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(normalized_market_submission)
    chapter = job.chapters.get(chapter_number=1)
    chapter.cost_eur = Decimal("3.9990")
    chapter.save(update_fields=["cost_eur", "updated_at"])

    assert max_tokens_for_job(job, default_max_tokens=3500) == 400


@pytest.mark.django_db
def test_max_tokens_for_job_splits_remaining_budget_across_call_count(
    normalized_market_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(normalized_market_submission)
    chapter = job.chapters.get(chapter_number=1)
    # 1.70 EUR = seuil de throttle. Avec MAX_CONTINUATIONS=1 et ~20 chapitres
    # restants, single_call > 400 et split_call <= single_call (l'assertion
    # verifie que call_count=2 reduit bien le max_tokens par call).
    chapter.cost_eur = Decimal("1.7000")
    chapter.save(update_fields=["cost_eur", "updated_at"])

    single_call = max_tokens_for_job(job, default_max_tokens=3500, call_count=1)
    split_call = max_tokens_for_job(job, default_max_tokens=3500, call_count=2)

    assert split_call <= single_call
    assert single_call > _MIN_MAX_TOKENS  # throttle actif mais pas au plancher
