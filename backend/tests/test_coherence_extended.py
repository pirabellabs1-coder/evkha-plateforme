"""Verrouillage etendu des chiffres cles projet (retour client juillet 2026).

Le moteur de coherence detectait uniquement TCAC et taille de marche. Le
client a signale des glissements silencieux d'un chapitre a l'autre sur les
chiffres financiers du projet (CA cible, seuil de rentabilite, panier moyen,
marge brute). Ces tests verrouillent le comportement etendu.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.coherence import (
    extract_and_lock_chiffres_cles,
    locked_facts_as_context,
)
from generation.models import GenerationJob
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order


@pytest.fixture
def bp_job() -> GenerationJob:
    offer = Offer.objects.create(
        name="BP test", slug="bp-test",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email="a@b.c")
    order = Order.objects.create(systeme_order_id="o1", customer=customer, offer=offer)
    IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "x", "PAYS": "FR"},
    )
    return GenerationJob.objects.create(order=order, deliverable_type=DeliverableType.BUSINESS_PLAN)


@pytest.mark.django_db
def test_ca_cible_is_locked(bp_job: GenerationJob) -> None:
    content = "Le chiffre d'affaires cible de 285 000 EUR sera atteint en annee 2."
    extract_and_lock_chiffres_cles(bp_job, 5, content)
    facts = locked_facts_as_context(bp_job)
    assert "ca_cible_eur = 285000 EUR" in facts


@pytest.mark.django_db
def test_seuil_rentabilite_is_locked(bp_job: GenerationJob) -> None:
    content = "Le seuil de rentabilite se situe a 118 387 euros de chiffre d'affaires."
    extract_and_lock_chiffres_cles(bp_job, 15, content)
    facts = locked_facts_as_context(bp_job)
    assert "seuil_rentabilite_eur = 118387 EUR" in facts


@pytest.mark.django_db
def test_point_mort_is_also_captured(bp_job: GenerationJob) -> None:
    content = "Le point mort est de 45 000 EUR annuels."
    extract_and_lock_chiffres_cles(bp_job, 15, content)
    facts = locked_facts_as_context(bp_job)
    assert "seuil_rentabilite_eur = 45000 EUR" in facts


@pytest.mark.django_db
def test_panier_moyen_is_locked(bp_job: GenerationJob) -> None:
    content = "Le panier moyen de 87,50 EUR est superieur a la mediane du secteur."
    extract_and_lock_chiffres_cles(bp_job, 8, content)
    facts = locked_facts_as_context(bp_job)
    assert "panier_moyen_eur = 87.50 EUR" in facts


@pytest.mark.django_db
def test_marge_brute_is_locked(bp_job: GenerationJob) -> None:
    content = "En annee 1, le taux de marge brute est de 92 % (charges variables 8 %)."
    extract_and_lock_chiffres_cles(bp_job, 15, content)
    facts = locked_facts_as_context(bp_job)
    assert "marge_brute = 92%" in facts


@pytest.mark.django_db
def test_first_mention_wins_across_chapters(bp_job: GenerationJob) -> None:
    # Chapitre 5 fixe le CA cible a 285 000. Chapitre 10 essaie de le
    # remonter a 287 500 — la valeur verrouillee (premiere mention) doit
    # etre conservee et un incident MEDIUM cree en arriere-plan.
    extract_and_lock_chiffres_cles(bp_job, 5, "Le CA cible de 285 000 EUR est prudent.")
    extract_and_lock_chiffres_cles(
        bp_job, 10, "Le chiffre d'affaires cible de 287 500 EUR reste realiste."
    )
    facts = locked_facts_as_context(bp_job)
    # La premiere mention (285 000) fait foi
    assert "ca_cible_eur = 285000 EUR" in facts
    assert "287500" not in facts


@pytest.mark.django_db
def test_close_values_do_not_trigger_incident(bp_job: GenerationJob) -> None:
    # Tolerance 20 % : 285 000 vs 287 500 = 0,88 % d'ecart -> pas d'incident,
    # meme ordre de grandeur. La valeur d'origine est conservee.
    from monitoring.models import OperationalIncident
    extract_and_lock_chiffres_cles(bp_job, 5, "Le CA cible de 285 000 EUR est valide.")
    extract_and_lock_chiffres_cles(bp_job, 12, "Le CA cible de 287 500 EUR est confirme.")
    assert not OperationalIncident.objects.filter(job=bp_job).exists()
