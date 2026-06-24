from __future__ import annotations

from celery import shared_task

from .credits import refresh_monthly_credits_for_subscription
from .models import Subscription, SubscriptionStatus


@shared_task(name="customers.refresh_monthly_credits")  # type: ignore[untyped-decorator]
def refresh_monthly_credits() -> dict[str, int]:
    """Cron horaire : recree les tickets B2B du mois pour chaque abonnement actif.

    Idempotent grace a Order.period_year_month. Le 1er du mois, les nouveaux tickets
    sont crees et l'email envoye. Les autres jours, ne fait rien (les tickets du mois
    existent deja).
    """
    refreshed = 0
    skipped = 0
    for subscription in Subscription.objects.filter(status=SubscriptionStatus.ACTIVE):
        result = refresh_monthly_credits_for_subscription(subscription)
        if result is None:
            skipped += 1
        else:
            refreshed += 1
    return {"refreshed": refreshed, "skipped": skipped}
