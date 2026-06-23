from __future__ import annotations

from typing import Any

from catalog.models import Offer
from customers.models import Customer

from .models import Order, OrderStatus


class OrderIngestionError(ValueError):
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


def sync_order_from_systeme_payload(payload: dict[str, Any]) -> Order:
    systeme_order_id = _lookup(payload, "order_id", "id", "sale.id", "order.id")
    email = _lookup(payload, "customer_email", "email", "customer.email", "contact.email")
    offer_slug = _lookup(payload, "offer_slug", "offer.slug", "product.slug", "tag")

    missing = [
        field
        for field, value in (
            ("order_id", systeme_order_id),
            ("customer_email", email),
            ("offer_slug", offer_slug),
        )
        if not value
    ]
    if missing:
        msg = f"Systeme.io payload missing required fields: {', '.join(missing)}"
        raise OrderIngestionError(msg)

    try:
        offer = Offer.objects.get(slug=offer_slug, is_active=True)
    except Offer.DoesNotExist as exc:
        msg = f"Unknown active offer slug: {offer_slug}"
        raise OrderIngestionError(msg) from exc

    customer, _created = Customer.objects.update_or_create(
        email=email,
        defaults={
            "first_name": _lookup(payload, "customer.first_name", "contact.first_name"),
            "last_name": _lookup(payload, "customer.last_name", "contact.last_name"),
            "company_name": _lookup(payload, "customer.company_name", "contact.company_name"),
            "systeme_contact_id": _lookup(payload, "customer.id", "contact.id"),
        },
    )

    order, _created = Order.objects.update_or_create(
        systeme_order_id=systeme_order_id,
        defaults={
            "customer": customer,
            "offer": offer,
            "status": OrderStatus.WAITING_INTAKE,
            "raw_payload": payload,
        },
    )

    # Abonnements : auto-créer N tickets de crédit (un par crédit mensuel).
    # Crédits suppl. : auto-créer 1 ticket.
    credits = offer.credits_per_month if offer.is_subscription else (1 if offer.is_extra_credit else 0)
    for n in range(1, credits + 1):
        Order.objects.get_or_create(
            systeme_order_id=f"{systeme_order_id}-t{n}",
            defaults={
                "customer": customer,
                "offer": offer,
                "parent_order": order,
                "status": OrderStatus.WAITING_INTAKE,
                "raw_payload": {},
            },
        )

    return order
