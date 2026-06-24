"""python manage.py seed_offers

Crée ou met à jour les 12 offres Systeme.io dans le catalogue EVKHA.

Les slugs correspondent aux noms de produits Systeme.io slugifiés.
Si un webhook renvoie un slug différent, mettre à jour le slug dans Django Admin.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from catalog.models import DeliverableType, Offer

# (slug, name, deliverable_type, credits_per_month, is_subscription, is_extra_credit)
_OFFERS: list[tuple[str, str, str, int, bool, bool]] = [
    # ── B2C — achats à l'unité ──────────────────────────────────────────────
    (
        "etude-de-marche",
        "Étude de marché",
        DeliverableType.MARKET_STUDY,
        0, False, False,
    ),
    (
        "etude-de-la-concurrence",
        "Étude de la concurrence",
        DeliverableType.COMPETITOR_STUDY,
        0, False, False,
    ),
    (
        "business-plan",
        "Business plan",
        DeliverableType.BUSINESS_PLAN,
        0, False, False,
    ),
    (
        "strategie-business",
        "Stratégie business",
        DeliverableType.BUSINESS_STRATEGY,
        0, False, False,
    ),
    # ── B2B — abonnements mensuels ───────────────────────────────────────────
    (
        "abonnement-solo",
        "Abonnement Solo",
        "",   # deliverable_type défini par Tally (champ caché)
        2, True, False,
    ),
    (
        "abonnement-pro",
        "Abonnement Pro",
        "",
        3, True, False,
    ),
    (
        "abonnement-pro-plus",
        "Abonnement Pro Plus",
        "",
        5, True, False,
    ),
    (
        "abonnement-structure",
        "Abonnement Structure",
        "",
        10, True, False,
    ),
    # ── B2B — crédits supplémentaires ────────────────────────────────────────
    (
        "solo-credit-supplementaire",
        "Solo Crédit Supplémentaire",
        "",
        0, False, True,
    ),
    (
        "pro-credit-supplementaire",
        "Pro Crédit Supplémentaire",
        "",
        0, False, True,
    ),
    (
        "pro-plus-credit-supplementaire",
        "Pro Plus Crédit Supplémentaire",
        "",
        0, False, True,
    ),
    (
        "structure-credit-supplementaire",
        "Structure Crédit Supplémentaire",
        "",
        0, False, True,
    ),
]


class Command(BaseCommand):
    help = "Crée ou met à jour les offres Systeme.io dans le catalogue."

    def handle(self, *args: object, **options: object) -> None:
        created_count = 0
        updated_count = 0

        for (
            slug, name, deliverable_type, credits_per_month, is_subscription, is_extra_credit
        ) in _OFFERS:
            offer, created = Offer.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "deliverable_type": deliverable_type,
                    "credits_per_month": credits_per_month,
                    "is_subscription": is_subscription,
                    "is_extra_credit": is_extra_credit,
                    "is_active": True,
                },
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
