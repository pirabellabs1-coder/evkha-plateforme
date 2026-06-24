"""Phase 8 — Systeme de credits B2B (abonnements + credits supplementaires).

Tests deterministes (aucun appel reseau, stub Brevo) :
  - issue_credit_tickets : creation N tickets idempotente par mois
  - issue_and_email_credits : creation + email Brevo stub
  - sync_subscription : declenche creation tickets sur activation
  - sync_order : declenche creation tickets pour abonnement + extra credit
  - refresh_monthly_credits : cron idempotent
  - process_webhook_event (Tally) : ouvre incident si type livrable invalide
  - intake : normalisation DELIVERABLE_TYPE depuis libelle humain
  - tier slug : reconnait les slugs Systeme.io complets (abonnement-solo, etc.)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.credits import (
    current_period,
    issue_and_email_credits,
    issue_credit_tickets,
    refresh_monthly_credits_for_subscription,
    tally_links_for_period,
)
from customers.models import Customer, Subscription, SubscriptionStatus, SubscriptionTier
from customers.services import sync_subscription_from_systeme_payload
from intake.services import normalize_intake_variables
from monitoring.models import OperationalIncident
from orders.models import Order, OrderStatus
from orders.services import sync_order_from_systeme_payload

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def solo_offer() -> Offer:
    return Offer.objects.create(
        name="Abonnement Solo",
        slug="abonnement-solo",
        deliverable_type="",
        credits_per_month=2,
        is_subscription=True,
    )


@pytest.fixture()
def extra_credit_offer() -> Offer:
    return Offer.objects.create(
        name="Solo Credit Supplementaire",
        slug="solo-credit-supplementaire",
        deliverable_type="",
        credits_per_month=0,
        is_extra_credit=True,
    )


@pytest.fixture()
def b2c_offer() -> Offer:
    return Offer.objects.create(
        name="Etude de marche",
        slug="etude-de-marche",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )


@pytest.fixture()
def customer() -> Customer:
    return Customer.objects.create(email="client@example.com", first_name="Eva")


# ---------------------------------------------------------------------------
# issue_credit_tickets
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_issue_credit_tickets_creates_n_tickets(
    solo_offer: Offer, customer: Customer
) -> None:
    parent = Order.objects.create(
        customer=customer, offer=solo_offer, systeme_order_id="order-001"
    )
    tickets = issue_credit_tickets(
        customer=customer,
        offer=solo_offer,
        parent_order=parent,
        count=2,
        period="2026-06",
    )
    assert len(tickets) == 2
    assert all(t.parent_order_id == parent.id for t in tickets)
    assert all(t.period_year_month == "2026-06" for t in tickets)
    assert all(t.status == OrderStatus.WAITING_INTAKE for t in tickets)


@pytest.mark.django_db
def test_issue_credit_tickets_idempotent_per_period(
    solo_offer: Offer, customer: Customer
) -> None:
    parent = Order.objects.create(
        customer=customer, offer=solo_offer, systeme_order_id="order-002"
    )
    issue_credit_tickets(
        customer=customer, offer=solo_offer, parent_order=parent, count=2,
        period="2026-06",
    )
    # Deuxieme appel sur la meme periode -> ne cree pas de doublons
    issue_credit_tickets(
        customer=customer, offer=solo_offer, parent_order=parent, count=2,
        period="2026-06",
    )
    assert Order.objects.filter(parent_order=parent, period_year_month="2026-06").count() == 2


@pytest.mark.django_db
def test_issue_credit_tickets_separates_by_period(
    solo_offer: Offer, customer: Customer
) -> None:
    parent = Order.objects.create(
        customer=customer, offer=solo_offer, systeme_order_id="order-003"
    )
    issue_credit_tickets(
        customer=customer, offer=solo_offer, parent_order=parent, count=2,
        period="2026-06",
    )
    issue_credit_tickets(
        customer=customer, offer=solo_offer, parent_order=parent, count=2,
        period="2026-07",
    )
    assert Order.objects.filter(parent_order=parent).count() == 4


# ---------------------------------------------------------------------------
# issue_and_email_credits — incident si pas d'URL Tally configuree
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_issue_and_email_credits_opens_incident_if_no_tally_url(
    solo_offer: Offer, customer: Customer
) -> None:
    parent = Order.objects.create(
        customer=customer, offer=solo_offer, systeme_order_id="order-004"
    )
    issue_and_email_credits(
        customer=customer, offer=solo_offer, parent_order=parent, count=2,
        period="2026-06",
    )
    incidents = OperationalIncident.objects.filter(order=parent)
    assert incidents.count() == 1
    incident = incidents.first()
    assert incident is not None
    assert "Tally" in incident.title


@pytest.mark.django_db
@override_settings(
    EVKHA_TALLY_URL_MARKET_STUDY="https://tally.so/r/marketstudy",
    EVKHA_TALLY_URL_COMPETITOR_STUDY="https://tally.so/r/competitor",
    EVKHA_TALLY_URL_BUSINESS_PLAN="https://tally.so/r/bp",
    EVKHA_TALLY_URL_BUSINESS_STRATEGY="https://tally.so/r/strategy",
    EVKHA_USE_STUB_EMAIL=True,
)
def test_issue_and_email_credits_sends_email_when_configured(
    solo_offer: Offer, customer: Customer
) -> None:
    parent = Order.objects.create(
        customer=customer, offer=solo_offer, systeme_order_id="order-005"
    )
    issue_and_email_credits(
        customer=customer, offer=solo_offer, parent_order=parent, count=2,
        period="2026-06",
    )
    # Aucun incident : stub Brevo a accepte l'envoi
    assert OperationalIncident.objects.filter(order=parent).count() == 0


@pytest.mark.django_db
@override_settings(
    EVKHA_TALLY_URL_MARKET_STUDY="https://tally.so/r/marketstudy",
    EVKHA_TALLY_URL_COMPETITOR_STUDY="https://tally.so/r/competitor",
    EVKHA_TALLY_URL_BUSINESS_PLAN="https://tally.so/r/bp",
    EVKHA_TALLY_URL_BUSINESS_STRATEGY="https://tally.so/r/strategy",
)
def test_tally_links_for_subscription_lists_4_types_per_ticket(
    solo_offer: Offer, customer: Customer
) -> None:
    parent = Order.objects.create(
        customer=customer, offer=solo_offer, systeme_order_id="order-006"
    )
    issue_credit_tickets(
        customer=customer, offer=solo_offer, parent_order=parent, count=2,
        period="2026-06",
    )
    links = tally_links_for_period(parent)
    # 2 tickets x 4 types = 8 liens (le client choisit le type via le formulaire)
    assert len(links) == 8
    assert all("order_id=" in url for _label, url in links)
    assert all("deliverable_type=" in url for _label, url in links)


@pytest.mark.django_db
@override_settings(EVKHA_TALLY_URL_MARKET_STUDY="https://tally.so/r/marketstudy")
def test_tally_links_for_b2c_lists_only_fixed_type(
    b2c_offer: Offer, customer: Customer
) -> None:
    parent = Order.objects.create(
        customer=customer, offer=b2c_offer, systeme_order_id="order-007"
    )
    # B2C : 1 seul ticket, 1 seul lien (type fige sur Offer)
    issue_credit_tickets(
        customer=customer, offer=b2c_offer, parent_order=parent, count=1,
        period="2026-06",
    )
    links = tally_links_for_period(parent)
    assert len(links) == 1


# ---------------------------------------------------------------------------
# sync_order — auto-creation tickets pour abonnement + extra credit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sync_order_creates_credit_tickets_for_subscription(
    solo_offer: Offer,
) -> None:
    sync_order_from_systeme_payload(
        {
            "order_id": "order-sub-001",
            "customer_email": "newclient@example.com",
            "offer_slug": "abonnement-solo",
        }
    )
    parent = Order.objects.get(systeme_order_id="order-sub-001")
    tickets = Order.objects.filter(parent_order=parent)
    assert tickets.count() == 2
    assert all(t.period_year_month == current_period() for t in tickets)


@pytest.mark.django_db
def test_sync_order_creates_one_ticket_for_extra_credit(
    extra_credit_offer: Offer,
) -> None:
    sync_order_from_systeme_payload(
        {
            "order_id": "order-extra-001",
            "customer_email": "extraclient@example.com",
            "offer_slug": "solo-credit-supplementaire",
        }
    )
    parent = Order.objects.get(systeme_order_id="order-extra-001")
    assert Order.objects.filter(parent_order=parent).count() == 1


@pytest.mark.django_db
def test_sync_order_no_tickets_for_b2c(b2c_offer: Offer) -> None:
    sync_order_from_systeme_payload(
        {
            "order_id": "order-b2c-001",
            "customer_email": "b2c@example.com",
            "offer_slug": "etude-de-marche",
        }
    )
    parent = Order.objects.get(systeme_order_id="order-b2c-001")
    assert Order.objects.filter(parent_order=parent).count() == 0


# ---------------------------------------------------------------------------
# sync_subscription — declenche la creation des tickets sur activation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sync_subscription_triggers_credit_tickets_when_parent_order_exists(
    solo_offer: Offer,
) -> None:
    # Etape 1 : achat -> Order parent + tickets crees par sync_order
    sync_order_from_systeme_payload(
        {
            "order_id": "order-flow-001",
            "customer_email": "flow@example.com",
            "offer_slug": "abonnement-solo",
        }
    )
    # Etape 2 : webhook subscription.started
    sync_subscription_from_systeme_payload(
        {
            "event_type": "subscription.started",
            "subscription": {"id": "sub-flow-001"},
            "contact": {"email": "flow@example.com"},
            "product": {"slug": "abonnement-solo"},
        }
    )
    parent = Order.objects.get(systeme_order_id="order-flow-001")
    # Idempotent : pas de doublons malgre les 2 evenements
    assert Order.objects.filter(parent_order=parent).count() == 2


@pytest.mark.django_db
def test_sync_subscription_full_slug_resolves_to_correct_tier(
    solo_offer: Offer,
) -> None:
    sub = sync_subscription_from_systeme_payload(
        {
            "event_type": "subscription.started",
            "subscription": {"id": "sub-full-001"},
            "contact": {"email": "tier@example.com"},
            "product": {"slug": "abonnement-pro-plus"},
        }
    )
    assert sub.tier == SubscriptionTier.PRO_PLUS


# ---------------------------------------------------------------------------
# refresh_monthly_credits — cron beat
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_refresh_monthly_credits_recreates_tickets_for_new_period(
    solo_offer: Offer,
) -> None:
    sync_order_from_systeme_payload(
        {
            "order_id": "order-renew-001",
            "customer_email": "renew@example.com",
            "offer_slug": "abonnement-solo",
        }
    )
    customer = Customer.objects.get(email="renew@example.com")
    sub = Subscription.objects.create(
        customer=customer,
        tier=SubscriptionTier.SOLO,
        systeme_subscription_id="sub-renew-001",
        status=SubscriptionStatus.ACTIVE,
    )
    # Simule un second appel le mois suivant en patchant current_period
    with patch("customers.credits.current_period", return_value="2099-12"):
        refresh_monthly_credits_for_subscription(sub)

    parent = Order.objects.get(systeme_order_id="order-renew-001")
    periods = set(
        Order.objects.filter(parent_order=parent).values_list("period_year_month", flat=True)
    )
    # 2 tickets pour le mois courant + 2 tickets pour 2099-12
    assert "2099-12" in periods
    assert Order.objects.filter(parent_order=parent, period_year_month="2099-12").count() == 2


@pytest.mark.django_db
def test_refresh_monthly_credits_skips_inactive_subscription() -> None:
    customer = Customer.objects.create(email="inactive@example.com")
    sub = Subscription.objects.create(
        customer=customer,
        tier=SubscriptionTier.SOLO,
        systeme_subscription_id="sub-inactive",
        status=SubscriptionStatus.CANCELLED,
    )
    result = refresh_monthly_credits_for_subscription(sub)
    assert result is None


# ---------------------------------------------------------------------------
# Normalisation DELIVERABLE_TYPE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("market_study", "market_study"),
        ("Etude de marché", "market_study"),
        ("etude de marche", "market_study"),
        ("Business Plan", "business_plan"),
        ("BP", "business_plan"),
        ("competitor_study", "competitor_study"),
        ("Étude de la concurrence", "competitor_study"),
        ("strategie business", "business_strategy"),
    ],
)
def test_normalize_deliverable_type_from_tally_payload(raw: str, expected: str) -> None:
    payload = {
        "data": {
            "fields": [
                {"label": "deliverable_type", "value": raw},
                {"label": "SECTEUR", "value": "x"},
                {"label": "PAYS", "value": "x"},
                {"label": "PROJET", "value": "x"},
                {"label": "ZONE", "value": "x"},
            ]
        }
    }
    variables, missing = normalize_intake_variables(payload)
    assert variables["DELIVERABLE_TYPE"] == expected
    assert missing == []
