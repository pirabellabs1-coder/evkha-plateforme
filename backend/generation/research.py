"""Collecte du brief de recherche web (ancrage anti-hallucination, §6 cadrage).

Au démarrage d'un job, on lance quelques requêtes ciblées, dérivées de
PERSPECTIVES d'analyse (technique inspirée de STORM, Stanford : le
questionnement multi-perspectives donne un brief plus large et plus profond
qu'une poignée d'axes génériques). On stocke les VRAIS résultats sur le job.
Ce brief est réinjecté dans le contexte de chaque chapitre : les chiffres
s'appuient sur des sources réelles et datées, et la section Sources liste de
vraies URLs au lieu d'en inventer.

Coût maîtrisé : la recherche est faite UNE fois par job (pas par chapitre),
bornée à _MAX_QUERIES requêtes, et le fournisseur par défaut est GRATUIT
(DuckDuckGo). AUCUN appel LLM ici : les perspectives sont curées, pas générées.
En mode stub (défaut), aucun réseau : le brief reste vide et le pipeline
fonctionne comme avant.
"""
from __future__ import annotations

from django.utils import timezone

from catalog.models import DeliverableType
from integrations.search import SearchResult, WebSearchClient, get_search_client

# Nombre de requêtes par job (borne le coût et la latence ; DuckDuckGo gratuit
# mais rate-limité, donc on reste raisonnable).
_MAX_QUERIES = 7
_RESULTS_PER_QUERY = 4
# Score minimal pour retenir un résultat (Tavily uniquement ; DuckDuckGo
# renvoie score=0, jamais filtré).
_MIN_SCORE = 0.4

# Perspectives d'analyse communes à tous les livrables (STORM-style). Chaque
# perspective devient une requête « secteur + pays + perspective ».
_PERSPECTIVES_COMMUNES: tuple[str, ...] = (
    "taille du marché chiffres",
    "taux de croissance TCAC prévisions",
    "segments de clientèle besoins comportement d'achat",
    "réglementation cadre légal normes",
    "tendances récentes innovation",
)

# Perspectives additionnelles spécifiques au type de livrable.
_PERSPECTIVES_PAR_TYPE: dict[str, tuple[str, ...]] = {
    DeliverableType.COMPETITOR_STUDY: (
        "principaux concurrents directs et indirects",
        "positionnement prix et offres des acteurs",
        "avis clients réputation des acteurs",
    ),
    DeliverableType.BUSINESS_PLAN: (
        "coûts d'investissement et de démarrage",
        "financements aides et subventions",
        "rentabilité marges du secteur",
    ),
    DeliverableType.BUSINESS_STRATEGY: (
        "leviers de croissance et stratégies gagnantes",
        "modèles économiques rentables du secteur",
        "risques et barrières à l'entrée",
    ),
    DeliverableType.MARKET_STUDY: (
        "principaux acteurs et parts de marché",
        "risques et barrières à l'entrée",
    ),
}


def _perspectives_for(deliverable_type: str) -> list[str]:
    """Perspectives d'analyse (spécifiques d'abord, puis communes), dédupliquées."""
    specifiques = _PERSPECTIVES_PAR_TYPE.get(deliverable_type, ())
    ordered = [*specifiques, *_PERSPECTIVES_COMMUNES]
    seen: set[str] = set()
    unique: list[str] = []
    for p in ordered:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def _recency_hint() -> str:
    """Indice d'année pour privilégier les données récentes (charte : 2025/2026...)."""
    year = timezone.now().year
    return f"{year - 1} {year}"


def build_queries(variables: dict[str, object]) -> list[str]:
    """Construit les requêtes multi-perspectives à partir du brief client.

    Chaque requête combine secteur + pays + une perspective d'analyse + un
    indice de récence, pour rester géographiquement et sectoriellement
    pertinente (cohérent avec l'adaptation géographique §7) et couvrir les
    angles structurants du livrable (STORM-style, sans coût LLM).
    """
    secteur = str(variables.get("SECTEUR", "")).strip()
    pays = str(variables.get("PAYS", "")).strip()
    if not secteur:
        return []

    zone = f"{secteur} {pays}".strip()
    recency = _recency_hint()
    perspectives = _perspectives_for(str(variables.get("DELIVERABLE_TYPE", "")))
    queries = [f"{zone} {perspective} {recency}".strip() for perspective in perspectives]
    # Dédoublonne en conservant l'ordre, puis borne le nombre de requêtes.
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        key = q.lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique[:_MAX_QUERIES]


def _format_result(result: SearchResult) -> str:
    date = f" ({result.published_date})" if result.published_date else ""
    extrait = result.content.strip().replace("\n", " ")
    if len(extrait) > 320:
        extrait = extrait[:320].rstrip() + "…"
    return f"- {result.title}{date}\n  URL : {result.url}\n  Extrait : {extrait}"


def collect_research_brief(
    deliverable_type: str,
    variables: dict[str, object],
    *,
    client: WebSearchClient | None = None,
) -> str:
    """Lance les recherches et renvoie un brief textuel prêt à injecter.

    Renvoie "" si la recherche est désactivée (stub sans résultats réels),
    si le secteur manque, ou si aucun résultat pertinent n'est trouvé — dans
    ce cas le pipeline continue sans ancrage web (comportement historique).
    """
    client = client or get_search_client()
    variables = {**variables, "DELIVERABLE_TYPE": deliverable_type}
    queries = build_queries(variables)
    if not queries:
        return ""

    blocks: list[str] = []
    seen_urls: set[str] = set()
    for query in queries:
        try:
            response = client.search(
                query=query, max_results=_RESULTS_PER_QUERY, topic="general"
            )
        except Exception:  # noqa: BLE001 — la recherche ne doit jamais casser le job
            continue
        kept: list[str] = []
        for result in response.results:
            if not result.url or result.url in seen_urls:
                continue
            if result.score and result.score < _MIN_SCORE:
                continue
            # Le stub marque ses URLs .evkha.local : on ne les injecte jamais
            # comme si c'étaient de vraies sources.
            if result.url.endswith(".evkha.local") or ".evkha.local/" in result.url:
                continue
            seen_urls.add(result.url)
            kept.append(_format_result(result))
        if kept:
            blocks.append(f"Recherche : {query}\n" + "\n".join(kept))

    if not blocks:
        return ""

    header = (
        "SOURCES WEB COLLECTÉES (données réelles datées — utilise-les pour "
        "ancrer les chiffres et construire la section Sources ; ne cite JAMAIS "
        "une URL absente de cette liste) :\n\n"
    )
    return header + "\n\n".join(blocks)
