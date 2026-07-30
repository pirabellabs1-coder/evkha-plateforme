"""Production du livrable Word d'un job (lot 3).

Point d'entrée unique : `produire_docx(job)`. Il lit le socle verrouillé et les
chapitres structurés, les assemble, rend le `.docx` et le dépose sur disque.

Ce module ne crée pas d'artefact et ne parle pas au dashboard : cette
séparation permet de rendre un document pour inspection sans rien écrire en
base, ce qui est exactement ce dont on a besoin pour vérifier un livrable avant
de le déclarer prêt.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings

from ..chapitres.schema import ChapitrePayload
from ..models import ChapterGeneration, ChapterStatus, GenerationJob
from ..socle.schema import Socle
from ..socle.services import socle_verrouille
from .assemblage import RapportAssemblage, assembler_etude
from .depuis_json import rendre_etude

_log = logging.getLogger(__name__)

#: Intitulé du livrable, par type. Sert de titre de couverture.
TITRES = {
    "market_study": "Étude de marché",
    "competitor_study": "Étude de la concurrence",
    "business_strategy": "Stratégie d'entreprise",
    "business_plan": "Business plan",
}


class LivrableIncompletError(RuntimeError):
    """Il manque le socle ou les chapitres : rien à rendre."""


@dataclass(frozen=True)
class LivrableWord:
    chemin: Path
    rapport: RapportAssemblage
    etude: dict[str, Any]


def _repertoire_de_sortie() -> Path:
    racine = Path(getattr(settings, "MEDIA_ROOT", "")) or Path.cwd() / "media"
    return Path(racine) / "livrables"


def payloads_du_job(job: GenerationJob) -> list[ChapitrePayload]:
    """Chapitres structurés et terminés du job, dans l'ordre de lecture.

    Un chapitre sans `payload` est ignoré : il vient de l'ancien moteur, qui ne
    produisait que du markdown. Le mélanger aux autres donnerait un document
    dont une partie seulement respecte la charte — pire qu'un document
    incomplet, parce que l'incohérence se voit et l'absence non.
    """
    chapitres: list[ChapitrePayload] = []
    requete = (
        ChapterGeneration.objects.filter(job=job, status=ChapterStatus.DONE)
        .order_by("chapter_number")
    )
    for chapitre in requete:
        if not chapitre.payload:
            _log.warning(
                "Chapitre %s du job %s sans payload structuré : ignoré au rendu Word.",
                chapitre.chapter_number, job.id,
            )
            continue
        chapitres.append(ChapitrePayload.model_validate(chapitre.payload))
    return chapitres


def marque_du_job(job: GenerationJob) -> dict[str, str]:
    """Charte du client final, lue depuis le formulaire d'entrée.

    La charte n'appartient pas à l'abonné B2B mais à **son** client : elle
    change à chaque étude. Elle est donc lue sur la soumission de la commande,
    jamais sur un profil persistant. `extract_branding` porte déjà cette
    lecture ; on ne la refait pas ici (règle 5).
    """
    from ..rendering import extract_branding  # noqa: PLC0415

    marque = extract_branding(job)
    return {
        "nom": marque.company_name,
        "logo_url": marque.logo_url,
        "couleur_principale": marque.color_primary,
        "couleur_secondaire": marque.color_secondary,
    }


def produire_docx(
    job: GenerationJob, destination: Path | None = None
) -> LivrableWord:
    """Rend le `.docx` du job. Ne touche ni à la base, ni aux artefacts."""
    socle: Socle | None = socle_verrouille(job)
    if socle is None:
        msg = (
            f"Job {job.id} : aucun socle verrouillé. Le livrable Word ne peut "
            "pas être rendu sans socle — ses graphiques n'auraient rien à citer."
        )
        raise LivrableIncompletError(msg)

    chapitres = payloads_du_job(job)
    if not chapitres:
        msg = (
            f"Job {job.id} : aucun chapitre structuré terminé. Rien à assembler."
        )
        raise LivrableIncompletError(msg)

    marque = marque_du_job(job)
    etude, rapport = assembler_etude(
        socle=socle,
        chapitres=chapitres,
        titre=TITRES.get(str(job.deliverable_type), "Livrable EVKHA"),
        sous_titre=socle.secteur,
        marque=marque,
    )

    cible = destination or _repertoire_de_sortie() / f"{job.id}.docx"
    rendre_etude(etude, cible)

    _log.info("Livrable Word du job %s : %s (%s)", job.id, cible, rapport.resume())
    if not rapport.complet:
        _log.warning(
            "Job %s : %s graphique(s) abandonné(s) — %s",
            job.id, len(rapport.graphiques_abandonnes),
            " | ".join(rapport.graphiques_abandonnes),
        )
    return LivrableWord(chemin=cible, rapport=rapport, etude=etude)
