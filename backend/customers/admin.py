from __future__ import annotations

from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("email", "customer_type", "company_name", "systeme_contact_id")
    list_filter = ("customer_type",)
    search_fields = ("email", "first_name", "last_name", "company_name", "systeme_contact_id")
