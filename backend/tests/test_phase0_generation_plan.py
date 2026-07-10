from __future__ import annotations

from decimal import Decimal

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import ChapterStatus
from generation.prompts import build_section_prompt
from generation.runner import _build_phase0_plan, run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order


@pytest.fixture
def competitor_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Etude concurrentielle",
        slug="etude-concurrentielle",
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
    )
    customer = Customer.objects.create(email="client@example.com")
    order = Order.objects.create(systeme_order_id="order_ec_phase0", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "mode",
            "PAYS": "France",
            "ZONE": "Paris",
            "PROJET": "marque textile responsable",
            "CONCURRENTS": ["Nike", "Adidas", "Veja"],
            "DEMANDES_SPECIFIQUES": "Comparer le digital.",
            "ELEMENTS_A_RETENIR": "Positionnement premium accessible.",
        },
    )


@pytest.mark.django_db
def test_phase0_plan_does_not_duplicate_client_brief(
    competitor_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(competitor_submission)

    plan = _build_phase0_plan(job, competitor_submission.normalized_variables)

    assert "VARIABLES_PROJET" in plan
    assert "Nike" not in plan
    assert "['Nike'" not in plan
    assert "Comparer le digital" not in plan
    assert "Chapitre 2" not in plan
    assert "sélectionner" in plan


@pytest.mark.django_db
def test_run_generation_job_keeps_existing_phase0_plan_on_relaunch(
    competitor_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(competitor_submission)
    job.phase0_plan = "PLAN EXISTANT"
    job.save(update_fields=["phase0_plan", "updated_at"])
    job.chapters.update(status=ChapterStatus.DONE, content="ok", operational_summary="ok")

    run_generation_job(job, client=StubClaudeClient())

    job.refresh_from_db()
    assert job.phase0_plan == "PLAN EXISTANT"


@pytest.mark.django_db
def test_build_section_prompt_keeps_recent_previous_context(
    competitor_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(competitor_submission)
    chapter = job.chapters.get(chapter_number=2)
    previous_context = "DEBUT_ANCIEN " + ("x" * 4100) + " FIN_RECENTE"

    prompt = build_section_prompt(chapter, "ec.02.a.directs", previous_context=previous_context)

    assert "FIN_RECENTE" in prompt
    assert "DEBUT_ANCIEN" not in prompt


@pytest.mark.django_db
def test_market_study_budget_keeps_phase0_margin() -> None:
    offer = Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche-phase0",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="client-em@example.com")
    order = Order.objects.create(systeme_order_id="order_em_phase0", customer=customer, offer=offer)
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "beaute", "PAYS": "Benin"},
    )

    job = bootstrap_generation_job(submission)

    # Budget releve a 3.20 EUR pour supporter le nouveau plancher
    # _MIN_MAX_TOKENS=2500 (evite les chapitres etrangles a 1200 tok).
    assert job.budget_eur == Decimal("3.2000")
