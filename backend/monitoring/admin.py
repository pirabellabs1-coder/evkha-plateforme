from __future__ import annotations

from django.contrib import admin

from .models import OperationalIncident


@admin.register(OperationalIncident)
class OperationalIncidentAdmin(admin.ModelAdmin):
    list_display = ("title", "severity", "status", "order", "job", "created_at")
    list_filter = ("severity", "status")
    search_fields = ("title", "order__systeme_order_id", "job__order__systeme_order_id")
    autocomplete_fields = ("order", "job")
