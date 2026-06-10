from __future__ import annotations

from typing import Any

from .models import Customer, CustomerType, Subscription, SubscriptionStatus, SubscriptionTier


class SubscriptionIngestionError(ValueError):
    pass


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
# Les slugs sont ceux configurés dans les produits Systeme.io d'Evangeline.
_TIER_SLUGS: dict[str, str] = {
    "solo": SubscriptionTier.SOLO,
    "pro": SubscriptionTier.PRO,
    "pro-plus": SubscriptionTier.PRO_PLUS,
    "pro_plus": SubscriptionTier.PRO_PLUS,
    "structure": SubscriptionTier.STRUCTURE,
}

# Événements Systeme.io qui activent un abonnement.
_ACTIVE_EVENTS = frozenset(
    {"subscription.started", "subscription.renewed", "subscription.activated"}
)
# Événements Systeme.io qui désactivent un abonnement.
_CANCELLED_EVENTS = frozenset(
    {"subscription.cancelled", "subscription.stopped", "subscription.expired"}
)


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


def sync_subscription_from_systeme_payload(payload: dict[str, Any]) -> Subscription:
    """Crée ou met à jour un abonnement B2B depuis un payload webhook Systeme.io.

    Événements supportés :
    - subscription.started / subscription.renewed → ACTIVE
    - subscription.cancelled / subscription.stopped / subscription.expired → CANCELLED

    Élève SubscriptionIngestionError si les champs obligatoires sont absents.
    """
    event_type = _lookup(payload, "event_type", "type", "event")
    systeme_sub_id = _lookup(
        payload,
        "subscription.id",
        "subscription_id",
        "id",
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

    missing = [
        field
        for field, value in (
            ("event_type", event_type),
            ("subscription_id", systeme_sub_id),
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
    return subscription
