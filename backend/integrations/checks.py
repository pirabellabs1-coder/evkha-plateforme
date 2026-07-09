from __future__ import annotations

import os

from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def check_webhook_secrets(app_configs: object, **kwargs: object) -> list[Error | Warning]:
    """Risque 2 — endpoints webhook publics si les secrets ne sont pas configures."""
    issues: list[Error | Warning] = []
    is_prod = not settings.DEBUG

    for setting_name, endpoint, code in (
        ("TALLY_WEBHOOK_SECRET", "/webhooks/tally/intake/", "W001"),
        ("SYSTEME_WEBHOOK_SECRET", "/webhooks/systeme/order/", "W002"),
    ):
        if not getattr(settings, setting_name, ""):
            msg = (
                f"{setting_name} non configure : "
                f"l'endpoint {endpoint} accepte toutes les requetes sans verification."
            )
            hint = f"Definir {setting_name} dans les variables d'environnement du VPS (Coolify)."
            cls = Error if is_prod else Warning
            issues.append(cls(msg, hint=hint, id=f"evkha.{code}"))

    return issues


@register()
def check_ai_credentials(app_configs: object, **kwargs: object) -> list[Error | Warning]:
    """Risque 3 — generation en mode stub si ANTHROPIC_API_KEY absente."""
    issues: list[Error | Warning] = []

    use_stub = getattr(settings, "EVKHA_USE_STUB_AI", True)
    if not use_stub and not os.environ.get("ANTHROPIC_API_KEY", ""):
        issues.append(Error(
            "ANTHROPIC_API_KEY absente alors que EVKHA_USE_STUB_AI=False. "
            "Toutes les generations produiront du contenu de demonstration.",
            hint="Definir ANTHROPIC_API_KEY dans les variables d'environnement du VPS.",
            id="evkha.E001",
        ))

    return issues


@register()
def check_email_credentials(app_configs: object, **kwargs: object) -> list[Error | Warning]:
    """Risque 4 — livraison email bloquee si BREVO_API_KEY absente."""
    issues: list[Error | Warning] = []

    use_stub = getattr(settings, "EVKHA_USE_STUB_EMAIL", True)
    if not use_stub and not getattr(settings, "BREVO_API_KEY", ""):
        issues.append(Error(
            "BREVO_API_KEY absente alors que EVKHA_USE_STUB_EMAIL=False. "
            "Les emails de livraison echoueront systematiquement.",
            hint="Definir BREVO_API_KEY dans les variables d'environnement du VPS.",
            id="evkha.E002",
        ))

    return issues
