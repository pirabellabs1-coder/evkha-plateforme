from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from monitoring.models import IncidentSeverity, OperationalIncident

from .models import ChapterGeneration, GenerationJob

# Tarifs indicatifs EUR par token (input, output), configurables par modele (M4).
# A verifier/ajuster avec la grille Anthropic en vigueur. Le modele actif est
# choisi via EVKHA_CLAUDE_MODEL.
MODEL_PRICING_EUR: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet": (Decimal("0.0000027"), Decimal("0.0000135")),
    "claude-opus": (Decimal("0.0000135"), Decimal("0.0000675")),
    "claude-haiku": (Decimal("0.0000007"), Decimal("0.0000036")),
}
_FALLBACK_MODEL = "claude-sonnet"


class CostBudgetExceededError(RuntimeError):
    """Raised when a job's cumulative cost passes its EUR budget (regle d'or #1)."""


def _pricing(model: str | None) -> tuple[Decimal, Decimal]:
    key = str(model or getattr(settings, "EVKHA_CLAUDE_MODEL", _FALLBACK_MODEL))
    return MODEL_PRICING_EUR.get(key, MODEL_PRICING_EUR[_FALLBACK_MODEL])


def estimate_call_cost_eur(
    input_tokens: int,
    output_tokens: int,
    model: str | None = None,
) -> Decimal:
    input_eur, output_eur = _pricing(model)
    cost = (Decimal(input_tokens) * input_eur) + (Decimal(output_tokens) * output_eur)
    return cost.quantize(Decimal("0.0001"))


def record_chapter_cost(
    *,
    chapter: ChapterGeneration,
    input_tokens: int,
    output_tokens: int,
    model: str | None = None,
) -> Decimal:
    cost = estimate_call_cost_eur(input_tokens, output_tokens, model)
    chapter.input_tokens = input_tokens
    chapter.output_tokens = output_tokens
    chapter.cost_eur = cost
    chapter.save(update_fields=["input_tokens", "output_tokens", "cost_eur", "updated_at"])

    job = chapter.job
    total = sum((item.cost_eur for item in job.chapters.all()), Decimal("0"))
    GenerationJob.objects.filter(pk=job.pk).update(total_cost_eur=total)

    enforce_budget(job, current_total=total)
    return cost


def enforce_budget(job: GenerationJob, *, current_total: Decimal | None = None) -> None:
    """Stop and alert when the job exceeds its EUR budget (H2)."""
    total = current_total if current_total is not None else job.total_cost_eur
    if total <= job.budget_eur:
        return

    OperationalIncident.objects.create(
        title=f"Budget IA depasse pour le job {job.id}",
        severity=IncidentSeverity.HIGH,
        job=job,
        order=job.order,
        details={
            "total_cost_eur": str(total),
            "budget_eur": str(job.budget_eur),
        },
    )
    msg = f"Cost budget exceeded: {total} EUR > {job.budget_eur} EUR (job {job.id})"
    raise CostBudgetExceededError(msg)
