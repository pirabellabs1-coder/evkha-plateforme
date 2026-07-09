from __future__ import annotations

import re

from django.utils import timezone

from intake.models import IntakeSubmission
from integrations.claude import _DEFAULT_MAX_TOKENS, ClaudeClient, get_claude_client
from monitoring.models import IncidentSeverity, OperationalIncident

from .blueprints import get_blueprint
from .coherence import (
    extract_and_lock_chiffres_cles,
    seed_locked_facts_from_variables,
)
from .cost import CostBudgetExceededError, max_tokens_for_job, record_chapter_cost
from .models import ChapterGeneration, ChapterStatus, GenerationJob, JobStatus
from .prompt_library import PHASE0_PROMPTS
from .prompts import build_chapter_prompt, build_section_prompt, build_system_prompt
from .qa import detect_violations, repair_rule_based

_SUMMARY_MAX_CHARS = 150
_SOURCES_SPLIT = re.compile(r"\n\s*sources\b", re.IGNORECASE)


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


def _build_brief(variables: dict[str, object]) -> str:
    """Extrait les champs client du brief sous forme de bloc texte.

    Renvoie une chaîne vide si aucun champ pertinent n'est renseigné.
    """
    lines: list[str] = []
    if demandes := str(variables.get("DEMANDES_SPECIFIQUES", "")).strip():
        lines.append(f"DEMANDES_SPECIFIQUES : {demandes}")
    if elements := str(variables.get("ELEMENTS_A_RETENIR", "")).strip():
        lines.append(f"ELEMENTS_A_RETENIR : {elements}")
    if concurrents := str(variables.get("CONCURRENTS", "")).strip():
        lines.append(f"CONCURRENTS : {concurrents}")
    return "\n".join(lines)


def _generate_phase0_plan(
    job: GenerationJob,
    variables: dict[str, object],
    *,
    client: ClaudeClient,
) -> str:
    """Appel Haiku pré-génération : plan structuré verrouillé (concurrents, chiffres, brief).

    Résultat stocké dans job.phase0_plan et retourné pour injection dans
    le system prompt de chaque chapitre.
    Coût indicatif : ~€0.005 (Haiku, prompt court).
    """
    plan_prompt = PHASE0_PROMPTS.get(job.deliverable_type)
    if not plan_prompt:
        return ""

    secteur = str(variables.get("SECTEUR", "")).strip()
    pays = str(variables.get("PAYS", "")).strip()
    projet = str(variables.get("PROJET", "")).strip()
    brief = _build_brief(variables)

    context_lines = []
    if secteur:
        context_lines.append(f"SECTEUR : {secteur}")
    if pays:
        context_lines.append(f"PAYS : {pays}")
    if projet:
        context_lines.append(f"PROJET : {projet}")
    if brief:
        context_lines.append(brief)
    context_block = "\n".join(context_lines)

    prompt = f"{context_block}\n\n{plan_prompt}"
    system = (
        "Tu es un planificateur structuré. Produis uniquement le plan demandé, "
        "sans introduction ni commentaire. Sois précis, factuel, exploitable."
    )
    result = client.complete(system=system, prompt=prompt, max_tokens=1024, model="claude-haiku")
    plan = result.content.strip()

    job.phase0_plan = plan
    job.save(update_fields=["phase0_plan", "updated_at"])
    return plan


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
    brief = _build_brief(variables)

    # Phase 0 : plan verrouillé (concurrents, chiffres, brief) — appel Haiku unique.
    # Ignoré si le job a déjà un plan (reprise) ou si le type n'a pas de prompt Phase 0.
    if not job.phase0_plan:
        try:
            _generate_phase0_plan(job, variables, client=client)
        except Exception:  # noqa: BLE001 - Phase 0 non-fatale : la génération continue sans plan
            pass

    system_prompt = build_system_prompt(
        job.deliverable_type, country=country, brief=brief, plan=job.phase0_plan
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
