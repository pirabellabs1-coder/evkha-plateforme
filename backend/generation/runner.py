from __future__ import annotations

import re

from django.utils import timezone
from intake.models import IntakeSubmission
from integrations.claude import ClaudeClient, get_claude_client
from monitoring.models import IncidentSeverity, OperationalIncident

from .coherence import seed_locked_facts_from_variables
from .cost import CostBudgetExceededError, record_chapter_cost
from .models import ChapterGeneration, ChapterStatus, GenerationJob, JobStatus
from .prompts import build_chapter_prompt, build_system_prompt

_SUMMARY_MAX_CHARS = 320
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

    seed_locked_facts_from_variables(job, _variables_for(job))
    system_prompt = build_system_prompt(job.deliverable_type)

    chapters = job.chapters.exclude(status=ChapterStatus.DONE).order_by("chapter_number")
    for chapter in chapters:
        try:
            _generate_chapter(job, chapter, client=client, system_prompt=system_prompt)
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

    job.status = JobStatus.DONE
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_at", "updated_at"])
    return job


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

    prompt = build_chapter_prompt(chapter)
    result = client.complete(system=system_prompt, prompt=prompt)

    chapter.content = result.content
    chapter.operational_summary = _operational_summary(result.content)
    chapter.status = ChapterStatus.DONE
    chapter.save(update_fields=["content", "operational_summary", "status", "updated_at"])

    # Le Cost Engine enregistre le cout, met a jour le total et applique le plafond.
    record_chapter_cost(
        chapter=chapter,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        model=result.model,
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
