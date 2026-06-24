"""Phase 9 — Conformite 100% aux Consignes EVKHA + Note de cadrage.

Verifie :
  - Bloc 1 Consignes : strip pipeline + phrases meta + sources intermediaires
  - Bloc 3 Consignes : substitutions anglicismes + jargon, mots metier preserves
  - Bloc 5 Consignes : variables fiche projet etendues, "Fin de l'etude" rendu
  - Bloc 6 Consignes : palette officielle (#1A1A1A / #C9A227 / #FBF8EF), Calibri
  - §5 cadrage : verrouillage TCAC + taille de marche
  - §7 cadrage : adaptation geographique automatique (titre + consigne)
  - §14 cadrage : photos client BP injectees dans le rendu
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.coherence import (
    CoherenceConflictError,
    extract_and_lock_chiffres_cles,
)
from generation.geography import (
    chapter_title_em_01,
    geographic_consigne_for,
    macro_zone_for,
)
from generation.models import FactKind, GenerationJob
from generation.prompts import build_system_prompt
from generation.rendering import (
    apply_lexical_substitutions,
    extract_photos,
    render_branded_html,
    strip_intermediate_sources,
    strip_internal_markers,
)
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def market_offer() -> Offer:
    return Offer.objects.create(
        name="Etude marche",
        slug="etude-marche-conformite",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )


@pytest.fixture()
def bp_offer() -> Offer:
    return Offer.objects.create(
        name="Business plan",
        slug="bp-conformite",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )


@pytest.fixture()
def customer() -> Customer:
    return Customer.objects.create(email="conformite@example.com")


@pytest.fixture()
def bp_job_with_photos(bp_offer: Offer, customer: Customer) -> GenerationJob:
    order = Order.objects.create(
        systeme_order_id="conf-bp-001", customer=customer, offer=bp_offer
    )
    IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "BTP",
            "PAYS": "Côte d'Ivoire",
            "PROJET": "Test",
            "ZONE": "Abidjan",
            "PHOTO_1": "https://example.com/local.jpg",
            "PHOTO_2": "https://example.com/produit.jpg",
            "PHOTO_3": "https://example.com/equipe.jpg",
        },
    )
    return bootstrap_generation_job(IntakeSubmission.objects.get(order=order))


@pytest.fixture()
def em_job_ci(market_offer: Offer, customer: Customer) -> GenerationJob:
    order = Order.objects.create(
        systeme_order_id="conf-em-ci", customer=customer, offer=market_offer
    )
    IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "VTC",
            "PAYS": "Côte d'Ivoire",
            "PROJET": "Plateforme mobilite",
            "ZONE": "Abidjan",
        },
    )
    return bootstrap_generation_job(IntakeSubmission.objects.get(order=order))


# ---------------------------------------------------------------------------
# BLOC 1 — Strip pipeline + phrases meta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "Étape 1.1 : Analyse",
        "Etape 2.3",
        "Point de contrôle",
        "Validation finale",
        "Cas 1",
        "Livrable automatisé",
        "Méthodologie EVKHA",
        "Pipeline",
        "Version CSV exportée",
        "CONTEXTE À RÉINJECTER",
        "La liste ci-dessous présente",
        "Cette lecture prépare le chapitre suivant",
        "L'objectif est de structurer",
        "Tableau de conformité",
    ],
)
def test_strip_internal_markers_removes_pipeline_and_meta(line: str) -> None:
    raw = f"Texte avant.\n{line}\nTexte après."
    cleaned = strip_internal_markers(raw)
    assert line not in cleaned
    assert "Texte avant." in cleaned
    assert "Texte après." in cleaned


def test_strip_intermediate_sources_removes_internal_sources_block() -> None:
    raw = (
        "Analyse du marché.\n\n"
        "## Sources\n"
        "- INSEE 2025\n"
        "- BPI France\n\n"
        "## Suite de l'analyse\n"
        "Texte suivant."
    )
    cleaned = strip_intermediate_sources(raw)
    assert "INSEE" not in cleaned
    assert "BPI France" not in cleaned
    assert "Suite de l'analyse" in cleaned
    assert "Texte suivant." in cleaned


# ---------------------------------------------------------------------------
# BLOC 3 — Substitutions lexicales + preservation mots metier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected_substring"),
    [
        ("Le blended learning gagne", "format mixte (e-learning + présentiel)"),
        ("Identifier les pain points", "vraies difficultés"),
        ("Notre pitch convainc", "présentation"),
        ("Le ticket moyen progresse", "prix moyen par client"),
        ("Onboarding client", "accueil des nouveaux"),
        ("Solvabiliser la demande", "financer"),
        ("Une dynamique porteuse", "tendance favorable"),
        ("La polarisation du marché", "séparation"),
        ("Approche actionnable", "applicable"),
        ("Il convient de noter que X", "À noter"),
    ],
)
def test_apply_lexical_substitutions(source: str, expected_substring: str) -> None:
    assert expected_substring in apply_lexical_substitutions(source)


@pytest.mark.parametrize(
    "metier_term",
    ["ASN", "ANDPC", "DPC", "Qualiopi", "MERM", "IBODE", "radioprotection"],
)
def test_apply_lexical_substitutions_preserves_metier_words(metier_term: str) -> None:
    source = f"Le centre est certifié {metier_term} depuis 2023."
    result = apply_lexical_substitutions(source)
    assert metier_term in result


# ---------------------------------------------------------------------------
# BLOC 6 — Palette officielle + Calibri + filet or
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_render_branded_html_uses_official_palette(em_job_ci: GenerationJob) -> None:
    html = render_branded_html(em_job_ci)
    # Defaults palette officielle (fallback si pas de COULEUR_PRINCIPALE)
    assert "#1A1A1A" in html
    assert "#C9A227" in html
    assert "#FBF8EF" in html
    assert "#5A5A5A" in html


@pytest.mark.django_db
def test_render_branded_html_uses_calibri(em_job_ci: GenerationJob) -> None:
    html = render_branded_html(em_job_ci)
    assert "Calibri" in html


@pytest.mark.django_db
def test_render_branded_html_has_header_and_footer(em_job_ci: GenerationJob) -> None:
    html = render_branded_html(em_job_ci)
    assert "EVKHA · " in html  # header pages internes
    assert "Document stratégique confidentiel" in html  # footer


# ---------------------------------------------------------------------------
# BLOC 5 — "Fin de l'etude" + variables fiche projet etendues
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_render_branded_html_includes_fin_de_letude(em_job_ci: GenerationJob) -> None:
    html = render_branded_html(em_job_ci)
    assert "Fin de l'étude" in html


def test_intake_optional_variables_includes_fiche_projet_complete() -> None:
    from intake.services import OPTIONAL_VARIABLES
    for var in ("POSITIONNEMENT", "CLIENTELE_CIBLE", "MODELE_ECONOMIQUE"):
        assert var in OPTIONAL_VARIABLES


def test_intake_optional_variables_includes_photos_bp() -> None:
    from intake.services import OPTIONAL_VARIABLES
    for var in ("PHOTO_1", "PHOTO_2", "PHOTO_3"):
        assert var in OPTIONAL_VARIABLES


# ---------------------------------------------------------------------------
# §5 cadrage — Verrouillage TCAC + taille de marche
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_extract_and_lock_chiffres_cles_locks_tcac(
    em_job_ci: GenerationJob,
) -> None:
    extract_and_lock_chiffres_cles(em_job_ci, 1, "Le marché affiche un TCAC de 7,5%.")
    fact = em_job_ci.coherence_facts.get(kind=FactKind.GROWTH_RATE, key="tcac")
    assert fact.value == "7.5%"


@pytest.mark.django_db
def test_extract_and_lock_chiffres_cles_raises_on_conflict(
    em_job_ci: GenerationJob,
) -> None:
    extract_and_lock_chiffres_cles(em_job_ci, 1, "TCAC de 5%")
    with pytest.raises(CoherenceConflictError):
        extract_and_lock_chiffres_cles(em_job_ci, 2, "TCAC de 8%")


@pytest.mark.django_db
def test_extract_and_lock_chiffres_cles_locks_market_size(
    em_job_ci: GenerationJob,
) -> None:
    extract_and_lock_chiffres_cles(
        em_job_ci, 1, "Le marché mondial pèse 12 milliards en 2025."
    )
    fact = em_job_ci.coherence_facts.get(kind=FactKind.MARKET_SIZE, key="taille_marche")
    assert "12" in fact.value
    assert "milliards" in fact.value.lower()


# ---------------------------------------------------------------------------
# §7 cadrage — Adaptation geographique automatique
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("country", "expected_zone"),
    [
        ("Côte d'Ivoire", "africain"),
        ("Cote d'Ivoire", "africain"),
        ("Sénégal", "africain"),
        ("France", "europeen"),
        ("Belgique", "europeen"),
        ("Maroc", "maghrebin"),
        ("Canada", "nord-americain"),
        ("Pays Inconnu", "international"),
    ],
)
def test_macro_zone_for_country(country: str, expected_zone: str) -> None:
    zone = macro_zone_for(country)
    assert expected_zone in zone


def test_chapter_title_em_01_adapts_to_country() -> None:
    assert "africain" in chapter_title_em_01("Côte d'Ivoire")
    assert "europeen" in chapter_title_em_01("France")
    assert "maghrebin" in chapter_title_em_01("Maroc")


def test_geographic_consigne_blocks_irrelevant_zones() -> None:
    consigne = geographic_consigne_for("Côte d'Ivoire")
    assert "Cote d'Ivoire" in consigne or "Côte d'Ivoire" in consigne
    assert "africain" in consigne
    assert "europeen" in consigne.lower()  # phrase d'interdiction


def test_build_system_prompt_includes_geographic_adaptation() -> None:
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="Côte d'Ivoire")
    assert "ADAPTATION GEOGRAPHIQUE" in prompt
    assert "africain" in prompt


def test_build_system_prompt_no_geographic_section_when_no_country() -> None:
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)
    assert "ADAPTATION GEOGRAPHIQUE" not in prompt


@pytest.mark.django_db
def test_render_branded_html_overrides_chapter_1_title_for_ci(
    em_job_ci: GenerationJob,
) -> None:
    # Force le chapitre 1 a etre DONE pour qu'il apparaisse dans le rendu
    chapter_1 = em_job_ci.chapters.get(chapter_number=1)
    chapter_1.content = "Analyse du marche."
    chapter_1.status = "done"
    chapter_1.save()
    html = render_branded_html(em_job_ci)
    assert "marche mondial et africain" in html.lower() or "marché mondial et africain" in html


# ---------------------------------------------------------------------------
# §14 cadrage — Photos client BP
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_extract_photos_returns_bp_photos(bp_job_with_photos: GenerationJob) -> None:
    photos = extract_photos(bp_job_with_photos)
    assert len(photos) == 3
    assert "local.jpg" in photos[0]
    assert "produit.jpg" in photos[1]
    assert "equipe.jpg" in photos[2]


@pytest.mark.django_db
def test_extract_photos_empty_for_non_bp(em_job_ci: GenerationJob) -> None:
    photos = extract_photos(em_job_ci)
    assert photos == []


@pytest.mark.django_db
def test_render_branded_html_includes_photos_for_bp(
    bp_job_with_photos: GenerationJob,
) -> None:
    html = render_branded_html(bp_job_with_photos)
    assert "local.jpg" in html
    assert "Illustrations du projet" in html
