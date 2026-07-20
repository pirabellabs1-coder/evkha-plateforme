"""Recherche web pour ancrer les données de marché (anti-hallucination).

Le pipeline générait les chiffres et les sources de mémoire (coupure de
connaissance du modèle) : URLs inventées, dates fabriquées. Ce module fournit
un vrai moteur de recherche, sur le même patron que les autres intégrations
(Protocol + Stub déterministe + client réel + fabrique gâtée sur un flag).

Fournisseur par défaut : DuckDuckGo (GRATUIT, sans clé, via `ddgs`). Tavily
reste disponible en option (EVKHA_SEARCH_PROVIDER=tavily + clé) mais n'est
JAMAIS activé implicitement — aucun coût sans décision explicite. Aucun appel
réseau tant que EVKHA_USE_STUB_SEARCH est vrai : le stub prend le relais et
le pipeline continue de fonctionner (dégradé mais jamais cassé).
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


class DuckDuckGoWebSearchClient:
    """Client réel GRATUIT (aucune clé, aucun coût) via DuckDuckGo.

    Utilise la bibliothèque `ddgs` (ex-`duckduckgo_search`), installable en
    extra `[search]`. Aucune facturation, aucune inscription : c'est le
    fournisseur par défaut pour l'ancrage des sources.

    Limites assumées : DuckDuckGo ne renvoie ni score ni date de publication
    (score=0 -> jamais filtré ; date vide). En cas de rate-limit ou d'absence
    de la lib, l'appel lève et la collecte ignore la requête (brief partiel ou
    vide) ; le pipeline continue.
    """

    def search(
        self,
        *,
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        topic: str = "general",
        time_range: str = "",
    ) -> SearchResponse:
        try:
            from ddgs import DDGS  # lib récente
        except ImportError:
            try:
                # `no-redef` assume : c'est un repli sur l'ancien nom du
                # paquet, pas une vraie redefinition. mypy ne le signale que
                # lorsque `ddgs` est reellement installe (donc en CI, pas en
                # local sans l'extra [search]).
                from duckduckgo_search import (  # type: ignore[no-redef]
                    DDGS,  # ancien nom du package
                )
            except ImportError as exc:
                msg = (
                    "Recherche gratuite indisponible : installe l'extra "
                    "'pip install systeme-evkha[search]' (paquet ddgs)."
                )
                raise RuntimeError(msg) from exc

        raw = DDGS().text(query, max_results=max(1, min(max_results, 20)))
        results = tuple(
            SearchResult(
                title=str(item.get("title", "")).strip(),
                url=str(item.get("href", item.get("url", ""))).strip(),
                content=str(item.get("body", item.get("content", ""))).strip(),
                score=0.0,
                published_date="",
            )
            for item in raw
            if item.get("href") or item.get("url")
        )
        return SearchResponse(query=query, results=results, answer="")


def get_search_client() -> WebSearchClient:
    """Stub par défaut ; sinon fournisseur réel selon EVKHA_SEARCH_PROVIDER.

    - EVKHA_USE_STUB_SEARCH=true (défaut) -> stub, aucun réseau.
    - Sinon, provider = EVKHA_SEARCH_PROVIDER :
        * "duckduckgo" (défaut) -> gratuit, sans clé.
        * "tavily" -> uniquement si TAVILY_API_KEY présente, sinon repli
          DuckDuckGo (jamais de blocage faute de clé payante).
    Aucune brique payante n'est jamais activée implicitement.
    """
    import os

    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_SEARCH", True))
    if use_stub:
        return StubWebSearchClient()

    provider = str(getattr(settings, "EVKHA_SEARCH_PROVIDER", "duckduckgo")).lower()
    if provider == "tavily":
        has_key = bool(
            os.environ.get("TAVILY_API_KEY", "")
            or str(getattr(settings, "TAVILY_API_KEY", ""))
        )
        if has_key:
            return TavilyWebSearchClient()
        # Pas de clé payante -> repli gratuit plutôt que stub muet.
        return DuckDuckGoWebSearchClient()
    return DuckDuckGoWebSearchClient()
