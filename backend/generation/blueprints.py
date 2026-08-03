from __future__ import annotations

from dataclasses import dataclass

from catalog.models import DeliverableType

# Source de verite du chapitrage EM : « Systeme EVKHA — Cheminement manuel
# d'une etude de marche » (Evangeline, juillet 2026), pp. 8-17.
# Ordre final : page de garde -> sommaire -> FICHE PROJET (ouverture) ->
# chapitres 1 a 20 -> chapitre 21 « Sources et methodologie » -> ANNEXE
# « Reponses essentielles au client » -> « Fin de l'etude ».
# 21 chapitres analytiques + fiche projet en opening + annexe (§8, pp. 33-34).
# Blocs de controle (§6 manuel) : A(1-2) B(3) C(4-5) D(6) E(7-8) F(9-11)
# G(12-14) H(15-17) I(18-20) J(21-22). Chaque bloc declenche un CHECK Sonnet
# apres generation, gere par `checks_blocs.py` (Vague 2).
# BP/EC/STR : blueprints inchanges (le manuel Evangeline ne couvre que l'EM).


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
    # Cible editoriale indicative en mots pour ce chapitre (ou par section si
    # chunked). Injectee dans le prompt utilisateur comme borne haute afin que
    # Claude planifie sa sortie dans la fenetre token allouee. 0 = pas de borne.
    # QC Evangeline #5 : c'est ce plafond qui evite la dilution en 126 pages
    # d'un sujet qui tient en 46 pages en chat direct.
    max_words: int = 0
    # Modele Claude a utiliser pour ce chapitre (alias EVKHA : "claude-sonnet").
    # None = herite de EVKHA_CLAUDE_MODEL (defaut global, actuellement
    # claude-sonnet-4-6 pour toute la pipeline — decision du 25/07/2026).
    model: str | None = None
    # Autorise l'outil d'execution de code Anthropic sur ce chapitre (Python
    # sandboxe, sans reseau). Declaratif et volontairement TRES restreint : un
    # outil s'ajoute au niveau `tools`, qui precede `system` dans la hierarchie
    # de cache, donc chaque chapitre qui l'active re-ecrit son prefixe au lieu
    # de le relire a 10 %. A ne poser que sur un chapitre dont l'arithmetique
    # est emboitee et sensible a la precision — pas sur un chapitre qui cite
    # simplement des chiffres.
    code_execution: bool = False


MARKET_STUDY_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    # Bloc opening ── fiche projet
    #
    # PAS Haiku, contrairement aux autres livrables. La fiche projet n'est pas
    # un chapitre de remplissage : le manuel p. 6 en fait « la memoire de
    # l'etude », relue avant chaque nouveau bloc, et c'est elle qui choisit les
    # 4 a 5 questions du porteur auxquelles l'etude devra repondre. Une lecture
    # faible du questionnaire ici se propage aux 21 chapitres suivants.
    # Effet de bord favorable : le cache de prompt Anthropic est par modele.
    # Avec Haiku au chapitre 0, l'entree de cache ecrite au premier appel
    # n'etait reutilisable par aucun autre chapitre, et le system prompt
    # (~5000 tokens) frolait le minimum de 4096 tokens exige par Haiku 4.5.
    ChapterBlueprint(0, "Fiche projet", "em.00.fiche_projet", SectionKind.OPENING),
    # Bloc A ── marché, géographie et chiffres-fondations
    ChapterBlueprint(
        1,
        "Marché mondial et continent pertinent",
        "em.01.marche_mondial_europeen",
        sections=("em.01.a.mondial", "em.01.b.europeen"),
        max_words=900,
    ),
    # PAS de `sections` ici, volontairement : le chapitre 2 porte le calcul
    # TAM/SAM/SOM, qui est un raisonnement arithmetique continu. Le decouper
    # en « 2.a national / 2.b local » faisait recalculer le marche accessible
    # dans un second appel qui ne voyait du premier qu'un resume de 1200
    # caracteres — d'ou les deux valeurs de SAM constatees sur le run reel
    # 010e3bf2 et le verdict « TAM, SAM et SOM incoherents ». max_words = somme
    # des deux anciennes cibles de section (1100 + 800), le volume attendu ne
    # change pas.
    # `code_execution` : SEUL chapitre du systeme a l'activer. C'est ici que
    # s'emboitent TAM, SAM, SOM a sept variables, taux d'annulation, commissions
    # et montee en charge mensuelle — soit exactement le declencheur nomme par
    # la doc de l'outil (« mathematiques non triviales : grands nombres,
    # nombreuses etapes, resultats sensibles a la precision »), et exactement le
    # premier reproche d'Evangeline sur le run 010e3bf2 (« erreurs de calcul
    # importantes »). Le modele faisait cette arithmetique en prose ; il la pose
    # maintenant dans un interpreteur.
    ChapterBlueprint(
        2,
        "Marché national, local et marché accessible",
        "em.02.marche_national_local",
        max_words=1900,
        code_execution=True,
    ),
    # Bloc B ── segmentation et alignement avec la demande
    ChapterBlueprint(3, "Segmentation approfondie", "em.03.segmentation", max_words=1800),
    # Bloc C ── présent, contraintes et opportunités futures
    ChapterBlueprint(
        4, "Avantages et contraintes structurelles du secteur",
        "em.04.avantages_inconvenients", max_words=1600
    ),
    ChapterBlueprint(
        5, "Défis et opportunités 2026-2030",
        "em.05.defis_opportunites", max_words=1600
    ),
    # Bloc D ── réglementation applicable
    ChapterBlueprint(
        6, "Réglementation, normes et conformité",
        "em.06.reglementation", max_words=1800
    ),
    # Bloc E ── tendances 2026-2027 et scénarios 2030
    ChapterBlueprint(
        7, "Tendances à court terme 2026-2027",
        "em.07.tendances_court_terme", max_words=1600
    ),
    ChapterBlueprint(
        8, "Perspectives et scénarios à horizon 2030",
        "em.08.perspectives_long_terme", max_words=1600
    ),
    # Bloc F ── chiffres clés, comportements et personas
    ChapterBlueprint(
        9, "Les 12 chiffres clés",
        "em.09.douze_chiffres_cles", max_words=1200
    ),
    ChapterBlueprint(
        10,
        "Clientèle cible et comportements d'achat",
        "em.10.clientele_cible",
        sections=(
            "em.10.a.profil_besoins",
            "em.10.b.comportements",
            "em.10.c.criteres_decision",
        ),
        max_words=800,
    ),
    ChapterBlueprint(11, "Deux personas fondés sur les données", "em.11.personas", max_words=1400),
    # Bloc G ── risques et viabilité
    ChapterBlueprint(
        12, "Risques et plan de maîtrise",
        "em.12.risques_plan_gestion", max_words=1600
    ),
    ChapterBlueprint(
        13, "Cartographie des risques externes",
        "em.13.cartographie_risques", max_words=1400
    ),
    ChapterBlueprint(
        14,
        "Potentiel de viabilité",
        "em.14.rentabilite_viabilite",
        sections=(
            "em.14.a.hypotheses",
            "em.14.b.projections",
            "em.14.c.viabilite",
        ),
        max_words=800,
    ),
    # Bloc H ── visuels, offre/demande et géographie
    ChapterBlueprint(15, "Tableau de bord visuel du marché", "em.15.graphiques_tableaux"),
    ChapterBlueprint(
        16, "Analyse de l'offre et de la demande",
        "em.16.offre_demande", max_words=1800
    ),
    ChapterBlueprint(
        17, "Analyse géographique avancée",
        "em.17.geographique_avancee", max_words=1800
    ),
    # Bloc I ── SWOT, recommandations et conclusion
    ChapterBlueprint(18, "SWOT de synthèse", "em.18.swot", max_words=1800),
    ChapterBlueprint(
        19,
        "Analyse stratégique et recommandations",
        "em.19.recommandations",
        sections=("em.19.a.diagnostic", "em.19.b.plan_action"),
        max_words=1000,
    ),
    ChapterBlueprint(
        20, "Conclusion analytique", "em.20.conclusion", max_words=1400
    ),
    # Bloc J ── sources, méthodologie et contrôle final
    ChapterBlueprint(
        21, "Sources et méthodologie", "em.21.sources_methodologie",
        SectionKind.SOURCES, model=None
    ),
    # Bloc K ── annexe des reponses essentielles
    #
    # RETABLIE. Elle avait ete supprimee sur la foi de la version precedente du
    # manuel, au motif que les CHECKs inter-blocs suffisaient a garantir que
    # « toutes les demandes du client aient une reponse identifiable ». Le
    # manuel de juillet 2026 la reinstaure explicitement (§8, pp. 33-34) : deux
    # a quatre pages, un tableau a cinq colonnes, place APRES le chapitre 21 ;
    # et son CHECK FINAL exige desormais qu'elle soit presente.
    #
    # Un CHECK verifie que la reponse EXISTE quelque part dans soixante pages.
    # L'annexe la rend TROUVABLE en une minute. Ce n'est pas la meme promesse.
    ChapterBlueprint(
        22,
        "Réponses essentielles au client — en un coup d'œil",
        "em.22.annexe_reponses",
        SectionKind.ANNEXE,
        max_words=1200,
        model=None,
    ),
)


# Source de verite EC : "PROMPT FINAL VERSION 3 EM_EC" (sommaire p.54-55) +
# "ETUDE DE LA CONCURRENCE VIVIEN". 8 chapitres canoniques + fiche projet en
# ouverture. La "base consolidee des concurrents" est integree au chapitre 1.
# Ne PAS inventer de chapitres.
COMPETITOR_STUDY_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    ChapterBlueprint(
        0, "Fiche projet", "ec.00.fiche_projet", SectionKind.OPENING, model=None
    ),
    ChapterBlueprint(1, "Identification des concurrents", "ec.01.identification", max_words=2000),
    ChapterBlueprint(
        2,
        "Classement et analyse qualitative",
        "ec.02.classement_qualitatif",
        sections=("ec.02.a.directs", "ec.02.b.indirects"),
        max_words=1200,
    ),
    ChapterBlueprint(
        3,
        "Approfondissement stratégique",
        "ec.03.approfondissement",
        sections=("ec.03.a.directs", "ec.03.b.indirects"),
        max_words=1600,
    ),
    ChapterBlueprint(
        4,
        "Positionnement recommandé et annexes stratégiques",
        "ec.04.positionnement_annexes",
        max_words=1800,
    ),
    ChapterBlueprint(
        5,
        "Matrice de positionnement concurrentiel et zones stratégiques",
        "ec.05.matrice_positionnement",
        max_words=1600,
    ),
    ChapterBlueprint(
        6,
        "Estimation des chiffres d'affaires et parts de marché",
        "ec.06.parts_de_marche",
        max_words=1400,
    ),
    ChapterBlueprint(
        7, "Conclusion analytique et graphiques", "ec.07.conclusion_graphiques", max_words=1400
    ),
    ChapterBlueprint(
        8,
        "Annexe - Réponses aux demandes spécifiques du client",
        "ec.08.annexe_brief",
        SectionKind.ANNEXE,
        model=None,
    ),
    ChapterBlueprint(
        9, "Sources et méthodologie", "ec.09.sources", SectionKind.SOURCES, model=None
    ),
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
    ChapterBlueprint(
        0, "Fiche projet", "bp.00.fiche_projet", SectionKind.OPENING, model=None
    ),
    ChapterBlueprint(1, "Résumé exécutif", "bp.01.resume_executif", max_words=1200),
    ChapterBlueprint(
        2, "Présentation du porteur de projet", "bp.02.porteur_projet", max_words=1200
    ),
    ChapterBlueprint(3, "Genèse du projet", "bp.03.genese_projet", max_words=1000),
    ChapterBlueprint(4, "Présentation de l'activité", "bp.04.activite", max_words=1400),
    ChapterBlueprint(
        5, "Positionnement et concept", "bp.05.positionnement_concept", max_words=1400
    ),
    ChapterBlueprint(6, "Analyse de marché (synthèse)", "bp.06.marche_synthese", max_words=1600),
    ChapterBlueprint(7, "Analyse concurrentielle", "bp.07.concurrentielle", max_words=1600),
    ChapterBlueprint(8, "Offre commerciale", "bp.08.offre_commerciale", max_words=1600),
    ChapterBlueprint(
        9, "Modèle économique et Business Model Canvas", "bp.09.modele_bmc", max_words=1600
    ),
    ChapterBlueprint(
        10, "Stratégie commerciale et marketing", "bp.10.strategie_commerciale", max_words=1600
    ),
    ChapterBlueprint(
        11, "Stratégie de développement", "bp.11.strategie_developpement", max_words=1400
    ),
    ChapterBlueprint(12, "Organisation et moyens", "bp.12.organisation_moyens", max_words=1400),
    ChapterBlueprint(
        13, "Structure juridique et réglementaire", "bp.13.structure_juridique", max_words=1200
    ),
    # Fusion chapitres 14+15 (demande client, juillet 2026) : reduit la
    # duplication des sections financieres liees et compresse le budget IA.
    # Chunked en 2 sections qui reutilisent les prompts existants bp.14 et
    # bp.15 : aucun contenu editorial n'est perdu.
    ChapterBlueprint(
        14,
        "Besoin au démarrage et plan de financement initial",
        "bp.14.besoin_financement",
        sections=("bp.14.investissements", "bp.15.plan_financement"),
        max_words=1250,
    ),
    # Fusion chapitres 16+17 (demande client, juillet 2026) : previsionnel
    # + tresorerie forment un tout financier, plus lisible d'un bloc.
    # Chunked en 3 sections (comptes resultats, bilan/graph, tresorerie)
    # pour eviter les troncatures sur le contenu dense (tables + graphes).
    ChapterBlueprint(
        15,
        "Prévisionnel financier et trésorerie",
        "bp.15.previsionnel_tresorerie",
        sections=(
            "bp.16.a.comptes_resultats",
            "bp.16.b.bilan_projection",
            "bp.17.budget_tresorerie",
        ),
        max_words=900,
    ),
    ChapterBlueprint(
        16, "Risques et facteurs de sécurisation", "bp.18.risques_securisation", max_words=1400
    ),
    ChapterBlueprint(17, "Conclusion", "bp.19.conclusion", max_words=1000),
    ChapterBlueprint(18, "Annexes", "bp.20.annexes", SectionKind.ANNEXE, model=None),
    ChapterBlueprint(
        19, "Sources et méthodologie", "bp.21.sources", SectionKind.SOURCES, model=None
    ),
)

# ---------------------------------------------------------------------------
# Strategie Business (STR)
# Chapitrage officiel EVKHA V1 (spec "SYSTEME EVKHA STRATEGIES BUSINESS
# AUTOMATISEES V1"). 17 chapitres analytiques (0-16 dans la spec, renumerotes
# 1-17 ici pour laisser 0 a la fiche projet EVKHA) + sources.
# Ne PAS modifier sans validation d'Evangeline.
# ---------------------------------------------------------------------------
BUSINESS_STRATEGY_CHAPTERS: tuple[ChapterBlueprint, ...] = (
    ChapterBlueprint(
        0, "Fiche projet", "str.00.fiche_projet", SectionKind.OPENING, model=None
    ),
    ChapterBlueprint(1, "Introduction stratégique générale", "str.01.introduction", max_words=1200),
    ChapterBlueprint(
        2, "Lecture stratégique du projet", "str.02.lecture_strategique", max_words=1400
    ),
    ChapterBlueprint(
        3, "Analyse du positionnement actuel", "str.03.positionnement_actuel", max_words=1600
    ),
    ChapterBlueprint(
        4,
        "Analyse des forces structurelles du business",
        "str.04.forces_structurelles",
        max_words=1800,
    ),
    ChapterBlueprint(
        5,
        "Analyse des contraintes et fragilités structurelles",
        "str.05.contraintes_fragilites",
        max_words=1600,
    ),
    ChapterBlueprint(
        6,
        "Enjeux stratégiques du positionnement",
        "str.06.enjeux_positionnement",
        max_words=1600,
    ),
    ChapterBlueprint(
        7,
        "Définition des verticales stratégiques",
        "str.07.verticales_strategiques",
        max_words=1800,
    ),
    ChapterBlueprint(
        8,
        "Proposition de valeur et différenciation",
        "str.08.valeur_differenciation",
        max_words=1600,
    ),
    ChapterBlueprint(
        9,
        "Lecture stratégique des offres actuelles",
        "str.09.offres_actuelles",
        max_words=1600,
    ),
    ChapterBlueprint(10, "Architecture d'offre cible", "str.10.architecture_offre", max_words=1600),
    ChapterBlueprint(
        11,
        "Logique de montée en gamme et valeur perçue",
        "str.11.montee_gamme",
        max_words=1400,
    ),
    ChapterBlueprint(
        12,
        "Analyse des canaux et acquisition actuelle",
        "str.12.canaux_acquisition",
        max_words=1400,
    ),
    ChapterBlueprint(
        13,
        "Stratégie de visibilité et acquisition cohérente",
        "str.13.strategie_visibilite",
        max_words=1600,
    ),
    ChapterBlueprint(
        14,
        "Lecture économique et rentabilité du modèle",
        "str.14.rentabilite_modele",
        max_words=1600,
    ),
    ChapterBlueprint(
        15,
        "Arbitrages stratégiques et allocation des ressources",
        "str.15.arbitrages_ressources",
        max_words=1600,
    ),
    ChapterBlueprint(
        16,
        "Pilotage stratégique et soutenabilité du business",
        "str.16.pilotage_soutenabilite",
        max_words=1400,
    ),
    ChapterBlueprint(
        17,
        "Feuille de route stratégique et priorisation",
        "str.17.feuille_route",
        max_words=1600,
    ),
    ChapterBlueprint(
        18,
        "Annexe - Réponses aux demandes spécifiques du client",
        "str.18.annexe_brief",
        SectionKind.ANNEXE,
        model=None,
    ),
    ChapterBlueprint(
        19, "Sources et méthodologie", "str.19.sources", SectionKind.SOURCES, model=None
    ),
)

_BLUEPRINTS: dict[str, tuple[ChapterBlueprint, ...]] = {
    DeliverableType.MARKET_STUDY: MARKET_STUDY_CHAPTERS,
    DeliverableType.COMPETITOR_STUDY: COMPETITOR_STUDY_CHAPTERS,
    DeliverableType.BUSINESS_PLAN: BUSINESS_PLAN_CHAPTERS,
    DeliverableType.BUSINESS_STRATEGY: BUSINESS_STRATEGY_CHAPTERS,
}


# Cible editoriale PAR SECTION pour les chapitres chunkes a haute densite.
# Ces valeurs REMPLACENT ChapterBlueprint.max_words dans build_section_prompt
# quand la section apparait ici. Calibrees sur : N_concurrents × mots_moyen.
#
# Pourquoi les surcharger ?  Le max_words du blueprint est concu pour des chapitres
# monolithiques. Pour ec.02.a (8 directs × 325 mots = 2600 mots) et ec.03.a
# (8 directs × 475 mots = 3800 mots), le budget chapitre est trop bas : Claude
# s'arrete au 6e concurrent avec stop_reason=end_turn (la boucle de continuation
# ne se declenche PAS car elle ne s'active que sur stop_reason=max_tokens).
SECTION_MAX_WORDS: dict[str, int] = {
    # EC chapitre 2 — classement qualitatif
    "ec.02.a.directs":   2600,  # 8 directs  × ~325 mots (3F + 3F + VA)
    "ec.02.b.indirects":  900,  # 3 indirects × ~300 mots
    # EC chapitre 3 — approfondissement strategique
    "ec.03.a.directs":   3800,  # 8 directs  × ~475 mots (5 dimensions)
    "ec.03.b.indirects": 1100,  # 3 indirects × ~335 mots + synthese comparative
    # EM chapitre 1 — analyse marche mondial/europeen
    "em.01.a.mondial":   1200,  # analyse mondiale chiffree
    "em.01.b.europeen":   900,  # analyse europeenne chiffree
    # EM chapitre 2 : plus de section, cf. le blueprint (calcul TAM/SAM/SOM
    # indivisible). La cible vit dans ChapterBlueprint.max_words.
    # EM chapitre 10 — clientele cible (3 sections)
    "em.10.a.profil_besoins":     800,  # profil et besoins
    "em.10.b.comportements":      700,  # comportements d'achat
    "em.10.c.criteres_decision":  600,  # criteres de decision
    # EM chapitre 14 — rentabilite/viabilite (3 sections)
    "em.14.a.hypotheses":  800,  # hypotheses financieres
    "em.14.b.projections": 800,  # projections chiffrees
    "em.14.c.viabilite":   600,  # viabilite et seuil
    # EM chapitre 19 — recommandations strategiques
    "em.19.a.diagnostic":  900,  # diagnostic strategique
    "em.19.b.plan_action": 800,  # plan d'action concret
    # BP chapitre 14 — besoin au demarrage et plan de financement (fusion 14+15)
    "bp.14.investissements":      1400,  # investissements initiaux + BFR
    "bp.15.plan_financement":     1100,  # plan de financement + graphique
    # BP chapitre 15 — previsionnel financier et tresorerie (fusion 16+17)
    "bp.16.a.comptes_resultats":  1000,  # comptes de resultats projetes
    "bp.16.b.bilan_projection":    800,  # bilan + graphique CA/EBITDA
    "bp.17.budget_tresorerie":    1000,  # budget de tresorerie mensuel
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
