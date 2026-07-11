from __future__ import annotations

import re

from django.utils import timezone

from intake.models import IntakeSubmission
from integrations.claude import _DEFAULT_MAX_TOKENS, ClaudeClient, get_claude_client
from monitoring.models import IncidentSeverity, OperationalIncident

from .blueprints import chapters_for_deliverable, get_blueprint
from .coherence import (
    extract_and_lock_chiffres_cles,
    seed_locked_facts_from_variables,
)
from .cost import CostBudgetExceededError, max_tokens_for_job, record_chapter_cost
from .models import ChapterGeneration, ChapterStatus, GenerationJob, JobStatus
from .prompts import build_chapter_prompt, build_section_prompt, build_system_prompt
from .qa import detect_violations, repair_rule_based

_SUMMARY_MAX_CHARS = 320
_SOURCES_SPLIT = re.compile(r"\n\s*sources\b", re.IGNORECASE)

# Em-dash et en-dash sont des signatures IA immediatement reperees par les
# lecteurs professionnels. La consigne prompt (INTERDICTIONS ABSOLUES) demande
# a Claude de les eviter, mais il en glisse regulierement. Ce regex les
# elimine systematiquement en post-processing : remplace " — " et " – " par
# ", " ; les usages isoles ("- word") sont aussi convertis. Le tiret court "-"
# reste intact pour les mots composes (self-stockage, ordre-du-jour...).
_AI_TELL_DASHES = re.compile(r"\s*[—–]\s*")


def _strip_ai_tell_dashes(content: str) -> str:
    """Retire les em-dashes / en-dashes generes par Claude.

    Ceinture-bretelles avec la regle typographique injectee dans le system
    prompt : garantit 100% de couverture meme si Claude ignore la consigne
    (comportement observe en pratique sur les modeles Sonnet/Opus).
    """
    return _AI_TELL_DASHES.sub(", ", content)


class GenerationRunError(RuntimeError):
    """Echec irrecuperable d'un cycle de generation (au moins un chapitre KO)."""


def _operational_summary(content: str) -> str:
    """Resume operationnel court (Context Engine : jamais le chapitre brut).

    On retire le bloc Sources puis on tronque proprement sur une fin de phrase.
    """
    body = _SOURCES_SPLIT.split(content, maxsplit=1)[0].strip()
    body = " ".join(body.split())
    if len(body) <= _SUMMARY_MAX_CHARS:
        return body
    truncated = body[:_SUMMARY_MAX_CHARS]
    cut = truncated.rfind(". ")
    if cut > 80:
        return truncated[: cut + 1]
    return truncated.rstrip() + "..."


def _variables_for(job: GenerationJob) -> dict[str, object]:
    submission = IntakeSubmission.objects.filter(order=job.order).first()
    return submission.normalized_variables if submission else {}


def _build_phase0_plan(job: GenerationJob, variables: dict[str, object]) -> str:
    """Plan pré-génération déterministe, sans recopier le brief client.

    Historique : ce plan listait auparavant tous les concurrents, exigences et
    sous-sections avec des "RÈGLE ABSOLUE". Deux problèmes majeurs identifiés :
    1. Duplication : VARIABLES_PROJET (context.py) sérialise déjà tout le brief
       dans le user prompt. Ré-émettre dans le system prompt coûte ~1500 tok/appel
       × 30 appels = ~45k tok/job = ~€0.12/job pour zéro info nouvelle.
    2. Contradiction : "traiter les N concurrents dans l'ordre exact" écrasait
       `ec.01.identification` qui dit "sélectionne les 8 plus pertinents". Prompts
       contradictoires → Claude sur-focalise sur les concurrents et zappe
       d'autres sous-parties (ex. chap 6.2 EC absent).

    Fix : bloc court (~350 chars, cachable) qui rappelle l'importance du brief
    SANS lister ni contraindre l'ordre. La sélection/priorisation reste
    gouvernée par les prompts individuels du prompt_library.
    """
    if not chapters_for_deliverable(job.deliverable_type):
        return ""

    has_brief = any(
        _var(variables, k) for k in ("CONCURRENTS", "DEMANDES_SPECIFIQUES", "ELEMENTS_A_RETENIR")
    )
    if not has_brief:
        return ""

    return (
        "PLAN VERROUILLÉ — CONTRAINTES DE GÉNÉRATION\n"
        "- Le brief client (CONCURRENTS, DEMANDES_SPECIFIQUES, ELEMENTS_A_RETENIR) "
        "est transmis une seule fois via VARIABLES_PROJET dans le user prompt.\n"
        "- Pour les concurrents, applique la consigne du chapitre cible : "
        "sélectionner, compléter ou ordonner selon ce que demande CE chapitre.\n"
        "- Pour les chapitres découpés, traite intégralement la SECTION_A_GENERER "
        "courante ; les autres sections sont pilotées par leurs appels dédiés.\n"
        "- Ne survole aucune demande spécifique du brief."
    )


def _var(v: dict[str, object], k: str) -> str:
    """Lit une variable normalisée en gérant les valeurs list-valued de Tally.

    Tally peut envoyer un champ multi-select comme list ; intake/services.py
    stocke la valeur brute sans coercion. str([...]) produit du charabia
    (crochets + quotes) — on rejoint proprement avec ', ' à la place.
    """
    raw = v.get(k)
    if raw is None:
        return ""
    if isinstance(raw, list):
        return ", ".join(str(x).strip() for x in raw if str(x).strip())
    return str(raw).strip()


def run_generation_job(
    job: GenerationJob,
    *,
    client: ClaudeClient | None = None,
) -> GenerationJob:
    """Genere tous les chapitres d'un job dans l'ordre.

    Resumable : les chapitres deja DONE sont ignores. Garde-fous : budget cout
    (regle d'or #1) et coherence (faits verrouilles). Tout echec marque le job
    FAILED, ouvre un incident operationnel et leve une exception.
    """
    client = client or get_claude_client()

    job.status = JobStatus.RUNNING
    if job.started_at is None:
        job.started_at = timezone.now()
    job.error_message = ""
    job.save(update_fields=["status", "started_at", "error_message", "updated_at"])

    variables = _variables_for(job)
    seed_locked_facts_from_variables(job, variables)
    country = str(variables.get("PAYS", "")).strip()

    # Phase 0 : rappel court des exigences client. Garde `if not job.phase0_plan` :
    # sur une relance avec chapitres partiellement DONE, on préserve le plan
    # initial pour ne pas générer les chapitres restants avec un plan divergent
    # (ex. brief édité entre deux runs).
    if not job.phase0_plan:
        phase0_plan = _build_phase0_plan(job, variables)
        if phase0_plan:
            job.phase0_plan = phase0_plan
            job.save(update_fields=["phase0_plan", "updated_at"])
    else:
        phase0_plan = job.phase0_plan

    system_prompt = build_system_prompt(
        job.deliverable_type, country=country, plan=phase0_plan
    )

    chapters = job.chapters.exclude(status=ChapterStatus.DONE).order_by("chapter_number")
    for chapter in chapters:
        # Vérification annulation entre chaque chapitre (check DB allégé)
        job.refresh_from_db(fields=["status"])
        if job.status == JobStatus.CANCELLED:
            return job

        try:
            _generate_chapter(job, chapter, client=client, system_prompt=system_prompt)
            # QA rule-based immédiate : corrections automatiques sans appel IA.
            # Les violations critiques restantes sont traitées par le QA final (IA).
            _inline_qa_repair(chapter)
        except CostBudgetExceededError as exc:
            # L'incident budget est deja ouvert par le Cost Engine ; le chapitre
            # courant a un contenu valide. On stoppe juste le job proprement.
            GenerationJob.objects.filter(pk=job.pk).update(
                status=JobStatus.FAILED,
                error_message=str(exc),
            )
            raise
        except Exception as exc:  # noqa: BLE001 - tout echec doit etre trace + incident
            _fail(job, chapter, exc, title=f"Echec generation chapitre {chapter.chapter_number}")
            msg = f"Generation failed on chapter {chapter.chapter_number}: {exc}"
            raise GenerationRunError(msg) from exc

    # Ne pas écraser une annulation demandée pendant la dernière génération
    job.refresh_from_db(fields=["status"])
    if job.status == JobStatus.CANCELLED:
        return job

    job.status = JobStatus.DONE
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_at", "updated_at"])
    return job


def _inline_qa_repair(chapter: ChapterGeneration) -> bool:
    """QA rule-based immediate apres generation d'un chapitre.

    Applique les corrections automatiques (code fences, balises orphelines,
    marqueurs pipeline...) directement apres la generation, sans appel IA.
    Retourne True si des violations critiques persistent apres correction
    (signal pour le QA final qui pourra tenter une reparation IA).
    """
    content = chapter.content
    if not content or not content.strip():
        return True

    violations = detect_violations(content, chapter.prompt_key, chapter.chapter_number)
    if not violations:
        return False

    repaired, _fixes = repair_rule_based(content, chapter.prompt_key, chapter.chapter_number)
    if repaired != content:
        chapter.content = repaired
        chapter.save(update_fields=["content", "updated_at"])
        # Re-détection sur le contenu réparé pour savoir si des critiques subsistent
        violations = detect_violations(repaired, chapter.prompt_key, chapter.chapter_number)

    return any(v.severity == "critical" for v in violations)


def _generate_chunked(
    job: GenerationJob,
    chapter: ChapterGeneration,
    sections: tuple[str, ...],
    *,
    client: ClaudeClient,
    system_prompt: str,
    chapter_model: str | None = None,
) -> tuple[str, int, int, str | None]:
    """Genere un chapitre section par section et fusionne le contenu.

    Retourne (content, total_input_tokens, total_output_tokens, model).
    Les tokens sont accumules sur l'ensemble des sections pour que le
    Cost Engine dispose du cout reel complet du chapitre. Le budget restant
    (regle d'or #1 durcie) est reparti sur les sections de CE chapitre.
    """
    parts: list[str] = []
    total_input = 0
    total_output = 0
    last_model: str | None = None
    max_tokens = max_tokens_for_job(
        job, default_max_tokens=_DEFAULT_MAX_TOKENS, call_count=len(sections)
    )

    for section_key in sections:
        # Contexte accumulé des sections déjà générées dans ce chapitre.
        # Aide Claude à ne pas répéter et à rester cohérent entre sections.
        previous_context = "\n\n".join(parts) if parts else ""
        prompt = build_section_prompt(chapter, section_key, previous_context=previous_context)
        result = client.complete(
            system=system_prompt, prompt=prompt, max_tokens=max_tokens, model=chapter_model
        )
        parts.append(result.content)
        total_input += result.input_tokens
        total_output += result.output_tokens
        last_model = result.model

    return "\n\n".join(parts), total_input, total_output, last_model


def _generate_chapter(
    job: GenerationJob,
    chapter: ChapterGeneration,
    *,
    client: ClaudeClient,
    system_prompt: str,
) -> None:
    chapter.status = ChapterStatus.RUNNING
    chapter.error_message = ""
    chapter.save(update_fields=["status", "error_message", "updated_at"])

    blueprint = get_blueprint(job.deliverable_type, chapter.chapter_number)
    sections = blueprint.sections if blueprint else ()
    # Modele specifique au chapitre (None = herite de EVKHA_CLAUDE_MODEL).
    # Exemples : fiche_projet, annexe, sources → "claude-haiku" (structure pure).
    chapter_model = blueprint.model if blueprint else None

    if sections:
        content, total_input, total_output, model = _generate_chunked(
            job, chapter, sections, client=client, system_prompt=system_prompt,
            chapter_model=chapter_model,
        )
    else:
        prompt = build_chapter_prompt(chapter)
        max_tokens = max_tokens_for_job(job, default_max_tokens=_DEFAULT_MAX_TOKENS)
        result = client.complete(
            system=system_prompt, prompt=prompt, max_tokens=max_tokens, model=chapter_model
        )
        content, total_input, total_output, model = (
            result.content, result.input_tokens, result.output_tokens, result.model
        )

    content = _strip_ai_tell_dashes(content)
    chapter.content = content
    chapter.operational_summary = _operational_summary(content)
    chapter.status = ChapterStatus.DONE
    chapter.save(update_fields=["content", "operational_summary", "status", "updated_at"])

    # §5 cadrage : verrouille TCAC + taille de marche au passage. Les conflits
    # sont traites comme incidents MEDIUM (non-fatals) par upsert_locked_fact.
    extract_and_lock_chiffres_cles(job, chapter.chapter_number, content)

    record_chapter_cost(
        chapter=chapter,
        input_tokens=total_input,
        output_tokens=total_output,
        model=model,
    )


def _fail(
    job: GenerationJob,
    chapter: ChapterGeneration,
    exc: Exception,
    *,
    title: str,
) -> None:
    ChapterGeneration.objects.filter(pk=chapter.pk).update(
        status=ChapterStatus.FAILED,
        error_message=str(exc),
    )
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.FAILED,
        error_message=str(exc),
    )
    OperationalIncident.objects.create(
        title=title,
        severity=IncidentSeverity.HIGH,
        job=job,
        order=job.order,
        details={"chapter_number": chapter.chapter_number, "error": str(exc)},
    )
