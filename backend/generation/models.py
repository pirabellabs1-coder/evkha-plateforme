from __future__ import annotations

from decimal import Decimal

from django.db import models

from catalog.models import DeliverableType
from core.models import UUIDModel
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


class FactKind(models.TextChoices):
    MARKET_SIZE = "market_size", "Taille de marche"
    GROWTH_RATE = "growth_rate", "Taux de croissance"
    CURRENCY = "currency", "Devise"
    ASSUMPTION = "assumption", "Hypothese"
    SOURCE = "source", "Source"
    COMPETITOR = "competitor", "Concurrent"


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


class CoherenceFact(UUIDModel):
    job = models.ForeignKey(GenerationJob, on_delete=models.CASCADE, related_name="coherence_facts")
    kind = models.CharField(max_length=32, choices=FactKind.choices)
    key = models.CharField(max_length=120)
    value = models.CharField(max_length=500)
    source_chapter_number = models.PositiveSmallIntegerField(null=True, blank=True)
    is_locked = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "kind", "key"],
                name="uniq_coherence_fact_per_job_kind_key",
            )
        ]
        ordering = ["job", "kind", "key"]

    def __str__(self) -> str:
        return f"{self.kind}:{self.key}"
