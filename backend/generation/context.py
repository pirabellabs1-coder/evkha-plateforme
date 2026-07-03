from __future__ import annotations

import json

from django.utils import timezone

from intake.models import IntakeSubmission

from .coherence import locked_facts_as_context
from .models import ChapterGeneration

ROLE_LINE = (
    "ROLE: Methode EVKHA, ton mentor, rendu client sans balises internes "
    "(jamais 'Etape', 'Point de controle' ni vocabulaire pipeline). "
    "Si VARIABLES_PROJET contient CONTEXTE_ETUDE_PRECEDENTE, appuie-toi sur "
    "ce resume d'une etude ou d'un document deja produit pour ce client pour "
    "rester coherent avec son contenu et eviter les repetitions, sans le "
    "recopier tel quel. "
    "Quand une instruction de chapitre fournit un pattern HTML/CSS (tableau, "
    "grille, graphique en barres), tu DOIS produire ce bloc HTML rempli avec "
    "les donnees reelles du projet : ne le remplace jamais par une simple "
    "description textuelle equivalente, meme si cela demande de rester concis "
    "dans le texte qui l'entoure."
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

    return "\n\n".join(
        [
            ROLE_LINE,
            _date_line(),
            f"VARIABLES_PROJET: {json.dumps(variables, ensure_ascii=False, sort_keys=True)}",
            f"FICHE_SECTORIELLE:\n{fiche_sectorielle}",
            f"FAITS_VERROUILLES:\n{locked_facts_as_context(job)}",
            "RESUME_OPERATIONNEL_PRECEDENT:\n" + ("\n".join(summary_lines) or "Aucun."),
            f"CHAPITRE_CIBLE: {chapter.chapter_number}. {chapter.chapter_title}",
            f"PROMPT_KEY: {chapter.prompt_key}",
        ]
    )
