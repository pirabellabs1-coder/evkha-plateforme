"""La recherche doit nourrir vingt-et-un chapitres, pas les répéter.

Défaut mesuré sur le premier livrable réel : sept requêtes de quatre résultats,
soit **vingt-huit extraits au maximum**, collectés une fois, puis le même bloc
injecté dans les vingt-et-un chapitres. Deux conséquences.

1. Le manuel EM exige « 35 à 60 sources distinctes ». Le plafond était à
   vingt-huit AVANT dédoublonnage : la cible était hors d'atteinte par
   construction, quelle que soit la qualité de la rédaction.
2. Le chapitre 6, sur la réglementation, recevait exactement les extraits du
   chapitre 11, sur les personas. Vingt-et-un chapitres nourris de la même
   matière n'ont plus rien de neuf à dire passé le troisième — c'est
   l'explication mécanique des redites relevées par la cliente. Ce n'est pas le
   modèle qui se répète, c'est la matière qui manque.

Ces tests échouent sur le code d'avant : `build_queries` y rendait sept requêtes
et `research.brief_pour_chapitre` n'existait pas.
"""
from __future__ import annotations

from typing import Any

from catalog.models import DeliverableType
from generation.research import (
    PREFIXE_SECTION,
    axes_pour,
    brief_pour_chapitre,
    build_queries,
    collect_research_brief,
)
from integrations.search import SearchResponse, SearchResult

VARIABLES = {"SECTEUR": "coworking", "PAYS": "France"}


class _ClientQuiRepond:
    """Doublure qui renvoie des URLs DISTINCTES par requête.

    Rendre la même URL partout ferait passer le dédoublonnage pour de la
    couverture : on mesurerait le nombre de requêtes, pas de sources.
    """

    def __init__(self) -> None:
        self.requetes: list[str] = []

    def search(self, **kwargs: Any) -> SearchResponse:
        requete = str(kwargs.get("query", ""))
        self.requetes.append(requete)
        rang = len(self.requetes)
        nombre = int(kwargs.get("max_results", 5))
        return SearchResponse(
            query=requete,
            results=tuple(
                SearchResult(
                    title=f"Source {rang}.{i}",
                    url=f"https://exemple-{rang}-{i}.fr/etude",
                    content="Contenu daté de 2025.",
                    score=0.9,
                    published_date="2025-03-01",
                )
                for i in range(nombre)
            ),
            answer="",
        )


class _ClientQuiTombe:
    """Le fournisseur gratuit limite le débit : une requête sur deux lève."""

    def __init__(self) -> None:
        self.appels = 0

    def search(self, **kwargs: Any) -> SearchResponse:
        self.appels += 1
        if self.appels % 2 == 0:
            msg = "rate limited"
            raise RuntimeError(msg)
        return SearchResponse(
            query=str(kwargs.get("query", "")),
            results=(
                SearchResult(
                    title=f"Source {self.appels}",
                    url=f"https://exemple-{self.appels}.fr",
                    content="…",
                    score=0.9,
                    published_date="",
                ),
            ),
            answer="",
        )


# ── L'ampleur : atteindre la cible du manuel ─────────────────────────────────


def test_l_etude_de_marche_couvre_assez_d_axes_pour_35_sources() -> None:
    """Le test qui échoue sur le code d'avant : sept requêtes, vingt-huit sources.

    On ne teste pas « il y a plus de requêtes » mais la propriété qui compte :
    le plafond théorique atteint la cible basse du manuel. Sans elle, aucune
    rédaction ne peut être conforme.
    """
    # La constante du module, jamais une copie : avec « 5 » écrit ici, le test
    # passait sur le code d'avant (7 requêtes × 5 = 35) alors que la collecte
    # réelle en ramenait 28 (7 × 4). Un test qui mesure sa propre hypothèse ne
    # verrouille rien (règles 5 et 6).
    from generation.research import _RESULTS_PER_QUERY

    requetes = build_queries({**VARIABLES, "DELIVERABLE_TYPE": DeliverableType.MARKET_STUDY})
    plafond = len(requetes) * _RESULTS_PER_QUERY
    assert plafond >= 35, (
        f"{len(requetes)} requêtes × {_RESULTS_PER_QUERY} résultats = {plafond} "
        "sources au mieux, sous les 35 sources distinctes exigées par le manuel"
    )


def test_les_axes_ne_se_repetent_pas() -> None:
    """Deux axes de même clé produiraient deux fois la même requête."""
    for type_livrable in (
        DeliverableType.MARKET_STUDY,
        DeliverableType.COMPETITOR_STUDY,
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.BUSINESS_STRATEGY,
    ):
        axes = axes_pour(str(type_livrable))
        cles = [a.cle for a in axes]
        assert len(cles) == len(set(cles)), f"{type_livrable} : axes en double"
        requetes = build_queries({**VARIABLES, "DELIVERABLE_TYPE": type_livrable})
        assert len(requetes) == len(set(requetes))


def test_aucun_livrable_ne_declare_plus_d_axes_que_le_plafond() -> None:
    """Le plafond tronque en queue — c'est-à-dire les axes COMMUNS.

    Ce sont eux que tous les chapitres reçoivent. Les perdre priverait les
    chapitres de synthèse de toute matière, et l'erreur serait muette : le
    brief aurait l'air complet.
    """
    from generation.research import _AXES_COMMUNS, _AXES_PAR_TYPE, _MAX_QUERIES

    for type_livrable, specifiques in _AXES_PAR_TYPE.items():
        total = len({a.cle for a in (*specifiques, *_AXES_COMMUNS)})
        assert total <= _MAX_QUERIES, (
            f"{type_livrable} déclare {total} axes pour un plafond de "
            f"{_MAX_QUERIES} : les axes communs seraient tronqués"
        )


def test_les_axes_declarent_des_chapitres_qui_existent() -> None:
    """Un axe visant le chapitre 22 ne nourrirait jamais personne.

    L'erreur serait muette : la section resterait dans le brief entier, et
    aucun chapitre ne la recevrait.
    """
    from generation.blueprints import MARKET_STUDY_CHAPTERS

    connus = {c.number for c in MARKET_STUDY_CHAPTERS}
    for axe in axes_pour(str(DeliverableType.MARKET_STUDY)):
        inconnus = set(axe.chapitres) - connus
        assert not inconnus, f"axe {axe.cle} : chapitres inexistants {sorted(inconnus)}"


# ── Le filtrage par chapitre ─────────────────────────────────────────────────


def _brief() -> str:
    return collect_research_brief(
        DeliverableType.MARKET_STUDY, dict(VARIABLES), client=_ClientQuiRepond()
    )


def test_deux_chapitres_ne_recoivent_pas_la_meme_matiere() -> None:
    """La CLASSE du défaut, pas un exemple choisi (règle 4)."""
    brief = _brief()
    assert PREFIXE_SECTION in brief

    vues = {n: brief_pour_chapitre(brief, n) for n in (2, 6, 10, 14, 17)}
    assert len(set(vues.values())) == 5, (
        "des chapitres reçoivent exactement les mêmes sources"
    )
    for numero, vue in vues.items():
        assert vue, f"chapitre {numero} : aucune source"
        assert len(vue) < len(brief), f"chapitre {numero} : reçoit le brief entier"


def test_la_reglementation_et_les_personas_ne_partagent_pas_leurs_sources() -> None:
    """Le cas nommé : le chapitre 6 recevait les extraits du chapitre 11."""
    brief = _brief()
    reglementation = brief_pour_chapitre(brief, 6)
    personas = brief_pour_chapitre(brief, 11)

    assert "licences" in reglementation
    assert "licences" not in personas
    assert "frequence_achat" in personas
    assert "frequence_achat" not in reglementation


def test_les_axes_de_fondation_vont_a_tous_les_chapitres() -> None:
    """Contre-épreuve : filtrer ne doit pas priver du socle commun.

    La taille du marché et sa croissance sont citées partout ; les retirer
    d'un chapitre l'inviterait à en chercher d'autres, donc à diverger.
    """
    brief = _brief()
    for numero in (2, 6, 11, 16):
        vue = brief_pour_chapitre(brief, numero)
        assert "[chapitres: tous]" in vue, f"chapitre {numero} : socle commun perdu"


def test_le_chapitre_des_sources_recoit_le_brief_entier() -> None:
    """Le manuel : « faire apparaître toutes les sources réellement utilisées »."""
    brief = _brief()
    assert brief_pour_chapitre(brief, 21) == brief


def test_un_chapitre_de_synthese_ne_recoit_que_le_socle_commun() -> None:
    """Les chapitres 18 à 20 n'ont aucun axe propre : ils synthétisent.

    Ils gardent les fondations — taille du marché, croissance —, sur lesquelles
    la SWOT et les recommandations s'appuient. Mais aucune matière neuve : le
    manuel leur interdit d'introduire un chiffre que les chapitres précédents
    n'ont pas déjà posé.
    """
    # 22 est l'annexe : c'est le chapitre où la règle compte le plus, puisque le
    # manuel lui interdit d'introduire le moindre chiffre nouveau.
    for numero in (18, 19, 20, 22):
        vue = brief_pour_chapitre(_brief(), numero)
        sections = [
            ligne for ligne in vue.splitlines() if ligne.startswith(PREFIXE_SECTION)
        ]
        assert sections, f"chapitre {numero} : privé même des fondations"
        assert all("[chapitres: tous]" in ligne for ligne in sections), (
            f"chapitre {numero} : reçoit de la matière neuve alors qu'il "
            "synthétise — "
            + str([s for s in sections if "[chapitres: tous]" not in s])
        )


def test_un_chapitre_sans_aucune_section_est_prevenu_au_lieu_d_etre_vide() -> None:
    """Cas atteignable : la limitation de débit n'a laissé passer que les
    sections d'AUTRES chapitres, fondations comprises.

    Rendre un bloc vide inviterait le chapitre à combler le manque — donc à
    inventer une source. On le lui dit (règle 1).
    """
    brief = (
        "SOURCES WEB COLLECTÉES — 1 source distincte collectée sur 23 axes.\n\n"
        f"{PREFIXE_SECTION}licences [chapitres: 6] — licence activité\n"
        "- Service public\n  URL : https://service-public.fr/x\n  Extrait : …"
    )
    vue = brief_pour_chapitre(brief, 11)
    assert "synthèse des chapitres précédents" in vue
    assert "aucun chiffre nouveau" in vue
    assert "service-public.fr" not in vue


def test_un_brief_sans_marqueur_est_rendu_tel_quel() -> None:
    """Les jobs déjà lancés portent un brief de l'ancien format.

    Le filtrer le ferait disparaître en silence : le chapitre perdrait son
    ancrage sans que rien ne le signale (règle 1).
    """
    ancien = "SOURCES WEB COLLECTÉES :\n- INSEE — https://insee.fr/x"
    assert brief_pour_chapitre(ancien, 6) == ancien
    assert brief_pour_chapitre("", 6) == ""


# ── Un brief amputé doit se voir ─────────────────────────────────────────────


def test_les_recherches_tombees_sont_annoncees() -> None:
    """`continue` en silence rendait un brief de six sources identique à un complet."""
    brief = collect_research_brief(
        DeliverableType.MARKET_STUDY, dict(VARIABLES), client=_ClientQuiTombe()
    )
    assert "n'ont rien renvoyé" in brief
    assert "URL inventée" in brief


def test_un_brief_complet_ne_s_annonce_pas_ampute() -> None:
    """Contre-épreuve : l'avertissement ne doit pas apparaître à tort."""
    brief = _brief()
    assert "n'ont rien renvoyé" not in brief
    assert "sources distinctes collectées" in brief
