"""Assemblage du livrable Word et de son PDF (lot 3).

Chaîne parallèle à `assemble_document`, qui reste en place et inchangée : elle
produit l'aperçu HTML et le PDF issus de l'ancien moteur. Les deux coexistent
le temps de la bascule, et c'est délibéré — remplacer la chaîne en service
avant d'avoir vu un livrable Word sur un dossier réel reviendrait à parier sur
du code que personne n'a encore lu en production (règle 7).

Ordre imposé : **le Word d'abord, le PDF ensuite, converti depuis lui**. Le PDF
est une photographie du Word, jamais un second rendu — sans quoi les deux
fichiers livrés au même client divergeraient sur la pagination.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from generation.models import GenerationJob
from generation.rendu_word.assemblage import RapportAssemblage
from generation.rendu_word.services import produire_docx
from generation.verification import RapportControle, verifier_livrable
from integrations.docx_pdf import (
    ConversionPdfError,
    ConvertisseurDocx,
    get_convertisseur_docx,
)

from .models import ArtifactKind, ArtifactStatus, DocumentArtifact

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LivrableAssemble:
    docx: DocumentArtifact
    pdf: DocumentArtifact | None
    rapport: RapportAssemblage
    pages: int = 0
    controle: RapportControle | None = None

    @property
    def livrable(self) -> bool:
        """Le document peut-il partir au client ?

        Absence de contrôle vaut **non** : ne pas avoir vérifié n'est pas la
        même chose qu'avoir vérifié sans rien trouver (règle 1).
        """
        return self.controle is not None and self.controle.livrable


def _url(cle: str) -> str:
    """URL de telechargement, SIGNEE.

    Sans signature, `/media/` servait n'importe quel chemin a qui le devinait
    ou l'avait vu passer, sans limite de duree. Le lien reste ouvrable par qui
    le recoit — Brevo et le client final n'ont pas de session a presenter —
    mais il ne se devine plus et il expire.
    """
    from evkha import signatures  # noqa: PLC0415 — evite un cycle a l'import

    base = str(getattr(settings, "EVKHA_BASE_URL", "")).rstrip("/")
    return f"{base}{signatures.lien(cle)}"


def _retention(job: GenerationJob) -> timedelta:
    return timedelta(days=int(getattr(job.order.offer, "retention_days", 7) or 7))


def assembler_livrable_word(
    job: GenerationJob,
    *,
    convertisseur: ConvertisseurDocx | None = None,
    verifier: bool = True,
) -> LivrableAssemble:
    """Produit le `.docx`, le convertit en PDF, et enregistre les deux artefacts.

    Idempotent par (job, kind) : une relance met à jour les artefacts existants
    au lieu d'en empiler de nouveaux.

    Un échec de conversion **ne perd pas le Word**. L'artefact `docx` est
    enregistré prêt, l'artefact `pdf` est marqué en échec, et l'exception n'est
    pas propagée : le client a payé pour un livrable, pas pour une chaîne
    d'outils. L'échec reste visible en base, ce qui est le point.
    """
    racine = Path(str(getattr(settings, "MEDIA_ROOT", "") or "media"))
    cle_docx = f"livrables/{job.id}.docx"
    cle_pdf = f"livrables/{job.id}.pdf"

    livrable = produire_docx(job, destination=racine / cle_docx)
    octets = livrable.chemin.read_bytes()
    expire_le = timezone.now() + _retention(job)

    # La vérification porte sur le FICHIER, et elle passe avant l'enregistrement
    # des artefacts : ce qui refait le document après le contrôle doit être
    # contrôlé à son tour (règle 3). Ici plus rien ne le refait.
    controle = (
        verifier_livrable(job, livrable.chemin, assemblage=livrable.rapport)
        if verifier
        else None
    )
    if controle is not None and not controle.livrable:
        _log.error(
            "Job %s : livrable retenu à la vérification — %s",
            job.id, " | ".join(a.detail for a in controle.bloquantes),
        )

    artefact_docx, _ = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.DOCX,
        defaults={
            "status": ArtifactStatus.READY,
            "storage_key": cle_docx,
            "download_url": _url(cle_docx),
            "checksum_sha256": hashlib.sha256(octets).hexdigest(),
            "expires_at": expire_le,
        },
    )

    convertisseur = convertisseur or get_convertisseur_docx()
    try:
        conversion = convertisseur.convertir(livrable.chemin, racine / cle_pdf)
    except ConversionPdfError as erreur:
        _log.error("Job %s : conversion PDF échouée — %s", job.id, erreur)
        artefact_pdf, _ = DocumentArtifact.objects.update_or_create(
            job=job,
            kind=ArtifactKind.PDF,
            defaults={
                "status": ArtifactStatus.FAILED,
                "storage_key": "",
                "download_url": "",
                "checksum_sha256": "",
                "expires_at": expire_le,
            },
        )
        return LivrableAssemble(
            docx=artefact_docx, pdf=artefact_pdf, rapport=livrable.rapport,
            controle=controle,
        )

    artefact_pdf, _ = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.PDF,
        defaults={
            "status": ArtifactStatus.READY,
            "storage_key": cle_pdf,
            "download_url": _url(cle_pdf),
            "checksum_sha256": "",
            "expires_at": expire_le,
        },
    )
    _log.info(
        "Job %s : livrable Word et PDF prêts (%s, %s pages).",
        job.id, livrable.rapport.resume(), conversion.pages or "inconnu",
    )
    return LivrableAssemble(
        docx=artefact_docx,
        pdf=artefact_pdf,
        rapport=livrable.rapport,
        pages=conversion.pages,
        controle=controle,
    )
