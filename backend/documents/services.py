from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from generation.models import GenerationJob, JobStatus
from generation.rendering import (
    ClientDocument,
    render_branded_html,
    render_client_document,
)
from integrations.pdf import PdfClient, get_pdf_client

from .models import ArtifactKind, ArtifactStatus, DocumentArtifact
from .rendu_fidelite import RapportRendu, controler_rendu

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentAssembly:
    """Paire d'artefacts produits par assemble_document.

    - link : fichier HTML (aperçu navigateur, artefact LINK)
    - pdf  : livrable final WeasyPrint brandé (artefact PDF)
    """

    link: DocumentArtifact
    pdf: DocumentArtifact


class DocumentAssemblyError(RuntimeError):
    pass


# Limites de pages par type de livrable (§2 du cadrage EVKHA : "80 pages
# maximum" EM/BP, "45 pages maximum" EC/Strategie). Verifiees apres rendu
# WeasyPrint ; un depassement ouvre un incident MEDIUM (le document reste
# livrable, mais l'admin doit resserrer les max_words des blueprints).
_MAX_PAGES_BY_TYPE: dict[str, int] = {
    "market_study":      80,
    "business_plan":     80,
    "competitor_study":  45,
    "business_strategy": 45,
}


def _check_page_limit(job: GenerationJob, page_count: int) -> None:
    if page_count <= 0:
        return  # stub PDF ou moteur sans pagination : rien a verifier
    limit = _MAX_PAGES_BY_TYPE.get(str(job.deliverable_type))
    if limit is None or page_count <= limit:
        return
    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    OperationalIncident.objects.get_or_create(
        title=f"Limite de pages depassee (job {job.id})",
        defaults={
            "severity": IncidentSeverity.MEDIUM,
            "job": job,
            "order": job.order,
            "details": {
                "pages": page_count,
                "limite": limit,
                "deliverable_type": str(job.deliverable_type),
                "hint": "Resserrer max_words dans generation/blueprints.py.",
            },
        },
    )


def _retention_days(job: GenerationJob) -> int:
    return int(getattr(job.order.offer, "retention_days", 7) or 7)


def _incident_rendu(
    job: GenerationJob, rapport: RapportRendu, *, bloquant: bool
) -> None:
    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    OperationalIncident.objects.create(
        title=(
            f"Rendu infidele — assemblage bloque (job {job.id})"
            if bloquant
            else f"Rendu repare sans decoupage des tableaux (job {job.id})"
        ),
        severity=IncidentSeverity.HIGH if bloquant else IncidentSeverity.MEDIUM,
        job=job,
        order=job.order,
        details={
            "motifs": list(rapport.motifs),
            "lignes_markdown": rapport.lignes_markdown,
            "lignes_html": rapport.lignes_html,
            "balises_vides": rapport.balises_vides,
        },
    )


def _rendu_controle(
    job: GenerationJob, document: ClientDocument
) -> tuple[str, RapportRendu]:
    """Rend le HTML, controle sa fidelite, et REPARE si besoin.

    Une seule etape du rendu reecrit la structure du document : le decoupage
    des tableaux longs. C'est donc la seule qui peut en perdre — et elle l'a
    fait. La reparation consiste a re-rendre sans elle : un tableau qui deborde
    d'une page est moins beau, un tableau ampute est faux.

    Retourne le HTML retenu et le rapport correspondant. Si la reparation
    reussit, on livre le rendu repare et on trace un incident MEDIUM : le
    document est complet, mais quelque chose a du etre contourne.
    """
    markdown = document.to_markdown()

    html = render_branded_html(job)
    rapport = controler_rendu(html=html, markdown=markdown)
    if rapport.fidele:
        return html, rapport

    _log.warning(
        "assemble_document: rendu infidele pour job %s (%s) — tentative de "
        "reparation sans decoupage des tableaux.",
        job.id, rapport.motif,
    )
    html_repare = render_branded_html(job, chunk_tables=False)
    rapport_repare = controler_rendu(html=html_repare, markdown=markdown)
    if rapport_repare.fidele:
        _incident_rendu(job, rapport, bloquant=False)
        return html_repare, rapport_repare

    return html, rapport


def _verifier_completude_chapitres(
    job: GenerationJob, document: ClientDocument
) -> None:
    """Tous les chapitres prevus sont-ils la ? Sinon, pas de PDF.

    `render_client_document` ne retient que les chapitres DONE : un chapitre
    manquant disparait du livrable sans que rien ne le signale. Le gate le
    verifie deja, mais l'assemblage est appele par d'autres chemins (relance
    admin, PDF de relecture). Si le blueprint dit 20 chapitres, le PDF en a 20.

    Un job FAILED est explicitement exempte : son PDF sert justement a relire
    ce qui a ete produit avant l'echec.
    """
    if job.status != JobStatus.DONE:
        return
    from generation.blueprints import chapters_for_deliverable  # noqa: PLC0415

    attendus = {bp.number for bp in chapters_for_deliverable(job.deliverable_type)}
    if not attendus:
        return
    presents = {s.number for s in document.sections}
    manquants = sorted(attendus - presents)
    if manquants:
        msg = (
            f"Chapitre(s) absent(s) du livrable : {manquants}. Le PDF partirait "
            f"ampute ({len(presents)} chapitres sur {len(attendus)})."
        )
        raise DocumentAssemblyError(msg)


def assemble_document(
    job: GenerationJob,
    *,
    pdf_client: PdfClient | None = None,
) -> DocumentAssembly:
    """Assemble le livrable client (Rendering Engine) et génère le PDF brandé.

    Idempotent par (job, kind) : un re-run met à jour les artefacts existants.

    Flux :
    1. render_branded_html() → HTML complet A4 brandé client
    2. pdf_client.generate()  → HTML + PDF écrits dans MEDIA_ROOT (ou stub)
    3. update_or_create LINK (HTML) + PDF dans DocumentArtifact
    """
    allowed_statuses = (JobStatus.DONE, JobStatus.FAILED)
    if job.status not in allowed_statuses:
        msg = f"Cannot assemble document for job in status {job.status}."
        raise DocumentAssemblyError(msg)

    pdf_client = pdf_client or get_pdf_client()

    document = render_client_document(job)
    if not document.sections:
        msg = "No completed chapters to assemble."
        raise DocumentAssemblyError(msg)

    _verifier_completude_chapitres(job, document)

    # ── Boucle de controle du rendu, AVANT toute generation de PDF ──────
    # Le gate valide le markdown ; le moteur de rendu fabrique le HTML, et
    # personne ne regardait son resultat. `chunk_long_tables` detruisait les
    # lignes des tableaux de plus de 12 lignes — donc les tableaux financiers —
    # et le client recevait `<tbody><></><></></tbody>` a la place du compte de
    # resultat. Le markdown, lui, etait propre : le gate passait, le PDF partait
    # ampute.
    #
    # On ne se contente donc pas de bloquer : on REPARE puis on RECONTROLE, et
    # le PDF n'est produit qu'ensuite. Un incident ne doit pas etre la premiere
    # reponse a un defaut qu'on sait corriger.
    html, rapport = _rendu_controle(job, document)
    if not rapport.fidele:
        _incident_rendu(job, rapport, bloquant=True)
        msg = f"Rendu infidele au document valide : {rapport.motif}"
        raise DocumentAssemblyError(msg)

    html_checksum = hashlib.sha256(html.encode("utf-8")).hexdigest()
    result = pdf_client.generate(title=document.title, html=html)
    _check_page_limit(job, getattr(result, "page_count", 0))
    expires_at = timezone.now() + timedelta(days=_retention_days(job))

    link_artifact, _ = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.LINK,
        defaults={
            "status": ArtifactStatus.READY,
            "storage_key": result.html_storage_key,
            "download_url": result.html_download_url,
            "checksum_sha256": html_checksum,
            "expires_at": expires_at,
        },
    )
    pdf_artifact, _ = DocumentArtifact.objects.update_or_create(
        job=job,
        kind=ArtifactKind.PDF,
        defaults={
            "status": ArtifactStatus.READY,
            "storage_key": result.pdf_storage_key,
            "download_url": result.pdf_download_url,
            # Pas de checksum sur les octets binaires du PDF (non garanti stable).
            "checksum_sha256": "",
            "expires_at": expires_at,
        },
    )
    return DocumentAssembly(link=link_artifact, pdf=pdf_artifact)
