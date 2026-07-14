"""Recherche web pour ancrer les données de marché (anti-hallucination).

Le pipeline générait les chiffres et les sources de mémoire (coupure de
connaissance du modèle) : URLs inventées, dates fabriquées. Ce module fournit
un vrai moteur de recherche, sur le même patron que les autres intégrations
(Protocol + Stub déterministe + client réel + fabrique gâtée sur un flag).

Client réel : Tavily (API pensée pour l'ancrage LLM). Endpoint documenté :
POST https://api.tavily.com/search, auth Bearer, réponse `results[]` avec
title/url/content/score. Aucun appel réseau tant que EVKHA_USE_STUB_SEARCH
est vrai ou que la clé manque : le stub prend le relais et le pipeline
continue de fonctionner (dégradé mais jamais cassé).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from django.conf import settings

# Nombre de résultats par requête et budget de sécurité réseau.
_DEFAULT_MAX_RESULTS = 5
_HTTP_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class SearchResult:
    """Un résultat de recherche normalisé, indépendant du fournisseur."""

    title: str
    url: str
    content: str
    score: float = 0.0
    published_date: str = ""


@dataclass(frozen=True)
class SearchResponse:
    query: str
    results: tuple[SearchResult, ...]
    # Réponse synthétique optionnelle (Tavily include_answer) : utile pour un
    # aperçu, jamais utilisée comme source à elle seule.
    answer: str = ""


@runtime_checkable
class WebSearchClient(Protocol):
    def search(
        self,
        *,
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        topic: str = "general",
        time_range: str = "",
    ) -> SearchResponse: ...


class StubWebSearchClient:
    """Client déterministe pour dev/CI : aucun réseau, résultats reproductibles.

    Les résultats sont marqués explicitement comme simulés pour qu'aucun test
    (ni relecture humaine) ne les prenne pour de vraies sources.
    """

    def search(
        self,
        *,
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        topic: str = "general",
        time_range: str = "",
    ) -> SearchResponse:
        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:8]
        results = tuple(
            SearchResult(
                title=f"[Résultat simulé {i + 1}] {query[:60]}",
                url=f"https://exemple.evkha.local/{digest}/{i + 1}",
                content=(
                    "Contenu de démonstration (mode stub EVKHA). Aucune donnée "
                    "réelle : la recherche web réelle nécessite EVKHA_USE_STUB_SEARCH"
                    "=false et une clé TAVILY_API_KEY."
                ),
                score=1.0 - i * 0.1,
            )
            for i in range(min(max_results, 3))
        )
        return SearchResponse(query=query, results=results, answer="")


class TavilyWebSearchClient:
    """Client réel Tavily. Le SDK n'est pas requis : appel HTTP direct via httpx.

    httpx est déjà une dépendance du projet (Kling/Pexels/Creatomate côté
    video-api ; ici on reste sur la lib standard du backend). Import paresseux
    pour ne jamais charger httpx en CI.
    """

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key

    def search(
        self,
        *,
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        topic: str = "general",
        time_range: str = "",
    ) -> SearchResponse:
        import os

        import httpx  # import paresseux : dépendance optionnelle

        api_key = self._api_key or os.environ.get("TAVILY_API_KEY", "") or str(
            getattr(settings, "TAVILY_API_KEY", "")
        )
        if not api_key:
            msg = "TAVILY_API_KEY manquante pour TavilyWebSearchClient."
            raise RuntimeError(msg)

        body: dict[str, object] = {
            "query": query,
            "search_depth": "advanced",
            "max_results": max(1, min(max_results, 20)),
            "include_answer": "advanced",
            "topic": topic,
        }
        if time_range:
            body["time_range"] = time_range

        response = httpx.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()

        results = tuple(
            SearchResult(
                title=str(item.get("title", "")).strip(),
                url=str(item.get("url", "")).strip(),
                content=str(item.get("content", "")).strip(),
                score=float(item.get("score", 0.0) or 0.0),
                published_date=str(item.get("published_date", "") or "").strip(),
            )
            for item in payload.get("results", [])
            if item.get("url")
        )
        return SearchResponse(
            query=str(payload.get("query", query)),
            results=results,
            answer=str(payload.get("answer", "") or ""),
        )


def get_search_client() -> WebSearchClient:
    """Stub par défaut ; client Tavily réel si EVKHA_USE_STUB_SEARCH=false + clé.

    Robustesse : si le flag réel est demandé mais qu'aucune clé n'est présente,
    on retombe silencieusement sur le stub (le pipeline ne casse jamais faute
    de configuration ; l'absence de vraies sources est visible dans le brief).
    """
    import os

    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_SEARCH", True))
    has_key = bool(
        os.environ.get("TAVILY_API_KEY", "") or str(getattr(settings, "TAVILY_API_KEY", ""))
    )
    if use_stub or not has_key:
        return StubWebSearchClient()
    return TavilyWebSearchClient()
