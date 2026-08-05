from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.blueprints import BUSINESS_PLAN_CHAPTERS, BUSINESS_STRATEGY_CHAPTERS, SectionKind
from generation.models import ChapterStatus, JobStatus
from generation.rendering import render_client_document
from generation.runner import run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order


@pytest.fixture
def bp_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Business Plan",
        slug="business-plan",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email="client-bp@example.com")
    order = Order.objects.create(systeme_order_id="order_bp_1", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "restauration rapide halal",
            "PAYS": "France",
            "ZONE": "Ile-de-France",
            "PROJET": "chaine snacks halal premium",
            "FORME_JURIDIQUE": "SAS",
            "CAPITAL_INITIAL": "30000 EUR",
            "MODELE_REVENUS": "vente directe + catering",
            "EQUIPE": "2 associes, profils complementaires cuisine et gestion",
        },
    )


@pytest.fixture
def str_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Strategie Business",
        slug="strategie-business",
        deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )
    customer = Customer.objects.create(email="client-str@example.com")
    order = Order.objects.create(systeme_order_id="order_str_1", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "e-commerce mode africaine",
            "PAYS": "Benin",
            "ZONE": "Cotonou",
            "PROJET": "marketplace mode africaine premium",
            "OBJECTIF_STRATEGIQUE": "devenir le leader regional en 3 ans",
            "HORIZON_PLANIFICATION": "3 ans",
        },
    )


# --- Blueprint tests -------------------------------------------------------


def test_business_plan_blueprint_structure() -> None:
    # Document « Systeme EVKHA — Business Plans — V1 FINALE » (05/08/2026) :
    # fiche projet + ses vingt chapitres + sources = 22 unites.
    #
    # Les fusions 14+15 et 16+17 de juillet 2026 ont ete DEFAITES : le document
    # redetaille ces chapitres separement, et la cliente a confirme le retour
    # aux vingt chapitres. Le chapitre 18, Politique de remuneration, est ajoute
    # — il n'existait dans aucun des vingt prompts precedents.
    assert len(BUSINESS_PLAN_CHAPTERS) == 22
    assert BUSINESS_PLAN_CHAPTERS[0].prompt_key == "bp.00.fiche_projet"
    assert BUSINESS_PLAN_CHAPTERS[0].section_kind == SectionKind.OPENING
    assert BUSINESS_PLAN_CHAPTERS[-1].section_kind == SectionKind.SOURCES
    assert BUSINESS_PLAN_CHAPTERS[-1].prompt_key == "bp.21.sources"
    keys = [c.prompt_key for c in BUSINESS_PLAN_CHAPTERS]
    # Les deux chapitres rendus a leur autonomie.
    assert "bp.14.investissements" in keys
    assert "bp.15.plan_financement" in keys
    # Le chapitre qui manquait.
    assert "bp.18.remuneration" in keys
    # Les dispatchers des fusions doivent avoir disparu avec elles : les
    # laisser aurait maintenu deux cles vers un chapitre qui n'existe plus.
    assert "bp.14.besoin_financement" not in keys
    assert "bp.15.previsionnel_tresorerie" not in keys
    assert "bp.09.modele_bmc" in keys
    assert "bp.20.annexes" in keys


def test_business_strategy_blueprint_structure() -> None:
    # Document « SYSTEME EVKHA — STRATEGIES BUSINESS AUTOMATISEES » (96 pages).
    # Son sommaire officiel — « STRUCTURE OFFICIELLE V1 RECOMMANDEE », p. 31 —
    # donne : INTRODUCTION GENERALE (ch. 0), sept PARTIES portant les chapitres
    # 1 a 16, puis CONCLUSION STRATEGIQUE. Soit 18 unites de contenu.
    #
    # Le depot reserve l'index 0 a la fiche projet et decale donc les chapitres
    # du document de +1. Total : fiche projet + 18 unites + annexe + sources = 21.
    #
    # Le 20 d'avant tenait a une omission : la CONCLUSION STRATEGIQUE GENERALE
    # (p. 93-96) n'existait dans aucun des vingt prompts. Le document lui consacre
    # une section entiere au format d'un chapitre — objectif, role, questions,
    # structure interne obligatoire en quatre parties, controle qualite — et le
    # chapitre precedent doit s'ouvrir sur elle. Le livrable se terminait donc sur
    # une feuille de route, une annexe et une bibliographie : aucune lecture
    # finale de cabinet.
    assert len(BUSINESS_STRATEGY_CHAPTERS) == 21
    assert BUSINESS_STRATEGY_CHAPTERS[0].prompt_key == "str.00.fiche_projet"
    assert BUSINESS_STRATEGY_CHAPTERS[0].section_kind == SectionKind.OPENING
    assert BUSINESS_STRATEGY_CHAPTERS[-1].section_kind == SectionKind.SOURCES
    keys = [c.prompt_key for c in BUSINESS_STRATEGY_CHAPTERS]
    assert "str.07.verticales_strategiques" in keys
    assert "str.14.rentabilite_modele" in keys
    assert "str.17.feuille_route" in keys
    # Le chapitre qui manquait.
    assert "str.18.conclusion" in keys
    # Decales par son insertion. Les anciennes cles doivent avoir DISPARU : les
    # laisser vivre aurait maintenu deux cles vers un meme chapitre, et la
    # migration 0013 qui renomme l'existant n'aurait plus de cible unique.
    assert "str.19.annexe_brief" in keys
    assert "str.20.sources" in keys
    assert "str.18.annexe_brief" not in keys
    assert "str.19.sources" not in keys


# --- Bootstrap tests -------------------------------------------------------


@pytest.mark.django_db
def test_bootstrap_bp_job_creates_all_sections(bp_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(bp_submission)

    assert job.deliverable_type == DeliverableType.BUSINESS_PLAN
    assert job.chapters.count() == 22
    assert list(job.chapters.values_list("chapter_number", flat=True)) == list(range(0, 22))


@pytest.mark.django_db
def test_bootstrap_str_job_creates_all_sections(str_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(str_submission)

    assert job.deliverable_type == DeliverableType.BUSINESS_STRATEGY
    assert job.chapters.count() == 21
    assert list(job.chapters.values_list("chapter_number", flat=True)) == list(range(0, 21))


# --- Generation tests -------------------------------------------------------


@pytest.mark.django_db
def test_run_bp_job_completes_and_renders(bp_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(bp_submission)

    run_generation_job(job, client=StubClaudeClient())
    job.refresh_from_db()

    assert job.status == JobStatus.DONE
    assert job.chapters.filter(status=ChapterStatus.DONE).count() == 22
    assert job.total_cost_eur <= job.budget_eur

    document = render_client_document(job)
    assert document.title == "Business plan"
    assert document.sections[0].number == 0  # fiche projet
    markdown = document.to_markdown()
    assert "# Business plan" in markdown


@pytest.mark.django_db
def test_run_str_job_completes_and_renders(str_submission: IntakeSubmission) -> None:
    job = bootstrap_generation_job(str_submission)

    run_generation_job(job, client=StubClaudeClient())
    job.refresh_from_db()

    assert job.status == JobStatus.DONE
    # 21 depuis l'ajout de la conclusion stratégique (05/08/2026) : le document
    # la place au sommaire après le chapitre 16 et lui consacre une section
    # entière, mais elle n'existait dans aucun des vingt prompts du dépôt.
    assert job.chapters.filter(status=ChapterStatus.DONE).count() == 21
    assert job.total_cost_eur <= job.budget_eur

    document = render_client_document(job)
    assert document.title == "Stratégie business"
    markdown = document.to_markdown()
    assert "# Stratégie business" in markdown


@pytest.mark.django_db
def test_bp_coherence_seeds_forme_juridique_and_capital(bp_submission: IntakeSubmission) -> None:
    from generation.coherence import locked_facts_as_context

    job = bootstrap_generation_job(bp_submission)
    run_generation_job(job, client=StubClaudeClient())

    facts = locked_facts_as_context(job)
    assert "forme_juridique = SAS" in facts
    assert "capital_initial = 30000 EUR" in facts
    # France -> EUR
    assert "currency = EUR" in facts
