from __future__ import annotations

from core.models import UUIDModel
from django.db import models
from generation.models import GenerationJob
from orders.models import Order


class IncidentSeverity(models.TextChoices):
    LOW = "low", "Faible"
    MEDIUM = "medium", "Moyenne"
    HIGH = "high", "Haute"
    CRITICAL = "critical", "Critique"


class IncidentStatus(models.TextChoices):
    OPEN = "open", "Ouvert"
    ACKNOWLEDGED = "acknowledged", "Pris en compte"
    RESOLVED = "resolved", "Resolu"


class OperationalIncident(UUIDModel):
    title = models.CharField(max_length=220)
    severity = models.CharField(max_length=16, choices=IncidentSeverity.choices)
    status = models.CharField(
        max_length=16,
        choices=IncidentStatus.choices,
        default=IncidentStatus.OPEN,
    )
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    job = models.ForeignKey(GenerationJob, on_delete=models.SET_NULL, null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title
