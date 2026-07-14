"""Collecte du brief de recherche web (ancrage anti-hallucination, §6 cadrage).

Au démarrage d'un job, on lance quelques requêtes ciblées (secteur + pays +
axes structurants du livrable) et on stocke les VRAIS résultats sur le job.
Ce brief est ensuite réinjecté dans le contexte de chaque chapitre : les
chiffres s'appuient sur des sources réelles et datées, et la section Sources
liste de vraies URLs au lieu d'en inventer.

Coût maîtrisé : la recherche est faite UNE fois par job (pas par chapitre),
avec un petit nombre de requêtes. En mode stub (défaut), aucun réseau : le
brief reste vide et le pipeline fonctionne comme avant.
"""
from __future__ import annotations

from catalog.models import DeliverableType
from integrations.search import SearchResult, WebSearchClient, get_search_client

# Nombre de requêtes par job (borne le coût et la latence).
_MAX_QUERIES = 6
_RESULTS_PER_QUERY = 4
# Score Tavily minimal pour retenir un résultat (filtre le bruit peu pertinent).
_MIN_SCORE = 0.4


def _axes_for(deliverable_type: str) -> list[str]:
    """Axes de recherche structurants selon le type de livrable."""
    common = ["taille du marché chiffres récents", "taux de croissance TCAC"]
    if deliverable_type == DeliverableType.COMPETITOR_STUDY:
        return ["principaux concurrents parts de marché", "positionnement acteurs", *common]
    if deliverable_type == DeliverableType.BUSINESS_PLAN:
        return ["réglementation cadre légal", "coûts investissement secteur", *common]
    if deliverable_type == DeliverableType.BUSINESS_STRATEGY:
        return ["tendances stratégiques secteur", "leviers de croissance", *common]
    # Étude de marché (défaut) : couverture large.
    return [
        "taille du marché chiffres récents",
        "taux de croissance TCAC",
        "réglementation cadre légal",
        "tendances récentes 2025 2026",
        "segments clientèle comportements",
    ]


def build_queries(variables: dict[str, object]) -> list[str]:
    """Construit les requêtes ciblées à partir du brief client.

    Chaque requête combine secteur + pays + un axe, pour rester géographiquement
    et sectoriellement pertinente (cohérent avec l'adaptation géographique §7).
    """
    secteur = str(variables.get("SECTEUR", "")).strip()
    pays = str(variables.get("PAYS", "")).strip()
    if not secteur:
        return []

    zone = f"{secteur} {pays}".strip()
    axes = _axes_for(str(variables.get("DELIVERABLE_TYPE", "")))
    queries = [f"{zone} {axe}".strip() for axe in axes]
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
