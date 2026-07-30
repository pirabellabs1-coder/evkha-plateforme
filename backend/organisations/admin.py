"""Administration des organisations et des crédits (lot 4, §10.2).

Le cahier des charges demande à EVKHA de pouvoir doter un compte, suspendre une
organisation et consulter la consommation ligne par ligne. Tout passe par ici
en attendant l'espace administrateur du lot 5.

Un mouvement de crédit est **non modifiable** : le journal est la seule
définition du solde, et permettre d'éditer une ligne passée reviendrait à
réécrire l'histoire comptable sans trace. Une erreur se corrige par un
mouvement inverse, motivé.
"""
from __future__ import annotations

from typing import Any

from django.contrib import admin, messages
from django.http import HttpRequest

from . import credits, services
from .models import (
    AbonnementOrganisation,
    ClientFinal,
    Formule,
    MembreOrganisation,
    MouvementCredit,
    Organisation,
    PortefeuilleCredits,
)


class MembreEnLigne(admin.TabularInline):
    model = MembreOrganisation
    extra = 0
    fields = ("customer", "role", "invite_le", "revoque_le")


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = (
        "raison_sociale", "statut", "solde_credits", "formule_active",
        "marque_blanche",
    )
    list_filter = ("statut", "marque_blanche")
    search_fields = ("raison_sociale", "contact__email")
    inlines = (MembreEnLigne,)
    actions = ("action_suspendre", "action_reactiver")

    @admin.display(description="Solde")
    def solde_credits(self, obj: Organisation) -> int:
        return credits.solde(obj)

    @admin.display(description="Formule")
    def formule_active(self, obj: Organisation) -> str:
        abonnement = obj.abonnements.filter(statut="actif").first()
        return abonnement.formule.libelle if abonnement else "—"

    @admin.action(description="Suspendre les organisations sélectionnées")
    def action_suspendre(self, request: HttpRequest, queryset: Any) -> None:
        for organisation in queryset:
            services.suspendre(organisation, motif=f"Admin {request.user}")
        self.message_user(request, f"{queryset.count()} organisation(s) suspendue(s).")

    @admin.action(description="Réactiver les organisations sélectionnées")
    def action_reactiver(self, request: HttpRequest, queryset: Any) -> None:
        for organisation in queryset:
            services.reactiver(organisation)
        self.message_user(request, f"{queryset.count()} organisation(s) réactivée(s).")


@admin.register(Formule)
class FormuleAdmin(admin.ModelAdmin):
    list_display = (
        "libelle", "code", "credits_par_echeance", "prix_affiche",
        "cout_par_livrable", "report_credits", "active",
    )
    list_filter = ("active", "report_credits")
    prepopulated_fields = {"code": ("libelle",)}

    @admin.display(description="Prix mensuel")
    def prix_affiche(self, obj: Formule) -> str:
        return f"{obj.prix_mensuel_cents / 100:.2f} {obj.devise}"

    @admin.display(description="Par livrable")
    def cout_par_livrable(self, obj: Formule) -> str:
        """Chiffre annoncé sur la page publique. Le voir ici évite qu'il dérive."""
        if not obj.credits_par_echeance:
            return "—"
        return f"{obj.prix_mensuel_cents / 100 / obj.credits_par_echeance:.2f} €"


@admin.register(AbonnementOrganisation)
class AbonnementAdmin(admin.ModelAdmin):
    list_display = (
        "organisation", "formule", "statut", "debut_le", "derniere_periode_dotee",
    )
    list_filter = ("statut", "formule")
    search_fields = ("organisation__raison_sociale",)
    actions = ("action_appliquer_echeance",)

    @admin.action(description="Appliquer l'échéance de la période courante")
    def action_appliquer_echeance(self, request: HttpRequest, queryset: Any) -> None:
        total = 0
        for abonnement in queryset.filter(statut="actif"):
            total += services.appliquer_echeance(abonnement)
        self.message_user(
            request, f"{total} crédit(s) dotés.",
            messages.SUCCESS if total else messages.INFO,
        )


class MouvementEnLigne(admin.TabularInline):
    model = MouvementCredit
    extra = 0
    fields = ("created_at", "type", "quantite", "motif", "reference", "auteur")
    readonly_fields = fields
    ordering = ("-created_at",)

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(PortefeuilleCredits)
class PortefeuilleAdmin(admin.ModelAdmin):
    list_display = ("organisation", "solde_affiche")
    search_fields = ("organisation__raison_sociale",)
    inlines = (MouvementEnLigne,)

    @admin.display(description="Solde")
    def solde_affiche(self, obj: PortefeuilleCredits) -> int:
        return obj.solde


@admin.register(MouvementCredit)
class MouvementCreditAdmin(admin.ModelAdmin):
    """Journal en lecture seule. Une erreur se corrige par un mouvement inverse."""

    list_display = (
        "created_at", "organisation_affichee", "type", "quantite", "motif",
        "reference", "auteur",
    )
    list_filter = ("type",)
    search_fields = (
        "portefeuille__organisation__raison_sociale", "motif", "reference",
    )
    date_hierarchy = "created_at"

    @admin.display(description="Organisation")
    def organisation_affichee(self, obj: MouvementCredit) -> str:
        return obj.portefeuille.organisation.raison_sociale

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(ClientFinal)
class ClientFinalAdmin(admin.ModelAdmin):
    list_display = (
        "raison_sociale", "organisation", "secteur", "couleur_principale",
        "archive_le",
    )
    list_filter = ("organisation",)
    search_fields = ("raison_sociale", "secteur")
