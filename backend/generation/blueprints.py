from __future__ import annotations

from dataclasses import dataclass

from catalog.models import DeliverableType

# Source de verite du chapitrage : sommaire du document "PROMPT FINAL VERSION 3
# EM_EC" + "Consignes d'ecriture EVKHA" (mai 2026). Ne PAS inventer de chapitres.
# Ordre final impose par les consignes :
#   page de garde -> sommaire -> FICHE PROJET (ouverture) -> chapitres 1 a 20
#   -> ANNEXE (reponses au brief) -> chapitre 21 Sources -> "Fin de l'etude".
# Le numero ci-dessous = ordre de generation/rendu (la fiche projet est 0,
# l'annexe et les sources viennent apres les 20 chapitres analytiques).


class SectionKind:
    OPENING = "opening"
    CHAPTER = "chapter"
    ANNEXE = "annexe"
    SOURCES = "sources"


@dataclass(frozen=True)
class ChapterBlueprint:
    number: int
    title: str
    prompt_key: str
    section_kind: str = SectionKind.CHAPTER


MARKET_STUDY_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    ChapterBlueprint(0, "Fiche projet", "em.00.fiche_projet", SectionKind.OPENING),
    ChapterBlueprint(
        1, "Analyse chiffree du marche mondial et europeen", "em.01.marche_mondial_europeen"
    ),
    ChapterBlueprint(
        2, "Analyse chiffree du marche national et local / regional", "em.02.marche_national_local"
    ),
    ChapterBlueprint(3, "Segmentation approfondie du marche", "em.03.segmentation"),
    ChapterBlueprint(4, "Avantages et inconvenients du secteur", "em.04.avantages_inconvenients"),
    ChapterBlueprint(5, "Defis et opportunites du marche", "em.05.defis_opportunites"),
    ChapterBlueprint(6, "Analyse approfondie de la reglementation", "em.06.reglementation"),
    ChapterBlueprint(7, "Tendances du marche a court terme", "em.07.tendances_court_terme"),
    ChapterBlueprint(8, "Perspectives d'evolution a long terme", "em.08.perspectives_long_terme"),
    ChapterBlueprint(9, "Les 12 chiffres cles du marche", "em.09.douze_chiffres_cles"),
    ChapterBlueprint(10, "Analyse approfondie de la clientele cible", "em.10.clientele_cible"),
    ChapterBlueprint(11, "Personas", "em.11.personas"),
    ChapterBlueprint(12, "Analyse des risques et plan de gestion", "em.12.risques_plan_gestion"),
    ChapterBlueprint(13, "Cartographie des risques externes", "em.13.cartographie_risques"),
    ChapterBlueprint(
        14, "Analyse de la rentabilite et de la viabilite", "em.14.rentabilite_viabilite"
    ),
    ChapterBlueprint(15, "Graphiques et tableaux visuels", "em.15.graphiques_tableaux"),
    ChapterBlueprint(16, "Analyse de l'offre et de la demande", "em.16.offre_demande"),
    ChapterBlueprint(17, "Analyse geographique avancee", "em.17.geographique_avancee"),
    ChapterBlueprint(18, "Analyse SWOT complete", "em.18.swot"),
    ChapterBlueprint(19, "Analyse strategique et recommandations finales", "em.19.recommandations"),
    ChapterBlueprint(20, "Conclusion analytique et lecture synthetique", "em.20.conclusion"),
    ChapterBlueprint(
        21,
        "Annexe - Reponses aux questions du brief",
        "em.21.annexe_brief",
        SectionKind.ANNEXE,
    ),
    ChapterBlueprint(22, "Sources et methodologie", "em.22.sources", SectionKind.SOURCES),
)


# Source de verite EC : "PROMPT FINAL VERSION 3 EM_EC" (sommaire p.54-55) +
# "ETUDE DE LA CONCURRENCE VIVIEN". 8 chapitres canoniques + fiche projet en
# ouverture. La "base consolidee des concurrents" est integree au chapitre 1.
# Ne PAS inventer de chapitres.
COMPETITOR_STUDY_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    ChapterBlueprint(0, "Fiche projet", "ec.00.fiche_projet", SectionKind.OPENING),
    ChapterBlueprint(1, "Identification des concurrents", "ec.01.identification"),
    ChapterBlueprint(2, "Classement et analyse qualitative", "ec.02.classement_qualitatif"),
    ChapterBlueprint(3, "Approfondissement strategique", "ec.03.approfondissement"),
    ChapterBlueprint(
        4, "Positionnement recommande et annexes strategiques", "ec.04.positionnement_annexes"
    ),
    ChapterBlueprint(
        5, "Matrice de positionnement concurrentiel et zones strategiques",
        "ec.05.matrice_positionnement",
    ),
    ChapterBlueprint(
        6, "Estimation des chiffres d'affaires et parts de marche", "ec.06.parts_de_marche"
    ),
    ChapterBlueprint(7, "Conclusion analytique et graphiques", "ec.07.conclusion_graphiques"),
    ChapterBlueprint(
        8,
        "Annexe - Reponses aux demandes specifiques du client",
        "ec.08.annexe_brief",
        SectionKind.ANNEXE,
    ),
)


# ---------------------------------------------------------------------------
# Business Plan (BP)
# Structure pro francophone standard + consignes EVKHA (donnees chiffrees,
# ton mentor). Le chapitrage exact de la methode EVKHA sera confirme avec
# les documents du Drive (https://drive.google.com/…) — TODO: aligner
# apres acces. En attendant on applique la structure canonique BP France.
# ---------------------------------------------------------------------------
BUSINESS_PLAN_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    ChapterBlueprint(0, "Fiche projet", "bp.00.fiche_projet", SectionKind.OPENING),
    ChapterBlueprint(1, "Resume executif", "bp.01.resume_executif"),
    ChapterBlueprint(
        2, "Presentation du porteur de projet et de l'equipe", "bp.02.porteur_equipe"
    ),
    ChapterBlueprint(3, "Description du projet et de l'offre", "bp.03.description_offre"),
    ChapterBlueprint(4, "Analyse du marche cible", "bp.04.marche_cible"),
    ChapterBlueprint(5, "Analyse concurrentielle", "bp.05.concurrentielle"),
    ChapterBlueprint(6, "Strategie commerciale et marketing", "bp.06.strategie_commerciale"),
    ChapterBlueprint(7, "Modele economique et sources de revenus", "bp.07.modele_economique"),
    ChapterBlueprint(8, "Plan operationnel et organisationnel", "bp.08.plan_operationnel"),
    ChapterBlueprint(9, "Previsions financieres sur 3 ans", "bp.09.previsions_financieres"),
    ChapterBlueprint(
        10, "Plan de financement et besoins en capital", "bp.10.plan_financement"
    ),
    ChapterBlueprint(
        11, "Analyse des risques et plan de contingence", "bp.11.risques_contingence"
    ),
    ChapterBlueprint(
        12, "Calendrier de developpement et jalons", "bp.12.calendrier_jalons"
    ),
    ChapterBlueprint(
        13,
        "Annexes et reponses aux demandes specifiques",
        "bp.13.annexes",
        SectionKind.ANNEXE,
    ),
)

# ---------------------------------------------------------------------------
# Strategie Business (STR)
# Structure diagnostic-choix-action conforme aux standards du conseil
# strategique. Meme note TODO Drive que BP.
# ---------------------------------------------------------------------------
BUSINESS_STRATEGY_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    ChapterBlueprint(0, "Fiche projet", "str.00.fiche_projet", SectionKind.OPENING),
    ChapterBlueprint(1, "Diagnostic interne", "str.01.diagnostic_interne"),
    ChapterBlueprint(2, "Analyse de l'environnement externe (PESTEL)", "str.02.pestel"),
    ChapterBlueprint(3, "Analyse concurrentielle strategique", "str.03.concurrentielle"),
    ChapterBlueprint(4, "Vision et objectifs strategiques", "str.04.vision_objectifs"),
    ChapterBlueprint(5, "Choix de positionnement strategique", "str.05.positionnement"),
    ChapterBlueprint(6, "Strategie d'entree sur le marche", "str.06.entree_marche"),
    ChapterBlueprint(7, "Strategie de croissance et developpement", "str.07.croissance"),
    ChapterBlueprint(
        8,
        "Strategie de differentiation et avantage concurrentiel",
        "str.08.differentiation",
    ),
    ChapterBlueprint(9, "Plan d'action operationnel", "str.09.plan_action"),
    ChapterBlueprint(10, "Indicateurs de performance (KPIs)", "str.10.kpis"),
    ChapterBlueprint(
        11, "Risques strategiques et scenarios", "str.11.risques_scenarios"
    ),
    ChapterBlueprint(
        12,
        "Conclusion, recommandations et prochaines etapes",
        "str.12.conclusion",
        SectionKind.ANNEXE,
    ),
)

_BLUEPRINTS: dict[str, tuple[ChapterBlueprint, ...]] = {
    DeliverableType.MARKET_STUDY: MARKET_STUDY_CHAPTERS,
    DeliverableType.COMPETITOR_STUDY: COMPETITOR_STUDY_CHAPTERS,
    DeliverableType.BUSINESS_PLAN: BUSINESS_PLAN_CHAPTERS,
    DeliverableType.BUSINESS_STRATEGY: BUSINESS_STRATEGY_CHAPTERS,
}


def chapters_for_deliverable(deliverable_type: str) -> tuple[ChapterBlueprint, ...]:
    blueprint = _BLUEPRINTS.get(deliverable_type)
    if blueprint is None:
        msg = f"No chapter blueprint configured for deliverable type: {deliverable_type}"
        raise ValueError(msg)
    return blueprint
