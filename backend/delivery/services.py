from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.db import transaction
from django.utils import timezone
from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact
from documents.services import assemble_document
from generation.models import GenerationJob, JobStatus
from generation.rendering import render_client_document
from integrations.brevo import (
    EmailAttachment,
    TransactionalEmailClient,
    get_transactional_email_client,
)
from integrations.gamma import GammaClient, GammaExportResult, get_gamma_client
from monitoring.models import IncidentSeverity, OperationalIncident
from orders.models import OrderStatus

from .models import DeliveryBatch, DeliveryEvent, DeliveryStatus


class DeliveryError(RuntimeError):
    pass


def _retention_days(job: GenerationJob) -> int:
    return int(getattr(job.order.offer, "retention_days", 7) or 7)


def _expires_at(job: GenerationJob) -> datetime:
    return timezone.now() + timedelta(days=_retention_days(job))


def _pdf_download_url(link_url: str) -> str:
    """Ajoute ?format=pdf en respectant les query strings existants."""
    parsed = urlparse(link_url)
    existing = parse_qs(parsed.query)
    existing["format"] = ["pdf"]
    new_query = urlencode({k: v[0] for k, v in existing.items()})
    return urlunparse(parsed._replace(query=new_query))


def _theme_id_for(job: GenerationJob) -> str:
    raw_payload = job.order.raw_payload or {}
    if isinstance(raw_payload, dict):
        theme_id = raw_payload.get("gamma_theme_id") or raw_payload.get("theme_id")
        if theme_id:
            return str(theme_id)
    return "evkha-default"


def _html_body(job: GenerationJob, artifacts: tuple[DocumentArtifact, ...]) -> str:
    # escape() protege contre l'injection HTML depuis des valeurs externes (XSS).
    order_id_safe = escape(job.order.systeme_order_id)
    links = [
        f'<li><a href="{escape(artifact.download_url)}">'
        f"{escape(artifact.kind)}</a></li>"
        for artifact in artifacts
        if artifact.download_url
    ]
    return (
        f"<p>Bonjour,</p><p>Vos livrables EVKHA sont prets pour la commande "
        f"<strong>{order_id_safe}</strong>.</p><ul>{''.join(links)}</ul>"
    )


def _attachment_filename(artifact: DocumentArtifact, order_id: str) -> str:
    """Nom de fichier lisible : ex. 'EVKHA_order123_gamma.pdf'."""
    slug = order_id.replace(" ", "_")[:40]
    extension = "pptx" if artifact.kind == ArtifactKind.GAMMA_PPTX else "pdf"
    label = "gamma_pptx" if artifact.kind == ArtifactKind.GAMMA_PPTX else artifact.kind
    return f"EVKHA_{slug}_{label}.{extension}"


def ensure_pdf_artifact(job: GenerationJob, *, link_artifact: DocumentArtifact) -> DocumentArtifact:
    # Le PDF est un rendu derive du lien Google Docs : on ne lui attribue pas
    # le checksum du markdown (qui ne correspond pas aux octets du PDF reel).
    artifact, _created = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.PDF,
        defaults={
            "status": ArtifactStatus.READY,
            "storage_key": f"{link_artifact.storage_key}/pdf",
            "download_url": _pdf_download_url(link_artifact.download_url),
            "checksum_sha256": "",
            "expires_at": _expires_at(job),
        },
    )
    return artifact


def _persist_gamma_artifacts(
    job: GenerationJob,
    *,
    export: GammaExportResult,
    presentation_id: str,
) -> list[DocumentArtifact]:
    """Persiste les artefacts Gamma en base (DB uniquement, aucun appel reseau)."""
    common = {
        "status": ArtifactStatus.READY,
        "expires_at": _expires_at(job),
        "checksum_sha256": "",
    }
    gamma_pdf, _ = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.GAMMA_PDF,
        defaults={
            **common,
            "storage_key": f"gamma/{presentation_id}/pdf",
            "download_url": export.pdf_url,
        },
    )
    gamma_pptx, _ = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.GAMMA_PPTX,
        defaults={
            **common,
            "storage_key": f"gamma/{presentation_id}/pptx",
            "download_url": export.pptx_url,
        },
    )
    return [gamma_pdf, gamma_pptx]


def ensure_gamma_artifacts(
    job: GenerationJob,
    *,
    gamma_client: GammaClient | None = None,
) -> list[DocumentArtifact]:
    """Genere la presentation Gamma et persiste les artefacts.

    Appels reseau (create_presentation, wait_until_ready, export) effectues
    EN DEHORS de toute transaction atomique pour eviter de bloquer la connexion
    DB pendant les 5-30 s de polling Gamma.
    """
    if not job.order.offer.gamma_enabled:
        return []

    gamma_client = gamma_client or get_gamma_client()
    document = render_client_document(job)
    markdown = document.to_markdown()

    # I/O reseau -- pas de transaction ouverte ici.
    presentation = gamma_client.create_presentation(
        title=document.title,
        markdown=markdown,
        theme_id=_theme_id_for(job),
    )
    gamma_client.wait_until_ready(presentation_id=presentation.presentation_id)
    export = gamma_client.export(presentation=presentation)

    # Uniquement des ecritures DB a partir d'ici.
    return _persist_gamma_artifacts(
        job,
        export=export,
        presentation_id=presentation.presentation_id,
    )


def deliver_job(
    job: GenerationJob,
    *,
    gamma_client: GammaClient | None = None,
    email_client: TransactionalEmailClient | None = None,
) -> DeliveryBatch:
    """Orchestre la livraison complete d'un job termine.

    Architecture d'atomicite :
    1. Appels externes (Gamma, email) AVANT la transaction principale.
    2. Ecriture en base dans une transaction atomique.
    3. Sur echec, persistence des traces (batch FAILED + incident) dans une
       transaction SEPAREE pour survivre au rollback de la transaction principale.
    """
    if job.status != JobStatus.DONE:
        msg = f"Cannot deliver job in status {job.status}."
        raise DeliveryError(msg)

    email_client = email_client or get_transactional_email_client()
    gamma_client = gamma_client or get_gamma_client()

    try:
        # --- I/O externe (pas de transaction ouverte) ---
        # assemble_document est idempotent via update_or_create.
        link_artifact = assemble_document(job)
        pdf_artifact = ensure_pdf_artifact(job, link_artifact=link_artifact)
        gamma_artifacts = ensure_gamma_artifacts(job, gamma_client=gamma_client)
        all_artifacts: tuple[DocumentArtifact, ...] = (
            link_artifact,
            pdf_artifact,
            *gamma_artifacts,
        )

        attachments = tuple(
            EmailAttachment(
                filename=_attachment_filename(artifact, job.order.systeme_order_id),
                url=artifact.download_url,
            )
            for artifact in all_artifacts
            if artifact.kind in {ArtifactKind.PDF, ArtifactKind.GAMMA_PDF, ArtifactKind.GAMMA_PPTX}
        )
        result = email_client.send_delivery_email(
            recipient_email=job.order.customer.email,
            subject=f"Livrables EVKHA - {job.order.systeme_order_id}",
            html_body=_html_body(job, all_artifacts),
            attachments=attachments,
        )

        # --- Transaction DB pure (aucun I/O reseau) ---
        with transaction.atomic():
            batch, _created = DeliveryBatch.objects.update_or_create(
                order=job.order,
                defaults={
                    "status": DeliveryStatus.SENT,
                    "email_provider": "brevo",
                    "recipient_email": job.order.customer.email,
                    "download_url": link_artifact.download_url,
                    "error_message": "",
                    "sent_at": timezone.now(),
                },
            )
            batch.artifacts.set(all_artifacts)
            DeliveryEvent.objects.create(
                batch=batch,
                status=DeliveryStatus.SENT,
                message="Livraison envoyee",
                provider_message_id=result.provider_message_id,
            )
            job.order.status = OrderStatus.DELIVERED
            job.order.save(update_fields=["status", "updated_at"])
            return batch

    except Exception as exc:
        # Transaction separee pour survivre au rollback de la transaction principale
        # et garantir que l'incident + le batch FAILED sont toujours persistes.
        try:
            with transaction.atomic():
                DeliveryBatch.objects.update_or_create(
                    order=job.order,
                    defaults={
                        "status": DeliveryStatus.FAILED,
                        "email_provider": "brevo",
                        "recipient_email": job.order.customer.email,
                        "error_message": str(exc),
                    },
                )
                OperationalIncident.objects.create(
                    title="Echec livraison livrable",
                    severity=IncidentSeverity.HIGH,
                    order=job.order,
                    job=job,
                    details={"error": str(exc)},
                )
        except Exception:  # noqa: BLE001 - on ne peut pas faire grand chose ici
            pass  # l'exception originale est relancee ci-dessous

        raise DeliveryError(str(exc)) from exc


def purge_expired_artifacts(*, now: datetime | None = None) -> int:
    now = now or timezone.now()
    expired = DocumentArtifact.objects.filter(
        status=ArtifactStatus.READY,
        expires_at__isnull=False,
        expires_at__lte=now,
    )
    count = expired.count()
    expired.update(status=ArtifactStatus.EXPIRED, download_url="")
    return count
