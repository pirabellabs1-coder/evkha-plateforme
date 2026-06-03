from __future__ import annotations

from django.contrib import admin

from .models import ChapterGeneration, CoherenceFact, GenerationJob


class ChapterGenerationInline(admin.TabularInline):
    model = ChapterGeneration
    extra = 0
    fields = ("chapter_number", "chapter_title", "status", "cost_eur", "retry_count")
    readonly_fields = ("cost_eur",)


class CoherenceFactInline(admin.TabularInline):
    model = CoherenceFact
    extra = 0
    fields = ("kind", "key", "value", "source_chapter_number", "is_locked")


@admin.register(GenerationJob)
class GenerationJobAdmin(admin.ModelAdmin):
    list_display = ("order", "deliverable_type", "status", "total_cost_eur", "budget_eur")
    list_filter = ("deliverable_type", "status")
    search_fields = ("order__systeme_order_id", "order__customer__email")
    autocomplete_fields = ("order",)
    inlines = (ChapterGenerationInline, CoherenceFactInline)


@admin.register(ChapterGeneration)
class ChapterGenerationAdmin(admin.ModelAdmin):
    list_display = ("job", "chapter_number", "chapter_title", "status", "cost_eur", "retry_count")
    list_filter = ("status",)
    search_fields = ("chapter_title", "prompt_key", "job__order__systeme_order_id")
    autocomplete_fields = ("job",)


@admin.register(CoherenceFact)
class CoherenceFactAdmin(admin.ModelAdmin):
    list_display = ("job", "kind", "key", "value", "is_locked")
    list_filter = ("kind", "is_locked")
    search_fields = ("key", "value", "job__order__systeme_order_id")
    autocomplete_fields = ("job",)
