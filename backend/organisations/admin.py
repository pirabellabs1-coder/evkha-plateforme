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

from django import forms
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


class FormuleForm(forms.ModelForm):
    """Vérifie l'identifiant de tarif Stripe AU MOMENT où on le colle.

    Le champ était saisissable sans aucun contrôle. Trois façons de se tromper,
    et les trois ne se manifestaient qu'au clic du client :

    - un identifiant qui n'existe pas — faute de frappe, ou tarif supprimé ;
    - un tarif PONCTUEL là où l'abonnement attend un tarif récurrent : Stripe
      accepte la session, puis rien ne se renouvelle jamais ;
    - un tarif dont le MONTANT ne correspond pas au prix affiché sur la page
      partenaires. C'est le pire des trois : personne ne le remarque sur notre
      écran, et l'abonné le découvre sur son relevé bancaire.

    On interroge donc Stripe ici. Un identifiant refusé ne s'enregistre pas, et
    le motif dit quoi corriger (règle 2). Sans clé Stripe configurée, on laisse
    passer en le disant : bloquer la saisie sur une plateforme de recette
    empêcherait de préparer la configuration.
    """

    class Meta:
        model = Formule
        #: Enumeres, jamais `__all__` : un champ ajoute au modele demain serait
        #: sinon expose dans l'administration sans que personne ne l'ait decide.
        #: L'oubli inverse — un champ absent de cette liste — se voit tout de
        #: suite a l'ecran, alors qu'un champ expose par megarde ne se voit pas.
        fields = (
            "libelle",
            "code",
            "credits_par_echeance",
            "prix_mensuel_cents",
            "devise",
            "report_credits",
            "plafond_report",
            "regenerations_offertes",
            "validation_socle_par_client",
            "controle_qualite_avant_envoi",
            "prix_credit_supplementaire_cents",
            "reference_paiement",
            "avantages",
            "rang",
            "mise_en_avant",
            "active",
        )

    def clean_reference_paiement(self) -> str:
        reference = str(self.cleaned_data.get("reference_paiement") or "").strip()
        if not reference:
            return reference

        from paiement.stripe_api import PaiementIndisponible, cle_secrete  # noqa: PLC0415

        try:
            cle = cle_secrete()
        except PaiementIndisponible:
            return reference

        import stripe  # noqa: PLC0415

        try:
            tarif = stripe.Price.retrieve(reference, api_key=cle)
        except Exception as erreur:  # noqa: BLE001 — toute erreur Stripe vaut refus
            msg = (
                f"Stripe ne reconnaît pas « {reference} ». Vérifier l'identifiant "
                f"dans le tableau de bord Stripe, section Tarifs. ({erreur})"
            )
            raise forms.ValidationError(msg) from erreur

        if not tarif.get("recurring"):
            msg = (
                f"« {reference} » est un tarif PONCTUEL. Un abonnement mensuel "
                "exige un tarif récurrent, sinon rien ne se renouvelle."
            )
            raise forms.ValidationError(msg)

        attendu = int(self.cleaned_data.get("prix_mensuel_cents") or 0)
        montant = int(tarif.get("unit_amount") or 0)
        if attendu and montant != attendu:
            msg = (
                f"Le montant ne correspond pas : ce tarif Stripe facture "
                f"{montant / 100:.2f}, la formule annonce {attendu / 100:.2f}. "
                "L'abonné verrait la différence sur son relevé, pas sur nos écrans."
            )
            raise forms.ValidationError(msg)

        return reference


@admin.register(Formule)
class FormuleAdmin(admin.ModelAdmin):
    form = FormuleForm
    list_display = (
        "libelle", "code", "credits_par_echeance", "prix_affiche",
        "cout_par_livrable", "tarif_stripe", "report_credits", "active",
    )
    list_filter = ("active", "report_credits")
    prepopulated_fields = {"code": ("libelle",)}

    @admin.display(description="Tarif Stripe")
    def tarif_stripe(self, obj: Formule) -> str:
        """Dit d'un coup d'œil si la formule est reliée à un tarif.

        Le champ était saisissable mais invisible dans la liste : pour savoir
        laquelle des quatre formules manquait sa référence, il fallait les
        ouvrir une par une. Or une formule active sans tarif Stripe est un
        bouton « Souscrire » qui échoue au clic — le pire endroit où découvrir
        un oubli.
        """
        reference = str(obj.reference_paiement or "").strip()
        if reference:
            return reference
        return "— absent" if obj.active else "—"

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
