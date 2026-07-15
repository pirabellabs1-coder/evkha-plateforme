"""Boucle d'auto-correction avant blocage (concept "loop", brief client).

Inspiré du principe des boucles agentiques (Forward-Future/loopy) : plutôt que
de BLOQUER dès qu'un défaut subsiste, le système « apprend du résultat et fait
le pas utile suivant » — il régénère UNIQUEMENT les chapitres fautifs avec la
liste exacte des problèmes en consigne, puis repasse le gate. Répété au plus
`EVKHA_CORRECTION_ROUNDS` fois (défaut 1) pour borner strictement le coût.

Objectif : réduire les omissions/erreurs qui obligeaient Evangeline à relancer
manuellement, SANS dépasser le budget strict PAR DOSSIER (règle d'or #1 :
EM 3,20 € / BP 2,80 € / STR 2,40 € / EC 2,00 € max ; cible cadrage §3 : idéal
< 1-2 €). La régénération puise dans CE MÊME plafond : elle ne peut donc rien
« faire exploser ». Si la boucle n'aboutit pas dans le budget, le comportement
historique s'applique : le gate bloque la livraison (décision admin).

Bornes de sécurité :
- nombre de rondes plafonné (défaut 1) ;
- seuls les chapitres directement désignés par un échec sont régénérés ;
- AUCUNE régénération n'est lancée s'il ne reste plus de budget sur le dossier
  (on ne démarre pas un appel qu'on ne peut pas payer) ;
- un dépassement de budget en cours arrête la boucle proprement (le job reste
  bloqué, jamais livré à moitié).
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from . import gate as _gate
from .cost import CostBudgetExceededError, current_job_cost_eur
from .gate import GateFailure, GateReport
from .models import GenerationJob

# Réserve minimale de budget avant de tenter une régénération : sous ce seuil,
# un nouvel appel Claude dépasserait le plafond du dossier — on s'abstient.
_BUDGET_MARGIN_EUR = Decimal("0.05")


def _has_budget_headroom(job: GenerationJob) -> bool:
    """Reste-t-il du budget sur ce dossier pour un appel de régénération ?"""
    return current_job_cost_eur(job) < (job.budget_eur - _BUDGET_MARGIN_EUR)

# Types d'échec réparables en régénérant un chapitre précis. Les échecs
# `verticales` sont au niveau document (pas de chapitre unique) : on ne les
# régénère pas automatiquement (risque de casser d'autres chapitres) — ils
# restent bloquants, à traiter à la source (brief/prompt).
_CHAPTER_LEVEL_CHECKS = frozenset(
    {"contamination", "coherence_chiffree", "troncature"}
)

# Libellés lisibles injectés dans la consigne de correction.
_CHECK_LABELS = {
    "contamination": "Marqueur technique interne présent dans le texte (interdit)",
    "coherence_chiffree": "Chiffre incohérent avec le prévisionnel client",
    "troncature": "Chapitre coupé / phrase ou structure non terminée",
}


def _default_rounds() -> int:
    try:
        return max(0, int(getattr(settings, "EVKHA_CORRECTION_ROUNDS", 1)))
    except (TypeError, ValueError):
        return 1


def _feedback_by_chapter(failures: tuple[GateFailure, ...]) -> dict[int, str]:
    """Regroupe les échecs réparables par numéro de chapitre → consigne texte."""
    grouped: dict[int, list[str]] = {}
    for failure in failures:
        if failure.check not in _CHAPTER_LEVEL_CHECKS:
            continue
        if failure.chapter_number is None:
            continue
        label = _CHECK_LABELS.get(failure.check, failure.check)
        grouped.setdefault(failure.chapter_number, []).append(f"- {label} : {failure.detail}")
    return {num: "\n".join(items) for num, items in grouped.items()}


def run_correction_loop(
    job: GenerationJob,
    *,
    client: object | None = None,
    max_rounds: int | None = None,
) -> GateReport:
    """Exécute le gate, régénère les chapitres fautifs, repasse le gate (borné).

    Retourne le rapport final du gate (passé ou non). Ne livre rien : c'est
    l'appelant (tasks.py) qui décide, sur report.passed, de livrer ou de
    marquer le job BLOCKED.
    """
    from integrations.claude import ClaudeClient, get_claude_client  # noqa: PLC0415

    from .runner import regenerate_chapter  # noqa: PLC0415 — évite le cycle d'import

    rounds = _default_rounds() if max_rounds is None else max(0, max_rounds)
    gen_client = client if isinstance(client, ClaudeClient) else get_claude_client()

    report = _gate.run_delivery_gate(job)
    attempt = 0
    while not report.passed and attempt < rounds:
        feedback = _feedback_by_chapter(report.failures)
        if not feedback:
            # Aucun échec réparable au niveau chapitre (ex. verticale manquante
            # au niveau document) : la régénération ciblée n'aiderait pas.
            break
        if not _has_budget_headroom(job):
            # Plafond du dossier atteint : on ne lance pas d'appel qu'on ne
            # peut pas payer. Le job reste bloqué (décision admin).
            break
        attempt += 1
        for chapter_number, note in feedback.items():
            if not _has_budget_headroom(job):
                break
            chapter = job.chapters.filter(chapter_number=chapter_number).first()
            if chapter is None:
                continue
            try:
                regenerate_chapter(job, chapter, corrective_note=note, client=gen_client)
            except CostBudgetExceededError:
                # Budget dépassé en cours : on arrête, le job reste bloqué.
                return _gate.run_delivery_gate(job)
            except Exception:  # noqa: BLE001 — une régénération KO ne casse pas la boucle
                continue
        report = _gate.run_delivery_gate(job)

    return report


def regenerable_chapter_numbers(report: GateReport) -> list[int]:  # pragma: no cover
    """Aide de diagnostic : numéros de chapitres qu'une ronde de correction ciblerait."""
    return sorted(_feedback_by_chapter(report.failures).keys())
