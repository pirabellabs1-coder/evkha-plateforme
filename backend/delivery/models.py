from __future__ import annotations

from django.db import models

from core.models import UUIDModel
from documents.models import DocumentArtifact
from orders.models import Order


class EmailProvider(models.TextChoices):
    BREVO = "brevo", "Brevo"


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    SENT = "sent", "Envoyee"
    FAILED = "failed", "Echec"


class DeliveryBatch(UUIDModel):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="delivery_batches")
    status = models.CharField(
        max_length=16,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
    )
    email_provider = models.CharField(
        max_length=16,
        choices=EmailProvider.choices,
        default=EmailProvider.BREVO,
    )
    recipient_email = models.EmailField()
    download_url = models.URLField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    artifacts = models.ManyToManyField(
        DocumentArtifact,
        related_name="delivery_batches",
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.order_id} - {self.status}"


class DeliveryEvent(UUIDModel):
    batch = models.ForeignKey(DeliveryBatch, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=16, choices=DeliveryStatus.choices)
    message = models.CharField(max_length=500, blank=True)
    provider_message_id = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.batch_id} - {self.status}"
