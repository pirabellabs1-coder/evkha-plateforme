from __future__ import annotations

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"
    verbose_name = "Dashboard EVKHA"

    def ready(self) -> None:
        from . import checks  # noqa: F401 — enregistre les verifications Django
