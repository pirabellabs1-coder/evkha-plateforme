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

# Regle d'or #1 durcie : sous 1.70 EUR, generation libre (max_tokens par
# defaut). Au-dela, on reduit strictement le max_tokens des appels Claude
# restants pour que le cout cumule du job ne puisse JAMAIS atteindre ni
# depasser budget_eur (2.00 EUR par defaut), meme dans le pire cas ou
# chaque appel restant consomme entierement son max_tokens. La marge de
# securite absorbe l'arrondi et le cout (petit mais non nul) des tokens
# d'entree du dernier appel.
_SOFT_THROTTLE_THRESHOLD_EUR = Decimal("1.7")
_HARD_CAP_SAFETY_MARGIN_EUR = Decimal("0.01")
_MIN_MAX_TOKENS = 400


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


def current_job_cost_eur(job: GenerationJob) -> Decimal:
    """Cout cumule reel du job, recalcule depuis les chapitres en base.

    Ne jamais lire job.total_cost_eur directement pour une decision en cours
    de generation : ce champ n'est mis a jour qu'en base (queryset.update),
    l'instance Python en memoire peut etre perimee au sein d'une meme boucle.
    """
    return sum((item.cost_eur for item in job.chapters.all()), Decimal("0"))


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
    total = current_job_cost_eur(job)
    GenerationJob.objects.filter(pk=job.pk).update(total_cost_eur=total)

    enforce_budget(job, current_total=total)
    return cost


def max_tokens_for_job(
    job: GenerationJob,
    *,
    default_max_tokens: int,
    call_count: int = 1,
    model: str | None = None,
) -> int:
    """Max_tokens a utiliser pour le(s) prochain(s) appel(s) Claude du job.

    Sous le seuil de 1.70 EUR : aucune limitation, max_tokens par defaut.
    Au-dela : le budget restant jusqu'a budget_eur (moins une marge de
    securite) est reparti sur `call_count` appels a venir (ex: les sections
    d'un meme chapitre decoupe), en pire cas (chaque appel consomme tout son
    max_tokens en sortie). Le resultat est toujours borne par _MIN_MAX_TOKENS
    en bas et default_max_tokens en haut : le job continue jusqu'au bout,
    avec des chapitres plus courts en fin de generation si necessaire, mais
    ne peut jamais atteindre ni depasser budget_eur.
    """
    total = current_job_cost_eur(job)
    if total < _SOFT_THROTTLE_THRESHOLD_EUR:
        return default_max_tokens

    _, output_eur = _pricing(model)
    remaining = job.budget_eur - total - _HARD_CAP_SAFETY_MARGIN_EUR
    if remaining <= 0:
        return _MIN_MAX_TOKENS

    per_call_budget = remaining / max(call_count, 1)
    allowed = int(per_call_budget / output_eur)
    return max(_MIN_MAX_TOKENS, min(default_max_tokens, allowed))


def enforce_budget(job: GenerationJob, *, current_total: Decimal | None = None) -> None:
    """Alert on budget overrun; hard stop only at 3× budget (circuit breaker).

    Un depassement modere (< 3x) ouvre un incident de monitoring mais laisse
    la generation continuer : mieux vaut un livrable complet legerement au-dessus
    du budget qu'un livrable tronque. L'arret dur a 3x protege contre un emballement.
    """
    total = current_total if current_total is not None else job.total_cost_eur
    if total <= job.budget_eur:
        return

    if not OperationalIncident.objects.filter(
        title__startswith="Budget IA depasse",
        job=job,
    ).exists():
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

    # Circuit breaker : arret dur uniquement a 3x le budget
    if total > job.budget_eur * Decimal("3"):
        msg = f"Cost budget exceeded (circuit breaker): {total} EUR > {job.budget_eur} EUR x3 (job {job.id})"  # noqa: E501
        raise CostBudgetExceededError(msg)
