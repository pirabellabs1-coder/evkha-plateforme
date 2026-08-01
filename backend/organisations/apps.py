from __future__ import annotations

from django.apps import AppConfig


class OrganisationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "organisations"
    verbose_name = "Organisations, crédits et clients finaux"

    def ready(self) -> None:
        from . import checks  # noqa: F401 — enregistre les verifications Django
