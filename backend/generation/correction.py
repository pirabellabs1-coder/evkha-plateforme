"""Boucle d'auto-correction avant blocage (concept "loop", brief client).

Inspiré du principe des boucles agentiques (Forward-Future/loopy) : plutôt que
de BLOQUER dès qu'un défaut subsiste, le système « apprend du résultat et fait
le pas utile suivant » — il régénère UNIQUEMENT les chapitres fautifs avec la
liste exacte des problèmes en consigne, puis repasse le gate. Répété au plus
`EVKHA_CORRECTION_ROUNDS` fois (défaut 1) pour borner strictement le coût.

Objectif : réduire les omissions/erreurs qui obligeaient Evangeline à relancer
20 fois à la main, sans faire exploser le budget API. Si la boucle n'y arrive
pas, le comportement historique s'applique : le gate bloque la livraison.

Bornes de sécurité :
- nombre de rondes plafonné (défaut 1) ;
- seuls les chapitres directement désignés par un échec sont régénérés ;
- un dépassement de budget arrête la boucle proprement (le job reste bloqué,
  jamais livré à moitié).
"""
from __future__ import annotations

from django.conf import settings

from . import gate as _gate
from .cost import CostBudgetExceededError
from .gate import GateFailure, GateReport
from .models import GenerationJob

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
        attempt += 1
        for chapter_number, note in feedback.items():
            chapter = job.chapters.filter(chapter_number=chapter_number).first()
            if chapter is None:
                continue
            try:
                regenerate_chapter(job, chapter, corrective_note=note, client=gen_client)
            except CostBudgetExceededError:
                # Budget épuisé : on arrête la boucle, le job reste bloqué.
                return _gate.run_delivery_gate(job)
            except Exception:  # noqa: BLE001 — une régénération KO ne casse pas la boucle
                continue
        report = _gate.run_delivery_gate(job)

    return report


def regenerable_chapter_numbers(report: GateReport) -> list[int]:  # pragma: no cover
    """Aide de diagnostic : numéros de chapitres qu'une ronde de correction ciblerait."""
    return sorted(_feedback_by_chapter(report.failures).keys())
