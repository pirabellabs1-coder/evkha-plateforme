from __future__ import annotations

from django.contrib import admin
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest

from .models import ChapterGeneration, CoherenceFact, GenerationJob, SocleDonnees


@admin.display(description="Cache")
def taux_de_cache(chapitre: ChapterGeneration) -> str:
    """Part de l'entrée servie par le cache, et ce qu'elle a évité de payer.

    Ces deux compteurs ont longtemps existé sur le résultat d'appel sans jamais
    atteindre la base ; les afficher est la seule façon qu'une régression du
    cache se voie autrement que par une facture qui monte sans raison.

    Une LECTURE de cache coûte 10 % d'un jeton d'entrée. L'économie affichée est
    donc la part lue × 0,9 — approximative à dessein, et libellée comme telle :
    le chiffre exact dépend du tarif du modèle, et le prétendre exact ici
    créerait une seconde source de vérité sur le prix (règle 5).
    """
    lues = chapitre.cache_read_tokens
    ecrites = chapitre.cache_write_tokens
    if not lues and not ecrites:
        return "—"
    total = chapitre.input_tokens + lues
    part = (100 * lues / total) if total else 0
    return f"{part:.0f} % lus (~{lues * 0.9 / 1000:.0f} k jetons évités)"


class ChapterGenerationInline(admin.TabularInline):
    model = ChapterGeneration
    extra = 0
    fields = (
        "chapter_number", "chapter_title", "status",
        "cost_eur", "cost_perdu_eur", taux_de_cache, "retry_count",
    )
    readonly_fields = ("cost_eur", "cost_perdu_eur", taux_de_cache)


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
    list_display = (
        "job", "chapter_number", "chapter_title", "status",
        "cost_eur", "cost_perdu_eur", taux_de_cache, "retry_count",
    )
    list_filter = ("status",)
    search_fields = ("chapter_title", "prompt_key", "job__order__systeme_order_id")
    autocomplete_fields = ("job",)


@admin.register(SocleDonnees)
class SocleDonneesAdmin(admin.ModelAdmin):
    """Point de correction manuelle du socle, exigé par le cahier des charges.

    La cliente doit pouvoir rectifier un chiffre AVANT que l'étude ne se
    construise dessus. Toute modification est revalidée contre le référentiel :
    une correction humaine n'échappe pas aux contrôles.
    """

    list_display = ("job", "version", "statut", "nb_donnees", "tentatives",
                    "corrige_manuellement", "valide_at")
    list_filter = ("statut", "corrige_manuellement")
    search_fields = ("job__order__systeme_order_id", "job__order__customer__email")
    autocomplete_fields = ("job",)
    readonly_fields = ("version", "tentatives", "valide_at", "motifs_rejet",
                       "input_tokens", "output_tokens", "cost_eur")
    actions = ("action_revalider", "action_regenerer")

    @admin.display(description="Données")
    def nb_donnees(self, objet: SocleDonnees) -> int:
        contenu = objet.contenu
        return len(contenu.get("donnees", [])) if isinstance(contenu, dict) else 0

    def save_model(
        self,
        request: HttpRequest,
        obj: SocleDonnees,
        form: ModelForm[SocleDonnees],
        change: bool,
    ) -> None:
        """Revalide systématiquement après une édition manuelle."""
        if change and "contenu" in form.changed_data:
            obj.corrige_manuellement = True
        super().save_model(request, obj, form, change)
        if change and "contenu" in form.changed_data:
            from .socle.services import revalider_socle  # noqa: PLC0415

            motifs = revalider_socle(obj)
            if motifs:
                self.message_user(
                    request,
                    f"Socle enregistré mais INVALIDE : {' ; '.join(motifs[:5])}",
                    level="ERROR",
                )
            else:
                self.message_user(request, "Socle corrigé et revalidé.")

    @admin.action(description="Revalider le socle contre le référentiel")
    def action_revalider(
        self, request: HttpRequest, queryset: QuerySet[SocleDonnees]
    ) -> None:
        from .socle.services import revalider_socle  # noqa: PLC0415

        for enregistrement in queryset:
            motifs = revalider_socle(enregistrement)
            niveau = "ERROR" if motifs else "INFO"
            texte = " ; ".join(motifs[:5]) if motifs else "valide"
            self.message_user(request, f"{enregistrement.job_id} : {texte}", level=niveau)

    @admin.action(description="Régénérer le socle (INVALIDE tous les chapitres)")
    def action_regenerer(
        self, request: HttpRequest, queryset: QuerySet[SocleDonnees]
    ) -> None:
        from .socle.services import regenerer_socle  # noqa: PLC0415

        for enregistrement in queryset:
            remis = regenerer_socle(enregistrement.job)
            self.message_user(
                request,
                f"{enregistrement.job_id} : socle invalidé, {remis} chapitre(s) "
                "remis en attente.",
            )


@admin.register(CoherenceFact)
class CoherenceFactAdmin(admin.ModelAdmin):
    list_display = ("job", "kind", "key", "value", "is_locked")
    list_filter = ("kind", "is_locked")
    search_fields = ("key", "value", "job__order__systeme_order_id")
    autocomplete_fields = ("job",)
