from __future__ import annotations

import logging
from datetime import datetime, timedelta
from html import escape

from django.db import transaction
from django.utils import timezone

from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact
from documents.services import DocumentAssembly, assemble_document
from generation.models import GenerationJob, JobStatus
from generation.rendering import render_client_document
from integrations.brevo import (
    EmailAttachment,
    TransactionalEmailClient,
    get_transactional_email_client,
)
from integrations.gamma import GammaClient, GammaExportResult, get_gamma_client
from integrations.pdf import PdfClient, get_pdf_client
from monitoring.models import IncidentSeverity, OperationalIncident
from orders.models import OrderStatus

from .models import DeliveryBatch, DeliveryEvent, DeliveryStatus

_log = logging.getLogger(__name__)

_DELIVERABLE_LABELS: dict[str, str] = {
    "market_study":      "Etude de marche",
    "competitor_study":  "Etude de la concurrence",
    "business_plan":     "Business Plan",
    "business_strategy": "Strategie business",
}


class DeliveryError(RuntimeError):
    pass


def _retention_days(job: GenerationJob) -> int:
    return int(getattr(job.order.offer, "retention_days", 7) or 7)


def _expires_at(job: GenerationJob) -> datetime:
    return timezone.now() + timedelta(days=_retention_days(job))


def _theme_id_for(job: GenerationJob) -> str:
    raw_payload = job.order.raw_payload or {}
    if isinstance(raw_payload, dict):
        theme_id = raw_payload.get("gamma_theme_id") or raw_payload.get("theme_id")
        if theme_id:
            return str(theme_id)
    return "evkha-default"


def _html_body(job: GenerationJob, artifacts: tuple[DocumentArtifact, ...]) -> str:
    order_id_safe = escape(job.order.systeme_order_id)
    deliverable_label = escape(
        _DELIVERABLE_LABELS.get(str(job.deliverable_type), str(job.deliverable_type))
    )
    retention = _retention_days(job)

    # Bouton principal : PDF (prioritaire) ou LINK si pas de PDF
    pdf_artifact = next(
        (a for a in artifacts if a.kind == ArtifactKind.PDF and a.download_url), None
    )
    link_artifact = next(
        (a for a in artifacts if a.kind == ArtifactKind.LINK and a.download_url), None
    )
    primary = pdf_artifact or link_artifact
    button_html = ""
    if primary:
        btn_label = (
            "Telecharger votre document (PDF)"
            if primary.kind == ArtifactKind.PDF
            else "Visualiser votre document"
        )
        button_html = (
            f'<p style="margin:28px 0;">'
            f'<a href="{escape(primary.download_url)}" '
            f'style="background:#1a1a2e;color:#ffffff;padding:13px 26px;'
            f'text-decoration:none;border-radius:4px;font-size:14px;font-weight:600;">'
            f'{btn_label}'
            f'</a></p>'
        )

    # Lien HTML de visualisation en complement du PDF
    preview_html = ""
    if link_artifact and primary is not link_artifact:
        preview_html = (
            f'<p style="margin:12px 0;font-size:13px;">'
            f'Vous pouvez egalement '
            f'<a href="{escape(link_artifact.download_url)}" style="color:#1a1a2e;">'
            f'visualiser votre document dans votre navigateur</a>.'
            f'</p>'
        )

    # Pieces jointes listees si presentes
    attached = [
        a for a in artifacts
        if a.kind in {ArtifactKind.PDF, ArtifactKind.GAMMA_PDF, ArtifactKind.GAMMA_PPTX}
        and a.download_url
    ]
    attachment_note = (
        "<p>Votre document est egalement disponible en piece jointe a cet e-mail.</p>"
        if attached else ""
    )

    return (
        "<p>Madame, Monsieur,</p>"
        "<p>Nous avons le plaisir de vous informer que votre document est pret.</p>"
        "<table style='border-collapse:collapse;margin:16px 0'>"
        f"<tr><td style='padding:4px 16px 4px 0;color:#666;'>Type de document</td>"
        f"<td style='padding:4px 0;font-weight:600;'>{deliverable_label}</td></tr>"
        f"<tr><td style='padding:4px 16px 4px 0;color:#666;'>Reference commande</td>"
        f"<td style='padding:4px 0;'>{order_id_safe}</td></tr>"
        "</table>"
        f"{button_html}"
        f"{preview_html}"
        f"{attachment_note}"
        f"<p style='color:#888;font-size:12px;'>"
        f"Ce lien de telechargement est valable {retention} jours.</p>"
        "<p style='margin-top:32px;'>Cordialement,<br>"
        "L'equipe EVKHA<br>"
        "<a href='mailto:contact@evkha.fr' style='color:#1a1a2e;'>contact@evkha.fr</a></p>"
    )


def notify_generation_started(
    job: GenerationJob,
    *,
    email_client: TransactionalEmailClient | None = None,
) -> None:
    """Envoie un email de confirmation au client des le lancement de la generation.

    Non bloquant : l'echec est logue mais ne fait pas echouer la generation.
    """
    if not job.order.customer.email:
        return
    email_client = email_client or get_transactional_email_client()
    deliverable_label = escape(
        _DELIVERABLE_LABELS.get(str(job.deliverable_type), str(job.deliverable_type))
    )
    order_id_safe = escape(job.order.systeme_order_id)
    html = (
        "<p>Madame, Monsieur,</p>"
        "<p>Nous vous confirmons la bonne reception de votre demande. "
        "La generation de votre document est en cours.</p>"
        "<table style='border-collapse:collapse;margin:16px 0'>"
        f"<tr><td style='padding:4px 16px 4px 0;color:#666;'>Type de document</td>"
        f"<td style='padding:4px 0;font-weight:600;'>{deliverable_label}</td></tr>"
        f"<tr><td style='padding:4px 16px 4px 0;color:#666;'>Reference commande</td>"
        f"<td style='padding:4px 0;'>{order_id_safe}</td></tr>"
        "</table>"
        "<p>Vous recevrez votre document par e-mail des que la generation sera terminee. "
        "Ce processus prend generalement entre 10 et 20 minutes.</p>"
        "<p style='margin-top:32px;'>Cordialement,<br>"
        "L'equipe EVKHA<br>"
        "<a href='mailto:contact@evkha.fr' style='color:#1a1a2e;'>contact@evkha.fr</a></p>"
    )
    try:
        email_client.send_delivery_email(
            recipient_email=job.order.customer.email,
            subject="Votre livrable est en cours de generation - EVKHA",
            html_body=html,
            attachments=(),
        )
    except Exception:  # noqa: BLE001
        _log.warning("notify_generation_started: echec envoi email pour job %s", job.id)


def _attachment_filename(artifact: DocumentArtifact, order_id: str) -> str:
    """Nom de fichier lisible : ex. 'EVKHA_order123_gamma.pdf'."""
    slug = order_id.replace(" ", "_")[:40]
    extension = "pptx" if artifact.kind == ArtifactKind.GAMMA_PPTX else "pdf"
    label = "gamma_pptx" if artifact.kind == ArtifactKind.GAMMA_PPTX else artifact.kind
    return f"EVKHA_{slug}_{label}.{extension}"


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

    Risque 5 — si l'API Gamma n'est pas configuree (NotImplementedError),
    on logue un warning et on retourne [] au lieu de bloquer la livraison.
    """
    if not job.order.offer.gamma_enabled:
        return []

    gamma_client = gamma_client or get_gamma_client()
    document = render_client_document(job)
    markdown = document.to_markdown()

    try:
        # I/O reseau -- pas de transaction ouverte ici.
        presentation = gamma_client.create_presentation(
            title=document.title,
            markdown=markdown,
            theme_id=_theme_id_for(job),
        )
        gamma_client.wait_until_ready(presentation_id=presentation.presentation_id)
        export = gamma_client.export(presentation=presentation)
    except NotImplementedError:
        _log.warning(
            "ensure_gamma_artifacts: API Gamma non configuree pour job %s — "
            "artefacts Gamma ignores, livraison PDF/email maintenue.",
            job.id,
        )
        return []

    # Uniquement des ecritures DB a partir d'ici.
    return _persist_gamma_artifacts(
        job,
        export=export,
        presentation_id=presentation.presentation_id,
    )


def generate_pdf_for_failed_job(
    job: GenerationJob,
    *,
    pdf_client: PdfClient | None = None,
) -> DocumentArtifact:
    """Genere le PDF admin d'un job FAILED (budget depasse) sans envoyer d'email.

    Permet a l'admin de telecharger le livrable partiel ou complet meme quand
    la generation a ete interrompue par le circuit breaker budget.
    N'envoie PAS d'email au client. Ne marque pas la commande DELIVERED.
    """
    if job.status != JobStatus.FAILED:
        msg = f"generate_pdf_for_failed_job attend un job FAILED, recu {job.status}."
        raise DeliveryError(msg)

    from documents.services import assemble_document  # noqa: PLC0415
    pdf_client = pdf_client or get_pdf_client()
    try:
        assembly = assemble_document(job, pdf_client=pdf_client)
        return assembly.pdf
    except Exception as exc:
        OperationalIncident.objects.create(
            title=f"Erreur generation PDF (job failed) {job.id}",
            severity=IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details={"error": str(exc)},
        )
        raise DeliveryError(str(exc)) from exc


def deliver_job(
    job: GenerationJob,
    *,
    pdf_client: PdfClient | None = None,
    gamma_client: GammaClient | None = None,
    email_client: TransactionalEmailClient | None = None,
) -> DeliveryBatch:
    """Orchestre la livraison complete d'un job termine.

    Architecture d'atomicite :
    1. Appels externes (PDF WeasyPrint, Gamma, email) AVANT la transaction principale.
    2. Ecriture en base dans une transaction atomique.
    3. Sur echec, persistence des traces (batch FAILED + incident) dans une
       transaction SEPAREE pour survivre au rollback de la transaction principale.
    """
    if job.status != JobStatus.DONE:
        msg = f"Cannot deliver job in status {job.status}."
        raise DeliveryError(msg)

    pdf_client = pdf_client or get_pdf_client()
    email_client = email_client or get_transactional_email_client()
    gamma_client = gamma_client or get_gamma_client()

    try:
        # --- I/O externe (pas de transaction ouverte) ---
        # assemble_document est idempotent via update_or_create.
        # Retourne DocumentAssembly(link=HTML, pdf=WeasyPrint PDF brandé).
        assembly: DocumentAssembly = assemble_document(job, pdf_client=pdf_client)
        gamma_artifacts = ensure_gamma_artifacts(job, gamma_client=gamma_client)
        all_artifacts: tuple[DocumentArtifact, ...] = (
            assembly.link,
            assembly.pdf,
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
                    "download_url": assembly.link.download_url,
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


def send_email_for_job(
    job: GenerationJob,
    *,
    email_client: TransactionalEmailClient | None = None,
) -> DeliveryBatch:
    """Envoie l'email de livraison avec les artefacts existants en base.

    N'effectue aucune generation PDF. Utile pour renvoyer un email depuis le dashboard.
    """
    if job.status != JobStatus.DONE:
        msg = f"Cannot send email for job in status {job.status}."
        raise DeliveryError(msg)

    email_client = email_client or get_transactional_email_client()

    artifacts = tuple(
        DocumentArtifact.objects.filter(
            job=job,
            status=ArtifactStatus.READY,
        ).exclude(download_url="")
    )

    attachments = tuple(
        EmailAttachment(
            filename=_attachment_filename(artifact, job.order.systeme_order_id),
            url=artifact.download_url,
        )
        for artifact in artifacts
        if artifact.kind in {ArtifactKind.PDF, ArtifactKind.GAMMA_PDF, ArtifactKind.GAMMA_PPTX}
        and artifact.download_url
    )

    try:
        result = email_client.send_delivery_email(
            recipient_email=job.order.customer.email,
            subject=f"Livrables EVKHA - {job.order.systeme_order_id}",
            html_body=_html_body(job, artifacts),
            attachments=attachments,
        )

        link_artifact = next(
            (a for a in artifacts if a.kind == ArtifactKind.LINK and a.download_url),
            None,
        )

        with transaction.atomic():
            batch, _ = DeliveryBatch.objects.update_or_create(
                order=job.order,
                defaults={
                    "status": DeliveryStatus.SENT,
                    "email_provider": "brevo",
                    "recipient_email": job.order.customer.email,
                    "download_url": link_artifact.download_url if link_artifact else "",
                    "error_message": "",
                    "sent_at": timezone.now(),
                },
            )
            if artifacts:
                batch.artifacts.set(artifacts)
            DeliveryEvent.objects.create(
                batch=batch,
                status=DeliveryStatus.SENT,
                message="Email envoye depuis le dashboard",
                provider_message_id=result.provider_message_id,
            )
            job.order.status = OrderStatus.DELIVERED
            job.order.save(update_fields=["status", "updated_at"])
            return batch

    except Exception as exc:
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
        except Exception:  # noqa: BLE001
            pass
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
