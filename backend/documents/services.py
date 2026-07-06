from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from generation.models import GenerationJob, JobStatus
from generation.rendering import render_branded_html, render_client_document
from integrations.pdf import PdfClient, get_pdf_client

from .models import ArtifactKind, ArtifactStatus, DocumentArtifact


@dataclass(frozen=True)
class DocumentAssembly:
    """Paire d'artefacts produits par assemble_document.

    - link : fichier HTML (aperçu navigateur, artefact LINK)
    - pdf  : livrable final WeasyPrint brandé (artefact PDF)
    """

    link: DocumentArtifact
    pdf: DocumentArtifact


class DocumentAssemblyError(RuntimeError):
    pass


def _retention_days(job: GenerationJob) -> int:
    return int(getattr(job.order.offer, "retention_days", 7) or 7)


def assemble_document(
    job: GenerationJob,
    *,
    pdf_client: PdfClient | None = None,
) -> DocumentAssembly:
    """Assemble le livrable client (Rendering Engine) et génère le PDF brandé.

    Idempotent par (job, kind) : un re-run met à jour les artefacts existants.

    Flux :
    1. render_branded_html() → HTML complet A4 brandé client
    2. pdf_client.generate()  → HTML + PDF écrits dans MEDIA_ROOT (ou stub)
    3. update_or_create LINK (HTML) + PDF dans DocumentArtifact
    """
    allowed_statuses = (JobStatus.DONE, JobStatus.FAILED)
    if job.status not in allowed_statuses:
        msg = f"Cannot assemble document for job in status {job.status}."
        raise DocumentAssemblyError(msg)

    pdf_client = pdf_client or get_pdf_client()

    document = render_client_document(job)
    if not document.sections:
        msg = "No completed chapters to assemble."
        raise DocumentAssemblyError(msg)

    html = render_branded_html(job)
    html_checksum = hashlib.sha256(html.encode("utf-8")).hexdigest()
    result = pdf_client.generate(title=document.title, html=html)
    expires_at = timezone.now() + timedelta(days=_retention_days(job))

    link_artifact, _ = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.LINK,
        defaults={
            "status": ArtifactStatus.READY,
            "storage_key": result.html_storage_key,
            "download_url": result.html_download_url,
            "checksum_sha256": html_checksum,
            "expires_at": expires_at,
        },
    )
    pdf_artifact, _ = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.PDF,
        defaults={
            "status": ArtifactStatus.READY,
            "storage_key": result.pdf_storage_key,
            "download_url": result.pdf_download_url,
            # Pas de checksum sur les octets binaires du PDF (non garanti stable).
            "checksum_sha256": "",
            "expires_at": expires_at,
        },
    )
    return DocumentAssembly(link=link_artifact, pdf=pdf_artifact)
