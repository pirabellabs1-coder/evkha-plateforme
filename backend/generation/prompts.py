from __future__ import annotations

from catalog.models import DeliverableType
from intake.models import IntakeSubmission

from .blueprints import SECTION_MAX_WORDS, get_blueprint
from .context import build_context
from .geography import geographic_consigne_for
from .models import ChapterGeneration
from .prompt_library import prompt_instruction

# Regles d'or editoriales communes (Consignes d'ecriture EVKHA). Le rendu doit
# rester "client" : aucun marqueur de pipeline ("Etape", "Point de controle",
# "Verification", "Prompt a utiliser"). Le Rendering Engine les filtre aussi,
# mais on l'interdit des l'amont.
_CHARTER = (
    "Charte editoriale EVKHA (a appliquer sans exception) :\n"
    "TON : Professionnel mais chaleureux. Expert qui explique sans jargon "
    "inutile. Mentor qui dit les verites sans complaisance. Concret et "
    "applicable. Direct sans etre familier. Le porteur doit reconnaitre le "
    "document comme personnalise a sa situation.\n"
    "DONNEES : Chiffrees, sourcees, concretes et exploitables. Aucune "
    "generalite, aucune theorie inutile. Si une donnee est incertaine, "
    "declare la fourchette et la source. "
    "PERIODE DE REFERENCE OBLIGATOIRE : les donnees de marche doivent couvrir "
    "la periode 2021-2026. Inclure systematiquement des chiffres 2025 et 2026 "
    "(estimations et projections argumentees acceptees). Ne jamais s'arreter a "
    "2024 : les etudes livrees en 2026 doivent refleter la realite actuelle.\n"
    "COMPLETUDE ABSOLUE (regle prioritaire) : tu dois toujours traiter la "
    "TOTALITE des elements demandes dans une section — tous les concurrents, "
    "toutes les rubriques, toutes les parties d'une liste. Ne jamais interrompre "
    "une liste a mi-parcours ni passer a la suite avant d'avoir couvert le "
    "dernier element. Si la densite depasse la cible indicative, condense le "
    "style mais ne coupe jamais un developpement en cours. L'ordre de priorite "
    "est : completude > densite > limite de mots.\n"
    "DENSITE ET LONGUEUR : chaque chapitre doit etre substantiel (minimum 4 a 6 "
    "paragraphes ou equivalent). L'etude complete cible 80 pages. Ne jamais "
    "tronquer un developpement : si un point merite 3 paragraphes, les ecrire "
    "tous. Privilegier la profondeur a la survol.\n"
    "SOURCES : Une seule section Sources en toute fin de document. Ne jamais "
    "integrer les references au fil du texte, dans les paragraphes ou a la "
    "fin des sections intermediaires.\n"
    "ENCADRES MENTOR (a inserer en cloture des chapitres strategiques) : "
    "- Diamant (ce qu'il faut comprendre) : lecture directe de l'enjeu reel. "
    "- Fleche (ce qu'il faut envisager) : piste d'action concrete. "
    "- Point d'exclamation (Attention) : le piege classique a eviter. "
    "- Coche (Action concrete) : feuille de route ou chiffres a retenir. "
    "Pas plus de 3 encadres mentor d'affilee dans un meme chapitre.\n"
    "INTERDICTIONS ABSOLUES : jamais d'emojis, de ton vendeur, de "
    "formulations typiques IA conversationnelle ('il apparait que', 'on peut "
    "observer', 'il convient de noter', 'dynamique porteuse'). Jamais de "
    "vocabulaire pipeline interne ('Etape', 'Point de controle', 'Validation', "
    "'Verification finale', 'Prompt a utiliser', 'CONTEXTE A REINJECTER', "
    "'Cas 1', 'Livrable automatise', 'Pipeline'). Ne jamais ecrire 'nous "
    "n\\'avons pas trouve de donnees' ou 'les donnees sont indisponibles' : "
    "produire une estimation argumentee.\n"
    "TYPOGRAPHIE (regle stricte) : JAMAIS d'em-dash (—) ni d'en-dash (–) "
    "dans le texte redige. Ce sont des signatures IA immediatement reperees "
    "par les lecteurs professionnels. Utilise a la place : une virgule pour "
    "les incises courtes, un point-virgule pour les propositions liees, deux "
    "points pour introduire une precision, ou une nouvelle phrase. Le tiret "
    "simple (-) reste autorise pour les mots composes uniquement."
)

_EM_ROLE = (
    "Tu es un analyste senior expert en etudes de marche, dote d'une capacite "
    "avancee a croiser des sources fiables (primaires et secondaires), a "
    "analyser en profondeur des donnees quantitatives et qualitatives, et a "
    "delivrer des recommandations strategiques concretes et actionnables. Tu "
    "maitrises la collecte de donnees internationales, europeennes et locales, "
    "et sais identifier les dynamiques sectorielles, les tendances emergentes, "
    "les risques et opportunites avec precision."
)

_EC_ROLE = (
    "Tu es un expert mondial en strategie concurrentielle, specialise dans les "
    "marches internationaux et locaux. Tu maitrises les outils utilises par les "
    "cabinets d'analyse strategique : identification fine des concurrents, "
    "cartographie concurrentielle, analyse SWOT concurrentielle, estimation des "
    "parts de marche, benchmark digital, analyse de positionnement, veille "
    "innovation et strategie RSE, lecture des avis clients comme signal "
    "strategique. Tu produis des analyses exploitables et decisionnelles."
)

_BP_ROLE = (
    "Tu es un expert en creation d'entreprise et en business plans "
    "professionnels, capable de produire des livrables de niveau cabinet de "
    "conseil destines aux banques, investisseurs, incubateurs et partenaires "
    "institutionnels. Tu ecris le business plan comme si le porteur de projet "
    "en etait lui-meme l'auteur : le client doit pouvoir s'approprier le "
    "document sans reecriture, le presenter a son banquier en confiance, et y "
    "reconnaitre son projet, ses mots, sa vision. Tu construis un recit "
    "entrepreneurial coherent et finançable."
)

_STR_ROLE = (
    "Tu es un consultant senior en strategie d'entreprise, specialiste du "
    "pilotage strategique des TPE et PME. Tu produis des strategies business "
    "professionnelles qui aident un dirigeant a piloter avec une vision claire : "
    "sortir d'une logique reactive, prioriser les bons leviers, structurer une "
    "croissance coherente et soutenable. Ton approche est centree sur les "
    "arbitrages strategiques reels, pas sur des conseils generiques. "
    "Tu ecris comme un consultant experimente qui explique intelligemment, "
    "non comme un rapport academique."
)

_ROLES: dict[str, str] = {
    DeliverableType.MARKET_STUDY: _EM_ROLE,
    DeliverableType.COMPETITOR_STUDY: _EC_ROLE,
    DeliverableType.BUSINESS_PLAN: _BP_ROLE,
    DeliverableType.BUSINESS_STRATEGY: _STR_ROLE,
}


def build_system_prompt(
    deliverable_type: str,
    country: str = "",
    plan: str = "",
) -> str:
    role = _ROLES.get(deliverable_type, _EM_ROLE)
    geo = geographic_consigne_for(country) if country else ""
    parts = [role, _CHARTER]
    if geo:
        parts.append(geo)
    if plan:
        # plan contient : concurrents client (liste verrouillée), exigences verbatim,
        # structure des sous-sections obligatoires — tout avec "RÈGLE ABSOLUE".
        parts.append(plan)
    return "\n\n".join(parts)


def _country_for(chapter: ChapterGeneration) -> str:
    submission = IntakeSubmission.objects.filter(order=chapter.job.order).first()
    if submission is None:
        return ""
    return str(submission.normalized_variables.get("PAYS", "")).strip()


def _word_limit_footer(max_words: int) -> str:
    """Contrainte de complétude + densité injectée en fin de prompt.

    Formulation avec ordre de priorité explicite : complétude AVANT densité.
    Évite que Claude s'arrête après le 6e concurrent parce qu'il approche
    de la limite de mots — la vraie erreur à éviter.
    """
    if not max_words:
        return ""
    return (
        f"\n\n[CONSIGNE IMPÉRATIVE DE COMPLÉTUDE ET DENSITÉ]\n"
        f"PRIORITÉ 1 — COMPLÉTUDE : traite TOUS les éléments demandés dans "
        f"cette section (tous les concurrents, toutes les rubriques, toutes "
        f"les parties de la liste). Ne jamais interrompre une liste avant "
        f"le dernier élément. La complétude prime sur toute autre contrainte.\n"
        f"PRIORITÉ 2 — DENSITÉ : budget indicatif de {max_words} mots. "
        "Si la complétude nécessite légèrement plus, c'est acceptable. "
        "Si tu approches de la limite, condense ton style (phrases plus "
        "courtes, moins de transitions) mais ne saute aucun élément.\n"
        "PRIORITÉ 3 — CLÔTURE : ferme toujours toutes tes balises HTML "
        "avant de terminer. Ne laisse jamais une structure ouverte."
    )


def build_chapter_prompt(chapter: ChapterGeneration) -> str:
    """Compose le prompt utilisateur : contexte (Context Engine) + consigne chapitre."""
    context = build_context(chapter)
    instruction = prompt_instruction(chapter.prompt_key)
    bp = get_blueprint(chapter.job.deliverable_type, chapter.chapter_number)
    word_limit = _word_limit_footer(bp.max_words if bp else 0)
    return (
        f"{context}\n\n"
        "CONSIGNE_DU_CHAPITRE :\n"
        f"{instruction}"
        f"{word_limit}\n\n"
        "Rends uniquement le contenu final destine au client, sans repeter ces "
        "consignes."
    )


def build_section_prompt(
    chapter: ChapterGeneration, section_key: str, previous_context: str = ""
) -> str:
    """Prompt pour une section d'un chapitre en mode chunk generation.

    Meme contexte que le chapitre complet, mais instruction ciblee sur
    un sous-perimetre precis pour maximiser la densite par appel API.

    Le budget max_words est d'abord cherche dans SECTION_MAX_WORDS (table
    de surcharge par cle de section) avant de fallback sur bp.max_words.
    Certaines sections (ec.02.a.directs, ec.03.a.directs) couvrent 8
    concurrents et necessitent un budget bien superieur au chapitre-parent.
    """
    context = build_context(chapter)
    instruction = prompt_instruction(section_key)
    bp = get_blueprint(chapter.job.deliverable_type, chapter.chapter_number)
    # Priorite : surcharge par section → budget chapitre → 0 (pas de contrainte)
    section_mw = SECTION_MAX_WORDS.get(section_key) or (bp.max_words if bp else 0)
    word_limit = _word_limit_footer(section_mw)
    previous_block = ""
    if previous_context:
        # Tail-slice : on garde la FIN (section précédente adjacente) qui est
        # celle que Claude risque le plus de répéter. `[:4000]` gardait le
        # début (section 1), invisible pour section 3 qui suit section 2.
        previous_block = (
            "\n\nSECTIONS_PRECEDENTES (déjà rédigées — ne pas répéter, "
            "assurer la continuité) :\n"
            + previous_context[-4000:]
            + "\n"
        )
    return (
        f"{context}\n\n"
        f"CHAPITRE_PARENT: {chapter.chapter_number}. {chapter.chapter_title}"
        f"{previous_block}\n\n"
        "SECTION_A_GENERER :\n"
        f"{instruction}"
        f"{word_limit}\n\n"
        "Rends uniquement le contenu de cette section, destine au client. "
        "Ne repete pas les consignes ni les donnees deja traitees dans les "
        "sections precedentes de ce chapitre."
    )
