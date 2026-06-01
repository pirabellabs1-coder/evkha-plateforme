from __future__ import annotations

from catalog.models import Offer
from core.models import UUIDModel
from customers.models import Customer
from django.db import models


class OrderStatus(models.TextChoices):
    RECEIVED = "received", "Recue"
    WAITING_INTAKE = "waiting_intake", "En attente formulaire"
    PROCESSING = "processing", "En traitement"
    DELIVERED = "delivered", "Livree"
    FAILED = "failed", "Echec"
    CANCELLED = "cancelled", "Annulee"


class Order(UUIDModel):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    offer = models.ForeignKey(Offer, on_delete=models.PROTECT, related_name="orders")
    systeme_order_id = models.CharField(max_length=140, unique=True)
    status = models.CharField(
        max_length=32,
        choices=OrderStatus.choices,
        default=OrderStatus.RECEIVED,
    )
    purchased_at = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.systeme_order_id} - {self.offer}"
