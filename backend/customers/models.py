from __future__ import annotations

from django.db import models

from core.models import UUIDModel


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

    @property
    def has_active_subscription(self) -> bool:
        return self.subscriptions.filter(status=SubscriptionStatus.ACTIVE).exists()


class SubscriptionTier(models.TextChoices):
    SOLO = "solo", "Solo"
    PRO = "pro", "Pro"
    PRO_PLUS = "pro_plus", "Pro Plus"
    STRUCTURE = "structure", "Structure"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Actif"
    CANCELLED = "cancelled", "Annule"
    EXPIRED = "expired", "Expire"


class Subscription(UUIDModel):
    """Abonnement B2B — ouverture/fermeture selon statut Systeme.io.

    Un client B2B peut avoir plusieurs abonnements dans l'historique
    mais un seul ACTIVE à la fois (contraint par le service).
    """

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    tier = models.CharField(
        max_length=16,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.SOLO,
    )
    status = models.CharField(
        max_length=12,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
    )
    systeme_subscription_id = models.CharField(max_length=160, unique=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.customer.email} · {self.tier} · {self.status}"
