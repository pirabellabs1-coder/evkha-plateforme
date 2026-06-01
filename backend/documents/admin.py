from __future__ import annotations

from django.contrib import admin

from .models import DocumentArtifact


@admin.register(DocumentArtifact)
class DocumentArtifactAdmin(admin.ModelAdmin):
    list_display = ("job", "kind", "status", "expires_at")
    list_filter = ("kind", "status")
    search_fields = ("job__order__systeme_order_id", "storage_key", "download_url")
    autocomplete_fields = ("job",)
