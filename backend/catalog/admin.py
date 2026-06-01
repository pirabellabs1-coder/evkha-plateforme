from __future__ import annotations

from django.contrib import admin

from .models import Offer


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("name", "deliverable_type", "gamma_enabled", "retention_days", "is_active")
    list_filter = ("deliverable_type", "gamma_enabled", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
