from __future__ import annotations

from django.db import models

from core.models import UUIDModel


class DeliverableType(models.TextChoices):
    MARKET_STUDY = "market_study", "Etude de marche"
    COMPETITOR_STUDY = "competitor_study", "Etude de concurrence"
    BUSINESS_PLAN = "business_plan", "Business plan"
    BUSINESS_STRATEGY = "business_strategy", "Strategie business"


class DeliveryMode(models.TextChoices):
    LINK_AND_PDF = "link_and_pdf", "Lien de telechargement + PDF"


class Offer(UUIDModel):
    name = models.CharField(max_length=140)
    slug = models.SlugField(unique=True)
    # Vide pour les offres B2B (abonnements, crédits suppl.) dont le type
    # de livrable est choisi via Tally (cf. DELIVERABLE_TYPE hidden field).
    deliverable_type = models.CharField(
        max_length=32,
        choices=DeliverableType.choices,
        blank=True,
        default="",
    )
    credits_per_month = models.PositiveSmallIntegerField(default=0)
    is_subscription = models.BooleanField(default=False)
    is_extra_credit = models.BooleanField(default=False)
    gamma_enabled = models.BooleanField(default=False)
    delivery_mode = models.CharField(
        max_length=32,
        choices=DeliveryMode.choices,
        default=DeliveryMode.LINK_AND_PDF,
    )
    retention_days = models.PositiveSmallIntegerField(default=7)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
