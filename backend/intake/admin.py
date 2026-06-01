from __future__ import annotations

from django.contrib import admin

from .models import IntakeSubmission


@admin.register(IntakeSubmission)
class IntakeSubmissionAdmin(admin.ModelAdmin):
    list_display = ("order", "source", "status", "submitted_at")
    list_filter = ("source", "status")
    search_fields = ("order__systeme_order_id", "order__customer__email")
    autocomplete_fields = ("order",)
