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


def chapters_for_deliverable(deliverable_type: str) -> tuple[ChapterBlueprint, ...]:
    if deliverable_type == DeliverableType.MARKET_STUDY:
        return MARKET_STUDY_CHAPTERS
    msg = f"No chapter blueprint configured for deliverable type: {deliverable_type}"
    raise ValueError(msg)
