from __future__ import annotations

from django.contrib import admin

from .models import ExternalCredentialRef, WebhookEvent


@admin.register(ExternalCredentialRef)
class ExternalCredentialRefAdmin(admin.ModelAdmin):
    list_display = ("provider", "env_var_name", "is_required")
    list_filter = ("provider", "is_required")
    search_fields = ("env_var_name", "description")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "status", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("event_id", "payload_hash", "error_message")
