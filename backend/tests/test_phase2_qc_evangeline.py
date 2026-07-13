"""QC Evangeline — tests des 9 fixes suite au retour du 12 juillet 2026.

Chaque test cible un symptome concret observe sur les documents pipeline :
- 6 valeurs differentes pour un meme chiffre cle => Fix #1 (memoire) + #2 (locks)
- tableaux vides, troncatures, placeholders qui fuient => Fix #3 (validation)
- listes "1. 1. 1." => Fix #4 (renumbering)
- docs de 126 pages => Fix #5 (target_words)
- sources trop anciennes => Fix #6 (freshness) via _CHARTER
- blocs analytiques fondus dans la prose => Fix #7a (parsing) + #7b (charter)
- paragraphes interchangeables => Fix #8b (charter anti-generique)
"""
from __future__ import annotations

import pytest

from generation.rendering import _md_to_html, strip_internal_markers
from generation.validation import (
    ValidationSeverity,
    detect_concatenation_bugs,
    detect_empty_tables,
    detect_placeholder_leaks,
    detect_truncation,
    has_blocking_issues,
    validate_chapter_content,
)


# --- Fix #1 : mémoire cross-chapitres --------------------------------------


def test_operational_summary_priorise_les_phrases_chiffrees() -> None:
    from generation.runner import _operational_summary

    content = (
        "Introduction generale sur le secteur qui pose le contexte. "
        "Le marche compte 1,8 million de micro-entrepreneurs actifs selon INSEE 2025. "
        "Les entreprises operant sur ce marche font face a plusieurs defis. "
        "Le CA moyen est de 32 000 euros par an d'apres URSSAF 2024. "
        "Beaucoup de generalites peu utiles pour la suite du raisonnement. "
        "Les charges sociales representent 22 % du CA au regime micro. "
    ) * 5

    summary = _operational_summary(content)

    # Les phrases chiffrees doivent etre presentes en priorite dans le resume.
    assert "1,8 million" in summary
    assert "32 000 euros" in summary
    assert "22 %" in summary
    # Et le total doit rester borne.
    assert len(summary) <= 1250


# --- Fix #2 : extraction de faits chiffrés dans CoherenceFact --------------


@pytest.mark.django_db
def test_extract_and_lock_numeric_facts_verrouille_les_chiffres() -> None:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.coherence import extract_and_lock_numeric_facts
    from generation.models import ChapterGeneration, FactKind, GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(name="EM", slug="em", deliverable_type=DeliverableType.MARKET_STUDY)
    customer = Customer.objects.create(email="c@x.com")
    order = Order.objects.create(systeme_order_id="qc_lock_1", customer=customer, offer=offer)
    job = GenerationJob.objects.create(order=order, deliverable_type=DeliverableType.MARKET_STUDY)
    chapter = ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Marche", prompt_key="em.01.marche_mondial_europeen",
        content=(
            "Le nombre de micro-entrepreneurs actifs est de 1,8 M en 2025. "
            "Le taux de croissance est de 8,5 % par an. "
            "Le CA moyen du secteur est de 300 M€."
        ),
    )

    locked = extract_and_lock_numeric_facts(chapter)

    assert len(locked) >= 2  # au moins 2 des 3 chiffres capturés
    keys = {f.key for f in locked}
    assert any("micro" in k for k in keys)
    assert all(f.kind == FactKind.MARKET_SIZE for f in locked)


@pytest.mark.django_db
def test_extract_ne_reecrase_pas_un_chiffre_deja_verrouille() -> None:
    """Le premier chapitre a mentionner un libelle fige la valeur pour la suite."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.coherence import extract_and_lock_numeric_facts
    from generation.models import ChapterGeneration, GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(name="EM", slug="em", deliverable_type=DeliverableType.MARKET_STUDY)
    customer = Customer.objects.create(email="c2@x.com")
    order = Order.objects.create(systeme_order_id="qc_lock_2", customer=customer, offer=offer)
    job = GenerationJob.objects.create(order=order, deliverable_type=DeliverableType.MARKET_STUDY)

    ch1 = ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Marche", prompt_key="em.01",
        content="Le nombre de micro-entrepreneurs actifs est de 1,8 M en 2025.",
    )
    extract_and_lock_numeric_facts(ch1)

    ch2 = ChapterGeneration.objects.create(
        job=job, chapter_number=2, chapter_title="Zone", prompt_key="em.02",
        content="Le nombre de micro-entrepreneurs actifs est de 4,4 M.",  # incoherent
    )
    # Ne doit PAS lever : on ignore silencieusement quand deja verrouille.
    extract_and_lock_numeric_facts(ch2)

    from generation.coherence import locked_facts_as_context
    dump = locked_facts_as_context(job)
    assert "1,8" in dump
    assert "4,4" not in dump  # la premiere valeur reste souveraine


# --- Fix #3 : validation post-génération -----------------------------------


def test_detect_empty_tables_signale_un_tableau_vide() -> None:
    content = (
        "Analyse des risques.\n\n"
        "| Risque | Probabilite | Impact |\n"
        "|--------|-------------|--------|\n"
        "|   —    |     —       |   —    |\n"
        "|        |             |        |\n\n"
        "Les deux risques classes CRITIQUE sont a surveiller."
    )
    issues = detect_empty_tables(content)
    assert len(issues) == 1
    assert issues[0].code == "empty_table"
    assert issues[0].severity == ValidationSeverity.ERROR


def test_detect_empty_tables_ne_signale_pas_un_tableau_rempli() -> None:
    content = (
        "| Risque | Probabilite | Impact |\n"
        "|--------|-------------|--------|\n"
        "| Change | Elevee      | Fort   |\n"
    )
    assert detect_empty_tables(content) == []


def test_detect_truncation_repere_fin_sur_asterisques() -> None:
    content = "Un contenu correct ici. Un autre element important. **"
    issues = detect_truncation(content)
    assert issues and issues[0].code == "truncated"


def test_detect_truncation_ne_signale_pas_fin_normale() -> None:
    content = "Un contenu correct qui se termine normalement."
    assert detect_truncation(content) == []


def test_detect_placeholder_leaks_reperer_prepare_une_offre() -> None:
    content = "Le prospect souscrit à un 'préparer une offre claire' au demarrage."
    issues = detect_placeholder_leaks(content)
    assert any(i.code == "leaked_prompt_snippet" for i in issues)


def test_detect_placeholder_leaks_reperer_clients_prioritaires_singulier() -> None:
    content = "Le segment constitue le clients prioritaires du projet."
    issues = detect_placeholder_leaks(content)
    assert any(i.code == "botched_substitution" for i in issues)


def test_detect_placeholder_leaks_reperer_variable_non_resolue() -> None:
    content = "Le projet cible le [SECTEUR] dans la zone [ZONE]."
    issues = detect_placeholder_leaks(content)
    codes = {i.code for i in issues}
    assert "unresolved_template_variable" in codes


def test_validate_chapter_content_combine_tout() -> None:
    content = (
        "Introduction.\n\n"
        "| A | B |\n"
        "|---|---|\n"
        "|   |   |\n\n"
        "souscrit à un 'préparer une offre claire' au chapitre suivant. **"
    )
    issues = validate_chapter_content(content)
    codes = {i.code for i in issues}
    assert "empty_table" in codes
    assert "leaked_prompt_snippet" in codes
    assert "truncated" in codes
    assert has_blocking_issues(issues)


def test_detect_concatenation_bugs() -> None:
    content = "Le CA netentre lapériode nette et le detrésorerie augmente."
    issues = detect_concatenation_bugs(content)
    assert len(issues) >= 2


# --- Fix #4 : renumérotation des listes ------------------------------------


def test_ordered_list_ne_repete_pas_le_prefixe_source() -> None:
    md = "1. Coach\n1. Web\n1. Livraison"
    html = _md_to_html(md)
    # Aucune occurrence "1. Coach" dans le HTML : c'est le <ol> qui numerote.
    assert "1. Coach" not in html
    assert "<li>Coach</li>" in html
    assert "<li>Web</li>" in html
    assert "<li>Livraison</li>" in html


# --- Fix #5 : cadre de longueur -------------------------------------------


def test_blueprints_expose_max_words() -> None:
    from generation.blueprints import MARKET_STUDY_CHAPTERS

    # Les chapitres analytiques portent un budget de mots (bp.max_words) ou,
    # pour les chapitres decoupes, via SECTION_MAX_WORDS. Seuls les chapitres
    # purement structurels (fiche projet, sources, annexe) restent a 0.
    assert any(bp.max_words > 0 for bp in MARKET_STUDY_CHAPTERS)


@pytest.mark.django_db
def test_build_chapter_prompt_injecte_cadre_editorial() -> None:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, GenerationJob
    from generation.prompts import build_chapter_prompt
    from orders.models import Order

    offer = Offer.objects.create(name="EM", slug="em3", deliverable_type=DeliverableType.MARKET_STUDY)
    customer = Customer.objects.create(email="c3@x.com")
    order = Order.objects.create(systeme_order_id="qc_len_1", customer=customer, offer=offer)
    job = GenerationJob.objects.create(order=order, deliverable_type=DeliverableType.MARKET_STUDY)
    chapter = ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Marche",
        prompt_key="em.01.marche_mondial_europeen",
    )
    prompt = build_chapter_prompt(chapter)
    assert "CONSIGNE IMPÉRATIVE DE COMPLÉTUDE ET DENSITÉ" in prompt
    assert "mots" in prompt


# --- Fix #6 : fraîcheur des sources ---------------------------------------


@pytest.mark.django_db
def test_build_chapter_prompt_injecte_date_courante() -> None:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.context import build_context
    from generation.models import ChapterGeneration, GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(name="EM", slug="em4", deliverable_type=DeliverableType.MARKET_STUDY)
    customer = Customer.objects.create(email="c4@x.com")
    order = Order.objects.create(systeme_order_id="qc_date_1", customer=customer, offer=offer)
    job = GenerationJob.objects.create(order=order, deliverable_type=DeliverableType.MARKET_STUDY)
    chapter = ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Marche", prompt_key="em.01",
    )
    context = build_context(chapter)
    assert "DATE_DU_JOUR" in context


def test_charter_impose_source_recente() -> None:
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt("etude_marche")
    assert "6 derniers mois" in prompt or "24 mois" in prompt


# --- Fix #7a : rendu des callouts -----------------------------------------


def test_callout_inline_est_rendu_en_div_stylise() -> None:
    md = "◆ Ce qu'il faut comprendre : le marche est en croissance."
    html = _md_to_html(md)
    assert "callout--understand" in html
    assert "le marche est en croissance" in html.lower() or "le marche est en croissance" in html


def test_callout_bloc_avec_marqueurs_est_rendu() -> None:
    md = (
        "[[CONSIDER]]\n"
        "Prioriser Paris et Lyon avant expansion.\n"
        "[[/CONSIDER]]"
    )
    html = _md_to_html(md)
    assert "callout--consider" in html
    assert "Paris et Lyon" in html


def test_callout_attention_est_rendu() -> None:
    md = "! Attention : la reglementation change en janvier."
    html = _md_to_html(md)
    assert "callout--attention" in html


# --- Fix #7b : la charte instruit d'emettre les marqueurs ------------------


def test_charter_mentionne_les_marqueurs_parseables() -> None:
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt("etude_marche")
    assert "[[UNDERSTAND]]" in prompt
    assert "[[CONSIDER]]" in prompt
    assert "[[ATTENTION]]" in prompt


# --- Fix #8b : la charte interdit les paragraphes génériques --------------


def test_charter_interdit_la_genericite() -> None:
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt("etude_marche")
    lower = prompt.lower()
    assert "anti-genericite" in lower or "anti-génericité" in lower or "acteur nomme" in lower


# --- Rendu HTML : les tableaux markdown deviennent de vrais <table> -------


def test_md_to_html_convertit_les_tableaux_markdown() -> None:
    md = (
        "| Nom | CA |\n"
        "|-----|----|\n"
        "| Shiva | 350 M€ |\n"
        "| O2 | 328 M€ |\n"
    )
    html = _md_to_html(md)
    assert "<table>" in html
    assert "<th>Nom</th>" in html
    assert "<td>Shiva</td>" in html


# --- Compat avec le test existant (strip_internal_markers) ----------------


def test_strip_internal_markers_reste_fonctionnel() -> None:
    raw = "Contenu.\n✅ Prompt a utiliser :\nSuite du contenu."
    assert "Prompt a utiliser" not in strip_internal_markers(raw)
