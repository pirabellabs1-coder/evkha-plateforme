"""Tests Phase 4b — PDF brandé WeasyPrint (D8).

Couvre :
- Branding extraction depuis les variables intake
- Conversion Markdown → HTML (_md_to_html)
- render_branded_html : cohérence HTML / branding
- assemble_document : artefacts LINK + PDF créés
- deliver_job : PDF en pièce jointe, LINK en body email
"""
from __future__ import annotations

import pytest
from catalog.models import DeliverableType, Offer
from customers.models import Customer
from documents.models import ArtifactKind, ArtifactStatus
from documents.services import assemble_document
from generation.rendering import (
    _EVKHA_PRIMARY,
    _EVKHA_SECONDARY,
    BrandingContext,
    _md_to_html,
    extract_branding,
    render_branded_html,
)
from generation.runner import run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.brevo import EmailAttachment, EmailSendResult
from integrations.claude import StubClaudeClient
from integrations.gamma import StubGammaClient
from integrations.pdf import StubPdfClient
from orders.models import Order

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def branded_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche-brand",
        deliverable_type=DeliverableType.MARKET_STUDY,
        gamma_enabled=False,
    )
    customer = Customer.objects.create(email="brand@example.com")
    order = Order.objects.create(
        systeme_order_id="order_brand_1",
        customer=customer,
        offer=offer,
    )
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "tech",
            "PAYS": "France",
            "ZONE": "Paris",
            "PROJET": "startup SaaS",
            "LOGO_URL": "https://cdn.example.com/logo.png",
            "COULEUR_PRINCIPALE": "#1A1A2E",
            "COULEUR_SECONDAIRE": "#E94560",
            "NOM_ENTREPRISE": "TechVision SAS",
        },
    )


@pytest.fixture
def unbranded_submission() -> IntakeSubmission:
    """Intake sans variables de branding — fallback palette EVKHA attendu."""
    offer = Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche-nobrand",
        deliverable_type=DeliverableType.MARKET_STUDY,
        gamma_enabled=False,
    )
    customer = Customer.objects.create(email="nobrand@example.com")
    order = Order.objects.create(
        systeme_order_id="order_nobrand_1",
        customer=customer,
        offer=offer,
    )
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "mode",
            "PAYS": "Senegal",
            "ZONE": "Dakar",
            "PROJET": "boutique en ligne",
        },
    )


# ── _md_to_html ───────────────────────────────────────────────────────────────


def test_md_to_html_heading() -> None:
    html = _md_to_html("## Titre principal")
    assert "<h3>" in html and "Titre principal" in html


def test_md_to_html_bold() -> None:
    html = _md_to_html("Du texte **en gras** ici.")
    assert "<strong>en gras</strong>" in html


def test_md_to_html_list() -> None:
    html = _md_to_html("- Item A\n- Item B\n- Item C")
    assert "<ul>" in html
    assert html.count("<li>") == 3


def test_md_to_html_ordered_list() -> None:
    html = _md_to_html("1. Premier\n2. Deuxième\n3. Troisième")
    assert "<ol>" in html
    assert html.count("<li>") == 3


def test_md_to_html_escapes_html_injection() -> None:
    html = _md_to_html("<script>alert('xss')</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_md_to_html_horizontal_rule() -> None:
    html = _md_to_html("Avant\n---\nAprès")
    assert "<hr>" in html


# ── extract_branding ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_extract_branding_reads_tally_variables(branded_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(branded_submission)
    run_generation_job(job, client=StubClaudeClient())

    branding = extract_branding(job)

    assert branding.logo_url == "https://cdn.example.com/logo.png"
    assert branding.color_primary == "#1A1A2E"
    assert branding.color_secondary == "#E94560"
    assert branding.company_name == "TechVision SAS"


@pytest.mark.django_db
def test_extract_branding_fallback_evkha(unbranded_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(unbranded_submission)
    run_generation_job(job, client=StubClaudeClient())

    branding = extract_branding(job)

    assert branding.logo_url == ""
    assert branding.color_primary == _EVKHA_PRIMARY
    assert branding.color_secondary == _EVKHA_SECONDARY
    assert branding.company_name == ""


# ── render_branded_html ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_render_branded_html_contains_title_and_colors(
    branded_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(branded_submission)
    run_generation_job(job, client=StubClaudeClient())

    html = render_branded_html(job)

    assert "Etude de marche" in html
    assert "#1A1A2E" in html
    assert "#E94560" in html
    assert "TechVision SAS" in html


@pytest.mark.django_db
def test_render_branded_html_with_custom_branding() -> None:
    """render_branded_html accepte un BrandingContext explicite."""
    offer = Offer.objects.create(
        name="BP test",
        slug="bp-brand-override",
        deliverable_type=DeliverableType.MARKET_STUDY,
        gamma_enabled=False,
    )
    customer = Customer.objects.create(email="override@example.com")
    order = Order.objects.create(
        systeme_order_id="order_override_1",
        customer=customer,
        offer=offer,
    )
    sub = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "agro", "PAYS": "Benin", "ZONE": "Cotonou", "PROJET": "cacao export"
        },
    )
    job = bootstrap_generation_job(sub)
    run_generation_job(job, client=StubClaudeClient())

    custom = BrandingContext(
        logo_url="",
        color_primary="#FF0000",
        color_secondary="#00FF00",
        company_name="ACME Corp",
    )
    html = render_branded_html(job, branding=custom)

    assert "#FF0000" in html
    assert "#00FF00" in html
    assert "ACME Corp" in html


# ── assemble_document ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_assemble_document_creates_link_and_pdf(branded_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(branded_submission)
    run_generation_job(job, client=StubClaudeClient())

    assembly = assemble_document(job, pdf_client=StubPdfClient())

    # LINK : HTML d'aperçu avec checksum
    assert assembly.link.kind == ArtifactKind.LINK
    assert assembly.link.status == ArtifactStatus.READY
    assert assembly.link.checksum_sha256  # SHA256 du HTML renseigné
    assert assembly.link.download_url

    # PDF : livrable WeasyPrint brandé, pas de checksum binaire
    assert assembly.pdf.kind == ArtifactKind.PDF
    assert assembly.pdf.status == ArtifactStatus.READY
    assert assembly.pdf.checksum_sha256 == ""
    assert assembly.pdf.download_url


@pytest.mark.django_db
def test_assemble_document_is_idempotent(branded_submission: IntakeSubmission) -> None:
    """Deux appels successifs ne doublent pas les artefacts."""
    job = bootstrap_generation_job(branded_submission)
    run_generation_job(job, client=StubClaudeClient())

    assemble_document(job, pdf_client=StubPdfClient())
    assemble_document(job, pdf_client=StubPdfClient())

    assert job.artifacts.filter(kind=ArtifactKind.PDF).count() == 1
    assert job.artifacts.filter(kind=ArtifactKind.LINK).count() == 1


# ── deliver_job avec PDF brandé ───────────────────────────────────────────────


@pytest.mark.django_db
def test_deliver_job_sends_pdf_as_attachment(branded_submission: IntakeSubmission) -> None:
    from delivery.services import deliver_job

    job = bootstrap_generation_job(branded_submission)
    run_generation_job(job, client=StubClaudeClient())

    captured: list[EmailAttachment] = []

    class CapturingEmailClient:
        def send_delivery_email(
            self,
            *,
            recipient_email: str,
            subject: str,
            html_body: str,
            attachments: tuple[EmailAttachment, ...],
        ) -> EmailSendResult:
            captured.extend(attachments)
            return EmailSendResult(provider_message_id="test-ok")

    deliver_job(
        job,
        pdf_client=StubPdfClient(),
        gamma_client=StubGammaClient(),
        email_client=CapturingEmailClient(),
    )

    # Le PDF doit être en pièce jointe, pas le HTML (LINK).
    filenames = [a.filename for a in captured]
    assert any("pdf" in f.lower() for f in filenames)
    assert not any("html" in f.lower() for f in filenames)
