from __future__ import annotations

from core.models import UUIDModel
from django.db import models


class CustomerType(models.TextChoices):
    B2C = "b2c", "B2C"
    B2B = "b2b", "B2B"


class Customer(UUIDModel):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    company_name = models.CharField(max_length=160, blank=True)
    customer_type = models.CharField(
        max_length=8,
        choices=CustomerType.choices,
        default=CustomerType.B2C,
    )
    systeme_contact_id = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email
