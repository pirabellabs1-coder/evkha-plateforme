"""Ce qui reste quand une génération s'arrête sans prévenir.

Défaut vécu, daté du 31/07/2026. Le premier appel réel a été refusé par
l'API en 0,9 seconde — plafond de dépenses atteint sur le compte. La tâche
Celery a levé, l'exception a été journalisée, et **le job est resté affiché
`running` pendant quatorze minutes**, sans erreur, sans incident, sans rien.
J'ai cherché une panne réseau alors que la réponse était dans les journaux
depuis le début. Un client aurait vu « en cours » sur une génération morte.

C'est la règle 1 : un traitement qui ne peut pas aboutir doit échouer
bruyamment, pas se taire. Et la règle 4 : le correctif ne vise pas l'erreur
de plafond, il vise **la classe** — toute exception qui s'échappe du
pipeline, quelle qu'en soit la cause.

Le gardien `reset_stuck_generation_jobs` existait déjà, mais il attend
**deux heures** avant de requalifier un job bloqué. C'est le bon délai pour
un worker mort, et beaucoup trop pour un crash instantané : entre les deux,
l'admin comme le client lisent « en cours » sur quelque chose de terminé.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — annotation seule, evite un cycle d'import
    from .models import GenerationJob

_log = logging.getLogger(__name__)

#: Motifs reconnus dans le message d'une erreur d'API, et ce qu'on en dit à
#: un humain. Une liste fermée serait incomplète par construction (règle 4) —
#: elle ne sert donc PAS à décider, seulement à mieux formuler. Tout ce qui
#: n'y figure pas est rendu tel quel, jamais avalé.
_TRADUCTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"usage limits?.*regain access on ([0-9T:\- ]+)", re.I),
        "Plafond de dépenses atteint sur le compte Anthropic. "
        "Accès rétabli le {0} UTC. Relever le plafond dans la console "
        "(Settings → Limits) ou attendre cette date.",
    ),
    (
        re.compile(r"invalid x-api-key|authentication_error", re.I),
        "Clé d'API refusée. Vérifier ANTHROPIC_API_KEY dans les variables "
        "d'environnement — mauvaise clé, clé révoquée, ou espace parasite "
        "au collage.",
    ),
    (
        re.compile(r"rate_limit_error|429", re.I),
        "Limite de débit atteinte chez le fournisseur. Le job peut être "
        "relancé tel quel dans quelques minutes.",
    ),
    (
        re.compile(r"credit balance is too low|billing", re.I),
        "Solde insuffisant sur le compte Anthropic. Recharger depuis la "
        "console (Plans & Billing).",
    ),
)


def motif_lisible(erreur: BaseException) -> str:
    """Message d'échec destiné à un humain, jamais à un journal.

    La règle 2 est explicite : un motif qu'on ne peut pas retrouver dans la
    réalité envoie corriger la mauvaise chose. « AnthropicError: Error code:
    400 - {'type': 'error', ...} » ne dit à personne qu'il faut relever un
    plafond dans une console.

    Le message d'origine est TOUJOURS conservé en queue : une traduction qui
    remplacerait la cause réelle serait pire que pas de traduction du tout.
    """
    brut = " ".join(str(erreur).split())
    for motif, gabarit in _TRADUCTIONS:
        trouve = motif.search(brut)
        if trouve:
            groupes = [g.strip() for g in trouve.groups()]
            try:
                lisible = gabarit.format(*groupes)
            except (IndexError, KeyError):  # gabarit et motif désaccordés
                lisible = gabarit
            return f"{lisible} [{type(erreur).__name__}: {brut}]"
    return f"{type(erreur).__name__}: {brut}"


def marquer_echec(
    job: GenerationJob, erreur: BaseException, *, etape: str
) -> None:
    """Requalifie le job en FAILED et ouvre un incident. Idempotent.

    N'écrase RIEN : si le job porte déjà un statut terminal, c'est que
    quelqu'un en amont a su dire mieux que nous ce qui s'est passé — on le
    laisse parler. Ce garde-fou est le dernier filet, pas le premier.
    """
    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    from .models import GenerationJob, JobStatus  # noqa: PLC0415

    motif = motif_lisible(erreur)
    _log.exception("Generation interrompue (%s) pour le job %s", etape,
                   job.id)

    # `filter(...).update(...)` sur le statut non terminal : deux workers qui
    # échoueraient en même temps n'écriraient pas deux incidents contradictoires.
    touches = GenerationJob.objects.filter(
        pk=job.pk,
        status__in=(JobStatus.PENDING, JobStatus.RUNNING),
    ).update(
        status=JobStatus.FAILED,
        error_message=f"Interrompu pendant « {etape} » : {motif}"[:2000],
    )
    if not touches:
        # Statut deja terminal : l'echec est deja raconte ailleurs.
        return

    OperationalIncident.objects.create(
        title=f"Generation interrompue pendant « {etape} » (job {job.id})",
        severity=IncidentSeverity.HIGH,
        job=job,
        order=job.order,
        details={
            "etape": etape,
            "exception": type(erreur).__name__,
            "motif": motif,
            "consigne": (
                "Aucun e-mail client n'est parti. Corriger la cause nommee "
                "ci-dessus, puis relancer le job depuis le tableau de bord."
            ),
        },
    )
