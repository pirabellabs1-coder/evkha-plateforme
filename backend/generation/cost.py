from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from integrations.claude import _MAX_CONTINUATIONS, _provision_reflexion
from monitoring.models import IncidentSeverity, OperationalIncident

from .models import ChapterGeneration, ChapterStatus, GenerationJob

# Tarifs indicatifs EUR par token (input, output), configurables par modele (M4).
# A verifier/ajuster avec la grille Anthropic en vigueur. Le modele actif est
# choisi via EVKHA_CLAUDE_MODEL.
MODEL_PRICING_EUR: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet": (Decimal("0.0000027"), Decimal("0.0000135")),
    "claude-opus": (Decimal("0.0000135"), Decimal("0.0000675")),
}
_FALLBACK_MODEL = "claude-sonnet"

# Regle d'or #1 — BUDGET STRICT, FAIL-FAST :
#   - Throttle actif des le premier chapitre (seuil = 0 EUR) : chaque appel
#     Claude ne peut consommer qu'une fraction equitable du budget restant.
#   - Des que total_cost > budget_eur : arret immediat, CostBudgetExceededError.
#     Le chapitre en cours est sauvegarde tel quel (le cout a deja ete engage
#     cote Anthropic), mais aucun chapitre suivant ne demarre.
_SOFT_THROTTLE_THRESHOLD_EUR = Decimal("0")  # throttle actif des le 1er chapitre
_HARD_CAP_SAFETY_MARGIN_EUR = Decimal("0.02")
# _MIN_MAX_TOKENS : plancher garanti pour chaque appel Claude, meme sous
# pression budgetaire. Historique : 400 tokens → provoquait des chapitres
# etrangles (SWOT/risques/conclusion a 1200 tokens output = min × 3 rounds
# de continuation). Ces chapitres sortaient "termines" mais structurellement
# incomplets — le client voyait un SWOT avec 2 quadrants sur 4.
# Correctif : plancher a 2500 tokens = ~1875 mots = un chapitre substantiel
# minimum. Si le budget ne peut pas absorber ce plancher, `enforce_budget`
# leve CostBudgetExceededError et le job passe FAILED proprement (fail-fast)
# plutot que de generer du contenu mutile.
_MIN_MAX_TOKENS = 2500


class CostBudgetExceededError(RuntimeError):
    """Raised when a job's cumulative cost passes its EUR budget (regle d'or #1)."""


def _pricing(model: str | None) -> tuple[Decimal, Decimal]:
    """Tarif du modele, resolu par FAMILLE et non par egalite stricte de cle.

    Piege desamorce (audit juillet 2026) : le cout etait indexe sur l'alias
    EVKHA_CLAUDE_MODEL tandis que l'appel reel peut etre surcharge vers un
    identifiant complet via EVKHA_ANTHROPIC_MODEL_ID. Une bascule vers Opus
    sans changer l'alias facturait Opus et affichait du Sonnet — soit un cout
    reel 5x superieur a celui du dashboard, sur le point que la cliente juge
    "tres important". On reconnait donc la famille dans l'identifiant, quelle
    que soit sa forme ("claude-opus", "claude-opus-4-6", "claude-3-opus-...").
    """
    key = str(
        model
        or getattr(settings, "EVKHA_ANTHROPIC_MODEL_ID", "")
        or getattr(settings, "EVKHA_CLAUDE_MODEL", _FALLBACK_MODEL)
    ).lower()
    if key in MODEL_PRICING_EUR:
        return MODEL_PRICING_EUR[key]
    # Resolution par famille : le tarif le PLUS CHER qui correspond, pour ne
    # jamais sous-estimer le cout reel.
    for family in ("opus", "sonnet", "haiku"):
        if family in key:
            return MODEL_PRICING_EUR[f"claude-{family}"]
    return MODEL_PRICING_EUR[_FALLBACK_MODEL]


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


def record_additional_cost(
    *,
    chapter: ChapterGeneration,
    input_tokens: int,
    output_tokens: int,
    model: str | None = None,
) -> Decimal:
    """Ajoute au chapitre le cout d'appels IA supplementaires (reparation QA).

    §4 cadrage (suivi des couts) : TOUS les appels Claude doivent etre
    comptabilises, y compris ceux de la passe QA post-generation qui
    n'etaient pas traces (audit juillet 2026 : cout dashboard sous-estime).
    N'applique PAS enforce_budget : la QA intervient sur un job deja DONE,
    la borne budgetaire de la QA est geree en amont (desactivation IA a 85%).
    """
    if input_tokens <= 0 and output_tokens <= 0:
        return Decimal("0")
    extra = estimate_call_cost_eur(input_tokens, output_tokens, model)
    chapter.input_tokens += input_tokens
    chapter.output_tokens += output_tokens
    chapter.cost_eur += extra
    chapter.save(update_fields=["input_tokens", "output_tokens", "cost_eur", "updated_at"])

    job = chapter.job
    GenerationJob.objects.filter(pk=job.pk).update(
        total_cost_eur=current_job_cost_eur(job)
    )
    return extra


# Un mot francais coute ~1,6 token. La marge absorbe le balisage (tableaux
# HTML, titres) qui consomme des tokens sans etre du texte lisible.
_TOKENS_PAR_MOT = 1.6
_MARGE_BALISAGE = 1.45
# Plancher : en dessous, meme un texte court serait coupe en pleine phrase, et
# une troncature declenche un retry — donc coute plus cher que la place gagnee.
_PLANCHER_CIBLE_TOKENS = 900


def tokens_pour_cible(max_words: int) -> int:
    """Plafond de sortie derive de la cible editoriale, en tokens.

    Le prompt demandait deja de tenir un budget de mots, mais rien ne l'y
    obligeait : le modele disposait de 8 192 tokens par appel (~5 100 mots) et
    jusqu'a 3 appels enchaines par section. Une consigne sans contrainte
    physique est un voeu — le prevesionnel visait 2 800 mots et en a produit
    5 639.

    Ce plafond rend le depassement IMPOSSIBLE, au lieu de le deconseiller.
    Retourne 0 si aucune cible n'est definie (pas de contrainte).
    """
    if max_words <= 0:
        return 0
    return max(_PLANCHER_CIBLE_TOKENS, int(max_words * _TOKENS_PAR_MOT * _MARGE_BALISAGE))


def max_tokens_for_job(
    job: GenerationJob,
    *,
    default_max_tokens: int,
    call_count: int = 1,
    model: str | None = None,
    validation_retries: int = 0,
) -> int:
    """Max_tokens a utiliser pour le(s) prochain(s) appel(s) Claude du job.

    Le budget restant (budget_eur - cout_cumule - marge) est reparti sur la
    totalite des appels restants en pire cas (chaque appel consomme tout son
    max_tokens en sortie). Le resultat est toujours borne par _MIN_MAX_TOKENS
    en bas et default_max_tokens en haut.

    Calcul du nombre total de slots restants :
      - Ce chapitre : call_count sections × worst_case_calls_per_prompt
      - Autres chapitres en attente : (pending - 1) × 1 × worst_case_calls_per_prompt
        (on suppose conservativement qu'ils n'ont qu'une seule section chacun)

    Cette formule — vs l'ancienne (pending × call_count × worst_case) — evite
    de surpenaliser les chapitres decoupe en sections : seul LE chapitre courant
    voit son call_count reel ; les autres sont comptes a 1 section.

    ClaudeClient.complete() peut relancer jusqu'a _MAX_CONTINUATIONS appels
    supplementaires (worst_case_calls_per_prompt = k+1).
    Taux effectif reel par token = output_eur + k/2 × input_eur
    (la continuation renvoie l'output precedent en input).
    """
    total = current_job_cost_eur(job)
    if total < _SOFT_THROTTLE_THRESHOLD_EUR:
        return default_max_tokens

    input_eur, output_eur = _pricing(model)
    remaining = job.budget_eur - total - _HARD_CAP_SAFETY_MARGIN_EUR
    if remaining <= 0:
        return _MIN_MAX_TOKENS

    pending_chapters = max(
        1,
        job.chapters.filter(
            status__in=[ChapterStatus.PENDING, ChapterStatus.RUNNING]
        ).count(),
    )

    k = _MAX_CONTINUATIONS
    worst_case_calls_per_prompt = k + 1
    effective_rate = output_eur + Decimal(k) * input_eur / 2

    # Slots : sections du chapitre courant + 1 slot par chapitre restant.
    # `validation_retries` (audit F4) : chaque section peut etre regeneree en
    # cas de defaut bloquant, ce que la formule ignorait. Le budget etait donc
    # sous-provisionne sur les chapitres decoupes — les plus denses, donc les
    # plus sujets au retry. Le plafond strict ne surfacturait pas (il leve
    # CostBudgetExceededError), mais faisait ECHOUER le job : c'est le taux
    # d'aboutissement qui payait le retry non anticipe.
    attempts_per_call = 1 + max(validation_retries, 0)
    this_chapter_slots = max(call_count, 1) * worst_case_calls_per_prompt * attempts_per_call
    other_chapters_slots = (
        (pending_chapters - 1) * worst_case_calls_per_prompt * attempts_per_call
    )
    total_slots = this_chapter_slots + other_chapters_slots

    per_call_budget = remaining / max(total_slots, 1)

    # Reflexion adaptative : les tokens de reflexion sont factures au tarif
    # OUTPUT et `AnthropicClaudeClient.complete` releve max_tokens de la
    # provision pour que la place laissee au contenu reste celle demandee. Ce
    # cout est donc engage a chaque appel EN PLUS du contenu — il doit sortir du
    # budget par appel avant le calcul, sinon le throttle autorise des chapitres
    # qu'il ne peut pas payer et le job meurt sur CostBudgetExceededError vers
    # 90 %.
    #
    # En adaptatif, la depense reelle de reflexion n'est plus connue d'avance :
    # le modele la choisit. La provision reste donc une ESTIMATION — mais elle
    # n'est pas le seul garde-fou : `max_tokens` borne la reflexion et le texte
    # ensemble, et `enforce_budget` coupe net au depassement. Une provision trop
    # basse rogne le texte, elle ne laisse pas filer la facture.
    cout_reflexion = Decimal(_provision_reflexion()) * output_eur
    per_call_budget -= cout_reflexion
    if per_call_budget <= 0:
        return _MIN_MAX_TOKENS

    allowed = int(per_call_budget / effective_rate)
    return max(_MIN_MAX_TOKENS, min(default_max_tokens, allowed))


def enforce_budget(job: GenerationJob, *, current_total: Decimal | None = None) -> None:
    """Arret immediat si total > budget_eur. Budget MAX = 2 EUR, STRICT, SANS TOLERANCE.

    Des que le cumul des chapitres depasse budget_eur, CostBudgetExceededError est
    leve et la generation s'arrete. Le chapitre qui a declenche le depassement est
    deja sauvegarde (le cout a ete engage cote Anthropic) mais aucun chapitre
    suivant ne demarre.
    """
    total = current_total if current_total is not None else job.total_cost_eur
    if total <= job.budget_eur:
        return

    # Un seul incident par job — pas de spam.
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

    msg = (
        f"Budget strict depasse : {total} EUR > {job.budget_eur} EUR (job {job.id}). "
        "Generation stoppee immediatement."
    )
    raise CostBudgetExceededError(msg)
