"""python manage.py seed_offers

Crée ou met à jour les 12 offres Systeme.io dans le catalogue EVKHA.

Les slugs correspondent aux noms de produits Systeme.io slugifiés.
Si un webhook renvoie un slug différent, mettre à jour le slug dans Django Admin.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from catalog.models import DeliverableType, Offer

# (slug, name, deliverable_type, credits_per_month, is_subscription, is_extra_credit,
#  systeme_product_name)
# systeme_product_name = valeur exacte de physicalProduct.name dans le payload SALE_NEW
# du webhook global Systeme.io. Laisser vide si inconnu ; renseigner via Django admin
# apres avoir observe un premier achat dans les WebhookEvents SKIPPED.
_OFFERS: list[tuple[str, str, str, int, bool, bool, str]] = [
    # ── B2C — achats à l'unité ──────────────────────────────────────────────
    # systeme_product_name = valeur exacte du nom de produit/page dans Systeme.io
    # (physicalProduct.name OU funnelStep.name dans le payload SALE_NEW).
    # Si le premier achat test reste SKIPPED, voir error_message pour le nom exact.
    (
        "etude-marche",
        "Étude de marché",
        DeliverableType.MARKET_STUDY,
        0, False, False,
        "PAGE DE PAIEMENT EM PERSONNALISÉE 149",
    ),
    (
        "etude-concurrence",
        "Étude de la concurrence",
        DeliverableType.COMPETITOR_STUDY,
        0, False, False,
        "PAGE DE PAIEMENT EC",
    ),
    (
        "business-plan",
        "Business plan",
        DeliverableType.BUSINESS_PLAN,
        0, False, False,
        "PAGE DE PAIEMENT BP",
    ),
    (
        "strategie-business",
        "Stratégie business",
        DeliverableType.BUSINESS_STRATEGY,
        0, False, False,
        "PAGE DE PAIEMENT STR",
    ),
    # ── B2B — abonnements mensuels ───────────────────────────────────────────
    (
        "abonnement-solo",
        "Abonnement Solo",
        "",
        2, True, False,
        "",  # TODO apres que tu partages les noms des produits abonnements
    ),
    (
        "abonnement-pro",
        "Abonnement Pro",
        "",
        3, True, False,
        "",
    ),
    (
        "abonnement-pro-plus",
        "Abonnement Pro Plus",
        "",
        5, True, False,
        "",
    ),
    (
        "abonnement-structure",
        "Abonnement Structure",
        "",
        10, True, False,
        "",
    ),
    # ── B2B — crédits supplémentaires ────────────────────────────────────────
    (
        "solo-credit-supplementaire",
        "Solo Crédit Supplémentaire",
        "",
        0, False, True,
        "PAGE DE PAIEMENT CREDIT SOLO SUPP",
    ),
    (
        "pro-credit-supplementaire",
        "Pro Crédit Supplémentaire",
        "",
        0, False, True,
        "PAGE DE PAIEMENT CREDIT PRO SUPP",
    ),
    (
        "pro-plus-credit-supplementaire",
        "Pro Plus Crédit Supplémentaire",
        "",
        0, False, True,
        "PAGE DE PAIEMENT CREDIT PRO PLUS SUPP",
    ),
    (
        "structure-credit-supplementaire",
        "Structure Crédit Supplémentaire",
        "",
        0, False, True,
        "PAGE DE PAIEMENT CREDIT STRUCTURE SUPP",
    ),
]


class Command(BaseCommand):
    help = "Crée ou met à jour les offres Systeme.io dans le catalogue."

    def handle(self, *args: object, **options: object) -> None:
        created_count = 0
        updated_count = 0

        for (
            slug, name, deliverable_type, credits_per_month,
            is_subscription, is_extra_credit, systeme_product_name,
        ) in _OFFERS:
            defaults: dict = {
                "name": name,
                "deliverable_type": deliverable_type,
                "credits_per_month": credits_per_month,
                "is_subscription": is_subscription,
                "is_extra_credit": is_extra_credit,
                "is_active": True,
            }
            # Ne pas ecraser un systeme_product_name deja configure en admin.
            if systeme_product_name:
                defaults["systeme_product_name"] = systeme_product_name
            offer, created = Offer.objects.update_or_create(
                slug=slug,
                defaults=defaults,
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  [CRÉÉ]    {offer.slug}"))
            else:
                updated_count += 1
                self.stdout.write(f"  [OK]      {offer.slug}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{created_count} créées, {updated_count} mises à jour. "
                f"Total : {len(_OFFERS)} offres."
            )
        )
