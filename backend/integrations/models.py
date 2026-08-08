from __future__ import annotations

from django.db import models

from core.models import UUIDModel


class IntegrationProvider(models.TextChoices):
    ANTHROPIC = "anthropic", "Anthropic Claude"
    GOOGLE = "google", "Google Docs / Drive"
    GAMMA = "gamma", "Gamma"
    BREVO = "brevo", "Brevo"
    SYSTEME = "systeme", "Systeme.io (commandes)"
    SYSTEME_SUB = "systeme_sub", "Systeme.io (abonnements)"
    TALLY = "tally", "Tally"
    N8N = "n8n", "n8n"
    STRIPE = "stripe", "Stripe (abonnements)"


class WebhookStatus(models.TextChoices):
    RECEIVED = "received", "Recue"
    ACCEPTED = "accepted", "Acceptee"
    PROCESSED = "processed", "Traitee"
    DUPLICATE = "duplicate", "Doublon"
    REJECTED = "rejected", "Rejetee"
    FAILED = "failed", "Echec"
    SKIPPED = "skipped", "Ignoree (produit non-EVKHA)"


class ExternalCredentialRef(UUIDModel):
    provider = models.CharField(max_length=24, choices=IntegrationProvider.choices)
    env_var_name = models.CharField(max_length=120)
    description = models.CharField(max_length=240, blank=True)
    is_required = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "env_var_name"],
                name="uniq_credential_ref_provider_env",
            )
        ]
        ordering = ["provider", "env_var_name"]

    def __str__(self) -> str:
        return f"{self.provider}:{self.env_var_name}"


class WebhookEvent(UUIDModel):
    provider = models.CharField(max_length=24, choices=IntegrationProvider.choices)
    event_id = models.CharField(max_length=160)
    payload_hash = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16,
        choices=WebhookStatus.choices,
        default=WebhookStatus.RECEIVED,
    )
    raw_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"],
                name="uniq_webhook_event_provider_event",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_id}"
