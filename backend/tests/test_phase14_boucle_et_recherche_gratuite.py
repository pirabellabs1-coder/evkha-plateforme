"""Phase 14 — Boucle d'auto-correction (loopy) + recherche web gratuite.

Couvre :
- Recherche gratuite DuckDuckGo par défaut (aucune clé, Tavily jamais implicite)
- Client DuckDuckGo (bibliothèque mockée)
- Boucle d'auto-correction : régénère les chapitres fautifs puis repasse le gate
- Bornes : rondes plafonnées, échec doc-level non régénéré, budget respecté
- Note corrective injectée dans le prompt de régénération
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.coherence import seed_locked_facts_from_variables
from generation.gate import GateFailure, GateReport
from generation.models import ChapterStatus, JobStatus
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
        def text(self, query, max_results=5):  # noqa: ANN001
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
def bp_job(db) -> object:  # noqa: ANN001
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
        },
    )
    job = bootstrap_generation_job(submission)
    seed_locked_facts_from_variables(job, submission.normalized_variables)
    return job


def _mark_all_done(job: object, body: str) -> None:
    for c in job.chapters.all():  # type: ignore[attr-defined]
        c.content, c.status = body, ChapterStatus.DONE
        c.save(update_fields=["content", "status"])
    job.status = JobStatus.DONE  # type: ignore[attr-defined]
    job.save(update_fields=["status"])  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_boucle_regenere_le_chapitre_fautif(
    bp_job: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un chapitre avec emprunt erroné est régénéré avec la bonne valeur -> gate OK."""
    from generation import correction as correction_mod

    good_body = (
        "Le financement repose sur un emprunt de 920 000 € sur 7 ans, "
        "conforme au plan du porteur, avec une analyse complète et argumentée."
    )
    bad_body = (
        "Le financement repose sur un emprunt de 300 000 € sur 7 ans, "
        "chiffre recalculé, avec une analyse complète et argumentée du projet."
    )
    _mark_all_done(bp_job, good_body)
    # Chapitre 14 fautif (emprunt ÷3)
    ch14 = bp_job.chapters.get(chapter_number=14)  # type: ignore[attr-defined]
    ch14.content = bad_body
    ch14.save(update_fields=["content"])

    captured: dict = {}

    def fake_regenerate(job, chapter, *, corrective_note, client=None):  # noqa: ANN001
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
    bp_job: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si la régénération ne corrige rien, la boucle s'arrête après max_rounds."""
    from generation import correction as correction_mod
    from generation import runner as runner_mod

    bad_body = (
        "Le financement repose sur un emprunt de 300 000 € sur 7 ans, "
        "chiffre recalculé localement, analyse complète du projet SYNAPSES."
    )
    _mark_all_done(bp_job, bad_body)

    calls = {"n": 0}

    def fake_regenerate(job, chapter, *, corrective_note, client=None):  # noqa: ANN001
        calls["n"] += 1  # ne corrige jamais

    monkeypatch.setattr(runner_mod, "regenerate_chapter", fake_regenerate)

    report = correction_mod.run_correction_loop(bp_job, client=object(), max_rounds=2)
    assert not report.passed
    # 2 rondes max, régénération appelée au moins une fois mais borné
    assert calls["n"] >= 1


@pytest.mark.django_db
def test_boucle_ignore_echec_niveau_document(
    bp_job: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Une verticale manquante (doc-level) ne déclenche pas de régénération ciblée."""
    from generation import correction as correction_mod
    from generation import runner as runner_mod

    calls = {"n": 0}

    def fake_regenerate(job, chapter, *, corrective_note, client=None):  # noqa: ANN001
        calls["n"] += 1

    def fake_gate(job):  # noqa: ANN001
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
    bp_job: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from generation import correction as correction_mod
    from generation import runner as runner_mod

    _mark_all_done(bp_job, "emprunt de 300 000 € recalculé, analyse complète du projet.")

    calls = {"n": 0}
    monkeypatch.setattr(
        runner_mod, "regenerate_chapter",
        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1),
    )
    correction_mod.run_correction_loop(bp_job, client=object(), max_rounds=0)
    assert calls["n"] == 0


# ── Note corrective dans le prompt ───────────────────────────────────────────


@pytest.mark.django_db
def test_corrective_note_injectee_dans_le_prompt(bp_job: object) -> None:
    from generation.prompts import build_chapter_prompt

    ch = bp_job.chapters.get(chapter_number=1)  # type: ignore[attr-defined]
    prompt = build_chapter_prompt(ch, corrective_note="- Chiffre incohérent : emprunt")
    assert "CORRECTION IMPERATIVE" in prompt
    assert "emprunt" in prompt


@pytest.mark.django_db
def test_regenerate_chapter_passe_la_note(bp_job: object) -> None:
    """regenerate_chapter transmet bien la note au générateur (via stub client)."""
    from generation.runner import regenerate_chapter

    captured: dict = {}

    class _CaptureClient:
        def complete(self, *, system, prompt, max_tokens=8192, model=None):  # noqa: ANN001
            captured["prompt"] = prompt
            return ClaudeResult(
                content=("Analyse complète et argumentée du projet. " * 40).strip() + ".",
                input_tokens=50, output_tokens=30, model="claude-sonnet",
            )

    ch = bp_job.chapters.get(chapter_number=1)  # type: ignore[attr-defined]
    regenerate_chapter(
        bp_job, ch, corrective_note="- Marqueur interne présent", client=_CaptureClient()
    )
    assert "CORRECTION IMPERATIVE" in captured["prompt"]
    assert "Marqueur interne" in captured["prompt"]
