from __future__ import annotations

from django.db import models

from core.models import UUIDModel
from orders.models import Order


class IntakeSource(models.TextChoices):
    TALLY = "tally", "Tally"
    TYPEFORM = "typeform", "Typeform"
    MANUAL = "manual", "Manuel"


class IntakeStatus(models.TextChoices):
    RECEIVED = "received", "Recue"
    INCOMPLETE = "incomplete", "Incomplete"
    NORMALIZED = "normalized", "Normalisee"
    REJECTED = "rejected", "Rejetee"


class IntakeSubmission(UUIDModel):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="intake_submission")
    source = models.CharField(
        max_length=16,
        choices=IntakeSource.choices,
        default=IntakeSource.TALLY,
    )
    status = models.CharField(
        max_length=16,
        choices=IntakeStatus.choices,
        default=IntakeStatus.RECEIVED,
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    normalized_variables = models.JSONField(default=dict, blank=True)
    missing_fields = models.JSONField(default=list, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.source} - {self.order_id}"
