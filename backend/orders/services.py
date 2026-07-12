from __future__ import annotations

from typing import Any

from catalog.models import Offer
from customers.models import Customer

from .models import Order, OrderStatus


class OrderIngestionError(ValueError):
    pass


class UnknownOfferSlugError(OrderIngestionError):
    """Slug produit absent du catalogue EVKHA.

    Leve quand le webhook global Systeme.io transmet une vente d'un
    produit non-EVKHA (formation, etude prete, etc.). L'event est marque
    SKIPPED — pas d'incident, pas de retry. Comportement normal.
    """


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


def _candidate_names_from_payload(payload: dict[str, Any]) -> list[str]:
    """Retourne les noms candidats pour identifier l'offre depuis le payload SALE_NEW.

    Par ordre de priorite :
    1. physicalProduct.name (nom du produit numerique dans Systeme.io)
    2. funnelStep.name (nom de la page de paiement)
    3. funnelStep.funnel.name (nom du tunnel)
    4. pricePlan.innerName (nom interne du plan tarifaire)

    Chacun est stocke dans Offer.systeme_product_name. Le premier match gagne.
    """
    names: list[str] = []
    resources = ((payload.get("orderItem") or {}).get("resources") or [])
    for resource in resources:
        if isinstance(resource, dict):
            name = ((resource.get("physicalProduct") or {}).get("name") or "").strip()
            if name and name not in names:
                names.append(name)
    for path in ("funnelStep.name", "funnelStep.funnel.name", "pricePlan.innerName"):
        val = _lookup(payload, path).strip()
        if val and val not in names:
            names.append(val)
    return names


def _offer_from_candidate_names(names: list[str]) -> Offer | None:
    """Recherche une offre active par correspondance exacte (insensible a la casse)
    sur Offer.systeme_product_name, en testant chaque nom candidat dans l'ordre.
    """
    for name in names:
        offer = Offer.objects.filter(
            systeme_product_name__iexact=name, is_active=True
        ).first()
        if offer:
            return offer
    return None


def sync_order_from_systeme_payload(payload: dict[str, Any]) -> Order:
    systeme_order_id = _lookup(payload, "order_id", "id", "sale.id", "order.id")
    email = _lookup(payload, "customer_email", "email", "customer.email", "contact.email")
    offer_slug = _lookup(payload, "offer_slug", "offer.slug", "product.slug", "tag")

    missing = [
        field
        for field, value in (
            ("order_id", systeme_order_id),
            ("customer_email", email),
        )
        if not value
    ]
    if missing:
        msg = f"Systeme.io payload missing required fields: {', '.join(missing)}"
        raise OrderIngestionError(msg)

    # Résolution de l'offre : priorité au slug URL (automations par produit),
    # fallback sur physicalProduct.name du webhook global SALE_NEW.
    offer: Offer | None = None
    if offer_slug:
        try:
            offer = Offer.objects.get(slug=offer_slug, is_active=True)
        except Offer.DoesNotExist as exc:
            raise UnknownOfferSlugError(f"Unknown active offer slug: {offer_slug}") from exc
    else:
        candidates = _candidate_names_from_payload(payload)
        offer = _offer_from_candidate_names(candidates)
        if offer is None:
            raise UnknownOfferSlugError(
                f"No active offer matched. Candidate names from payload: {candidates}. "
                "Renseigner Offer.systeme_product_name dans Django admin "
                "(copier l'un des noms candidats ci-dessus)."
            )

    customer, _created = Customer.objects.update_or_create(
        email=email,
        defaults={
            "first_name": _lookup(
                payload,
                "customer.first_name", "contact.first_name",
                "customer.fields.first_name",
            ),
            "last_name": _lookup(
                payload,
                "customer.last_name", "contact.last_name",
                "customer.fields.surname",
            ),
            "company_name": _lookup(
                payload,
                "customer.company_name", "contact.company_name",
                "customer.fields.company_name",
            ),
            "systeme_contact_id": _lookup(
                payload, "customer.id", "contact.id", "customer.contactId",
            ),
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

    # Import paresseux pour eviter cycle orders <-> customers.
    from customers.credits import issue_and_email_credits  # noqa: PLC0415
    if offer.is_subscription and offer.credits_per_month > 0:
        issue_and_email_credits(
            customer=customer,
            offer=offer,
            parent_order=order,
            count=offer.credits_per_month,
        )
    else:
        # B2C achat unique ET credits supplementaires : 1 ticket + email Tally.
        issue_and_email_credits(
            customer=customer,
            offer=offer,
            parent_order=order,
            count=1,
        )

    return order
