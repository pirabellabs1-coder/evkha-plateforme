"""Collecte du brief de recherche web (ancrage anti-hallucination, §6 cadrage).

Au démarrage d'un job, on lance des requêtes ciblées, dérivées d'AXES d'analyse
(technique inspirée de STORM, Stanford : le questionnement multi-perspectives
donne un brief plus large et plus profond qu'une poignée d'axes génériques). On
stocke les VRAIS résultats sur le job. Ce brief est réinjecté dans le contexte
des chapitres : les chiffres s'appuient sur des sources réelles et datées, et la
section Sources liste de vraies URLs au lieu d'en inventer.

Coût maîtrisé : la recherche est faite UNE fois par job (pas par chapitre) et le
fournisseur par défaut est GRATUIT (DuckDuckGo). AUCUN appel LLM ici : les axes
sont curés, pas générés. En mode stub (défaut), aucun réseau : le brief reste
vide et le pipeline fonctionne comme avant.

## Ce que la version précédente produisait, mesuré

Sept requêtes, quatre résultats chacune : **vingt-huit extraits au maximum**,
collectés une fois, puis **le même bloc injecté dans les vingt-et-un
chapitres**. Le chapitre 6, sur la réglementation, recevait exactement les
extraits du chapitre 11, sur les personas.

Deux conséquences, toutes deux visibles sur le premier livrable réel :

1. Le manuel EM exige « 35 à 60 sources distinctes » réparties en six familles.
   Le plafond était à vingt-huit avant dédoublonnage — la cible était hors
   d'atteinte par construction, quelle que soit la qualité de la rédaction.
2. Vingt-et-un chapitres nourris des mêmes vingt-huit paragraphes n'ont rien de
   neuf à dire à partir du troisième. C'est l'explication mécanique des redites
   relevées par la cliente : ce n'est pas le modèle qui se répète, c'est la
   matière qui manque.

Les axes portent donc désormais les CHAPITRES qu'ils servent, et le contexte
n'injecte que ce qui concerne le chapitre en cours (voir `context.py`).

## Pourquoi les échecs de requête sont comptés

`ddgs` limite le débit et lève. L'ancienne boucle faisait `continue` en silence :
un brief de six sources sur soixante avait exactement la même apparence qu'un
brief complet. On enregistre donc le nombre de requêtes tombées dans l'en-tête
du brief — un brief amputé doit se voir (règle 1).
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from django.utils import timezone

from catalog.models import DeliverableType
from integrations.search import (
    SearchResult,
    StubWebSearchClient,
    WebSearchClient,
    get_search_client,
)

_log = logging.getLogger(__name__)

#: Résultats demandés par requête. Cinq plutôt que quatre : après
#: dédoublonnage inter-requêtes, le rendement réel tourne autour de trois.
_RESULTS_PER_QUERY = 5

#: Score minimal pour retenir un résultat (Tavily uniquement ; DuckDuckGo
#: renvoie score=0, jamais filtré).
_MIN_SCORE = 0.4

#: Pause entre deux requêtes. DuckDuckGo est gratuit et sans clé, mais il
#: limite le débit : enchaîner vingt requêtes sans respirer fait tomber la
#: moitié d'entre elles. Une seconde suffit en pratique, et vingt secondes de
#: plus sur un job qui dure des minutes ne se remarquent pas.
_PAUSE_ENTRE_REQUETES_S = 1.0

#: Plafond de sécurité, pas une cible. Il borne le temps passé si un jour
#: quelqu'un déclare cinquante axes ; la cible réelle est le nombre d'axes du
#: livrable.
_MAX_QUERIES = 24


@dataclass(frozen=True)
class Axe:
    """Un angle de recherche, et les chapitres qu'il nourrit.

    `chapitres` vide signifie « tous » : c'est le cas des axes de fondation
    (taille du marché, croissance), qui servent partout parce que tout le
    document y revient.
    """

    cle: str
    requete: str
    chapitres: tuple[int, ...] = field(default_factory=tuple)


# ── Axes communs à tous les livrables ────────────────────────────────────────
#
# Ils décrivent le marché lui-même. Aucun chapitre n'est déclaré : ces sources
# valent pour l'ensemble du document.
_AXES_COMMUNS: tuple[Axe, ...] = (
    Axe("taille_marche", "taille du marché chiffres"),
    Axe("croissance", "taux de croissance TCAC prévisions"),
    Axe("segments", "segments de clientèle besoins comportement d'achat"),
    Axe("reglementation", "réglementation cadre légal normes"),
    Axe("tendances", "tendances récentes innovation"),
)


# ── Axes propres à l'étude de marché ─────────────────────────────────────────
#
# Un axe par bloc du manuel (§6, pp. 11-31), plus les familles de sources qu'il
# réclame nommément : statistiques publiques, organismes officiels, institutions
# internationales, fédérations professionnelles, observatoires, travaux
# académiques et cabinets reconnus.
#
# Les numéros de chapitre suivent `blueprints.MARKET_STUDY_CHAPTERS`. Le
# chapitre 21 n'apparaît nulle part : il recense TOUTES les sources, et reçoit
# donc le brief entier.
_AXES_ETUDE_DE_MARCHE: tuple[Axe, ...] = (
    # Bloc A — fondations chiffrées (ch. 1-2)
    Axe("marche_mondial", "marché mondial taille valeur milliards", (1,)),
    Axe("marche_national", "marché national chiffre d'affaires statistiques", (1, 2)),
    Axe("donnees_locales", "population revenus densité données locales INSEE", (2, 17)),
    # Bloc B — segmentation (ch. 3)
    Axe("typologie_clients", "typologie clientèle profils dépense moyenne", (3, 10, 11)),
    # Bloc C — présent et futur (ch. 4-5)
    Axe("barrieres_entree", "barrières à l'entrée coûts de démarrage secteur", (4,)),
    Axe("opportunites_2030", "opportunités croissance secteur 2026 2030", (5, 8)),
    # Bloc D — réglementation (ch. 6)
    Axe("licences", "licence agrément autorisation obligations légales activité", (6,)),
    Axe("fiscalite", "fiscalité TVA charges statut juridique activité", (6,)),
    # Bloc E — horizons (ch. 7-8)
    Axe("tendances_2026", "tendances 2026 2027 évolution des usages", (7,)),
    Axe("prospective", "prospective scénarios secteur horizon 2030", (8,)),
    # Bloc F — chiffres, clients, usages (ch. 9-11)
    Axe("prix_pratiques", "prix moyen tarifs pratiqués fourchette", (9, 10, 16)),
    Axe("frequence_achat", "fréquence d'achat panier moyen habitudes consommateurs", (10, 11)),
    # Bloc G — risques et viabilité (ch. 12-14)
    Axe("risques_secteur", "risques défaillances entreprises secteur", (12, 13)),
    Axe("rentabilite", "marge rentabilité taux de survie entreprises secteur", (14,)),
    # Bloc H — offre, demande, géographie (ch. 15-17)
    Axe("offre_existante", "nombre d'établissements densité de l'offre", (16, 17)),
    Axe("acteurs", "principaux acteurs parts de marché", (16,)),
    # Familles de sources exigées par le manuel, tous chapitres
    Axe("federation", "fédération professionnelle syndicat rapport annuel secteur"),
    Axe("observatoire", "observatoire étude sectorielle rapport"),
)


_AXES_PAR_TYPE: dict[str, tuple[Axe, ...]] = {
    DeliverableType.MARKET_STUDY: _AXES_ETUDE_DE_MARCHE,
    DeliverableType.COMPETITOR_STUDY: (
        Axe("concurrents", "principaux concurrents directs et indirects"),
        Axe("positionnement", "positionnement prix et offres des acteurs"),
        Axe("reputation", "avis clients réputation des acteurs"),
    ),
    DeliverableType.BUSINESS_PLAN: (
        Axe("investissement", "coûts d'investissement et de démarrage"),
        Axe("financement", "financements aides et subventions"),
        Axe("rentabilite", "rentabilité marges du secteur"),
    ),
    DeliverableType.BUSINESS_STRATEGY: (
        Axe("leviers", "leviers de croissance et stratégies gagnantes"),
        Axe("modeles", "modèles économiques rentables du secteur"),
        Axe("risques", "risques et barrières à l'entrée"),
    ),
}


#: Marqueur de section dans le brief. `chapitres.runner` et `context.py` s'en
#: servent pour ne réinjecter que les sections utiles au chapitre en cours. Le
#: format est lu par une regex : le modifier des deux côtés, ou pas du tout
#: (règle 5).
PREFIXE_SECTION = "### AXE "


def axes_pour(deliverable_type: str) -> list[Axe]:
    """Axes du livrable, spécifiques d'abord, puis communs, dédupliqués."""
    ordonnes = [*_AXES_PAR_TYPE.get(deliverable_type, ()), *_AXES_COMMUNS]
    vus: set[str] = set()
    retenus: list[Axe] = []
    for axe in ordonnes:
        if axe.cle not in vus:
            vus.add(axe.cle)
            retenus.append(axe)
    if len(retenus) > _MAX_QUERIES:
        # Les axes COMMUNS sont en queue : une troncature silencieuse ôterait
        # d'abord la matière que TOUS les chapitres reçoivent, et les chapitres
        # de synthèse se retrouveraient sans rien. On le dit (règle 1) ; un test
        # garde l'invariant à la déclaration.
        _log.warning(
            "%s déclare %s axes pour un plafond de %s : %s ne seront pas cherchés.",
            deliverable_type, len(retenus), _MAX_QUERIES,
            [a.cle for a in retenus[_MAX_QUERIES:]],
        )
    return retenus[:_MAX_QUERIES]


def _recency_hint() -> str:
    """Indice d'année. Le manuel exige de privilégier 2024-2026 pour décrire la
    situation actuelle, et la dernière année réellement disponible sinon."""
    year = timezone.now().year
    return f"{year - 1} {year}"


def build_queries(variables: dict[str, object]) -> list[str]:
    """Requêtes du job, dans l'ordre des axes.

    Conservée pour l'appelant historique et les tests : c'est la projection
    textuelle de `axes_et_requetes`.
    """
    return [requete for _, requete in axes_et_requetes(variables)]


def axes_et_requetes(variables: dict[str, object]) -> list[tuple[Axe, str]]:
    """Chaque axe avec la requête qu'il produit pour ce projet."""
    secteur = str(variables.get("SECTEUR", "")).strip()
    pays = str(variables.get("PAYS", "")).strip()
    if not secteur:
        return []

    zone = f"{secteur} {pays}".strip()
    recency = _recency_hint()
    couples: list[tuple[Axe, str]] = []
    vues: set[str] = set()
    for axe in axes_pour(str(variables.get("DELIVERABLE_TYPE", ""))):
        requete = f"{zone} {axe.requete} {recency}".strip()
        cle = requete.lower()
        if cle not in vues:
            vues.add(cle)
            couples.append((axe, requete))
    return couples


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
    pause_s: float | None = None,
) -> str:
    """Lance les recherches et renvoie un brief textuel prêt à injecter.

    Renvoie "" si la recherche est désactivée (stub sans résultats réels), si le
    secteur manque, ou si aucun résultat pertinent n'est trouvé — dans ce cas le
    pipeline continue sans ancrage web (comportement historique).

    La pause entre requêtes ne s'applique QU'À un client qui sort réellement sur
    le réseau. Le stub n'a aucune limite de débit : le faire attendre une
    seconde par axe ajoutait vingt-trois secondes à CHAQUE test qui lance un
    job, puisque `runner.py` appelle cette fonction sans client injecté. Décider
    d'après « le client a-t-il été injecté ? » regardait la mauvaise chose.
    """
    client = client or get_search_client()
    if pause_s is None:
        pause_s = 0.0 if isinstance(client, StubWebSearchClient) else _PAUSE_ENTRE_REQUETES_S
    variables = {**variables, "DELIVERABLE_TYPE": deliverable_type}
    couples = axes_et_requetes(variables)
    if not couples:
        return ""

    sections: list[str] = []
    urls_vues: set[str] = set()
    retenues = 0
    echecs = 0
    for rang, (axe, requete) in enumerate(couples):
        if rang and pause_s > 0:
            time.sleep(pause_s)
        try:
            response = client.search(
                query=requete, max_results=_RESULTS_PER_QUERY, topic="general"
            )
        except Exception:  # noqa: BLE001 — la recherche ne doit jamais casser le job
            echecs += 1
            _log.warning("Recherche tombée pour l'axe %s : %s", axe.cle, requete)
            continue
        gardees: list[str] = []
        for result in response.results:
            if not result.url or result.url in urls_vues:
                continue
            if result.score and result.score < _MIN_SCORE:
                continue
            # Le stub marque ses URLs .evkha.local : on ne les injecte jamais
            # comme si c'étaient de vraies sources.
            if result.url.endswith(".evkha.local") or ".evkha.local/" in result.url:
                continue
            urls_vues.add(result.url)
            gardees.append(_format_result(result))
        if gardees:
            retenues += len(gardees)
            # Les chapitres servis sont écrits DANS la section : c'est ce que
            # `context.py` lit pour n'injecter que l'utile.
            portee = (
                ",".join(str(n) for n in axe.chapitres) if axe.chapitres else "tous"
            )
            sections.append(
                f"{PREFIXE_SECTION}{axe.cle} [chapitres: {portee}] — {requete}\n"
                + "\n".join(gardees)
            )

    if not sections:
        return ""

    # Un brief amputé doit se voir. La cible du manuel est écrite ici pour que
    # le modèle sache ce qui lui manque, plutôt que de combler au jugé.
    etat = f"{retenues} sources distinctes collectées sur {len(couples)} axes"
    if echecs:
        etat += (
            f" ; {echecs} recherche(s) n'ont rien renvoyé (limitation du "
            "fournisseur). Le brief est incomplet : ne comble aucun manque par "
            "une URL inventée"
        )
    header = (
        f"SOURCES WEB COLLECTÉES — {etat}.\n"
        "Données réelles datées : ancre les chiffres dessus et construis la "
        "section Sources à partir d'elles. Ne cite JAMAIS une URL absente de "
        "cette liste.\n\n"
    )
    return header + "\n\n".join(sections)


#: Chapitre qui recense les sources : il reçoit le brief ENTIER, y compris les
#: axes qui ne l'ont pas nourri directement. Le manuel l'exige — « faire
#: apparaître toutes les sources réellement utilisées, même celles qui ont servi
#: à confirmer ou nuancer ».
_CHAPITRE_DES_SOURCES = 21

_ENTETE_SECTION = re.compile(
    re.escape(PREFIXE_SECTION) + r"\S+ \[chapitres: ([^\]]+)\]"
)


def brief_pour_chapitre(brief: str, numero: int) -> str:
    """Ne garde du brief que les axes qui nourrissent CE chapitre.

    Vingt-et-un chapitres alimentés des mêmes extraits n'ont plus rien de neuf à
    dire passé le troisième. Chaque chapitre reçoit donc les axes qui le
    concernent, plus ceux marqués « tous » — la matière commune sur laquelle
    tout le document s'accorde.

    Un brief SANS marqueur de section est rendu tel quel : c'est le cas des
    briefs déjà stockés sur les jobs en cours et de ceux que les tests posent à
    la main. Les filtrer les ferait disparaître en silence (règle 1).
    """
    if not brief or PREFIXE_SECTION not in brief:
        return brief
    if numero == _CHAPITRE_DES_SOURCES:
        return brief

    tete, _, corps = brief.partition(PREFIXE_SECTION)
    gardees: list[str] = []
    for section in (PREFIXE_SECTION + corps).split(PREFIXE_SECTION):
        if not section.strip():
            continue
        entete = _ENTETE_SECTION.match(PREFIXE_SECTION + section)
        if entete is None:
            # Section au format inattendu : on la garde. Perdre une source
            # utile coûte plus cher qu'en injecter une de trop.
            gardees.append(PREFIXE_SECTION + section.rstrip())
            continue
        portee = entete.group(1).strip()
        concerne = portee == "tous" or str(numero) in {
            part.strip() for part in portee.split(",")
        }
        if concerne:
            gardees.append(PREFIXE_SECTION + section.rstrip())

    if not gardees:
        # Aucun axe dédié : le chapitre est de synthèse (18 à 20). Il travaille
        # sur les chapitres précédents, pas sur de la matière neuve — mais on ne
        # lui rend pas un bloc vide, qui l'inviterait à inventer.
        return (
            tete.rstrip()
            + "\n\nAucun axe de recherche propre à ce chapitre : il fait la "
            "synthèse des chapitres précédents. N'introduis aucune source ni "
            "aucun chiffre nouveau."
        )
    return tete.rstrip() + "\n\n" + "\n\n".join(gardees)
