"""python manage.py seed_offers

Crée ou met à jour les 12 offres Systeme.io dans le catalogue EVKHA.

Les slugs correspondent aux noms de produits Systeme.io slugifiés.
Si un webhook renvoie un slug différent, mettre à jour le slug dans Django Admin.
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from catalog.models import DeliverableType, Offer

# (slug, name, deliverable_type, credits_per_month, is_subscription, is_extra_credit,
#  systeme_product_name, prix_unitaire_cents)
# prix_unitaire_cents : tarif d'un achat A L'UNITE. Zero pour les offres qui ne se
# vendent pas seules (abonnements, credits supplementaires : leur tarif vit sur la
# Formule). Les quatre tarifs B2C sont ceux affiches sur evkha.fr/etudedemarche.
# systeme_product_name = valeur exacte de physicalProduct.name dans le payload SALE_NEW
# du webhook global Systeme.io. Laisser vide si inconnu ; renseigner via Django admin
# apres avoir observe un premier achat dans les WebhookEvents SKIPPED.
_OFFERS: list[tuple[str, str, str, int, bool, bool, str, int]] = [
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
        14900,
    ),
    (
        "etude-concurrence",
        "Étude de la concurrence",
        DeliverableType.COMPETITOR_STUDY,
        0, False, False,
        "PAGE DE PAIEMENT EC",
        8900,
    ),
    (
        "business-plan",
        "Business plan",
        DeliverableType.BUSINESS_PLAN,
        0, False, False,
        "PAGE DE PAIEMENT BP",
        18500,
    ),
    (
        "strategie-business",
        "Stratégie business",
        DeliverableType.BUSINESS_STRATEGY,
        0, False, False,
        "PAGE DE PAIEMENT STR",
        19500,
    ),
    # ── B2B — abonnements mensuels ───────────────────────────────────────────
    (
        "abonnement-solo",
        "Abonnement Solo",
        "",
        2, True, False,
        "",  # TODO apres que tu partages les noms des produits abonnements
        0,
    ),
    (
        "abonnement-pro",
        "Abonnement Pro",
        "",
        3, True, False,
        "",
        0,
    ),
    (
        "abonnement-pro-plus",
        "Abonnement Pro Plus",
        "",
        5, True, False,
        "",
        0,
    ),
    (
        "abonnement-structure",
        "Abonnement Structure",
        "",
        10, True, False,
        "",
        0,
    ),
    # ── B2B — crédits supplémentaires ────────────────────────────────────────
    (
        "solo-credit-supplementaire",
        "Solo Crédit Supplémentaire",
        "",
        0, False, True,
        "PAGE DE PAIEMENT CREDIT SOLO SUPP",
        0,
    ),
    (
        "pro-credit-supplementaire",
        "Pro Crédit Supplémentaire",
        "",
        0, False, True,
        "PAGE DE PAIEMENT CREDIT PRO SUPP",
        0,
    ),
    (
        "pro-plus-credit-supplementaire",
        "Pro Plus Crédit Supplémentaire",
        "",
        0, False, True,
        "PAGE DE PAIEMENT CREDIT PRO PLUS SUPP",
        0,
    ),
    (
        "structure-credit-supplementaire",
        "Structure Crédit Supplémentaire",
        "",
        0, False, True,
        "PAGE DE PAIEMENT CREDIT STRUCTURE SUPP",
        0,
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
            prix_unitaire_cents,
        ) in _OFFERS:
            defaults: dict[str, Any] = {
                "name": name,
                "deliverable_type": deliverable_type,
                "credits_per_month": credits_per_month,
                "is_subscription": is_subscription,
                "is_extra_credit": is_extra_credit,
                "prix_unitaire_cents": prix_unitaire_cents,
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
