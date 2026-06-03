from __future__ import annotations

from datetime import timedelta

import pytest
from catalog.models import DeliverableType, Offer
from customers.models import Customer
from delivery.models import DeliveryStatus
from delivery.services import DeliveryError, deliver_job, purge_expired_artifacts
from documents.models import ArtifactKind, ArtifactStatus
from generation.runner import run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.brevo import EmailAttachment, EmailSendResult, StubBrevoClient
from integrations.claude import StubClaudeClient
from integrations.gamma import StubGammaClient
from monitoring.models import OperationalIncident
from orders.models import Order, OrderStatus


@pytest.fixture
def market_submission_no_gamma() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche",
        deliverable_type=DeliverableType.MARKET_STUDY,
        gamma_enabled=False,
    )
    customer = Customer.objects.create(email="client@example.com")
    order = Order.objects.create(
        systeme_order_id="order_delivery_1",
        customer=customer,
        offer=offer,
    )
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


@pytest.fixture
def market_submission_with_gamma() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Etude de marche premium",
        slug="etude-marche-gamma",
        deliverable_type=DeliverableType.MARKET_STUDY,
        gamma_enabled=True,
    )
    customer = Customer.objects.create(email="gamma@example.com")
    order = Order.objects.create(
        systeme_order_id="order_delivery_2",
        customer=customer,
        offer=offer,
        raw_payload={"gamma_theme_id": "theme-b2b-1"},
    )
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "beaute",
            "PAYS": "France",
            "ZONE": "Lyon",
            "PROJET": "reseau premium",
        },
    )


@pytest.mark.django_db
def test_deliver_job_creates_link_pdf_and_sent_batch(
    market_submission_no_gamma: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(market_submission_no_gamma)
    run_generation_job(job, client=StubClaudeClient())

    batch = deliver_job(
        job,
        gamma_client=StubGammaClient(),
        email_client=StubBrevoClient(),
    )

    job.order.refresh_from_db()
    assert batch.status == DeliveryStatus.SENT
    assert batch.sent_at is not None
    assert job.order.status == OrderStatus.DELIVERED
    assert batch.artifacts.filter(kind=ArtifactKind.LINK, status=ArtifactStatus.READY).exists()
    assert batch.artifacts.filter(kind=ArtifactKind.PDF, status=ArtifactStatus.READY).exists()
    assert not batch.artifacts.filter(kind=ArtifactKind.GAMMA_PDF).exists()
    # Verification XSS fix : le checksum du PDF est vide (pas celui du link).
    pdf = batch.artifacts.get(kind=ArtifactKind.PDF)
    assert pdf.checksum_sha256 == ""
    assert "format=pdf" in pdf.download_url


@pytest.mark.django_db
def test_deliver_job_creates_gamma_artifacts_when_enabled(
    market_submission_with_gamma: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(market_submission_with_gamma)
    run_generation_job(job, client=StubClaudeClient())

    batch = deliver_job(
        job,
        gamma_client=StubGammaClient(),
        email_client=StubBrevoClient(),
    )

    kinds = set(batch.artifacts.values_list("kind", flat=True))
    assert ArtifactKind.GAMMA_PDF in kinds
    assert ArtifactKind.GAMMA_PPTX in kinds


@pytest.mark.django_db
def test_purge_expired_artifacts_marks_ready_links_expired(
    market_submission_no_gamma: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(market_submission_no_gamma)
    run_generation_job(job, client=StubClaudeClient())
    batch = deliver_job(job, gamma_client=StubGammaClient(), email_client=StubBrevoClient())
    artifact = batch.artifacts.get(kind=ArtifactKind.LINK)
    assert artifact.expires_at is not None
    artifact.expires_at = artifact.expires_at - timedelta(days=8)
    artifact.save(update_fields=["expires_at", "updated_at"])

    purged = purge_expired_artifacts()

    artifact.refresh_from_db()
    assert purged >= 1
    assert artifact.status == ArtifactStatus.EXPIRED
    assert artifact.download_url == ""


@pytest.mark.django_db
def test_delivery_failure_creates_incident(
    market_submission_no_gamma: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(market_submission_no_gamma)
    run_generation_job(job, client=StubClaudeClient())

    class FailingEmailClient:
        def send_delivery_email(
            self,
            *,
            recipient_email: str,
            subject: str,
            html_body: str,
            attachments: tuple[EmailAttachment, ...],
        ) -> EmailSendResult:
            del recipient_email, subject, html_body, attachments
            raise RuntimeError("brevo down")

    with pytest.raises(DeliveryError):
        deliver_job(job, gamma_client=StubGammaClient(), email_client=FailingEmailClient())

    assert OperationalIncident.objects.filter(
        title="Echec livraison livrable",
        order=job.order,
    ).exists()
    batch = job.order.delivery_batches.latest("created_at")
    assert batch.status == DeliveryStatus.FAILED
