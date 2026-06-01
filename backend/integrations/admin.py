from __future__ import annotations

from django.contrib import admin

from .models import ExternalCredentialRef


@admin.register(ExternalCredentialRef)
class ExternalCredentialRefAdmin(admin.ModelAdmin):
    list_display = ("provider", "env_var_name", "is_required")
    list_filter = ("provider", "is_required")
    search_fields = ("env_var_name", "description")
