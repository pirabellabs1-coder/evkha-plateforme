"""Tests Phase 11 — visuels de respiration entre chapitres.

Injectes cote template (generation/visuals.py) : ne consomment aucun token
Claude, se produisent aux memes chapitres pour chaque livrable et sont
inseres apres le chapitre indique dans le rendu HTML final.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.rendering import render_branded_html
from generation.services import bootstrap_generation_job
from generation.visuals import render_visual_break, visual_breaks_html_for
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order


def test_visual_breaks_registered_for_each_deliverable_type() -> None:
    for dtype in (
        DeliverableType.MARKET_STUDY,
        DeliverableType.COMPETITOR_STUDY,
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.BUSINESS_STRATEGY,
    ):
        breaks = visual_breaks_html_for(dtype)
        assert breaks, f"Aucun visuel de respiration configure pour {dtype}"
        for chapter_number, html in breaks.items():
            assert isinstance(chapter_number, int)
            assert '<div class="evkha-visual' in html


def test_render_visual_break_variants_produce_expected_markers() -> None:
    from generation.visuals import VisualBreak, VisualItem

    cards = VisualBreak(
        after_chapter_number=0, variant="icon_cards",
        title="T", subtitle="S",
        items=(VisualItem("target", "A", "desc"),),
    )
    podium = VisualBreak(
        after_chapter_number=0, variant="podium",
        title="T", subtitle="S",
        items=(
            VisualItem("spark", "L", "d"),
            VisualItem("growth", "C", "d"),
            VisualItem("shield", "R", "d"),
        ),
    )
    chrono = VisualBreak(
        after_chapter_number=0, variant="chronology",
        title="T", subtitle="S",
        items=(VisualItem("clock", "Etape 1", "d"),),
    )

    assert "evkha-visual--cards" in render_visual_break(cards)
    assert "evkha-visual--podium" in render_visual_break(podium)
    assert "evkha-visual__pillar--center" in render_visual_break(podium)
    assert "evkha-visual--chrono" in render_visual_break(chrono)


@pytest.fixture
def market_job() -> object:
    offer = Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche-visuals",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="visuals@example.com")
    order = Order.objects.create(systeme_order_id="order_visuals", customer=customer, offer=offer)
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "beaute",
            "PAYS": "France",
            "ZONE": "Paris",
            "PROJET": "concept store",
        },
    )
    return bootstrap_generation_job(submission)


@pytest.mark.django_db
def test_render_branded_html_injects_visual_breaks_between_chapters(market_job: object) -> None:
    from generation.models import ChapterStatus

    for chapter in market_job.chapters.all():  # type: ignore[attr-defined]
        chapter.status = ChapterStatus.DONE
        chapter.content = f"Contenu chapitre {chapter.chapter_number}."
        chapter.save(update_fields=["status", "content", "updated_at"])

    html = render_branded_html(market_job)  # type: ignore[arg-type]
    assert "evkha-visual--cards" in html
    assert "Ce que cette étude va explorer" in html
