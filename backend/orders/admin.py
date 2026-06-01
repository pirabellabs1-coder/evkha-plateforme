from __future__ import annotations

from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("systeme_order_id", "customer", "offer", "status", "purchased_at")
    list_filter = ("status", "offer__deliverable_type")
    search_fields = ("systeme_order_id", "customer__email", "offer__name")
    autocomplete_fields = ("customer", "offer")
