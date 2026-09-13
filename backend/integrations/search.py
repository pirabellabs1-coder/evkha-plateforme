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


class ClaudeWebSearchClient:
    """Recherche web exécutée par l'outil serveur `web_search` de Claude.

    ## Pourquoi ce fournisseur

    Le fournisseur gratuit (DuckDuckGo) a rendu ZÉRO adresse sur six dossiers
    de suite, les 11 et 12 septembre 2026, sans que rien ne le dise. Le même
    serveur rapportait cinq résultats par requête le lendemain : un blocage
    passager, typique d'un moteur gratuit interrogé depuis un centre de
    données. La recherche de Claude s'exécute chez Anthropic — elle ne dépend
    pas de l'adresse de notre serveur. Décision du client, 13/09/2026.

    ## Ce qu'elle rend, et pourquoi pas davantage

    Le texte des pages trouvées arrive CHIFFRÉ (`encrypted_content`) : il n'est
    pas lisible hors de l'API. On demande donc au modèle de citer, pour chaque
    source, le fait qu'elle porte ; les CITATIONS de sa réponse donnent le
    passage exact (`cited_text`) rattaché à son adresse. Une source trouvée
    mais jamais citée garde son titre et son adresse, sans extrait : on ne
    fabrique pas d'extrait à sa place.

    ## Ce qu'elle coûte

    Une recherche est facturée (10 $ les 1 000) EN PLUS des jetons du modèle.
    Les compteurs `input_tokens`, `output_tokens` et `recherches` s'accumulent
    sur l'instance : l'appelant les inscrit au budget du dossier. Un coût
    qu'on ne compte pas est un plafond qui ment (voir `generation/cost.py`).

    ## Ce qu'elle refuse

    Une erreur de l'outil n'est PAS une exception de l'API : elle revient en
    HTTP 200, sous forme d'objet à la place de la liste de résultats. On la
    transforme en exception, pour que la collecte la compte comme un échec et
    la nomme — sinon elle passerait pour « aucun résultat ».
    """

    #: La variante BASIQUE, et non celle à filtrage dynamique.
    #:
    #: Mesuré le 13/09/2026, même requête Zenitek, `claude-sonnet-5` :
    #:
    #:     basique    13 s    6-8 résultats   6-8 citations   ~12 000 jetons
    #:     dynamique  36 s    6 résultats     0 citation      ~60 000 jetons
    #:                (105 s depuis la production)
    #:
    #: La variante dynamique filtre les pages par exécution de code avant de
    #: répondre : trois fois plus lente, cinq fois plus chère, et SANS AUCUNE
    #: citation — donc sans aucun extrait à donner aux chapitres. Seize
    #: requêtes à 105 s font une demi-heure de recherche, au-delà du délai de
    #: vingt minutes après lequel un dossier est déclaré interrompu.
    TYPE_OUTIL = "web_search_20250305"

    def __init__(
        self, *, api_key: str | None = None, model_id: str | None = None,
        sdk_client: object | None = None,
    ) -> None:
        self._api_key = api_key
        self._model_id = model_id
        self._sdk_client = sdk_client
        self.input_tokens = 0
        self.output_tokens = 0
        self.recherches = 0

    @property
    def modele(self) -> str:
        if self._model_id:
            return self._model_id
        from integrations.claude import (  # noqa: PLC0415
            _resolve_anthropic_model_id,
            _resolve_model_alias,
        )

        return _resolve_anthropic_model_id(_resolve_model_alias())

    def _sdk(self) -> object:
        if self._sdk_client is not None:
            return self._sdk_client
        import os

        import anthropic  # import paresseux : jamais chargé en CI

        api_key = self._api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            msg = "ANTHROPIC_API_KEY manquante pour ClaudeWebSearchClient."
            raise RuntimeError(msg)
        self._sdk_client = anthropic.Anthropic(api_key=api_key)
        return self._sdk_client

    def search(
        self,
        *,
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        topic: str = "general",
        time_range: str = "",
    ) -> SearchResponse:
        plafond = max(1, min(max_results, 10))
        # Consigne COURTE et effort BAS. Mesuré le 13/09/2026, même requête,
        # `claude-sonnet-5`, variante basique de l'outil :
        #
        #     consigne longue, effort par défaut  22,6 s   8 citations  1 888 jetons
        #     consigne courte, effort bas          7,9 s   5 citations    515 jetons
        #
        # Sur la stratégie `a678b10a`, la recherche avait produit ~2 100 jetons
        # de sortie par requête — réflexion comprise — pour une tâche qui n'en
        # demande pas : trouver, puis citer. Chaque source garde sa citation,
        # donc son extrait. La réflexion n'est pas désactivée : la documentation
        # de Claude recommande de baisser l'effort plutôt que de l'éteindre.
        consigne = (
            f"Recherche sur le web : « {query} ».\n\n"
            f"Retiens au plus {plafond} sources, les plus fiables d'abord "
            "(statistiques publiques, organismes officiels, fédérations "
            "professionnelles). Pour chacune, UNE phrase courte qui cite le fait "
            "chiffré ou daté qu'elle apporte. Aucune introduction, aucune "
            "conclusion, aucun commentaire : seulement ces phrases."
        )
        reponse = self._sdk().messages.create(  # type: ignore[attr-defined]
            model=self.modele,
            max_tokens=4096,
            output_config={"effort": "low"},
            tools=[{"type": self.TYPE_OUTIL, "name": "web_search", "max_uses": 1}],
            messages=[{"role": "user", "content": consigne}],
        )

        usage = getattr(reponse, "usage", None)
        self.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
        self.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
        serveur = getattr(usage, "server_tool_use", None)
        self.recherches += int(getattr(serveur, "web_search_requests", 0) or 0)

        trouvees: list[object] = []
        erreurs: list[str] = []
        extraits: dict[str, list[str]] = {}
        for bloc in getattr(reponse, "content", []) or []:
            genre = getattr(bloc, "type", "")
            if genre == "web_search_tool_result":
                contenu = getattr(bloc, "content", None)
                if not isinstance(contenu, list):
                    # Une erreur d'UNE recherche n'annule pas les autres. Mesuré
                    # le 13/09/2026 depuis la production : le modèle tente une
                    # seconde recherche au-delà de `max_uses`, l'outil rend
                    # `max_uses_exceeded` À CÔTÉ des résultats de la première —
                    # et rejeter toute la réponse jetait des résultats valides.
                    erreurs.append(str(getattr(contenu, "error_code", "inconnue")))
                    continue
                trouvees.extend(contenu)
            elif genre == "text":
                for citation in getattr(bloc, "citations", None) or []:
                    if getattr(citation, "type", "") != "web_search_result_location":
                        continue
                    passage = str(getattr(citation, "cited_text", "") or "").strip()
                    if passage:
                        extraits.setdefault(str(citation.url), []).append(passage)

        if not trouvees and erreurs:
            # Rien d'exploitable ET une erreur : c'est une panne, pas un vide.
            msg = f"Recherche Claude en erreur : {', '.join(erreurs)}"
            raise RuntimeError(msg)
        if not trouvees and not any(
            getattr(bloc, "type", "") == "web_search_tool_result"
            for bloc in getattr(reponse, "content", []) or []
        ):
            # Le modèle a répondu SANS chercher. Avec un effort bas, rien ne
            # l'y oblige ; forcer l'outil est incompatible avec la réflexion
            # adaptative. Rendre un vide ferait passer « pas cherché » pour
            # « rien trouvé » (relecture du 13/09/2026).
            msg = "Recherche Claude non exécutée : le modèle n'a pas appelé l'outil"
            raise RuntimeError(msg)

        vues: set[str] = set()
        resultats: list[SearchResult] = []
        for trouvee in trouvees:
            url = str(getattr(trouvee, "url", "") or "").strip()
            if not url or url in vues:
                continue
            vues.add(url)
            resultats.append(SearchResult(
                title=str(getattr(trouvee, "title", "") or "").strip(),
                url=url,
                content=" ".join(extraits.get(url, []))[:1500],
                score=0.0,
                published_date=str(getattr(trouvee, "page_age", "") or "").strip(),
            ))
        # Les sources CITÉES d'abord : ce sont celles dont on a un extrait.
        resultats.sort(key=lambda r: not r.content)
        return SearchResponse(query=query, results=tuple(resultats[:plafond]))


def get_search_client() -> WebSearchClient:
    """Stub par défaut ; sinon fournisseur réel selon EVKHA_SEARCH_PROVIDER.

    - EVKHA_USE_STUB_SEARCH=true (défaut) -> stub, aucun réseau.
    - Sinon, provider = EVKHA_SEARCH_PROVIDER :
        * "duckduckgo" (défaut) -> gratuit, sans clé.
        * "tavily" -> uniquement si TAVILY_API_KEY présente, sinon repli
          DuckDuckGo (jamais de blocage faute de clé payante).
        * "claude" -> outil `web_search` de Claude, si ANTHROPIC_API_KEY est
          présente ; sinon repli DuckDuckGo. Payant (13/09/2026).
    Aucune brique payante n'est jamais activée implicitement.
    """
    import os

    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_SEARCH", True))
    if use_stub:
        return StubWebSearchClient()

    provider = str(getattr(settings, "EVKHA_SEARCH_PROVIDER", "duckduckgo")).lower()
    if provider == "claude":
        # Payant : activé seulement par ce réglage explicite. Sans clé
        # d'API, repli gratuit — une recherche ne bloque jamais un dossier.
        if os.environ.get("ANTHROPIC_API_KEY", ""):
            return ClaudeWebSearchClient()
        return DuckDuckGoWebSearchClient()
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
