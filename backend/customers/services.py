from __future__ import annotations

from typing import Any

from .models import Customer, CustomerType, Subscription, SubscriptionStatus, SubscriptionTier


class SubscriptionIngestionError(ValueError):
    pass


class NotASubscriptionError(SubscriptionIngestionError):
    """Payload sans subscription_id — achat unique routé par le webhook COMMANDE."""


def _lookup(payload: dict[str, Any], *paths: str) -> str:
    for path in paths:
        current: Any = payload
        for part in path.split("."):
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(part)
        if current not in (None, ""):
            return str(current)
    return ""


# Mapping slugs Systeme.io → SubscriptionTier.
# Couvre les variantes de slug que Systeme.io peut envoyer.
_TIER_SLUGS: dict[str, str] = {
    # slugs courts
    "solo": SubscriptionTier.SOLO,
    "pro": SubscriptionTier.PRO,
    "pro-plus": SubscriptionTier.PRO_PLUS,
    "pro_plus": SubscriptionTier.PRO_PLUS,
    "structure": SubscriptionTier.STRUCTURE,
    # slugs Systeme.io complets (alignes sur catalog/management/seed_offers.py)
    "abonnement-solo": SubscriptionTier.SOLO,
    "abonnement-pro": SubscriptionTier.PRO,
    "abonnement-pro-plus": SubscriptionTier.PRO_PLUS,
    "abonnement-structure": SubscriptionTier.STRUCTURE,
}

# SALE_NEW est l'event_type du webhook global Systeme.io pour tout achat (y compris abo).
_ACTIVE_EVENTS = frozenset(
    {
        "subscription.started",
        "subscription.renewed",
        "subscription.activated",
        "SALE_NEW",
    }
)
# Événements Systeme.io qui désactivent un abonnement.
_CANCELLED_EVENTS = frozenset(
    {"subscription.cancelled", "subscription.stopped", "subscription.expired"}
)

# Mapping SubscriptionTier → slug d'offre catalogue EVKHA.
_TIER_TO_OFFER_SLUG: dict[str, str] = {
    SubscriptionTier.SOLO: "abonnement-solo",
    SubscriptionTier.PRO: "abonnement-pro",
    SubscriptionTier.PRO_PLUS: "abonnement-pro-plus",
    SubscriptionTier.STRUCTURE: "abonnement-structure",
}


def _tier_from_slug(slug: str) -> str:
    """Résout un slug produit Systeme.io vers un SubscriptionTier.

    Retourne SOLO par défaut si le slug est inconnu (plutôt que lever une erreur)
    pour ne pas bloquer l'accès d'un client réel sur un problème de configuration.
    """
    return _TIER_SLUGS.get(slug.lower().strip(), SubscriptionTier.SOLO)


def _status_from_event(event_type: str) -> str | None:
    if event_type in _ACTIVE_EVENTS:
        return SubscriptionStatus.ACTIVE
    if event_type in _CANCELLED_EVENTS:
        return SubscriptionStatus.CANCELLED
    return None


def _create_subscription_order_and_credits(
    customer: Customer,
    subscription: Subscription,
    systeme_sub_id: str,
    payload: dict[str, Any],
) -> None:
    """Crée (ou réutilise) le parent Order pour l'abonnement et émet les crédits du mois.

    Cherche d'abord un Order racine existant pour ce client+offre (créé par le webhook
    COMMANDE si l'offre avait un systeme_product_name). Sinon, crée un Order dédié
    préfixé "sub-" pour éviter toute collision avec les order_ids B2C.

    Idempotent : issue_and_email_credits ne recréé pas les tickets du mois déjà émis.
    """
    from catalog.models import Offer  # noqa: PLC0415
    from orders.models import Order, OrderStatus  # noqa: PLC0415

    from .credits import issue_and_email_credits  # noqa: PLC0415

    offer_slug = _TIER_TO_OFFER_SLUG.get(subscription.tier)
    if not offer_slug:
        return
    offer = Offer.objects.filter(slug=offer_slug, is_active=True).first()
    if not offer or offer.credits_per_month <= 0:
        return

    # Réutiliser un Order racine déjà créé par le webhook COMMANDE, le cas échéant.
    # Sinon, créer l'Order dédié à cet abonnement (préfixe "sub-" anti-collision).
    parent_order = (
        Order.objects.filter(
            customer=customer,
            offer=offer,
            parent_order__isnull=True,
        )
        .order_by("created_at")
        .first()
    )
    if parent_order is None:
        parent_order, _ = Order.objects.get_or_create(
            systeme_order_id=f"sub-{systeme_sub_id}",
            defaults={
                "customer": customer,
                "offer": offer,
                "status": OrderStatus.WAITING_INTAKE,
                "raw_payload": payload,
            },
        )
    issue_and_email_credits(
        customer=customer,
        offer=offer,
        parent_order=parent_order,
        count=offer.credits_per_month,
    )


def sync_subscription_from_systeme_payload(payload: dict[str, Any]) -> Subscription:
    """Crée ou met à jour un abonnement B2B depuis un payload webhook Systeme.io.

    Événements supportés :
    - SALE_NEW / subscription.started / subscription.renewed → ACTIVE
    - subscription.cancelled / subscription.stopped / subscription.expired → CANCELLED

    Élève NotASubscriptionError si le payload n'a pas de subscription_id
    (achat unique B2C → webhook COMMANDE s'en charge → SKIPPED silencieux).
    Élève SubscriptionIngestionError si les champs obligatoires sont absents.
    """
    event_type = _lookup(payload, "event_type", "type", "event")
    # Pas de fallback "id" : un achat unique n'a pas de subscription_id.
    systeme_sub_id = _lookup(
        payload,
        "subscription.id",
        "subscription_id",
    )
    email = _lookup(
        payload,
        "contact.email",
        "customer.email",
        "customer_email",
        "email",
    )
    tier_slug = _lookup(
        payload,
        "product.slug",
        "subscription.plan_slug",
        "plan_slug",
        "plan",
        "tag",
    )

    if not systeme_sub_id:
        raise NotASubscriptionError(
            "Payload sans subscription_id — achat unique, ignore par le webhook ABONNEMENT."
        )

    missing = [
        field
        for field, value in (
            ("event_type", event_type),
            ("email", email),
        )
        if not value
    ]
    if missing:
        msg = f"Systeme.io subscription payload missing required fields: {', '.join(missing)}"
        raise SubscriptionIngestionError(msg)

    new_status = _status_from_event(event_type)
    if new_status is None:
        msg = f"Unhandled subscription event_type: {event_type!r}"
        raise SubscriptionIngestionError(msg)

    # Crée ou récupère le client ; le type passe en B2B dès qu'il a un abonnement.
    customer, _ = Customer.objects.update_or_create(
        email=email,
        defaults={
            "customer_type": CustomerType.B2B,
            "first_name": _lookup(payload, "contact.first_name", "customer.first_name"),
            "last_name": _lookup(payload, "contact.last_name", "customer.last_name"),
            "company_name": _lookup(payload, "contact.company_name", "customer.company_name"),
            "systeme_contact_id": _lookup(payload, "contact.id", "customer.id"),
        },
    )

    subscription, _ = Subscription.objects.update_or_create(
        systeme_subscription_id=systeme_sub_id,
        defaults={
            "customer": customer,
            "tier": _tier_from_slug(tier_slug),
            "status": new_status,
            "raw_payload": payload,
        },
    )

    # Sur activation OU renouvellement : créer les tickets du mois et envoyer l'email.
    if new_status == SubscriptionStatus.ACTIVE:
        _create_subscription_order_and_credits(customer, subscription, systeme_sub_id, payload)

    return subscription
