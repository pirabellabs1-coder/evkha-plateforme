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
    # Chunk generation : si non vide, chaque cle est generee separement puis
    # fusionnee. Cela evite les troncatures sur les chapitres denses (>4096 tokens
    # de sortie) et reduit le risque d'hallucination par manque de place.
    sections: tuple[str, ...] = ()


MARKET_STUDY_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    ChapterBlueprint(0, "Fiche projet", "em.00.fiche_projet", SectionKind.OPENING),
    ChapterBlueprint(
        1,
        "Analyse chiffrée du marché mondial et européen",
        "em.01.marche_mondial_europeen",
        sections=("em.01.a.mondial", "em.01.b.europeen"),
    ),
    ChapterBlueprint(
        2,
        "Analyse chiffrée du marché national et local / régional",
        "em.02.marche_national_local",
        sections=("em.02.a.national", "em.02.b.local"),
    ),
    ChapterBlueprint(3, "Segmentation approfondie du marché", "em.03.segmentation"),
    ChapterBlueprint(4, "Avantages et inconvénients du secteur", "em.04.avantages_inconvenients"),
    ChapterBlueprint(5, "Défis et opportunités du marché", "em.05.defis_opportunites"),
    ChapterBlueprint(6, "Analyse approfondie de la réglementation", "em.06.reglementation"),
    ChapterBlueprint(7, "Tendances du marché à court terme", "em.07.tendances_court_terme"),
    ChapterBlueprint(8, "Perspectives d'évolution à long terme", "em.08.perspectives_long_terme"),
    ChapterBlueprint(9, "Les 12 chiffres clés du marché", "em.09.douze_chiffres_cles"),
    ChapterBlueprint(
        10,
        "Analyse approfondie de la clientèle cible",
        "em.10.clientele_cible",
        sections=(
            "em.10.a.profil_besoins",
            "em.10.b.comportements",
            "em.10.c.criteres_decision",
        ),
    ),
    ChapterBlueprint(11, "Personas", "em.11.personas"),
    ChapterBlueprint(12, "Analyse des risques et plan de gestion", "em.12.risques_plan_gestion"),
    ChapterBlueprint(13, "Cartographie des risques externes", "em.13.cartographie_risques"),
    ChapterBlueprint(
        14,
        "Analyse de la rentabilité et de la viabilité",
        "em.14.rentabilite_viabilite",
        sections=(
            "em.14.a.hypotheses",
            "em.14.b.projections",
            "em.14.c.viabilite",
        ),
    ),
    ChapterBlueprint(15, "Graphiques et tableaux visuels", "em.15.graphiques_tableaux"),
    ChapterBlueprint(16, "Analyse de l'offre et de la demande", "em.16.offre_demande"),
    ChapterBlueprint(17, "Analyse géographique avancée", "em.17.geographique_avancee"),
    ChapterBlueprint(18, "Analyse SWOT complète", "em.18.swot"),
    ChapterBlueprint(
        19,
        "Analyse stratégique et recommandations finales",
        "em.19.recommandations",
        sections=("em.19.a.diagnostic", "em.19.b.plan_action"),
    ),
    ChapterBlueprint(20, "Conclusion analytique et lecture synthétique", "em.20.conclusion"),
    ChapterBlueprint(
        21,
        "Annexe - Réponses aux questions du brief",
        "em.21.annexe_brief",
        SectionKind.ANNEXE,
    ),
    ChapterBlueprint(22, "Sources et méthodologie", "em.22.sources", SectionKind.SOURCES),
)


# Source de verite EC : "PROMPT FINAL VERSION 3 EM_EC" (sommaire p.54-55) +
# "ETUDE DE LA CONCURRENCE VIVIEN". 8 chapitres canoniques + fiche projet en
# ouverture. La "base consolidee des concurrents" est integree au chapitre 1.
# Ne PAS inventer de chapitres.
COMPETITOR_STUDY_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    ChapterBlueprint(0, "Fiche projet", "ec.00.fiche_projet", SectionKind.OPENING),
    ChapterBlueprint(1, "Identification des concurrents", "ec.01.identification"),
    ChapterBlueprint(
        2,
        "Classement et analyse qualitative",
        "ec.02.classement_qualitatif",
        sections=("ec.02.a.directs", "ec.02.b.indirects"),
    ),
    ChapterBlueprint(
        3,
        "Approfondissement stratégique",
        "ec.03.approfondissement",
        sections=("ec.03.a.directs", "ec.03.b.indirects"),
    ),
    ChapterBlueprint(
        4, "Positionnement recommandé et annexes stratégiques", "ec.04.positionnement_annexes"
    ),
    ChapterBlueprint(
        5, "Matrice de positionnement concurrentiel et zones stratégiques",
        "ec.05.matrice_positionnement",
    ),
    ChapterBlueprint(
        6, "Estimation des chiffres d'affaires et parts de marché", "ec.06.parts_de_marche"
    ),
    ChapterBlueprint(7, "Conclusion analytique et graphiques", "ec.07.conclusion_graphiques"),
    ChapterBlueprint(
        8,
        "Annexe - Réponses aux demandes spécifiques du client",
        "ec.08.annexe_brief",
        SectionKind.ANNEXE,
    ),
    ChapterBlueprint(9, "Sources et méthodologie", "ec.09.sources", SectionKind.SOURCES),
)


# ---------------------------------------------------------------------------
# Business Plan (BP)
# Chapitrage officiel EVKHA V1 (spec "Systeme EVKHA Business Plans V1 FINALE
# OK TOBIAS.pdf" + squelette FIRE EVENT). Chapitres 2-11 documentes dans la
# spec V1 partielle ; chapitres 12-19 issus du squelette de reference FIRE
# EVENT (structure validee Evangeline, jan 2026). Ne PAS modifier sans
# validation d'Evangeline.
# ---------------------------------------------------------------------------
BUSINESS_PLAN_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    ChapterBlueprint(0, "Fiche projet", "bp.00.fiche_projet", SectionKind.OPENING),
    ChapterBlueprint(1, "Résumé exécutif", "bp.01.resume_executif"),
    ChapterBlueprint(2, "Présentation du porteur de projet", "bp.02.porteur_projet"),
    ChapterBlueprint(3, "Genèse du projet", "bp.03.genese_projet"),
    ChapterBlueprint(4, "Présentation de l'activité", "bp.04.activite"),
    ChapterBlueprint(5, "Positionnement et concept", "bp.05.positionnement_concept"),
    ChapterBlueprint(6, "Analyse de marché (synthèse)", "bp.06.marche_synthese"),
    ChapterBlueprint(7, "Analyse concurrentielle", "bp.07.concurrentielle"),
    ChapterBlueprint(8, "Offre commerciale", "bp.08.offre_commerciale"),
    ChapterBlueprint(
        9, "Modèle économique et Business Model Canvas", "bp.09.modele_bmc"
    ),
    ChapterBlueprint(10, "Stratégie commerciale et marketing", "bp.10.strategie_commerciale"),
    ChapterBlueprint(11, "Stratégie de développement", "bp.11.strategie_developpement"),
    ChapterBlueprint(12, "Organisation et moyens", "bp.12.organisation_moyens"),
    ChapterBlueprint(
        13, "Structure juridique et réglementaire", "bp.13.structure_juridique"
    ),
    ChapterBlueprint(
        14, "Investissements et besoins au démarrage", "bp.14.investissements"
    ),
    ChapterBlueprint(15, "Plan de financement initial", "bp.15.plan_financement"),
    ChapterBlueprint(
        16, "Prévisionnel financier (synthèse)", "bp.16.previsionnel_financier"
    ),
    ChapterBlueprint(17, "Budget de trésorerie", "bp.17.budget_tresorerie"),
    ChapterBlueprint(
        18, "Risques et facteurs de sécurisation", "bp.18.risques_securisation"
    ),
    ChapterBlueprint(19, "Conclusion", "bp.19.conclusion"),
    ChapterBlueprint(20, "Annexes", "bp.20.annexes", SectionKind.ANNEXE),
    ChapterBlueprint(21, "Sources et méthodologie", "bp.21.sources", SectionKind.SOURCES),
)

# ---------------------------------------------------------------------------
# Strategie Business (STR)
# Chapitrage officiel EVKHA V1 (spec "SYSTEME EVKHA STRATEGIES BUSINESS
# AUTOMATISEES V1"). 17 chapitres analytiques (0-16 dans la spec, renumerotes
# 1-17 ici pour laisser 0 a la fiche projet EVKHA) + sources.
# Ne PAS modifier sans validation d'Evangeline.
# ---------------------------------------------------------------------------
BUSINESS_STRATEGY_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    ChapterBlueprint(0, "Fiche projet", "str.00.fiche_projet", SectionKind.OPENING),
    ChapterBlueprint(1, "Introduction stratégique générale", "str.01.introduction"),
    ChapterBlueprint(2, "Lecture stratégique du projet", "str.02.lecture_strategique"),
    ChapterBlueprint(3, "Analyse du positionnement actuel", "str.03.positionnement_actuel"),
    ChapterBlueprint(
        4, "Analyse des forces structurelles du business", "str.04.forces_structurelles"
    ),
    ChapterBlueprint(
        5,
        "Analyse des contraintes et fragilités structurelles",
        "str.05.contraintes_fragilites",
    ),
    ChapterBlueprint(
        6, "Enjeux stratégiques du positionnement", "str.06.enjeux_positionnement"
    ),
    ChapterBlueprint(
        7, "Définition des verticales stratégiques", "str.07.verticales_strategiques"
    ),
    ChapterBlueprint(
        8, "Proposition de valeur et différenciation", "str.08.valeur_differenciation"
    ),
    ChapterBlueprint(
        9, "Lecture stratégique des offres actuelles", "str.09.offres_actuelles"
    ),
    ChapterBlueprint(10, "Architecture d'offre cible", "str.10.architecture_offre"),
    ChapterBlueprint(
        11, "Logique de montée en gamme et valeur perçue", "str.11.montee_gamme"
    ),
    ChapterBlueprint(
        12, "Analyse des canaux et acquisition actuelle", "str.12.canaux_acquisition"
    ),
    ChapterBlueprint(
        13,
        "Stratégie de visibilité et acquisition cohérente",
        "str.13.strategie_visibilite",
    ),
    ChapterBlueprint(
        14, "Lecture économique et rentabilité du modèle", "str.14.rentabilite_modele"
    ),
    ChapterBlueprint(
        15,
        "Arbitrages stratégiques et allocation des ressources",
        "str.15.arbitrages_ressources",
    ),
    ChapterBlueprint(
        16,
        "Pilotage stratégique et soutenabilité du business",
        "str.16.pilotage_soutenabilite",
    ),
    ChapterBlueprint(
        17, "Feuille de route stratégique et priorisation", "str.17.feuille_route"
    ),
    ChapterBlueprint(
        18,
        "Annexe - Réponses aux demandes spécifiques du client",
        "str.18.annexe_brief",
        SectionKind.ANNEXE,
    ),
    ChapterBlueprint(19, "Sources et méthodologie", "str.19.sources", SectionKind.SOURCES),
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


def get_blueprint(deliverable_type: str, chapter_number: int) -> ChapterBlueprint | None:
    chapters = _BLUEPRINTS.get(deliverable_type, ())
    return next((bp for bp in chapters if bp.number == chapter_number), None)
