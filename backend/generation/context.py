from __future__ import annotations

import json

from django.utils import timezone

from intake.models import IntakeSubmission

from catalog.models import DeliverableType

from .coherence import (
    chiffres_fondations_as_table,
    client_facts_as_context,
    generated_facts_as_context,
)
from .models import ChapterGeneration, GenerationJob
from .substitution import tokens_catalogue

ROLE_LINE = (
    "ROLE: Methode EVKHA, ton mentor, rendu client sans balises internes "
    "(jamais 'Etape', 'Point de controle' ni vocabulaire pipeline). "
    # On n'enumere QUE les labels reellement presents dans le contexte ci-dessous.
    # Citer un token absent (l'ancien FAITS_VERROUILLES) pour l'interdire ne
    # faisait que le reintroduire dans la fenetre du modele : interdire un mot
    # en l'ecrivant est contre-productif (audit juillet 2026).
    "Tout intitule technique ecrit en MAJUSCULES_AVEC_UNDERSCORES dans ce "
    "contexte (VARIABLES_PROJET, DONNEES_CLIENT, REPERES_DEJA_ENONCES, "
    "FICHE_SECTORIELLE, SOURCES_WEB, RESUME_OPERATIONNEL_PRECEDENT, "
    "CHAPITRE_CIBLE, PROMPT_KEY) est un repere interne : "
    "il ne doit JAMAIS apparaitre dans ta redaction, ni entre "
    "parentheses, ni cite, ni reformule en 'faits verrouilles du dossier'. "
    "Si tu dois designer l'origine d'un chiffre client, ecris 'le "
    "previsionnel fourni par le porteur' ou equivalent naturel. "
    "Si VARIABLES_PROJET contient CONTEXTE_ETUDE_PRECEDENTE, appuie-toi sur "
    "ce resume d'une etude ou d'un document deja produit pour ce client pour "
    "rester coherent avec son contenu et eviter les repetitions, sans le "
    "recopier tel quel. "
    "Quand une instruction de chapitre fournit un pattern HTML/CSS (tableau, "
    "grille, graphique en barres), tu DOIS produire ce bloc HTML rempli avec "
    "les donnees reelles du projet, en respectant EXACTEMENT la structure "
    "fournie en exemple (memes balises, memes proprietes CSS) : ne le "
    "remplace jamais par une simple description textuelle equivalente, meme "
    "si cela demande de rester concis dans le texte qui l'entoure. "
    "N'utilise JAMAIS display:grid, display:flex ni position:absolute : "
    "seuls les <table> et les <div> de largeur variable (barres) sont "
    "correctement rendus par WeasyPrint, le moteur PDF utilise en production. "
    "Si une instruction de chapitre NE fournit AUCUN pattern HTML/CSS, "
    "redige uniquement en texte/Markdown (titres, paragraphes, listes) : "
    "n'invente jamais de bloc HTML/CSS de ta propre initiative. "
    "COHERENCE ABSOLUE (regle prioritaire, non negociable) : "
    "0) HIERARCHIE DES SOURCES : les chiffres du bloc DONNEES_CLIENT "
    "(previsionnel, investissement, emprunt, taux d'occupation, verticales "
    "d'activite...) priment sur TOUTE moyenne sectorielle, benchmark ou "
    "estimation. Tu ne substitues JAMAIS un cas generique aux hypotheses "
    "reelles du client. Chaque verticale d'activite listee par le client "
    "doit etre traitee — aucune ne disparait au profit d'un modele type. "
    "1) Les blocs DONNEES_CLIENT, REPERES_DEJA_ENONCES et "
    "RESUME_OPERATIONNEL_PRECEDENT sont la VERITE de reference du dossier. "
    "Si tu evoques un chiffre ou un nom deja mentionne, tu DOIS le reprendre "
    "a l'IDENTIQUE : meme valeur exacte, meme unite, meme orthographe. "
    "2) Une variation d'un chiffre entre deux chapitres (ex : TCAC 8,4 % au "
    "chapitre 2 puis 8,5 % au chapitre 7, ou CA cible 285 000 EUR puis "
    "287 000 EUR) est une incoherence percue instantanement par un lecteur "
    "professionnel et decredibilise l'ensemble du livrable. "
    "3) Si un chiffre a besoin d'etre affine, INDIQUE explicitement qu'il "
    "s'agit d'un affinage (ex: 'apres integration des couts logistiques, "
    "l'estimation passe de 285 000 a 287 500 EUR'). Ne modifie JAMAIS "
    "silencieusement une valeur deja posee. "
    "4) Pour les etudes de concurrence : les 8 concurrents directs et 3 "
    "indirects identifies au chapitre 1 sont VERROUILLES. Chaque chapitre "
    "suivant DOIT reprendre ces 11 acteurs, exactement dans le meme ordre, "
    "avec le meme nom (meme orthographe). Aucun ajout, aucun retrait, aucune "
    "substitution possible."
)


def _date_line() -> str:
    today = timezone.now()
    return (
        f"DATE_DU_JOUR: {today.strftime('%d/%m/%Y')}. Toutes les donnees, "
        "tendances, chiffres et projections doivent etre calibres par rapport "
        "a cette date : la periode recente correspond aux 2-3 dernieres annees "
        "civiles qui la precedent, les projections/estimations portent sur les "
        "annees suivantes. Ne jamais traiter une annee anterieure a cette date "
        "comme etant l'annee en cours."
    )


def _tokens_block(job: GenerationJob) -> str:
    """Catalogue des tokens de substitution (Brique 1).

    Le modele voit le nombre deja ecrit a cote du token : il n'a donc aucune
    raison de l'estimer, et le token garantit que la valeur livree est celle du
    brief, au caractere pres.
    """
    catalogue = tokens_catalogue(job)
    if not catalogue:
        return "CHIFFRES_A_CITER: aucun chiffre client scalaire fourni."
    return (
        "CHIFFRES_A_CITER (Brique 1 — substitution automatique) :\n"
        + catalogue
        + "\n\nREGLE : pour citer l'un de ces chiffres, ecris le token entre "
        "doubles accolades (ex: {{emprunt}}), JAMAIS le nombre a la main et "
        "JAMAIS une approximation ('environ', 'de l'ordre de'). Le token est "
        "remplace automatiquement par la valeur exacte du brief avant "
        "livraison. N'invente aucun token : seuls ceux listes ci-dessus "
        "existent. Pour tout autre chiffre, rédige normalement."
    )


def build_context(chapter: ChapterGeneration) -> str:
    job = chapter.job
    submission = IntakeSubmission.objects.filter(order=job.order).first()
    variables = submission.normalized_variables if submission else {}

    previous_summaries = job.chapters.filter(
        chapter_number__lt=chapter.chapter_number,
        operational_summary__gt="",
    ).order_by("chapter_number")

    summary_lines = [
        f"Chapitre {item.chapter_number}: {item.operational_summary}" for item in previous_summaries
    ]

    # La fiche sectorielle d'adaptation est stockee dans job.context_summary et
    # reinjectee comme contexte commun a tous les chapitres (consignes EVKHA).
    fiche_sectorielle = job.context_summary or "Non encore etablie."

    # Brief de recherche web (vraies sources datees). Vide en mode stub.
    research_block = job.research_brief or (
        "Aucune source web collectee : n'invente aucune URL ni date de "
        "publication ; presente toute donnee non etablie comme une estimation."
    )

    blocs = [
        ROLE_LINE,
        _date_line(),
        f"VARIABLES_PROJET: {json.dumps(variables, ensure_ascii=False, sort_keys=True)}",
        f"FICHE_SECTORIELLE:\n{fiche_sectorielle}",
        f"SOURCES_WEB:\n{research_block}",
        "DONNEES_CLIENT (brief client, intangibles, priorite absolue):\n"
        + client_facts_as_context(job),
        _tokens_block(job),
        "REPERES_DEJA_ENONCES (chiffres deja poses dans les chapitres "
        "precedents, a reprendre a l'identique, jamais presentes comme "
        "'faits verrouilles'):\n" + generated_facts_as_context(job),
    ]

    # Manuel Evangeline §5 (juillet 2026) : la fiche projet enrichie fait
    # office de memoire de l'etude EM. Injectee EN PLUS des REPERES_DEJA_ENONCES
    # pour rendre le format tableau (colonnes Information | Valeur | Source),
    # comme le manuel le prescrit p. 6. Uniquement pour l'EM — les autres
    # livrables gardent leur socle inchange.
    if str(job.deliverable_type) == DeliverableType.MARKET_STUDY:
        blocs.append(
            "CHIFFRES_FONDATIONS (manuel §5, memoire enrichie EM):\n"
            + chiffres_fondations_as_table(job)
        )

    blocs += [
        "RESUME_OPERATIONNEL_PRECEDENT:\n" + ("\n".join(summary_lines) or "Aucun."),
        f"CHAPITRE_CIBLE: {chapter.chapter_number}. {chapter.chapter_title}",
        f"PROMPT_KEY: {chapter.prompt_key}",
    ]

    # Bloc de contexte SPECIFIQUE au type de livrable : chaque strategy peut
    # decider d'injecter un tableau de reference (EM : base chiffree
    # consolidee apres chapitres 1-2), une checklist metier, un rappel de
    # posture. Le socle commun (blocs ci-dessus) reste identique.
    from .strategies import get_strategy  # noqa: PLC0415 (import local, evite cycle)
    supplement = get_strategy(str(job.deliverable_type)).contexte_supplementaire(
        job, chapter
    )
    if supplement is not None:
        blocs.append(f"{supplement.intitule.upper()}:\n{supplement.corps}")

    return "\n\n".join(blocs)
