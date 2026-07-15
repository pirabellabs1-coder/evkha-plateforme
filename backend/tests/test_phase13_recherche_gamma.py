"""Phase 13 — Recherche web (ancrage sources) + Gamma (mise en page) + outils.

Couvre :
- Client de recherche Tavily (requête/réponse mockée) + stub filtré
- Construction des requêtes + collecte du brief de recherche
- Injection du brief dans le contexte + non-fuite de SOURCES_WEB
- Client Gamma réel (create/poll/export mockés) + repli sur GammaError
- Livraison : PDF Gamma prioritaire, PPTX vide non persisté
- Commande verifier_gate (lecture seule)
- Lexique packager/packagée grammaticalement correct
"""
from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import ChapterStatus, JobStatus
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

# ── Fakes httpx ──────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("erreur", request=None, response=None)  # type: ignore[arg-type]


# ── Recherche : client Tavily ────────────────────────────────────────────────


def test_tavily_client_parse_la_reponse(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from integrations.search import TavilyWebSearchClient

    captured: dict[str, Any] = {}

    def fake_post(url, headers=None, json=None, timeout=None) -> _FakeResponse:  # noqa: ANN001
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json
        return _FakeResponse({
            "query": "coworking France",
            "answer": "synthèse",
            "results": [
                {
                    "title": "Marché du coworking 2025",
                    "url": "https://xerfi.com/coworking-2025",
                    "content": "Le marché atteint 1,2 Md€ en 2025.",
                    "score": 0.9,
                    "published_date": "2025-03-01",
                },
                {"title": "Sans URL", "url": "", "content": "ignoré", "score": 0.8},
            ],
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    client = TavilyWebSearchClient(api_key="tvly-test")
    resp = client.search(query="coworking France", max_results=5)

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["headers"]["Authorization"] == "Bearer tvly-test"
    assert captured["body"]["query"] == "coworking France"
    # Résultat sans URL filtré
    assert len(resp.results) == 1
    assert resp.results[0].url == "https://xerfi.com/coworking-2025"
    assert resp.results[0].published_date == "2025-03-01"


def test_tavily_client_sans_cle_leve() -> None:
    from integrations.search import TavilyWebSearchClient

    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        TavilyWebSearchClient(api_key="").search(query="x")


def test_get_search_client_stub_par_defaut() -> None:
    from integrations.search import StubWebSearchClient, get_search_client

    assert isinstance(get_search_client(), StubWebSearchClient)


# ── Recherche : construction des requêtes + collecte du brief ────────────────


def test_build_queries_combine_secteur_pays_axes() -> None:
    from generation.research import build_queries

    queries = build_queries({
        "SECTEUR": "coworking", "PAYS": "France", "DELIVERABLE_TYPE": "market_study",
    })
    assert queries
    assert all("coworking France" in q for q in queries)
    assert len(queries) <= 6


def test_build_queries_vide_sans_secteur() -> None:
    from generation.research import build_queries

    assert build_queries({"PAYS": "France"}) == []


class _FakeSearchClient:
    """Renvoie des résultats réels (URLs non-stub) pour un test de collecte."""

    def __init__(self) -> None:
        self.calls = 0

    def search(self, *, query, max_results=5, topic="general", time_range=""):  # type: ignore[no-untyped-def]  # noqa: ANN001
        from integrations.search import SearchResponse, SearchResult

        self.calls += 1
        return SearchResponse(
            query=query,
            results=(
                SearchResult(
                    title=f"Étude {query[:20]}",
                    url=f"https://insee.fr/{self.calls}",
                    content="Donnée sectorielle datée 2025.",
                    score=0.85,
                    published_date="2025-01-15",
                ),
            ),
        )


def test_collect_research_brief_agrege_les_sources() -> None:
    from generation.research import collect_research_brief

    brief = collect_research_brief(
        DeliverableType.MARKET_STUDY,
        {"SECTEUR": "coworking", "PAYS": "France"},
        client=_FakeSearchClient(),
    )
    assert "SOURCES WEB COLLECTÉES" in brief
    assert "https://insee.fr/1" in brief
    assert "2025-01-15" in brief


def test_collect_research_brief_ignore_les_urls_stub() -> None:
    """Les URLs .evkha.local du stub ne sont jamais injectées comme vraies sources."""
    from generation.research import collect_research_brief
    from integrations.search import StubWebSearchClient

    brief = collect_research_brief(
        DeliverableType.MARKET_STUDY,
        {"SECTEUR": "coworking", "PAYS": "France"},
        client=StubWebSearchClient(),
    )
    assert brief == ""


# ── Injection dans le contexte + non-fuite de SOURCES_WEB ────────────────────


@pytest.fixture
def em_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="EM", slug="em-rech", deliverable_type=DeliverableType.MARKET_STUDY
    )
    customer = Customer.objects.create(email="rech@example.com")
    order = Order.objects.create(systeme_order_id="order_rech_1", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Lyon", "PROJET": "tiers-lieu",
        },
    )


@pytest.mark.django_db
def test_contexte_injecte_le_brief_de_recherche(em_submission: IntakeSubmission) -> None:
    from generation.context import build_context

    job = bootstrap_generation_job(em_submission)
    job.research_brief = "SOURCES WEB COLLECTÉES :\n- INSEE — https://insee.fr/x"
    job.save(update_fields=["research_brief"])
    chapter = job.chapters.get(chapter_number=1)
    ctx = build_context(chapter)
    assert "SOURCES_WEB:" in ctx
    assert "https://insee.fr/x" in ctx


@pytest.mark.django_db
def test_contexte_sans_brief_interdit_invention(em_submission: IntakeSubmission) -> None:
    from generation.context import build_context

    job = bootstrap_generation_job(em_submission)
    chapter = job.chapters.get(chapter_number=1)
    ctx = build_context(chapter)
    assert "n'invente aucune URL" in ctx or "n'invente aucune url" in ctx.lower()


def test_sources_web_est_un_token_bloque_par_le_gate() -> None:
    from generation.gate import _FORBIDDEN_TOKEN_RE

    assert _FORBIDDEN_TOKEN_RE.search("voir SOURCES_WEB pour les références")


def test_sources_web_scrubbe_du_rendu() -> None:
    from generation.rendering import strip_internal_label_tokens

    out = strip_internal_label_tokens("d'après le bloc SOURCES_WEB, le marché...")
    assert "SOURCES_WEB" not in out


# ── Gamma : client réel ──────────────────────────────────────────────────────


def test_gamma_client_create_poll_export(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from integrations.gamma import GammaApiClient

    def fake_post(url, headers=None, json=None, timeout=None) -> _FakeResponse:  # noqa: ANN001
        assert url.endswith("/generations")
        assert headers["X-API-KEY"] == "gam-test"
        assert json["textMode"] == "preserve"
        assert json["format"] == "document"
        return _FakeResponse({"generationId": "gen-42"})

    def fake_get(url, headers=None, timeout=None) -> _FakeResponse:  # noqa: ANN001
        assert url.endswith("/generations/gen-42")
        return _FakeResponse({
            "status": "completed",
            "exportUrl": "https://gamma.app/export/gen-42.pdf",
            "gammaUrl": "https://gamma.app/docs/gen-42",
        })

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", fake_get)

    client = GammaApiClient(api_key="gam-test")
    pres = client.create_presentation(title="Étude", markdown="# Contenu", theme_id="theme-1")
    assert pres.presentation_id == "gen-42"
    client.wait_until_ready(presentation_id="gen-42")
    export = client.export(presentation=pres)
    assert export.pdf_url == "https://gamma.app/export/gen-42.pdf"
    assert export.pptx_url == ""
    assert export.presentation_url == "https://gamma.app/docs/gen-42"


def test_gamma_client_statut_failed_leve(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from integrations.gamma import GammaApiClient, GammaError

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResponse({"generationId": "g1"}))
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse({"status": "failed"}))

    client = GammaApiClient(api_key="gam-test")
    with pytest.raises(GammaError):
        client.wait_until_ready(presentation_id="g1")


def test_get_gamma_client_stub_sans_cle() -> None:
    from integrations.gamma import StubGammaClient, get_gamma_client

    assert isinstance(get_gamma_client(), StubGammaClient)


# ── Gamma : livraison ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_persist_gamma_ignore_pptx_vide(em_submission: IntakeSubmission) -> None:
    from delivery.services import _persist_gamma_artifacts
    from documents.models import ArtifactKind
    from integrations.gamma import GammaExportResult

    job = bootstrap_generation_job(em_submission)
    export = GammaExportResult(
        pdf_url="https://gamma.app/x.pdf", pptx_url="", presentation_url="https://gamma.app/x"
    )
    artifacts = _persist_gamma_artifacts(job, export=export, presentation_id="gen-1")
    kinds = {a.kind for a in artifacts}
    assert ArtifactKind.GAMMA_PDF in kinds
    assert ArtifactKind.GAMMA_PPTX not in kinds


@pytest.mark.django_db
def test_ensure_gamma_repli_sur_erreur(em_submission: IntakeSubmission) -> None:
    """Une erreur Gamma ne casse pas la livraison : retourne [] (repli WeasyPrint)."""
    from delivery.services import ensure_gamma_artifacts
    from integrations.gamma import GammaError

    offer = em_submission.order.offer
    offer.gamma_enabled = True
    offer.save(update_fields=["gamma_enabled"])

    job = bootstrap_generation_job(em_submission)
    for c in job.chapters.all():
        c.content, c.status = "Contenu.", ChapterStatus.DONE
        c.save(update_fields=["content", "status"])
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])

    class _BoomGamma:
        def create_presentation(self, **kw):  # noqa: ANN003
            raise GammaError("boom")

        def wait_until_ready(self, **kw):  # noqa: ANN003
            raise GammaError("boom")

        def export(self, **kw):  # noqa: ANN003
            raise GammaError("boom")

    assert ensure_gamma_artifacts(job, gamma_client=_BoomGamma()) == []


@pytest.mark.django_db
def test_html_body_privilegie_le_pdf_gamma(em_submission: IntakeSubmission) -> None:
    from delivery.services import _html_body
    from documents.models import ArtifactKind

    job = bootstrap_generation_job(em_submission)
    gamma_pdf = SimpleNamespace(
        kind=ArtifactKind.GAMMA_PDF, download_url="https://gamma.app/g.pdf"
    )
    weasy_pdf = SimpleNamespace(kind=ArtifactKind.PDF, download_url="https://evkha/w.pdf")
    html = _html_body(job, (weasy_pdf, gamma_pdf))  # type: ignore[arg-type]
    assert "https://gamma.app/g.pdf" in html
    assert "Telecharger votre document (PDF)" in html


# ── Gamma : lecture des thèmes (connectivité) ────────────────────────────────


def test_gamma_list_themes(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from integrations.gamma import GammaApiClient

    def fake_get(url, headers=None, timeout=None):  # noqa: ANN001
        assert url.endswith("/themes")
        assert headers["X-API-KEY"] == "gam-test"
        return _FakeResponse({"themes": [
            {"id": "th-1", "name": "Corporate"},
            {"id": "th-2", "name": "Minimal"},
        ]})

    monkeypatch.setattr(httpx, "get", fake_get)
    themes = GammaApiClient(api_key="gam-test").list_themes()
    assert themes == [
        {"id": "th-1", "name": "Corporate"},
        {"id": "th-2", "name": "Minimal"},
    ]


# ── tester_apis (commande de connectivité) ───────────────────────────────────


def test_tester_apis_signale_le_mode_stub() -> None:
    from django.core.management import call_command

    out = StringIO()
    call_command("tester_apis", stdout=out)
    text = out.getvalue()
    assert "STUB" in text
    # Aucun appel réseau en mode stub : les deux briques sont signalées.
    assert "Recherche web" in text and "Gamma" in text


# ── verifier_gate (commande) ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_verifier_gate_job_inexistant() -> None:
    from django.core.management import call_command
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("verifier_gate", "00000000-0000-0000-0000-000000000000")


@pytest.mark.django_db
def test_verifier_gate_rapport_ok(em_submission: IntakeSubmission) -> None:
    from django.core.management import call_command

    job = bootstrap_generation_job(em_submission)
    for c in job.chapters.all():
        c.content = (
            "Analyse détaillée et chiffrée du marché du coworking à Lyon, "
            "avec des données locales et une conclusion argumentée complète."
        )
        c.status = ChapterStatus.DONE
        c.save(update_fields=["content", "status"])
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])

    out = StringIO()
    call_command("verifier_gate", str(job.id), stdout=out)
    assert "GATE OK" in out.getvalue()


# ── Lexique packager/packagée ────────────────────────────────────────────────


def test_lexique_packager_grammatical() -> None:
    from generation.rendering import apply_lexical_substitutions

    out = apply_lexical_substitutions(
        "Il faut packager l'offre ; une offre packagée, un produit packagé, "
        "des services packagés, des solutions packagées."
    )
    assert "packag" not in out.lower()
    assert "structurer l'offre" in out
    assert "offre structurée" in out
    assert "produit structuré" in out
    assert "services structurés" in out
    assert "solutions structurées" in out
