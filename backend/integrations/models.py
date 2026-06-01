from __future__ import annotations

from core.models import UUIDModel
from django.db import models


class IntegrationProvider(models.TextChoices):
    ANTHROPIC = "anthropic", "Anthropic Claude"
    GOOGLE = "google", "Google Docs / Drive"
    GAMMA = "gamma", "Gamma"
    BREVO = "brevo", "Brevo"
    SYSTEME = "systeme", "Systeme.io"
    TALLY = "tally", "Tally"
    N8N = "n8n", "n8n"


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
