from __future__ import annotations

from django.contrib import admin

from .models import DeliveryBatch, DeliveryEvent


class DeliveryEventInline(admin.TabularInline):
    model = DeliveryEvent
    extra = 0
    fields = ("status", "message", "provider_message_id", "created_at")
    readonly_fields = ("created_at",)


@admin.register(DeliveryBatch)
class DeliveryBatchAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "email_provider", "recipient_email", "sent_at")
    list_filter = ("status", "email_provider")
    search_fields = ("order__systeme_order_id", "recipient_email")
    autocomplete_fields = ("order", "artifacts")
    inlines = (DeliveryEventInline,)


@admin.register(DeliveryEvent)
class DeliveryEventAdmin(admin.ModelAdmin):
    list_display = ("batch", "status", "provider_message_id", "created_at")
    list_filter = ("status",)
    search_fields = ("batch__order__systeme_order_id", "provider_message_id", "message")
    autocomplete_fields = ("batch",)
