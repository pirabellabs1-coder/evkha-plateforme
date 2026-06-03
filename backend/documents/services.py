from __future__ import annotations

import hashlib
from datetime import timedelta

from django.utils import timezone
from generation.models import GenerationJob, JobStatus
from generation.rendering import render_client_document
from integrations.google_docs import GoogleDocsClient, get_google_docs_client

from .models import ArtifactKind, ArtifactStatus, DocumentArtifact


class DocumentAssemblyError(RuntimeError):
    pass


def _retention_days(job: GenerationJob) -> int:
    return int(getattr(job.order.offer, "retention_days", 7) or 7)


def assemble_document(
    job: GenerationJob,
    *,
    docs_client: GoogleDocsClient | None = None,
) -> DocumentArtifact:
    """Assemble le livrable client (Rendering Engine) et publie un artefact.

    Idempotent par (job, kind=LINK) : un re-run met a jour l'artefact existant.
    """
    if job.status != JobStatus.DONE:
        msg = f"Cannot assemble document for job in status {job.status}."
        raise DocumentAssemblyError(msg)

    docs_client = docs_client or get_google_docs_client()

    document = render_client_document(job)
    if not document.sections:
        msg = "No completed chapters to assemble."
        raise DocumentAssemblyError(msg)

    markdown = document.to_markdown()
    checksum = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    export = docs_client.export(title=document.title, markdown=markdown)
    expires_at = timezone.now() + timedelta(days=_retention_days(job))

    artifact, _created = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.LINK,
        defaults={
            "status": ArtifactStatus.READY,
            "storage_key": export.storage_key,
            "download_url": export.download_url,
            "checksum_sha256": checksum,
            "expires_at": expires_at,
        },
    )
    return artifact
