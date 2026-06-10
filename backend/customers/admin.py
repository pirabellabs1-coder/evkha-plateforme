from __future__ import annotations

from django.contrib import admin

from .models import Customer, Subscription


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "email", "customer_type", "company_name",
        "systeme_contact_id", "has_active_subscription",
    )
    list_filter = ("customer_type",)
    search_fields = ("email", "first_name", "last_name", "company_name", "systeme_contact_id")

    @admin.display(boolean=True, description="Abonnement actif")
    def has_active_subscription(self, obj: Customer) -> bool:
        return obj.has_active_subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("customer", "tier", "status", "systeme_subscription_id", "created_at")
    list_filter = ("status", "tier")
    search_fields = ("customer__email", "systeme_subscription_id")
    raw_id_fields = ("customer",)
