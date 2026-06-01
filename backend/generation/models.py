from __future__ import annotations

from decimal import Decimal

from catalog.models import DeliverableType
from core.models import UUIDModel
from django.db import models
from orders.models import Order


class JobStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    RUNNING = "running", "En cours"
    DONE = "done", "Termine"
    FAILED = "failed", "Echec"
    CANCELLED = "cancelled", "Annule"


class ChapterStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    RUNNING = "running", "En cours"
    DONE = "done", "Termine"
    FAILED = "failed", "Echec"
    SKIPPED = "skipped", "Ignore"


class GenerationJob(UUIDModel):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="generation_job")
    deliverable_type = models.CharField(max_length=32, choices=DeliverableType.choices)
    status = models.CharField(max_length=16, choices=JobStatus.choices, default=JobStatus.PENDING)
    budget_eur = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("2.0000"))
    total_cost_eur = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"))
    context_summary = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.deliverable_type} - {self.order_id}"


class ChapterGeneration(UUIDModel):
    job = models.ForeignKey(GenerationJob, on_delete=models.CASCADE, related_name="chapters")
    chapter_number = models.PositiveSmallIntegerField()
    chapter_title = models.CharField(max_length=220)
    prompt_key = models.CharField(max_length=160)
    status = models.CharField(
        max_length=16,
        choices=ChapterStatus.choices,
        default=ChapterStatus.PENDING,
    )
    content = models.TextField(blank=True)
    operational_summary = models.TextField(blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_eur = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0.0000"))
    retry_count = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "chapter_number"],
                name="uniq_chapter_generation_per_job",
            )
        ]
        ordering = ["job", "chapter_number"]

    def __str__(self) -> str:
        return f"Chapitre {self.chapter_number} - {self.chapter_title}"
