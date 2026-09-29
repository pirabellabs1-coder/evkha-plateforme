"""La mémoire d'un dossier : construite depuis son socle et ses réponses, puis gardée.

Un seul point d'entrée, `memoire_du_job`, lu par la rédaction (bloc du
rédacteur), par l'enregistrement d'un chapitre (repères) et par le rapport
interne. Il ne rend RIEN pour un dossier sans `memoire_active` : c'est ce qui
garantit qu'aucune étude antérieure au 29/09/2026 ne change de chemin.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from generation.socle.schema import Socle

from .etude import MemoireEtude

if TYPE_CHECKING:
    from generation.models import GenerationJob

_log = logging.getLogger(__name__)


def _variables(job: GenerationJob) -> dict[str, object]:
    from intake.models import IntakeSubmission  # noqa: PLC0415

    soumission = IntakeSubmission.objects.filter(order=job.order).first()
    return dict(soumission.normalized_variables) if soumission else {}


def memoire_du_job(job: GenerationJob) -> MemoireEtude | None:
    """La mémoire du dossier, ou None s'il n'en a pas (ou pas encore).

    Construite depuis le socle VALIDE : sans socle verrouillé, il n'y a pas
    de faits de référence, donc pas de mémoire — on ne la fabrique pas à moitié.
    Déterministe : reconstruite à chaque appel, elle est la même ; elle n'est
    écrite en base que si elle a changé, pour le rapport interne.
    """
    from generation.models import SocleDonnees, SocleStatut  # noqa: PLC0415

    if not job.memoire_active:
        return None
    socle = SocleDonnees.objects.filter(job=job, statut=SocleStatut.VALIDE).first()
    if socle is None:
        return None
    try:
        lu = Socle.model_validate(socle.contenu)
    except ValidationError:
        _log.exception("Mémoire : socle illisible pour le dossier %s", job.id)
        return None
    try:
        memoire = MemoireEtude.construire(lu, _variables(job), str(job.deliverable_type))
    except Exception:  # noqa: BLE001 — la mémoire ne doit JAMAIS arrêter une étude
        # Une erreur ici remonterait dans la rédaction de chaque chapitre. Le
        # dossier retombe alors sur le chemin d'avant, sans mémoire : c'est un
        # document moins contrôlé, jamais une étude arrêtée (engagement du
        # 29/09/2026). La trace part au journal pour que la cause se corrige.
        _log.exception("Mémoire : construction impossible pour le dossier %s", job.id)
        return None
    # La trace des chapitres (`chapitres`) est écrite au fil de la rédaction :
    # reconstruire les faits et les décisions ne doit pas l'effacer.
    contenu = {**(job.memoire_etude or {}), **memoire.en_dict()}
    if job.memoire_etude != contenu:
        job.memoire_etude = contenu
        type(job).objects.filter(pk=job.pk).update(memoire_etude=contenu)
    return memoire
