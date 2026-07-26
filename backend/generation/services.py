from __future__ import annotations

from decimal import Decimal

from catalog.models import DeliverableType
from intake.models import IntakeStatus, IntakeSubmission

from .blueprints import chapters_for_deliverable
from .models import ChapterGeneration, ChapterStatus, GenerationJob, JobStatus

# Livrables couverts par le moteur de generation (phases 2-5).
_SUPPORTED_DELIVERABLES = frozenset(
    {
        DeliverableType.MARKET_STUDY,
        DeliverableType.COMPETITOR_STUDY,
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.BUSINESS_STRATEGY,
    }
)

# Budget IA par type de livrable, aligne sur le cout reel d'une generation
# COMPLETE (pas etranglee). Historique : budget EM 2.30-2.40 EUR + throttle
# _MIN_MAX_TOKENS=400 produisait des chapitres tardifs a 1200 tokens output
# (SWOT/risques/conclusion tronques). Correctif complet :
#   - _MIN_MAX_TOKENS releve a 2500 (cf. cost.py) : plus de contenu etrangle
#   - Budget EM releve a 3.20 EUR pour absorber le plancher garanti
#   - Prompt caching Anthropic (integrations/claude.py) reduit ~0.30 EUR/job
# Cible reelle apres tous les fixes : EM ~2.40-2.90 EUR / job avec contenu
# structurellement complet.
#
# Revision juillet 2026 — EM portee de 3,20 a 4,00 EUR. Deux faits mesures, pas
# une precaution :
#   - le run reel 010e3bf2 (22 chapitres) a coute 3,05 EUR, soit 95 % du
#     plafond de 3,20 : il n'y avait plus de marge pour un seul retry ;
#   - l'extended thinking (1024 tokens/appel, EVKHA_THINKING_BUDGET_TOKENS)
#     ajoute ~0,41 EUR sur 30 appels. A budget inchange, le throttle aurait
#     etrangle les derniers chapitres — exactement le defaut que le plancher
#     _MIN_MAX_TOKENS=2500 avait corrige.
# 4,00 EUR = 3,05 mesure + 0,41 de reflexion + ~0,55 de marge de retry.
#
# Revision (tache #12) — EM portee de 4,00 a 4,60 EUR. Le cout des 11 CHECKs
# n'etait ENREGISTRE NULLE PART (cf. checks_blocs._enregistrer_cout_check) : la
# depense existait cote Anthropic mais pas dans le grand livre. Les 3,05 EUR
# mesures sur le run 010e3bf2 sous-estimaient donc la realite d'environ
# 0,46 EUR. Maintenant que les CHECKs sont comptes, le plafond de 4,00 EUR
# aurait tue le job vers 95 % sur un cout qui, lui, n'a pas bouge.
#   3,05 chapitres mesures
# + 0,41 extended thinking (30 appels x 1024 tokens)
# + 0,46 CHECKs, desormais visibles (11 CHECKs, ~6 000 tok in / ~2 000 tok out)
# + 0,22 advisor sur les 5 blocs quantifies (EVKHA_ADVISOR_BLOCS)
# = 4,14 EUR attendus, + ~0,46 de marge de retry -> 4,60 EUR.
# Leviers de retour en arriere, par ordre d'effet : EVKHA_ADVISOR_ENABLED=false
# (-0,22), EVKHA_THINKING_BUDGET_TOKENS=0 (-0,41).
_BUDGET_EUR_BY_TYPE: dict[str, Decimal] = {
    DeliverableType.MARKET_STUDY:      Decimal("4.6000"),  # 30 appels + thinking + CHECKs
    DeliverableType.BUSINESS_PLAN:     Decimal("2.8000"),  # 20 chapitres, ~24 appels chunked
    DeliverableType.BUSINESS_STRATEGY: Decimal("2.4000"),  # 20 appels
    DeliverableType.COMPETITOR_STUDY:  Decimal("2.0000"),  # 12 appels (sans SWOT)
}


class GenerationBootstrapError(ValueError):
    pass


def bootstrap_generation_job(submission: IntakeSubmission) -> GenerationJob:
    if submission.status != IntakeStatus.NORMALIZED:
        msg = "Generation requires a normalized intake submission."
        raise GenerationBootstrapError(msg)

    # Offres B2B génériques (abonnements, crédits suppl.) :
    # deliverable_type est dans le payload Tally.
    deliverable_type = (
        submission.order.offer.deliverable_type
        or submission.normalized_variables.get("DELIVERABLE_TYPE")
    )
    if deliverable_type not in _SUPPORTED_DELIVERABLES:
        msg = f"Unsupported deliverable type for generation: {deliverable_type}"
        raise GenerationBootstrapError(msg)

    job, _created = GenerationJob.objects.get_or_create(
        order=submission.order,
        defaults={
            "deliverable_type": str(deliverable_type),
            "status": JobStatus.PENDING,
            "budget_eur": _BUDGET_EUR_BY_TYPE[deliverable_type],
        },
    )

    for blueprint in chapters_for_deliverable(deliverable_type):
        ChapterGeneration.objects.get_or_create(
            job=job,
            chapter_number=blueprint.number,
            defaults={
                "chapter_title": blueprint.title,
                "prompt_key": blueprint.prompt_key,
            },
        )

    return job


def relaunch_generation_job(job: GenerationJob) -> None:
    """Réinitialise les statuts d'un job échoué/annulé pour permettre sa relance.

    Recale aussi le budget sur la valeur correcte pour le type de livrable —
    couvre les jobs créés avant l'introduction de _BUDGET_EUR_BY_TYPE.
    """
    job.status = JobStatus.PENDING
    job.error_message = ""
    job.started_at = None
    job.completed_at = None
    # Recale le budget uniquement si aucun chapitre n'est déjà DONE (job vierge).
    # Pour un job partiellement généré, le coût cumulé est déjà fixé — on ne touche
    # pas au budget afin d'éviter un faux incident dès le redémarrage.
    if not job.chapters.filter(status=ChapterStatus.DONE).exists():
        job.budget_eur = _BUDGET_EUR_BY_TYPE.get(job.deliverable_type, job.budget_eur)
    job.save(update_fields=["status", "error_message", "started_at", "completed_at", "budget_eur"])

    job.chapters.filter(
        status__in=[ChapterStatus.FAILED, ChapterStatus.SKIPPED]
    ).update(status=ChapterStatus.PENDING, error_message="")
