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
from .logo import charger_logo

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
    #: La référence d'un logo ATTENDU mais illisible — vide s'il n'en fallait
    #: pas, ou s'il est imprimé. L'assemblage en fait un incident : un logo
    #: absent passait en silence (business plan ÉCLORE `28a257bf`, 30/09/2026).
    logo_introuvable: str = ""


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
        # Ces deux cles etaient absentes, et le rendu les lit : `rendre_etude`
        # interroge `marque["couleur_fond"]`, `mentions_finales` interroge
        # `marque["mention_confidentialite"]`. Les omettre ici rendait morts
        # deux champs que l'abonne remplit dans « Ma Marque ».
        "couleur_fond": marque.color_background,
        "mention_confidentialite": marque.confidentiality_mention,
    }


def identite_du_projet(job: GenerationJob) -> dict[str, str]:
    """Le nom du projet et celui de son porteur, tels que le client les a saisis.

    Ils étaient collectés et jamais lus par le rendu (29/09/2026, business plan
    ÉCLORE) : l'en-tête courant et l'auteur du PDF prenaient à leur place la
    raison sociale de « Ma marque », une phrase entière. `PORTEUR_PROJET` est le
    champ du questionnaire du business plan ; `NOM_PORTEUR` celui de l'ancien
    formulaire (`intake/services.py`). La lecture des variables du dossier
    existe déjà — `variables_du_job` — et n'est pas refaite ici (règle 5).
    """
    from ..chapitres.services import variables_du_job  # noqa: PLC0415

    variables = variables_du_job(job)

    def _lire(*cles: str) -> str:
        for cle in cles:
            valeur = str(variables.get(cle) or "").strip()
            if valeur:
                return valeur
        return ""

    return {
        "projet": _lire("PROJET"),
        "porteur": _lire("PORTEUR_PROJET", "NOM_PORTEUR"),
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

    # Le type de livrable décide de la recommandation de clôture : proposer une
    # étude de la concurrence à la fin d'une étude de la concurrence perdrait en
    # une phrase la crédibilité que trente pages ont construite.
    etude["type_livrable"] = str(job.deliverable_type)
    etude.update(identite_du_projet(job))
    # Le logo se charge UNE fois, ici : le rendu reçoit les octets, et on sait
    # s'il manque. `marque["logo_url"]` a déjà son repli sur le logo actuel de
    # l'organisation (`rendering.logo_du_job`).
    logo_introuvable = ""
    if marque.get("logo_url"):
        octets_logo = charger_logo(str(marque["logo_url"]))
        if octets_logo is not None:
            etude["logo"] = octets_logo
        else:
            logo_introuvable = str(marque["logo_url"])

    cible = destination or _repertoire_de_sortie() / f"{job.id}.docx"
    rendre_etude(etude, cible)

    _log.info("Livrable Word du job %s : %s (%s)", job.id, cible, rapport.resume())
    if not rapport.complet:
        _log.warning(
            "Job %s : %s graphique(s) abandonné(s) — %s",
            job.id, len(rapport.graphiques_abandonnes),
            " | ".join(rapport.graphiques_abandonnes),
        )
    return LivrableWord(
        chemin=cible, rapport=rapport, etude=etude, logo_introuvable=logo_introuvable,
    )
