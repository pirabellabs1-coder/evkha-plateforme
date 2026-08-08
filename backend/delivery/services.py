from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact
from documents.services import DocumentAssembly, assemble_document
from generation.models import GenerationJob, JobStatus
from generation.rendering import render_client_document
from integrations.brevo import (
    EmailAttachment,
    TransactionalEmailClient,
    get_transactional_email_client,
)
from integrations.gamma import GammaClient, GammaError, GammaExportResult, get_gamma_client
from integrations.pdf import PdfClient, get_pdf_client
from monitoring.models import IncidentSeverity, OperationalIncident
from orders.models import OrderStatus

from .gamma_fidelite import RapportFidelite, controler_fidelite, extraire_texte_pdf
from .models import DeliveryBatch, DeliveryEvent, DeliveryStatus

_log = logging.getLogger(__name__)

#: Intitulés lus PAR LE CLIENT — objet du courriel et corps du message.
#:
#: Accentués : ils étaient écrits « Etude de marche » et « Strategie business »,
#: ce qui suffit à faire passer un livrable à 189 € pour un envoi automatique
#: bâclé. Ce sont des valeurs d'affichage, jamais des clés : rien ne les
#: compare, les accentuer ne casse aucun appariement.
_DELIVERABLE_LABELS: dict[str, str] = {
    "market_study":      "Étude de marché",
    "competitor_study":  "Étude de la concurrence",
    "business_plan":     "Business plan",
    "business_strategy": "Stratégie business",
}


class DeliveryError(RuntimeError):
    pass


class LivrableRetenuError(DeliveryError):
    """La vérification a bloqué le document : il ne part pas chez le client.

    Volontairement une erreur de livraison, et non un retour silencieux : elle
    emprunte le chemin d'échec existant, qui enregistre un lot FAILED et un
    incident HIGH. Un document que le système lui-même déclare défectueux ne
    doit pas partir, et le fait qu'il ne soit pas parti doit se voir.
    """


@dataclass(frozen=True)
class Assemblage:
    """Ce que la chaîne de rendu produit, quelle que soit la chaîne employée."""

    artefacts: tuple[DocumentArtifact, ...]
    #: URL portée par le lot de livraison. C'était le lien HTML ; la chaîne Word
    #: n'en produit pas, on retient donc le PDF.
    url_principale: str
    #: Motif de blocage, vide si le document est livrable.
    retenu: str = ""


def _assembler_livrable(
    job: GenerationJob, *, pdf_client: PdfClient | None
) -> Assemblage:
    """Assemble le livrable par la chaîne configurée.

    `assembler_livrable_word` existait depuis le lot 3, complète et testée, et
    **n'était appelée par rien** : le pipeline passait par `assemble_document`.
    Autrement dit, les graphiques sectoriels, les profils de secteur et les six
    contrôles de cohérence n'avaient jamais tourné sur un document livré. C'est
    le défaut que la règle 8 décrit, déjà vécu ici avec Gamma.

    Le choix de la chaîne ne se lit plus sur le seul drapeau : il se prend sur
    ce que le dossier contient (`chaine_word_active`). Un drapeau global décidait
    pour quatre livrables dont deux — business plan et stratégie — ne produisent
    ni socle ni chapitres structurés, et n'obtenaient donc AUCUN document.
    """
    from documents.livrable_word import (  # noqa: PLC0415
        assembler_livrable_word,
        chaine_word_active,
    )

    if not chaine_word_active(job):
        ancien: DocumentAssembly = assemble_document(job, pdf_client=pdf_client)
        retenu_ancien = _controler_document_herite(job, ancien.html)
        return Assemblage(
            artefacts=(ancien.link, ancien.pdf),
            url_principale=ancien.link.download_url,
            retenu=retenu_ancien,
        )

    livrable = assembler_livrable_word(job)
    artefacts = tuple(
        artefact for artefact in (livrable.docx, livrable.pdf) if artefact is not None
    )
    # Le PDF si la conversion a réussi, sinon le Word : un échec de conversion
    # ne doit pas priver le client du document qu'il a payé.
    principale = (
        livrable.pdf.download_url
        if livrable.pdf is not None and livrable.pdf.status == ArtifactStatus.READY
        else livrable.docx.download_url
    )
    bloquantes = livrable.controle.bloquantes if livrable.controle else []
    retenu = (
        ""
        if livrable.livrable
        else " | ".join(anomalie.detail for anomalie in bloquantes)
        or "vérification non exécutée"
    )
    return Assemblage(
        artefacts=artefacts, url_principale=principale, retenu=retenu
    )


#: Marqueur lu par le tableau de bord : ce dossier est parti avec un contrôle
#: de moins que l'étude de marché. Il disparaîtra le jour où le business plan
#: et la stratégie rejoindront le moteur structuré.
INCIDENT_TYPE_CONTROLE_FICHIER_ABSENT = "controle_fichier_absent"


def _controler_document_herite(job: GenerationJob, html: str) -> str:
    """Contrôle de contenu du document livré par la chaîne héritée.

    Le contrôle de contenu du lot 4 ne s'appliquait qu'aux études de marché et
    concurrentielle : il ouvre un `.docx` et compare au socle. Le business plan
    et la stratégie n'ont ni l'un ni l'autre — ils partaient donc **sans aucun
    contrôle du fichier**, avec pour seul filet le contrôle de rendu (fidélité
    HTML/markdown) et le gate en amont.

    Deux des six contrôles ne demandent pourtant pas de socle, et ce sont ceux
    qui ont attrapé les désastres de ce dépôt : intégrité (tableaux vidés de
    leurs lignes, document sans prose) et densité. Ils s'exécutent désormais sur
    le HTML **exactement tel qu'il a été livré**, pas sur un second rendu.

    Ce qui BLOQUE : aucun tableau, un tableau sans une seule cellule remplie,
    aucun texte. Trois défauts que le lecteur constate en ouvrant le document.
    La densité, elle, n'émet que des avertissements — la cliente a refusé une
    livraison pour cette raison, mais un document dense à 35 % au lieu de 40
    reste un document.

    Ce qui NE tourne PAS reste dit, dans un incident : les quatre contrôles qui
    comparent au socle. Ne pas avoir vérifié n'est pas la même chose qu'avoir
    vérifié sans rien trouver (règle 1).

    Renvoie le motif de blocage, ou la chaîne vide.
    """
    from generation.verification.lecture import lire_livrable_html  # noqa: PLC0415
    from generation.verification.services import (  # noqa: PLC0415
        verifier_document_sans_socle,
    )

    rapport = verifier_document_sans_socle(lire_livrable_html(html))
    _signaler_controle_partiel(job, rapport.resume())
    if rapport.bloquantes:
        return " | ".join(anomalie.detail for anomalie in rapport.bloquantes)
    return ""


def _signaler_controle_partiel(job: GenerationJob, resume: str) -> None:
    """Dit ce qui a été contrôlé sur ce document — ET ce qui ne l'a pas été.

    Quatre des six contrôles du lot 4 comparent au socle. Le business plan et
    la stratégie n'en ont pas : ces quatre-là ne peuvent rien dire d'eux.
    Passer sous silence cette moitié manquante la ferait passer pour un « rien
    à signaler », et c'est exactement le défaut que la chaîne Word nomme
    elle-même : « ne pas avoir vérifié n'est pas la même chose qu'avoir vérifié
    sans rien trouver » (règle 1).

    L'incident nomme donc les contrôles EXÉCUTÉS autant que les manquants — un
    incident qui n'énumérerait que les absents laisserait croire que rien n'a
    été vérifié, ce qui est faux et démobilise autant qu'un silence.

    Un incident par job (`update_or_create`) : une relivraison ne doit pas
    empiler des doublons qui noieraient les vrais incidents.
    """
    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    OperationalIncident.objects.update_or_create(
        job=job,
        title=f"Contrôle de contenu partiel sur le fichier livré (job {job.id})"[:200],
        defaults={
            "severity": IncidentSeverity.MEDIUM,
            "order": job.order,
            "details": {
                "type": INCIDENT_TYPE_CONTROLE_FICHIER_ABSENT,
                "livrable": str(job.deliverable_type),
                "controles_executes": [
                    "gate de livraison",
                    "complétude des chapitres",
                    "fidélité du rendu HTML au markdown validé",
                    "intégrité du fichier livré (tableaux, prose)",
                    "densité du fichier livré",
                ],
                "resultat_sur_le_fichier": resume,
                "controles_manquants": [
                    "chiffres hors socle",
                    "couverture du socle",
                    "hiérarchie des marchés",
                    "visuels abandonnés à l'assemblage",
                ],
                "cause": (
                    "Ces quatre contrôles comparent au socle verrouillé. Ce "
                    "livrable tourne sur le moteur hérité : il n'en a pas."
                ),
            },
        },
    )


def _retention_days(job: GenerationJob) -> int:
    """Délégué à `evkha.retention` : ce repli `7` était l'une de cinq copies.

    C'est ce nombre que le courriel annonce au client (« valable N jours »). Il
    doit donc être le même que celui qui date la signature du lien, sans quoi la
    promesse est fausse — et invérifiable, puisque le lien mort répond 404.
    """
    from evkha import retention  # noqa: PLC0415 — evite un cycle a l'import

    return retention.jours(job)


def _expires_at(job: GenerationJob) -> datetime:
    return timezone.now() + timedelta(days=_retention_days(job))


def _theme_id_for(job: GenerationJob) -> str:
    """Theme Gamma : surcharge de la commande, sinon reglage, sinon AUCUN.

    Le repli etait `"evkha-default"`, un identifiant invente qui n'existe dans
    aucun compte Gamma. Consequence : chaque generation renvoyait
    HTTP 400 « Theme with id evkha-default not found », l'erreur etait avalee
    et la livraison repartait en WeasyPrint sans bruit. Gamma n'aurait donc
    jamais rien produit, meme cle et flag corrects.

    Le reglage `GAMMA_THEME_ID` existait pourtant depuis le debut (settings) et
    n'etait tout simplement pas lu ici.

    Chaine vide = on n'envoie pas `themeId` du tout, et Gamma applique son
    theme par defaut (verifie : HTTP 201). Mieux vaut le theme par defaut de
    Gamma qu'un identifiant fictif qui fait echouer l'appel.
    """
    raw_payload = job.order.raw_payload or {}
    if isinstance(raw_payload, dict):
        theme_id = raw_payload.get("gamma_theme_id") or raw_payload.get("theme_id")
        if theme_id:
            return str(theme_id)
    return str(getattr(settings, "GAMMA_THEME_ID", "") or "")


def sujet_de_livraison(job: GenerationJob) -> str:
    """Objet du courriel qui annonce l'étude terminée.

    Il était `f"Livrables EVKHA - {systeme_order_id}"` pour tout le monde. Cet
    identifiant vient de Systeme.io ; pour une commande passée depuis l'espace
    client, `commandes.creer_commande` le fabrique sous la forme
    `espace-a1b2c3d4e5f6`. Le client recevait donc dans sa boîte un objet
    contenant une référence interne qui ne lui dit rien et qu'il ne peut citer
    nulle part.

    Ce qui l'intéresse tient en deux mots : quel document, et pour qui. On les
    lui donne, et la référence reste dans le corps du message pour le support.
    """
    intitule = _DELIVERABLE_LABELS.get(
        str(job.deliverable_type), str(job.deliverable_type)
    )
    organisation = getattr(job.order, "organisation", None)
    if organisation is not None:
        return f"Votre {intitule.lower()} est prête — {organisation.raison_sociale}"
    return f"Livrables EVKHA - {job.order.systeme_order_id}"


def _html_body(job: GenerationJob, artifacts: tuple[DocumentArtifact, ...]) -> str:
    order_id_safe = escape(job.order.systeme_order_id)
    deliverable_label = escape(
        _DELIVERABLE_LABELS.get(str(job.deliverable_type), str(job.deliverable_type))
    )
    retention = _retention_days(job)

    # Bouton principal : PDF Gamma (moteur de mise en page privilegie) si
    # present, sinon PDF WeasyPrint (repli), sinon lien HTML.
    gamma_pdf_artifact = next(
        (a for a in artifacts if a.kind == ArtifactKind.GAMMA_PDF and a.download_url), None
    )
    pdf_artifact = next(
        (a for a in artifacts if a.kind == ArtifactKind.PDF and a.download_url), None
    )
    link_artifact = next(
        (a for a in artifacts if a.kind == ArtifactKind.LINK and a.download_url), None
    )
    primary = gamma_pdf_artifact or pdf_artifact or link_artifact
    button_html = ""
    if primary:
        btn_label = (
            "Telecharger votre document (PDF)"
            if primary.kind in {ArtifactKind.PDF, ArtifactKind.GAMMA_PDF}
            else "Visualiser votre document"
        )
        button_html = (
            f'<p style="margin:28px 0;">'
            f'<a href="{escape(primary.download_url)}" '
            f'style="background:#1a1a2e;color:#ffffff;padding:13px 26px;'
            f'text-decoration:none;border-radius:4px;font-size:14px;font-weight:600;">'
            f'{btn_label}'
            f'</a></p>'
        )

    # Lien HTML de visualisation en complement du PDF
    preview_html = ""
    if link_artifact and primary is not link_artifact:
        preview_html = (
            f'<p style="margin:12px 0;font-size:13px;">'
            f'Vous pouvez egalement '
            f'<a href="{escape(link_artifact.download_url)}" style="color:#1a1a2e;">'
            f'visualiser votre document dans votre navigateur</a>.'
            f'</p>'
        )

    # Pieces jointes listees si presentes
    attached = [
        a for a in artifacts
        if a.kind in {ArtifactKind.PDF, ArtifactKind.GAMMA_PDF, ArtifactKind.GAMMA_PPTX}
        and a.download_url
    ]
    attachment_note = (
        "<p>Votre document est egalement disponible en piece jointe a cet e-mail.</p>"
        if attached else ""
    )

    return (
        "<p>Madame, Monsieur,</p>"
        "<p>Nous avons le plaisir de vous informer que votre document est pret.</p>"
        "<table style='border-collapse:collapse;margin:16px 0'>"
        f"<tr><td style='padding:4px 16px 4px 0;color:#666;'>Type de document</td>"
        f"<td style='padding:4px 0;font-weight:600;'>{deliverable_label}</td></tr>"
        f"<tr><td style='padding:4px 16px 4px 0;color:#666;'>Reference commande</td>"
        f"<td style='padding:4px 0;'>{order_id_safe}</td></tr>"
        "</table>"
        f"{button_html}"
        f"{preview_html}"
        f"{attachment_note}"
        f"<p style='color:#888;font-size:12px;'>"
        f"Ce lien de telechargement est valable {retention} jours.</p>"
        "<p style='margin-top:32px;'>Cordialement,<br>"
        "L'equipe EVKHA<br>"
        "<a href='mailto:contact@evkha.fr' style='color:#1a1a2e;'>contact@evkha.fr</a></p>"
    )


def notify_generation_started(
    job: GenerationJob,
    *,
    email_client: TransactionalEmailClient | None = None,
) -> None:
    """Envoie un email de confirmation au client des le lancement de la generation.

    Non bloquant : l'echec est logue mais ne fait pas echouer la generation.
    """
    if not job.order.customer.email:
        return
    email_client = email_client or get_transactional_email_client()
    deliverable_label = escape(
        _DELIVERABLE_LABELS.get(str(job.deliverable_type), str(job.deliverable_type))
    )
    order_id_safe = escape(job.order.systeme_order_id)
    html = (
        "<p>Madame, Monsieur,</p>"
        "<p>Nous vous confirmons la bonne reception de votre demande. "
        "La generation de votre document est en cours.</p>"
        "<table style='border-collapse:collapse;margin:16px 0'>"
        f"<tr><td style='padding:4px 16px 4px 0;color:#666;'>Type de document</td>"
        f"<td style='padding:4px 0;font-weight:600;'>{deliverable_label}</td></tr>"
        f"<tr><td style='padding:4px 16px 4px 0;color:#666;'>Reference commande</td>"
        f"<td style='padding:4px 0;'>{order_id_safe}</td></tr>"
        "</table>"
        "<p>Vous recevrez votre document par e-mail des que la generation sera terminee. "
        "Ce processus prend generalement entre 10 et 20 minutes.</p>"
        "<p style='margin-top:32px;'>Cordialement,<br>"
        "L'equipe EVKHA<br>"
        "<a href='mailto:contact@evkha.fr' style='color:#1a1a2e;'>contact@evkha.fr</a></p>"
    )
    try:
        email_client.send_delivery_email(
            recipient_email=job.order.customer.email,
            subject="Votre livrable est en cours de generation - EVKHA",
            html_body=html,
            attachments=(),
        )
    except Exception:  # noqa: BLE001
        _log.warning("notify_generation_started: echec envoi email pour job %s", job.id)


#: Extension de REPLI, quand ni le fichier stocké ni l'URL n'en portent une.
_EXTENSIONS_PAR_NATURE: dict[str, str] = {
    ArtifactKind.DOCX: "docx",
    ArtifactKind.PDF: "pdf",
    ArtifactKind.GAMMA_PDF: "pdf",
    ArtifactKind.GAMMA_PPTX: "pptx",
    ArtifactKind.LINK: "html",
}


def _attachment_filename(artifact: DocumentArtifact, order_id: str) -> str:
    """Nom de fichier lisible : ex. `EVKHA_order123_docx.docx`.

    L'extension vient du FICHIER, pas d'une liste de cas. Elle était calculée
    par `"pptx" si GAMMA_PPTX sinon "pdf"` — deux cas énumérés, et tout le
    reste devenait `.pdf`. Le Word serait donc parti chez la cliente nommé
    `EVKHA_…_docx.pdf` : un document Word portant l'extension d'un PDF, que son
    ordinateur aurait refusé d'ouvrir correctement.

    Ajouter `docx` à l'énumération aurait refait la même faute au type suivant.
    Un correctif qui énumère des cas est incomplet (règle 4).
    """
    slug = order_id.replace(" ", "_")[:40]
    depuis_fichier = Path(str(artifact.storage_key or "")).suffix
    depuis_url = Path(urlparse(str(artifact.download_url or "")).path).suffix
    extension = (
        (depuis_fichier or depuis_url).lstrip(".").lower()
        or _EXTENSIONS_PAR_NATURE.get(str(artifact.kind), "bin")
    )
    label = "gamma_pptx" if artifact.kind == ArtifactKind.GAMMA_PPTX else artifact.kind
    return f"EVKHA_{slug}_{label}.{extension}"


def _persist_gamma_artifacts(
    job: GenerationJob,
    *,
    export: GammaExportResult,
    presentation_id: str,
) -> list[DocumentArtifact]:
    """Persiste les artefacts Gamma en base (DB uniquement, aucun appel reseau).

    Ne persiste QUE les formats reellement exportes : l'API Gamma reelle
    n'exporte qu'un format par generation (PDF), donc pptx_url est souvent
    vide et ne doit pas creer un artefact READY sans URL.
    """
    common = {
        "status": ArtifactStatus.READY,
        "expires_at": _expires_at(job),
        "checksum_sha256": "",
    }
    artifacts: list[DocumentArtifact] = []
    if export.pdf_url:
        gamma_pdf, _ = DocumentArtifact.objects.update_or_create(
            job=job,
            kind=ArtifactKind.GAMMA_PDF,
            defaults={
                **common,
                "storage_key": f"gamma/{presentation_id}/pdf",
                "download_url": export.pdf_url,
            },
        )
        artifacts.append(gamma_pdf)
    if export.pptx_url:
        gamma_pptx, _ = DocumentArtifact.objects.update_or_create(
            job=job,
            kind=ArtifactKind.GAMMA_PPTX,
            defaults={
                **common,
                "storage_key": f"gamma/{presentation_id}/pptx",
                "download_url": export.pptx_url,
            },
        )
        artifacts.append(gamma_pptx)
    return artifacts


def ensure_gamma_artifacts(
    job: GenerationJob,
    *,
    gamma_client: GammaClient | None = None,
) -> list[DocumentArtifact]:
    """Genere la presentation Gamma et persiste les artefacts.

    Appels reseau (create_presentation, wait_until_ready, export) effectues
    EN DEHORS de toute transaction atomique pour eviter de bloquer la connexion
    DB pendant les 5-30 s de polling Gamma.

    Risque 5 — si l'API Gamma echoue (non configuree, timeout, erreur reseau),
    on logue un warning et on retourne [] : la livraison continue avec le PDF
    WeasyPrint (repli). Gamma est le moteur de mise en page privilegie, jamais
    un point de defaillance unique.
    """
    if not job.order.offer.gamma_enabled:
        return []

    gamma_client = gamma_client or get_gamma_client()
    document = render_client_document(job)
    # `card_breaks=True` : un `---` par section, que Gamma respecte via
    # `cardSplit=inputTextBreaks`. Sans cela Gamma decide seul et compresse
    # tout dans son defaut de 10 cartes.
    markdown = document.to_markdown(card_breaks=True)

    try:
        # I/O reseau -- pas de transaction ouverte ici.
        presentation = gamma_client.create_presentation(
            title=document.title,
            markdown=markdown,
            theme_id=_theme_id_for(job),
        )
        gamma_client.wait_until_ready(presentation_id=presentation.presentation_id)
        export = gamma_client.export(presentation=presentation)
    except (NotImplementedError, GammaError) as exc:
        _log.warning(
            "ensure_gamma_artifacts: Gamma indisponible pour job %s (%s) — "
            "artefacts Gamma ignores, livraison PDF WeasyPrint maintenue.",
            job.id, exc,
        )
        return []

    # Gamma REECRIT le document : on verifie sa sortie avant de la livrer.
    # Le gate valide le markdown, puis Gamma refait tout — et rien ne
    # controlait le resultat. C'est ainsi que 5 verticales sur 10 ont ete
    # effacees APRES validation, en silence.
    rapport = _controler_pdf_gamma(job, export=export, markdown=markdown)
    if not rapport.fidele:
        _log.warning(
            "ensure_gamma_artifacts: PDF Gamma INFIDELE pour job %s — %s "
            "Artefacts Gamma ignores, livraison PDF WeasyPrint maintenue.",
            job.id, rapport.motif,
        )
        OperationalIncident.objects.create(
            title=f"PDF Gamma infidele — repli WeasyPrint (job {job.id})",
            severity=IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details={
                "motif": rapport.motif,
                "mots_source": rapport.mots_source,
                "mots_pdf": rapport.mots_pdf,
                "verticales_perdues": list(rapport.verticales_perdues),
                "pdf_url": export.pdf_url,
            },
        )
        return []

    # Uniquement des ecritures DB a partir d'ici.
    return _persist_gamma_artifacts(
        job,
        export=export,
        presentation_id=presentation.presentation_id,
    )


def _verticales_du_brief(job: GenerationJob) -> tuple[str, ...]:
    from generation.models import FactProvenance  # noqa: PLC0415

    fait = job.coherence_facts.filter(
        is_locked=True, provenance=FactProvenance.CLIENT, key="verticales"
    ).first()
    if fait is None or not fait.value.strip():
        return ()
    import re as _re  # noqa: PLC0415

    return tuple(v.strip() for v in _re.split(r"[/,;]|\n", fait.value) if v.strip())


def _controler_pdf_gamma(
    job: GenerationJob, *, export: GammaExportResult, markdown: str
) -> RapportFidelite:
    """Telecharge le PDF Gamma et verifie qu'il restitue bien le document."""
    if not export.pdf_url:
        return RapportFidelite(
            fidele=True, mots_source=len(markdown.split()), mots_pdf=0,
            verticales_perdues=(), motif="Pas d'URL PDF : rien a controler.",
        )
    try:
        import httpx  # noqa: PLC0415 — dependance optionnelle

        reponse = httpx.get(export.pdf_url, timeout=60.0, follow_redirects=True)
        reponse.raise_for_status()
        contenu = reponse.content
    except Exception as exc:  # noqa: BLE001 — un controle rate ne casse pas la livraison
        _log.warning(
            "_controler_pdf_gamma: telechargement impossible pour job %s (%s) — "
            "controle de fidelite non effectue.",
            job.id, exc,
        )
        return RapportFidelite(
            fidele=True, mots_source=len(markdown.split()), mots_pdf=0,
            verticales_perdues=(), motif=f"PDF non telechargeable : {exc}",
        )

    return controler_fidelite(
        texte_pdf=extraire_texte_pdf(contenu),
        markdown_source=markdown,
        verticales=_verticales_du_brief(job),
    )


def generate_pdf_for_failed_job(
    job: GenerationJob,
    *,
    pdf_client: PdfClient | None = None,
) -> DocumentArtifact:
    """Genere le PDF admin d'un job FAILED (budget depasse) sans envoyer d'email.

    Permet a l'admin de telecharger le livrable partiel ou complet meme quand
    la generation a ete interrompue par le circuit breaker budget.
    N'envoie PAS d'email au client. Ne marque pas la commande DELIVERED.
    """
    if job.status != JobStatus.FAILED:
        msg = f"generate_pdf_for_failed_job attend un job FAILED, recu {job.status}."
        raise DeliveryError(msg)

    from documents.services import assemble_document  # noqa: PLC0415
    pdf_client = pdf_client or get_pdf_client()
    try:
        assembly = assemble_document(job, pdf_client=pdf_client)
        return assembly.pdf
    except Exception as exc:
        OperationalIncident.objects.create(
            title=f"Erreur generation PDF (job failed) {job.id}",
            severity=IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details={"error": str(exc)},
        )
        raise DeliveryError(str(exc)) from exc


def deliver_job(
    job: GenerationJob,
    *,
    pdf_client: PdfClient | None = None,
    gamma_client: GammaClient | None = None,
    email_client: TransactionalEmailClient | None = None,
) -> DeliveryBatch:
    """Orchestre la livraison complete d'un job termine.

    Architecture d'atomicite :
    1. Appels externes (PDF WeasyPrint, Gamma, email) AVANT la transaction principale.
    2. Ecriture en base dans une transaction atomique.
    3. Sur echec, persistence des traces (batch FAILED + incident) dans une
       transaction SEPAREE pour survivre au rollback de la transaction principale.
    """
    if job.status != JobStatus.DONE:
        msg = f"Cannot deliver job in status {job.status}."
        raise DeliveryError(msg)

    pdf_client = pdf_client or get_pdf_client()
    email_client = email_client or get_transactional_email_client()
    gamma_client = gamma_client or get_gamma_client()

    try:
        # --- I/O externe (pas de transaction ouverte) ---
        # Les deux chaînes sont idempotentes via update_or_create.
        assemblage = _assembler_livrable(job, pdf_client=pdf_client)
        if assemblage.retenu:
            # Avant tout envoi. Un document que la vérification bloque ne part
            # pas, et l'incident dit pourquoi (règle 1 : échouer bruyamment).
            msg = f"Livrable retenu à la vérification : {assemblage.retenu}"
            raise LivrableRetenuError(msg)

        gamma_artifacts = ensure_gamma_artifacts(job, gamma_client=gamma_client)
        all_artifacts: tuple[DocumentArtifact, ...] = (
            *assemblage.artefacts,
            *gamma_artifacts,
        )

        # Le Word est joint lui aussi : c'est le document que la cliente
        # retravaille, le PDF n'en est que la photographie.
        attachments = tuple(
            EmailAttachment(
                filename=_attachment_filename(artifact, job.order.systeme_order_id),
                url=artifact.download_url,
            )
            for artifact in all_artifacts
            if artifact.download_url
            and artifact.kind
            in {
                ArtifactKind.DOCX,
                ArtifactKind.PDF,
                ArtifactKind.GAMMA_PDF,
                ArtifactKind.GAMMA_PPTX,
            }
        )
        result = email_client.send_delivery_email(
            recipient_email=job.order.customer.email,
            subject=sujet_de_livraison(job),
            html_body=_html_body(job, all_artifacts),
            attachments=attachments,
        )

        # --- Transaction DB pure (aucun I/O reseau) ---
        with transaction.atomic():
            batch, _created = DeliveryBatch.objects.update_or_create(
                order=job.order,
                defaults={
                    "status": DeliveryStatus.SENT,
                    "email_provider": "brevo",
                    "recipient_email": job.order.customer.email,
                    "download_url": assemblage.url_principale,
                    "error_message": "",
                    "sent_at": timezone.now(),
                },
            )
            batch.artifacts.set(all_artifacts)
            DeliveryEvent.objects.create(
                batch=batch,
                status=DeliveryStatus.SENT,
                message="Livraison envoyee",
                provider_message_id=result.provider_message_id,
            )
            job.order.status = OrderStatus.DELIVERED
            job.order.save(update_fields=["status", "updated_at"])
            return batch

    except Exception as exc:
        # Transaction separee pour survivre au rollback de la transaction principale
        # et garantir que l'incident + le batch FAILED sont toujours persistes.
        try:
            with transaction.atomic():
                DeliveryBatch.objects.update_or_create(
                    order=job.order,
                    defaults={
                        "status": DeliveryStatus.FAILED,
                        "email_provider": "brevo",
                        "recipient_email": job.order.customer.email,
                        "error_message": str(exc),
                    },
                )
                OperationalIncident.objects.create(
                    title="Echec livraison livrable",
                    severity=IncidentSeverity.HIGH,
                    order=job.order,
                    job=job,
                    details={"error": str(exc)},
                )
        except Exception:  # noqa: BLE001 - on ne peut pas faire grand chose ici
            pass  # l'exception originale est relancee ci-dessous

        raise DeliveryError(str(exc)) from exc


def send_email_for_job(
    job: GenerationJob,
    *,
    email_client: TransactionalEmailClient | None = None,
) -> DeliveryBatch:
    """Envoie l'email de livraison avec les artefacts existants en base.

    N'effectue aucune generation PDF. Utile pour renvoyer un email depuis le dashboard.
    """
    if job.status != JobStatus.DONE:
        msg = f"Cannot send email for job in status {job.status}."
        raise DeliveryError(msg)

    email_client = email_client or get_transactional_email_client()

    artifacts = tuple(
        DocumentArtifact.objects.filter(
            job=job,
            status=ArtifactStatus.READY,
        ).exclude(download_url="")
    )

    attachments = tuple(
        EmailAttachment(
            filename=_attachment_filename(artifact, job.order.systeme_order_id),
            url=artifact.download_url,
        )
        for artifact in artifacts
        if artifact.kind in {ArtifactKind.PDF, ArtifactKind.GAMMA_PDF, ArtifactKind.GAMMA_PPTX}
        and artifact.download_url
    )

    try:
        result = email_client.send_delivery_email(
            recipient_email=job.order.customer.email,
            subject=sujet_de_livraison(job),
            html_body=_html_body(job, artifacts),
            attachments=attachments,
        )

        link_artifact = next(
            (a for a in artifacts if a.kind == ArtifactKind.LINK and a.download_url),
            None,
        )

        with transaction.atomic():
            batch, _ = DeliveryBatch.objects.update_or_create(
                order=job.order,
                defaults={
                    "status": DeliveryStatus.SENT,
                    "email_provider": "brevo",
                    "recipient_email": job.order.customer.email,
                    "download_url": link_artifact.download_url if link_artifact else "",
                    "error_message": "",
                    "sent_at": timezone.now(),
                },
            )
            if artifacts:
                batch.artifacts.set(artifacts)
            DeliveryEvent.objects.create(
                batch=batch,
                status=DeliveryStatus.SENT,
                message="Email envoye depuis le dashboard",
                provider_message_id=result.provider_message_id,
            )
            job.order.status = OrderStatus.DELIVERED
            job.order.save(update_fields=["status", "updated_at"])
            return batch

    except Exception as exc:
        try:
            with transaction.atomic():
                DeliveryBatch.objects.update_or_create(
                    order=job.order,
                    defaults={
                        "status": DeliveryStatus.FAILED,
                        "email_provider": "brevo",
                        "recipient_email": job.order.customer.email,
                        "error_message": str(exc),
                    },
                )
                if isinstance(exc, LivrableRetenuError):
                    # Le job restait DONE : l'espace client continuait donc de
                    # presenter le document en telechargement, alors que la
                    # verification venait de le declarer defectueux. Le controle
                    # protegeait le courriel, pas ce que le lecteur allait
                    # ouvrir (regle 3).
                    #
                    # `INTERVENTION_REQUISE` existait deja et signifie exactement
                    # cela : produit, mais aucun envoi client possible.
                    GenerationJob.objects.filter(pk=job.pk).update(
                        status=JobStatus.INTERVENTION_REQUISE,
                        error_message=str(exc)[:2000],
                    )
                    OperationalIncident.objects.create(
                        title=f"Livrable retenu a la verification (job {job.id})",
                        severity=IncidentSeverity.HIGH,
                        job=job,
                        order=job.order,
                        details={
                            "motif": str(exc),
                            "consigne": (
                                "Aucun e-mail client n'est parti et le document "
                                "n'est PAS telechargeable depuis l'espace. "
                                "Corriger la cause, puis relancer le job."
                            ),
                        },
                    )
        except Exception:  # noqa: BLE001
            pass
        raise DeliveryError(str(exc)) from exc


def purge_expired_artifacts(*, now: datetime | None = None) -> int:
    """Supprime les documents arrivés à échéance — **du disque**, pas seulement
    de la base.

    Cette fonction ne faisait que basculer un statut et vider `download_url`.
    Le fichier, lui, restait dans `MEDIA_ROOT`, à une adresse que
    `django.views.static.serve` continuait de servir sans authentification :
    l'étude de marché d'un client final restait donc téléchargeable
    indéfiniment par quiconque avait vu passer le lien.

    La rétention était pourtant invoquée comme une garantie de confidentialité,
    en toutes lettres, dans le commentaire de la route `/media/`. Une garantie
    écrite et non tenue est le défaut de la règle 1 : elle a dispensé de poser
    la vraie protection.

    L'échec de suppression d'un fichier n'interrompt pas la purge : un artefact
    déjà absent du disque — nettoyage manuel, volume recréé — ne doit pas
    laisser tous les suivants en place. Il est journalisé, et le statut bascule
    quand même, sans quoi la purge le repasserait indéfiniment.
    """
    now = now or timezone.now()
    expired = DocumentArtifact.objects.filter(
        status=ArtifactStatus.READY,
        expires_at__isnull=False,
        expires_at__lte=now,
    )

    # On lit les cles AVANT le `update` : ensuite le filtre ne les retrouve
    # plus, et on supprimerait zero fichier en croyant en supprimer tous.
    cles = [cle for cle in expired.values_list("storage_key", flat=True) if cle]
    count = expired.count()
    expired.update(status=ArtifactStatus.EXPIRED, download_url="")

    for cle in cles:
        try:
            if default_storage.exists(cle):
                default_storage.delete(cle)
        except Exception:  # noqa: BLE001 — un fichier recalcitrant n'arrete pas la purge
            _log.exception("Purge : suppression impossible pour %s", cle)

    return count
