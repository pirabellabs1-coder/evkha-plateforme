"""Service de gestion des credits B2B (abonnements + credits supplementaires).

Cree les Orders 'ticket' (un par credit), envoie un email Brevo avec les liens
Tally personnalises, et garantit l'idempotence par mois.
"""
from __future__ import annotations

from html import escape

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from catalog.models import Offer
from customers.models import Customer, Subscription, SubscriptionStatus
from integrations.brevo import get_transactional_email_client
from monitoring.models import IncidentSeverity, OperationalIncident
from orders.models import Order, OrderStatus

_TALLY_URL_SETTINGS = {
    "market_study": "EVKHA_TALLY_URL_MARKET_STUDY",
    "competitor_study": "EVKHA_TALLY_URL_COMPETITOR_STUDY",
    "business_plan": "EVKHA_TALLY_URL_BUSINESS_PLAN",
    "business_strategy": "EVKHA_TALLY_URL_BUSINESS_STRATEGY",
}

_DELIVERABLE_LABELS = {
    "market_study": "Etude de marche",
    "competitor_study": "Etude de la concurrence",
    "business_plan": "Business plan",
    "business_strategy": "Strategie business",
}


def current_period() -> str:
    """Mois en cours au format YYYY-MM, pour l'idempotency key des tickets."""
    now = timezone.now()
    return f"{now.year:04d}-{now.month:02d}"


def tally_links_for_period(parent_order: Order) -> list[tuple[str, str]]:
    """Retourne [(label, url), ...] des liens Tally pour les tickets du parent_order.

    Un lien par ticket, avec l'order_id du ticket en query string. Pour les abonnements
    (deliverable_type=null cote Offer), on liste les 4 formulaires : le client choisit.
    Pour un B2C, on renvoie le seul lien correspondant au deliverable_type fige.
    """
    base = getattr(settings, "EVKHA_BASE_URL", "")
    tickets = list(parent_order.credit_tickets.order_by("created_at"))
    if not tickets:
        return []

    links: list[tuple[str, str]] = []
    fixed_type = parent_order.offer.deliverable_type
    for ticket in tickets:
        if fixed_type:
            # B2C : un seul livrable fige
            url = _build_tally_url(fixed_type, ticket.systeme_order_id, base)
            if url:
                links.append((_DELIVERABLE_LABELS.get(fixed_type, fixed_type), url))
        else:
            # B2B generique : 4 liens, client choisit dans le formulaire
            for d_type, label in _DELIVERABLE_LABELS.items():
                url = _build_tally_url(d_type, ticket.systeme_order_id, base)
                if url:
                    links.append((f"{label} (credit {ticket.systeme_order_id})", url))
    return links


def _build_tally_url(deliverable_type: str, order_id: str, base_url: str) -> str:
    setting_name = _TALLY_URL_SETTINGS.get(deliverable_type, "")
    if not setting_name:
        return ""
    template = str(getattr(settings, setting_name, "") or "")
    if not template:
        return ""
    sep = "&" if "?" in template else "?"
    # On passe deliverable_type dans l'URL pour que Tally remplisse automatiquement
    # le champ cache de ce nom (aucune valeur par defaut a configurer cote Tally).
    return f"{template}{sep}order_id={order_id}&deliverable_type={deliverable_type}"


@transaction.atomic
def issue_credit_tickets(
    *,
    customer: Customer,
    offer: Offer,
    parent_order: Order,
    count: int,
    period: str,
) -> list[Order]:
    """Cree N tickets de credit pour un (customer, offer, parent_order, period).

    Idempotent : si des tickets existent deja pour ce (parent_order, period),
    on les retourne sans en creer de nouveaux.
    """
    existing = list(
        Order.objects.filter(parent_order=parent_order, period_year_month=period).order_by(
            "created_at"
        )
    )
    if len(existing) >= count:
        return existing[:count]

    tickets = list(existing)
    next_index = len(existing) + 1
    while len(tickets) < count:
        ticket, _ = Order.objects.get_or_create(
            systeme_order_id=f"{parent_order.systeme_order_id}-{period}-t{next_index}",
            defaults={
                "customer": customer,
                "offer": offer,
                "parent_order": parent_order,
                "period_year_month": period,
                "status": OrderStatus.WAITING_INTAKE,
                "raw_payload": {},
            },
        )
        tickets.append(ticket)
        next_index += 1
    return tickets


def send_credit_email(
    *,
    customer: Customer,
    parent_order: Order,
    tickets: list[Order],
    period: str,
) -> None:
    """Envoie un email Brevo avec un lien Tally par ticket.

    Echec d'envoi -> incident HIGH ; les tickets restent valides en base.
    """
    links = tally_links_for_period(parent_order)
    if not links:
        OperationalIncident.objects.create(
            title="Aucun lien Tally configure pour envoyer les credits",
            severity=IncidentSeverity.HIGH,
            order=parent_order,
            details={
                "offer_slug": parent_order.offer.slug,
                "deliverable_type": parent_order.offer.deliverable_type or "generique",
                "period": period,
                "ticket_count": len(tickets),
                "hint": "Configurer EVKHA_TALLY_URL_* dans settings/.env",
            },
        )
        return

    if not customer.email:
        OperationalIncident.objects.create(
            title="Email client manquant pour l'envoi des credits",
            severity=IncidentSeverity.HIGH,
            order=parent_order,
            details={"order_id": str(parent_order.id), "period": period},
        )
        return

    nom = escape(customer.first_name or customer.company_name or "")
    offre = escape(parent_order.offer.name)
    items = "".join(
        f'<li style="margin:8px 0"><a href="{escape(url)}">{escape(label)}</a></li>'
        for label, url in links
    )
    is_subscription = parent_order.offer.is_subscription
    intro = (
        f"<p>Bonjour {nom},</p>"
        f"<p>Voici vos liens pour utiliser vos credits de l'abonnement "
        f"<strong>{offre}</strong> ({len(tickets)} credit{'s' if len(tickets) > 1 else ''} "
        f"disponible{'s' if len(tickets) > 1 else ''} ce mois-ci).</p>"
        if is_subscription
        else f"<p>Bonjour {nom},</p>"
        f"<p>Voici votre lien pour utiliser votre credit supplementaire "
        f"<strong>{offre}</strong>.</p>"
    )
    html = (
        f"{intro}"
        f"<ul>{items}</ul>"
        f"<p>Chaque lien correspond a un credit utilisable une seule fois. "
        f"Une fois le formulaire envoye, la generation de votre livrable commence "
        f"automatiquement.</p>"
        f"<p>L'equipe EVKHA</p>"
    )
    subject = (
        f"Vos credits EVKHA — {parent_order.offer.name}"
        if is_subscription
        else f"Votre credit supplementaire EVKHA — {parent_order.offer.name}"
    )

    try:
        client = get_transactional_email_client()
        client.send_delivery_email(
            recipient_email=customer.email,
            subject=subject,
            html_body=html,
            attachments=(),
        )
    except Exception as exc:  # noqa: BLE001 - tout echec d'envoi est un incident
        OperationalIncident.objects.create(
            title=f"Echec envoi email credits ({customer.email})",
            severity=IncidentSeverity.HIGH,
            order=parent_order,
            details={"error": str(exc), "period": period, "ticket_count": len(tickets)},
        )


def issue_and_email_credits(
    *,
    customer: Customer,
    offer: Offer,
    parent_order: Order,
    count: int,
    period: str | None = None,
) -> list[Order]:
    """Cree N tickets pour la periode et envoie l'email avec les liens Tally.

    Wrapper pratique appele depuis les services subscription/order.
    """
    period = period or current_period()
    tickets = issue_credit_tickets(
        customer=customer,
        offer=offer,
        parent_order=parent_order,
        count=count,
        period=period,
    )
    if tickets:
        send_credit_email(
            customer=customer,
            parent_order=parent_order,
            tickets=tickets,
            period=period,
        )
    return tickets


def refresh_monthly_credits_for_subscription(subscription: Subscription) -> list[Order] | None:
    """Pour un abonnement actif, recree les tickets du mois courant s'ils manquent.

    Idempotent : appele en boucle (cron horaire) sans creer de doublons.
    Retourne None si l'abonnement ne donne droit a aucun credit ou si aucun parent
    Order n'existe encore (le premier paiement n'est pas encore arrive).
    """
    if subscription.status != SubscriptionStatus.ACTIVE:
        return None

    # On considere l'Order le plus recent du client pour cette offre comme "parent"
    # de la periode courante. Si Systeme.io envoie un nouvel Order pour le renouvellement,
    # c'est lui ; sinon l'Order initial reste reference.
    # Seul un Order "racine" (parent_order NULL) peut etre le parent des tickets.
    # Sinon on risque de prendre un ticket comme parent et creer une chaine infinie.
    parent_order = (
        Order.objects.filter(
            customer=subscription.customer,
            offer__is_subscription=True,
            parent_order__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if parent_order is None or not parent_order.offer.is_subscription:
        return None

    credits = parent_order.offer.credits_per_month
    if credits <= 0:
        return None

    return issue_and_email_credits(
        customer=subscription.customer,
        offer=parent_order.offer,
        parent_order=parent_order,
        count=credits,
    )
