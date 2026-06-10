from __future__ import annotations

from django.db import models

from core.models import UUIDModel
from generation.models import GenerationJob


class ArtifactKind(models.TextChoices):
    DOCX = "docx", "Word"
    PDF = "pdf", "PDF"
    GAMMA_PDF = "gamma_pdf", "Gamma PDF"
    GAMMA_PPTX = "gamma_pptx", "Gamma PPTX"
    LINK = "link", "Lien"


class ArtifactStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    READY = "ready", "Pret"
    EXPIRED = "expired", "Expire"
    FAILED = "failed", "Echec"


class DocumentArtifact(UUIDModel):
    job = models.ForeignKey(GenerationJob, on_delete=models.CASCADE, related_name="artifacts")
    kind = models.CharField(max_length=16, choices=ArtifactKind.choices)
    status = models.CharField(
        max_length=16,
        choices=ArtifactStatus.choices,
        default=ArtifactStatus.PENDING,
    )
    storage_key = models.CharField(max_length=500, blank=True)
    download_url = models.URLField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["job", "kind", "-created_at"]

    def __str__(self) -> str:
        return f"{self.kind} - {self.job_id}"
