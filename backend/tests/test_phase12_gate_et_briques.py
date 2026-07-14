"""Phase 12 — Briques structurelles du brief client (juillet 2026) + audit.

Couvre :
- Brique 1 : etat chiffre client verrouille (provenance CLIENT, priorite absolue)
- Brique 2 : hierarchie des sources dans la charte
- Brique 3 : gate de livraison bloquant (contamination, coherence chiffree,
  completude verticales, troncature) + integration tasks.py
- Correctifs audit : fuite des labels internes, encadre ACTION, em-dash des
  titres preserve, couts exacts (retry + QA IA), limite de pages, fiche projet.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.coherence import seed_locked_facts_from_variables, upsert_locked_fact
from generation.gate import run_delivery_gate
from generation.models import (
    ChapterStatus,
    FactKind,
    FactProvenance,
    GenerationJob,
    JobStatus,
    QAStatus,
)
from generation.rendering import (
    _md_to_html,
    normalize_callout_markers,
    strip_callout_markers,
    strip_internal_label_tokens,
)
from generation.runner import _strip_ai_tell_dashes, run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import ClaudeResult, StubClaudeClient
from monitoring.models import IncidentSeverity, OperationalIncident
from orders.models import Order


@pytest.fixture
def bp_submission() -> IntakeSubmission:
    """Business plan avec etat chiffre client complet (cas SYNAPSES du brief)."""
    offer = Offer.objects.create(
        name="Business Plan",
        slug="business-plan",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email="synapses@example.com")
    order = Order.objects.create(systeme_order_id="order_bp_1", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "coworking",
            "PAYS": "France",
            "ZONE": "Annecy",
            "PROJET": "tiers-lieu hybride SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "EMPRUNT": "920 000 €",
            "TAUX_OCCUPATION": "55 % An1 vers 85 % An5",
            "VERTICALES": "coworking / self-storage / hébergement de serveurs / "
            "activités sportives douces",
        },
    )


def _job_with_content(
    submission: IntakeSubmission, content_by_number: dict[int, str]
) -> GenerationJob:
    """Bootstrap un job puis force le contenu de chapitres cibles en DONE."""
    job = bootstrap_generation_job(submission)
    variables = submission.normalized_variables
    seed_locked_facts_from_variables(job, variables)
    for chapter in job.chapters.all():
        body = content_by_number.get(
            chapter.chapter_number,
            "Analyse détaillée du projet, chiffrée et argumentée sur la zone cible. "
            "Cette section couvre coworking, self-storage, hébergement de serveurs "
            "et activités sportives douces avec des données locales précises.",
        )
        chapter.content = body
        chapter.status = ChapterStatus.DONE
        chapter.save(update_fields=["content", "status"])
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])
    return job


# ── Brique 1 : provenance des faits ─────────────────────────────────────────


@pytest.mark.django_db
def test_seed_verrouille_etat_chiffre_client_en_provenance_client(
    bp_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(bp_submission)
    seed_locked_facts_from_variables(job, bp_submission.normalized_variables)

    facts = {f.key: f for f in job.coherence_facts.all()}
    assert facts["investissement_total"].value == "1 250 000 €"
    assert facts["investissement_total"].provenance == FactProvenance.CLIENT
    assert facts["emprunt"].provenance == FactProvenance.CLIENT
    assert facts["verticales"].provenance == FactProvenance.CLIENT


@pytest.mark.django_db
def test_fait_client_jamais_ecrase_par_valeur_generee(
    bp_submission: IntakeSubmission,
) -> None:
    """Le 34% hallucine ne peut plus ecraser une donnee du brief."""
    job = bootstrap_generation_job(bp_submission)
    seed_locked_facts_from_variables(job, bp_submission.normalized_variables)

    fact = upsert_locked_fact(
        job=job,
        kind=FactKind.ASSUMPTION,
        key="emprunt",
        value="300 000 €",
        source_chapter_number=15,
        provenance=FactProvenance.GENERATED,
    )
    assert fact.value == "920 000 €"  # brief conserve
    assert fact.provenance == FactProvenance.CLIENT
    # Ecart avec un fait client = incident HIGH (repris par le gate)
    incident = OperationalIncident.objects.get(title__startswith="Incoh. donnee")
    assert incident.severity == IncidentSeverity.HIGH


@pytest.mark.django_db
def test_fait_client_remplace_fait_genere_existant(
    bp_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(bp_submission)
    upsert_locked_fact(
        job=job, kind=FactKind.ASSUMPTION, key="apport", value="100 000 €",
        provenance=FactProvenance.GENERATED,
    )
    fact = upsert_locked_fact(
        job=job, kind=FactKind.ASSUMPTION, key="apport", value="330 000 €",
        provenance=FactProvenance.CLIENT,
    )
    assert fact.value == "330 000 €"
    assert fact.provenance == FactProvenance.CLIENT


# ── Brique 2 : charte / hierarchie des sources ───────────────────────────────


def test_charter_impose_hierarchie_des_sources() -> None:
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt(DeliverableType.BUSINESS_PLAN)
    assert "HIERARCHIE DES SOURCES" in prompt
    assert "priment" in prompt
    assert "fait \nverrouille" not in prompt  # sanity
    assert "verticale" in prompt.lower()


def test_charter_interdit_les_sources_inventees() -> None:
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)
    assert "inventer une source" in prompt
    assert "estimation argumentee EXPLICITEMENT presentee comme telle" in prompt


def test_charter_regles_acronymes_et_tcac_retenu() -> None:
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)
    assert "ACRONYMES" in prompt
    assert "TCAC" in prompt
    assert "moyenne finale" in prompt


def test_charter_mentionne_le_marqueur_action() -> None:
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)
    assert "[[ACTION]]" in prompt


def test_charter_em_dash_exception_titres() -> None:
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)
    assert "X.Y — Titre" in prompt


# ── Brique 3 : gate de livraison ─────────────────────────────────────────────


@pytest.mark.django_db
def test_gate_passe_sur_document_sain(bp_submission: IntakeSubmission) -> None:
    job = _job_with_content(bp_submission, {})
    report = run_delivery_gate(job)
    assert report.passed, report.as_details()


@pytest.mark.django_db
def test_gate_bloque_la_fuite_faits_verrouilles(bp_submission: IntakeSubmission) -> None:
    """Cas reel du brief : 'en parfaite coherence avec les FAITS_VERROUILLES'.

    Le Rendering Engine neutralise la fuite (substitution naturelle) : le
    document nettoye ne contient plus le token, donc le gate PASSE. Mais un
    token non couvert par la substitution (TODO) reste bloquant.
    """
    job = _job_with_content(
        bp_submission,
        {15: "Le résultat net est en parfaite cohérence avec les FAITS_VERROUILLES. "
             "Analyse complète du prévisionnel sur la zone, coworking, self-storage, "
             "hébergement de serveurs et activités sportives douces inclus."},
    )
    report = run_delivery_gate(job)
    # La fuite est corrigee par le scrub -> pas de blocage sur ce token
    assert all(f.check != "contamination" for f in report.failures)

    job2_offer = Offer.objects.create(
        name="BP 2", slug="bp-2", deliverable_type=DeliverableType.BUSINESS_PLAN
    )
    customer = Customer.objects.get(email="synapses@example.com")
    order2 = Order.objects.create(
        systeme_order_id="order_bp_2", customer=customer, offer=job2_offer
    )
    submission2 = IntakeSubmission.objects.create(
        order=order2,
        status=IntakeStatus.NORMALIZED,
        normalized_variables=bp_submission.normalized_variables,
    )
    job2 = _job_with_content(
        submission2,
        {15: "Section à compléter TODO avant livraison. Analyse coworking, "
             "self-storage, hébergement de serveurs, activités sportives douces."},
    )
    report2 = run_delivery_gate(job2)
    assert not report2.passed
    assert any(f.check == "contamination" for f in report2.failures)


@pytest.mark.django_db
def test_gate_bloque_incoherence_chiffree_vs_brief(bp_submission: IntakeSubmission) -> None:
    """Cas reel du brief : emprunt 920 000 € remplace par 300 000 € (÷3)."""
    job = _job_with_content(
        bp_submission,
        {14: "Le financement repose sur un emprunt de 300 000 € sur 7 ans. "
             "Le projet couvre coworking, self-storage, hébergement de serveurs "
             "et activités sportives douces sur la zone d'Annecy."},
    )
    report = run_delivery_gate(job)
    assert not report.passed
    assert any(
        f.check == "coherence_chiffree" and "emprunt" in f.detail for f in report.failures
    )


@pytest.mark.django_db
def test_gate_accepte_trajectoire_dans_fourchette_client(
    bp_submission: IntakeSubmission,
) -> None:
    """Brief multi-annees (55% -> 85%) : une valeur intermediaire est valide."""
    job = _job_with_content(
        bp_submission,
        {14: "Le taux d'occupation de 70 % en année 3 reste conforme à la "
             "trajectoire du porteur. Coworking, self-storage, hébergement de "
             "serveurs et activités sportives douces contribuent à la montée."},
    )
    report = run_delivery_gate(job)
    assert all(f.check != "coherence_chiffree" for f in report.failures), report.as_details()


@pytest.mark.django_db
def test_gate_bloque_taux_hors_fourchette(bp_submission: IntakeSubmission) -> None:
    """Cas reel du brief : '62 % moyenne sectorielle' substitue a la trajectoire."""
    job = _job_with_content(
        bp_submission,
        {14: "Nous retenons un taux d'occupation de 42 % conforme à la moyenne "
             "sectorielle. Coworking, self-storage, hébergement de serveurs et "
             "activités sportives douces sont analysés."},
    )
    report = run_delivery_gate(job)
    assert not report.passed
    assert any(f.check == "coherence_chiffree" for f in report.failures)


@pytest.mark.django_db
def test_gate_bloque_verticale_effacee(bp_submission: IntakeSubmission) -> None:
    """Cas reel du brief : self-storage / serveurs / sport purement effaces."""
    generic = (
        "Le coworking générique répond à la demande locale avec une offre "
        "de bureaux flexibles et de salles de réunion sur Annecy."
    )
    job = _job_with_content(
        bp_submission, {n: generic for n in range(0, 20)}
    )
    report = run_delivery_gate(job)
    assert not report.passed
    missing = [f.detail for f in report.failures if f.check == "verticales"]
    assert any("self-storage" in d for d in missing)
    assert any("serveurs" in d for d in missing)


@pytest.mark.django_db
def test_gate_bloque_troncature(bp_submission: IntakeSubmission) -> None:
    """Cas reel du brief : chapitre 18 tronque en pleine phrase."""
    job = _job_with_content(
        bp_submission,
        {16: "L'analyse des risques montre que le projet coworking, self-storage, "
             "hébergement de serveurs et activités sportives douces dépend de"},
    )
    report = run_delivery_gate(job)
    assert not report.passed
    assert any(f.check == "troncature" for f in report.failures)


@pytest.mark.django_db
def test_task_bloque_la_livraison_si_gate_echoue(
    bp_submission: IntakeSubmission, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Integration tasks.py : gate KO -> qa BLOCKED + incident + PAS d'email."""
    from delivery.models import DeliveryBatch
    from generation import tasks as generation_tasks
    from generation.gate import GateFailure, GateReport

    job = bootstrap_generation_job(bp_submission)
    run_generation_job(job, client=StubClaudeClient())

    monkeypatch.setattr(
        generation_tasks, "run_generation_job", lambda j, **kw: j
    )

    def _failing_gate(_job: object) -> GateReport:
        return GateReport(
            passed=False,
            failures=(GateFailure(check="contamination", detail="TOKEN test"),),
        )

    import generation.gate as gate_module
    monkeypatch.setattr(gate_module, "run_delivery_gate", _failing_gate)

    generation_tasks.run_generation_job_task(str(job.id))
    job.refresh_from_db()

    assert job.qa_status == QAStatus.BLOCKED
    assert OperationalIncident.objects.filter(
        title__startswith="Gate qualité", job=job
    ).exists()
    assert not DeliveryBatch.objects.filter(order=job.order).exists()


@pytest.mark.django_db
def test_task_livre_si_gate_passe() -> None:
    """Brief sans etat chiffre ni verticales : le contenu stub passe le gate."""
    from generation.tasks import run_generation_job_task

    offer = Offer.objects.create(
        name="EM simple", slug="em-simple", deliverable_type=DeliverableType.MARKET_STUDY
    )
    customer = Customer.objects.create(email="simple@example.com")
    order = Order.objects.create(
        systeme_order_id="order_em_simple", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "beaute", "PAYS": "Benin", "ZONE": "Cotonou", "PROJET": "concept store",
        },
    )
    job = bootstrap_generation_job(submission)
    run_generation_job(job, client=StubClaudeClient())
    run_generation_job_task(str(job.id))
    job.refresh_from_db()
    assert job.qa_status != QAStatus.BLOCKED


# ── Contamination : scrub des labels internes ────────────────────────────────


def test_strip_internal_label_tokens_forme_parenthesee() -> None:
    raw = "le résultat net inscrit dans le prévisionnel de référence (FAITS_VERROUILLES) correspond"
    out = strip_internal_label_tokens(raw)
    assert "FAITS_VERROUILLES" not in out
    assert "prévisionnel de référence" in out


def test_strip_internal_label_tokens_forme_nue_sans_doublon_article() -> None:
    raw = "en parfaite cohérence avec les FAITS_VERROUILLES."
    out = strip_internal_label_tokens(raw)
    assert "FAITS_VERROUILLES" not in out
    assert "les les" not in out
    assert "données de référence du dossier" in out


def test_validation_detecte_label_interne() -> None:
    from generation.validation import detect_placeholder_leaks

    issues = detect_placeholder_leaks("conforme aux FAITS_VERROUILLES du dossier")
    assert any(i.code == "leaked_internal_label" for i in issues)


# ── Encadre ACTION (4e style, Bloc 4 Consignes) ─────────────────────────────


def test_callout_action_bloc_est_rendu() -> None:
    html = _md_to_html("[[ACTION]]\nMois 1 : valider 10 prospects.\n[[/ACTION]]")
    assert "callout--action" in html
    assert "Action concrète" in html


def test_callout_action_inline_est_rendu() -> None:
    html = _md_to_html("✓ Action concrète : appeler 5 clients cette semaine.")
    assert "callout--action" in html


def test_marqueurs_colles_sont_normalises_puis_rendus() -> None:
    raw = "Constat.[[UNDERSTAND]]Le marché croît.[[/UNDERSTAND]]Suite."
    html = _md_to_html(normalize_callout_markers(raw))
    assert "callout--understand" in html
    assert "[[" not in strip_callout_markers(html)


def test_template_definit_le_style_action() -> None:
    from pathlib import Path

    template = Path("backend/generation/templates/generation/document.html").read_text(
        encoding="utf-8"
    )
    assert "callout--action" in template
    # Le correctif tableaux (juillet 2026) ne doit plus etre ecrase par un
    # second bloc CSS duplique.
    assert template.count(".chapter__body table {") == 1


# ── Em-dash : titres preserves, prose nettoyee ──────────────────────────────


def test_em_dash_conserve_dans_les_titres() -> None:
    content = "### 3.1 — Segmentation du marché\nLe marché — en croissance — progresse."
    out = _strip_ai_tell_dashes(content)
    assert "3.1 — Segmentation" in out
    assert "marché, en croissance, progresse" in out


# ── Couts exacts : retry + QA IA comptabilises ──────────────────────────────


class _RetryThenGoodClient:
    """1er appel : tableau vide (defaut bloquant) ; 2e appel : contenu valide."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *, system: str, prompt: str, max_tokens: int = 8192,
                 model: str | None = None) -> ClaudeResult:
        self.calls += 1
        if self.calls == 1:
            content = "| A | B |\n|---|---|\n| — | — |\n| — | — |"
        else:
            content = ("Analyse substantielle. " * 60).strip() + "."
        return ClaudeResult(
            content=content, input_tokens=100, output_tokens=50, model="claude-sonnet"
        )


@pytest.mark.django_db
def test_retry_validation_accumule_les_tokens(bp_submission: IntakeSubmission) -> None:
    from generation.runner import _generate_chapter

    job = bootstrap_generation_job(bp_submission)
    chapter = job.chapters.get(chapter_number=3)  # non chunke
    client = _RetryThenGoodClient()
    _generate_chapter(job, chapter, client=client, system_prompt="sys")
    chapter.refresh_from_db()

    assert client.calls == 2
    assert chapter.input_tokens == 200   # 100 + 100 (les 2 appels comptent)
    assert chapter.output_tokens == 100  # 50 + 50


@pytest.mark.django_db
def test_qa_ai_repair_est_comptabilise_et_contextualise(
    bp_submission: IntakeSubmission,
) -> None:
    from generation.qa import ConditionViolation, ai_repair_chapter

    content, tin, tout = ai_repair_chapter(
        "contenu court",
        "Chapitre test",
        "chapter",
        [ConditionViolation("below_min_length", "critical", "50 mots < 400")],
        client=object(),  # pas un ClaudeClient -> aucun appel, tokens nuls
        project_context="CONTEXTE PROJET : secteur coworking",
    )
    assert (content, tin, tout) == ("contenu court", 0, 0)


# ── Limite de pages (§2 cadrage : 80/45 max) ────────────────────────────────


@pytest.mark.django_db
def test_depassement_pages_ouvre_un_incident(bp_submission: IntakeSubmission) -> None:
    from documents.services import _check_page_limit

    job = bootstrap_generation_job(bp_submission)
    _check_page_limit(job, page_count=95)  # BP : limite 80
    incident = OperationalIncident.objects.get(title__startswith="Limite de pages")
    assert incident.details["pages"] == 95
    assert incident.details["limite"] == 80


@pytest.mark.django_db
def test_pages_sous_la_limite_aucun_incident(bp_submission: IntakeSubmission) -> None:
    from documents.services import _check_page_limit

    job = bootstrap_generation_job(bp_submission)
    _check_page_limit(job, page_count=76)
    assert not OperationalIncident.objects.filter(
        title__startswith="Limite de pages"
    ).exists()


# ── Fiche projet : ligne d'en-tete explicite ────────────────────────────────


def test_fiche_projet_prompts_ont_une_ligne_entete() -> None:
    from generation.prompt_library import prompt_instruction

    for key in ("em.00.fiche_projet", "ec.00.fiche_projet",
                "bp.00.fiche_projet", "str.00.fiche_projet"):
        instruction = prompt_instruction(key)
        assert "| Élément | Détail |" in instruction, key


# ── Intake : etat chiffre client + verticales ───────────────────────────────


def test_intake_expose_les_variables_etat_chiffre() -> None:
    from intake.services import _ALIASES, OPTIONAL_VARIABLES

    for var in ("INVESTISSEMENT_TOTAL", "EMPRUNT", "APPORT", "TAUX_OCCUPATION",
                "SEUIL_RENTABILITE", "VERTICALES"):
        assert var in OPTIONAL_VARIABLES
    assert _ALIASES["investissement total"] == "INVESTISSEMENT_TOTAL"
    assert _ALIASES["verticales d'activite"] == "VERTICALES"
