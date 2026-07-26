from __future__ import annotations

from decimal import Decimal

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from documents.models import ArtifactStatus
from documents.services import assemble_document
from generation.models import ChapterStatus, JobStatus
from generation.rendering import render_client_document, strip_internal_markers
from generation.runner import run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from integrations.pdf import StubPdfClient
from orders.models import Order


@pytest.fixture
def market_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="client@example.com")
    order = Order.objects.create(systeme_order_id="order_em_1", customer=customer, offer=offer)
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
def test_run_generation_job_completes_all_chapters(market_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(market_submission)

    run_generation_job(job, client=StubClaudeClient())
    job.refresh_from_db()

    assert job.status == JobStatus.DONE
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.chapters.count() == 22
    assert job.chapters.filter(status=ChapterStatus.DONE).count() == 22
    assert all(c.content for c in job.chapters.all())
    assert all(c.operational_summary for c in job.chapters.all())


@pytest.mark.django_db
def test_run_generation_job_tracks_cost_under_budget(market_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(market_submission)

    run_generation_job(job, client=StubClaudeClient())
    job.refresh_from_db()

    assert job.total_cost_eur > Decimal("0")
    assert job.total_cost_eur <= job.budget_eur


@pytest.mark.django_db
def test_run_generation_job_seeds_coherence_currency(market_submission: IntakeSubmission) -> None:
    from generation.coherence import locked_facts_as_context

    job = bootstrap_generation_job(market_submission)
    run_generation_job(job, client=StubClaudeClient())

    assert "currency = XOF" in locked_facts_as_context(job)


@pytest.mark.django_db
def test_run_generation_job_is_resumable(market_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(market_submission)
    run_generation_job(job, client=StubClaudeClient())
    job.refresh_from_db()
    first_total = job.total_cost_eur

    # Relancer ne doit pas regenerer les chapitres deja DONE ni gonfler le cout.
    run_generation_job(job, client=StubClaudeClient())
    job.refresh_from_db()

    assert job.status == JobStatus.DONE
    assert job.total_cost_eur == first_total


@pytest.mark.django_db
def test_assemble_document_creates_ready_artifact(market_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(market_submission)
    run_generation_job(job, client=StubClaudeClient())

    assembly = assemble_document(job, pdf_client=StubPdfClient())

    # LINK : HTML d'aperçu avec checksum SHA256 du HTML (64 chars).
    assert assembly.link.status == ArtifactStatus.READY
    assert assembly.link.download_url
    assert len(assembly.link.checksum_sha256) == 64
    assert assembly.link.expires_at is not None
    # PDF : artefact prêt, pas de checksum binaire.
    assert assembly.pdf.status == ArtifactStatus.READY
    assert assembly.pdf.download_url
    assert assembly.pdf.checksum_sha256 == ""


@pytest.mark.django_db
def test_render_client_document_orders_sections(market_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(market_submission)
    run_generation_job(job, client=StubClaudeClient())

    document = render_client_document(job)

    assert document.title == "Étude de marché"
    assert document.sections[0].number == 0  # fiche projet en ouverture
    # Manuel Evangeline (24/07/2026) : chapitre 21 = Sources et méthodologie
    # (annexe brief séparée supprimée, réponses intégrées via CHECKs).
    assert document.sections[-1].number == 21
    markdown = document.to_markdown()
    assert markdown.startswith("# Étude de marché")


def test_strip_internal_markers_removes_pipeline_jargon() -> None:
    raw = (
        "Analyse chiffree du marche.\n"
        "✅ Prompt a utiliser :\n"
        "Etape 1-1 :\n"
        "Contenu redactionnel conserve.\n"
        "Elements attendus\n"
        "Point de controle : valide\n"
        "Conclusion finale."
    )

    cleaned = strip_internal_markers(raw)

    assert "Analyse chiffree du marche." in cleaned
    assert "Contenu redactionnel conserve." in cleaned
    assert "Conclusion finale." in cleaned
    assert "Prompt a utiliser" not in cleaned
    assert "Etape" not in cleaned
    assert "Elements attendus" not in cleaned
    assert "Point de controle" not in cleaned
