"""Phase 14 — Boucle d'auto-correction (loopy) + recherche web gratuite.

Couvre :
- Recherche gratuite DuckDuckGo par défaut (aucune clé, Tavily jamais implicite)
- Client DuckDuckGo (bibliothèque mockée)
- Boucle d'auto-correction : régénère les chapitres fautifs puis repasse le gate
- Bornes : rondes plafonnées, échec doc-level non régénéré, budget respecté
- Note corrective injectée dans le prompt de régénération
"""
from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.coherence import seed_locked_facts_from_variables
from generation.gate import GateFailure, GateReport
from generation.models import ChapterGeneration, ChapterStatus, GenerationJob, JobStatus
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import ClaudeResult
from orders.models import Order

# ── Recherche gratuite : fabrique ────────────────────────────────────────────


def test_get_search_client_duckduckgo_par_defaut_hors_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from django.conf import settings

    from integrations.search import DuckDuckGoWebSearchClient, get_search_client

    monkeypatch.setattr(settings, "EVKHA_USE_STUB_SEARCH", False)
    monkeypatch.setattr(settings, "EVKHA_SEARCH_PROVIDER", "duckduckgo")
    assert isinstance(get_search_client(), DuckDuckGoWebSearchClient)


def test_tavily_jamais_implicite_sans_cle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Même en demandant Tavily, sans clé payante on retombe sur le gratuit."""
    from django.conf import settings

    from integrations.search import DuckDuckGoWebSearchClient, get_search_client

    monkeypatch.setattr(settings, "EVKHA_USE_STUB_SEARCH", False)
    monkeypatch.setattr(settings, "EVKHA_SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert isinstance(get_search_client(), DuckDuckGoWebSearchClient)


def test_duckduckgo_client_mappe_les_resultats(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    from integrations.search import DuckDuckGoWebSearchClient

    # Faux module `ddgs` avec une classe DDGS.text(...)
    fake_mod = types.ModuleType("ddgs")

    class _DDGS:
        def text(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
            return [
                {"title": "INSEE coworking", "href": "https://insee.fr/a",
                 "body": "Le marché pèse 1,2 Md€."},
                {"title": "Sans lien", "href": "", "body": "ignoré"},
            ]

    fake_mod.DDGS = _DDGS  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ddgs", fake_mod)

    resp = DuckDuckGoWebSearchClient().search(query="coworking France", max_results=5)
    assert len(resp.results) == 1
    assert resp.results[0].url == "https://insee.fr/a"
    assert resp.results[0].score == 0.0  # DDG ne fournit pas de score


# ── Boucle d'auto-correction ─────────────────────────────────────────────────


@pytest.fixture
def bp_job(db: None) -> GenerationJob:
    offer = Offer.objects.create(
        name="BP", slug="bp-corr", deliverable_type=DeliverableType.BUSINESS_PLAN
    )
    customer = Customer.objects.create(email="corr@example.com")
    order = Order.objects.create(systeme_order_id="order_corr_1", customer=customer, offer=offer)
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES", "EMPRUNT": "920 000 €",
            # Etat chiffre complet : sans lui, le gate bloque desormais le BP
            # sur `etat_chiffre_client` avant meme d'examiner la coherence.
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
    )
    job = bootstrap_generation_job(submission)
    seed_locked_facts_from_variables(job, submission.normalized_variables)
    return job


def _mark_all_done(job: GenerationJob, body: str) -> None:
    for c in job.chapters.all():
        c.content, c.status = body, ChapterStatus.DONE
        c.save(update_fields=["content", "status"])
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])


@pytest.mark.django_db
def test_boucle_regenere_le_chapitre_fautif(
    bp_job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un chapitre avec emprunt erroné est régénéré avec la bonne valeur -> gate OK."""
    from generation import correction as correction_mod

    # Le check `chapitre_avorte` planche a 30 % du max_words du blueprint.
    # On repete le paragraphe pour tenir cette cible sans changer le sens du
    # test (verifier la valeur d'emprunt citee, pas la longueur).
    # La remuneration dirigeante est integree au corpus pour que le check
    # `strategy_business_plan_remuneration_dirigeant` (phase 33) passe :
    # un vrai BP l'a toujours, la fixture doit donc la representer.
    good_body = (
        "Le financement repose sur un emprunt de 920 000 € sur 7 ans, "
        "conforme au plan du porteur, avec une analyse complete et argumentee. "
        "Remuneration dirigeante de 30 000 EUR annuelle prevue au previsionnel. "
    ) * 60
    bad_body = (
        "Le financement repose sur un emprunt de 300 000 € sur 7 ans, "
        "chiffre recalcule, avec une analyse complete et argumentee du projet. "
        "Remuneration dirigeante de 30 000 EUR annuelle prevue au previsionnel. "
    ) * 60
    _mark_all_done(bp_job, good_body)
    # Chapitre 14 fautif (emprunt ÷3)
    ch14 = bp_job.chapters.get(chapter_number=14)
    ch14.content = bad_body
    ch14.save(update_fields=["content"])

    captured: dict[str, Any] = {}

    def fake_regenerate(
        job: GenerationJob,
        chapter: ChapterGeneration,
        *,
        corrective_note: str,
        client: object = None,
    ) -> None:
        captured["note"] = corrective_note
        captured["num"] = chapter.chapter_number
        chapter.content = good_body  # la régénération corrige
        chapter.save(update_fields=["content"])

    from generation import runner as runner_mod
    monkeypatch.setattr(runner_mod, "regenerate_chapter", fake_regenerate)

    report = correction_mod.run_correction_loop(bp_job, client=object(), max_rounds=1)
    assert report.passed, report.as_details()
    assert captured["num"] == 14
    assert "emprunt" in captured["note"].lower()


@pytest.mark.django_db
def test_boucle_bornee_ne_boucle_pas_indefiniment(
    bp_job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si la régénération ne corrige rien, la boucle s'arrête après max_rounds."""
    from generation import correction as correction_mod
    from generation import runner as runner_mod

    bad_body = (
        "Le financement repose sur un emprunt de 300 000 € sur 7 ans, "
        "chiffre recalculé localement, analyse complète du projet SYNAPSES."
    )
    _mark_all_done(bp_job, bad_body)

    calls: dict[str, int] = {"n": 0}

    def fake_regenerate(
        job: GenerationJob,
        chapter: ChapterGeneration,
        *,
        corrective_note: str,
        client: object = None,
    ) -> None:
        calls["n"] += 1  # ne corrige jamais

    monkeypatch.setattr(runner_mod, "regenerate_chapter", fake_regenerate)

    report = correction_mod.run_correction_loop(bp_job, client=object(), max_rounds=2)
    assert not report.passed
    # 2 rondes max, régénération appelée au moins une fois mais borné
    assert calls["n"] >= 1


@pytest.mark.django_db
def test_boucle_ignore_echec_niveau_document(
    bp_job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Une verticale manquante (doc-level) ne déclenche pas de régénération ciblée."""
    from generation import correction as correction_mod
    from generation import runner as runner_mod

    calls: dict[str, int] = {"n": 0}

    def fake_regenerate(
        job: GenerationJob,
        chapter: ChapterGeneration,
        *,
        corrective_note: str,
        client: object = None,
    ) -> None:
        calls["n"] += 1

    def fake_gate(job: GenerationJob) -> GateReport:
        return GateReport(
            passed=False,
            failures=(GateFailure(check="verticales", detail="X absent", chapter_number=None),),
        )

    import generation.gate as gate_module
    monkeypatch.setattr(runner_mod, "regenerate_chapter", fake_regenerate)
    monkeypatch.setattr(gate_module, "run_delivery_gate", fake_gate)

    report = correction_mod.run_correction_loop(bp_job, client=object(), max_rounds=1)
    assert not report.passed
    assert calls["n"] == 0  # aucune régénération pour un échec doc-level


@pytest.mark.django_db
def test_boucle_desactivee_si_zero_rondes(
    bp_job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    from generation import correction as correction_mod
    from generation import runner as runner_mod

    _mark_all_done(bp_job, "emprunt de 300 000 € recalculé, analyse complète du projet.")

    calls: dict[str, int] = {"n": 0}
    monkeypatch.setattr(
        runner_mod, "regenerate_chapter",
        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1),
    )
    correction_mod.run_correction_loop(bp_job, client=object(), max_rounds=0)
    assert calls["n"] == 0


@pytest.mark.django_db
def test_boucle_respecte_le_budget_par_dossier(
    bp_job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plafond du dossier atteint -> aucune régénération lancée (règle d'or #1)."""
    from generation import correction as correction_mod
    from generation import runner as runner_mod

    _mark_all_done(bp_job, "emprunt de 300 000 € recalculé, analyse complète du projet.")
    # Épuise le budget : un chapitre porte tout le coût du plafond.
    ch = bp_job.chapters.get(chapter_number=1)
    ch.cost_eur = bp_job.budget_eur
    ch.save(update_fields=["cost_eur"])

    calls: dict[str, int] = {"n": 0}
    monkeypatch.setattr(
        runner_mod, "regenerate_chapter",
        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1),
    )
    report = correction_mod.run_correction_loop(bp_job, client=object(), max_rounds=1)
    assert not report.passed
    assert calls["n"] == 0  # pas de budget -> pas d'appel


# ── Note corrective dans le prompt ───────────────────────────────────────────


@pytest.mark.django_db
def test_corrective_note_injectee_dans_le_prompt(bp_job: GenerationJob) -> None:
    from generation.prompts import build_chapter_prompt

    ch = bp_job.chapters.get(chapter_number=1)
    prompt = build_chapter_prompt(ch, corrective_note="- Chiffre incohérent : emprunt")
    assert "CORRECTION IMPERATIVE" in prompt
    assert "emprunt" in prompt


@pytest.mark.django_db
def test_regenerate_chapter_passe_la_note(bp_job: GenerationJob) -> None:
    """regenerate_chapter transmet bien la note au générateur (via stub client)."""
    from generation.runner import regenerate_chapter

    captured: dict[str, Any] = {}

    class _CaptureClient:
        def complete(
            self,
            *,
            system: str,
            prompt: str,
            max_tokens: int = 8192,
            model: str | None = None,
        ) -> ClaudeResult:
            captured["prompt"] = prompt
            return ClaudeResult(
                content=("Analyse complète et argumentée du projet. " * 40).strip() + ".",
                input_tokens=50, output_tokens=30, model="claude-sonnet",
            )

    ch = bp_job.chapters.get(chapter_number=1)
    regenerate_chapter(
        bp_job, ch, corrective_note="- Marqueur interne présent", client=_CaptureClient()
    )
    assert "CORRECTION IMPERATIVE" in captured["prompt"]
    assert "Marqueur interne" in captured["prompt"]
