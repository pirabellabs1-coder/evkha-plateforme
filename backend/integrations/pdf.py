from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from django.conf import settings


@dataclass(frozen=True)
class PdfGenerationResult:
    """Résultat d'une génération PDF brandé.

    Contient les références des deux artefacts produits :
    - HTML (aperçu navigateur, artefact LINK)
    - PDF  (livrable final, artefact PDF)
    """

    html_storage_key: str
    html_download_url: str
    pdf_bytes: bytes
    pdf_storage_key: str
    pdf_download_url: str
    # Nombre de pages du PDF rendu (§2 cadrage : limites 80/45 pages).
    # 0 = inconnu (stub, ou moteur sans pagination).
    page_count: int = 0


@runtime_checkable
class PdfClient(Protocol):
    """Génère un livrable PDF brandé à partir d'un titre et d'un corps HTML.

    `duree_lien_s` est la durée de validité des liens produits. Le client ne la
    DÉCIDE pas — il ne connaît ni le dossier ni son offre —, il l'applique. La
    politique reste chez l'appelant, qui la tire de `evkha/retention.py`.
    """

    def generate(
        self, *, title: str, html: str, duree_lien_s: int | None = None
    ) -> PdfGenerationResult: ...


class StubPdfClient:
    """Client PDF déterministe pour dev/CI : aucune écriture disque, URLs simulées.

    Le digest est calculé sur les 256 premiers caractères du HTML pour garantir
    la reproductibilité sans dépendre de WeasyPrint.
    """

    def generate(
        self, *, title: str, html: str, duree_lien_s: int | None = None
    ) -> PdfGenerationResult:
        # `duree_lien_s` est ignoree : le bouchon ne produit aucune URL servie
        # par `/media/`, donc aucune signature a dater.
        digest = hashlib.sha256(f"{title}:{html[:256]}".encode()).hexdigest()[:16]
        return PdfGenerationResult(
            html_storage_key=f"stub/html/{digest}.html",
            html_download_url=f"https://preview.evkha.local/{digest}.html",
            pdf_bytes=f"%PDF-1.4\n%%stub-evkha-{digest}\n%%EOF\n".encode(),
            pdf_storage_key=f"stub/pdf/{digest}.pdf",
            pdf_download_url=f"https://pdf.evkha.local/{digest}.pdf",
        )


class WeasyPrintPdfClient:
    """Génère un PDF via WeasyPrint (pip install systeme-evkha[pdf]).

    Écrit deux fichiers dans MEDIA_ROOT :
    - artifacts/html/{digest}.html  → artefact LINK (aperçu)
    - artifacts/pdf/{digest}.pdf    → artefact PDF  (livrable final)
    """

    def __init__(self, media_root: Path, base_url: str = "") -> None:
        # `media_url` a disparu des parametres : le prefixe `/media/` vit
        # desormais dans `signatures.lien`, avec la signature qui l'accompagne.
        # Le garder ici aurait laisse croire qu'on peut changer le prefixe a cet
        # endroit — alors que la route et le signataire ne l'auraient pas suivi.
        self._media_root = media_root
        self._base_url = base_url.rstrip("/")

    def url_de_telechargement(self, cle: str, duree_s: int | None = None) -> str:
        """Adresse publique d'un fichier de `MEDIA_ROOT`, **signée**.

        Ce client assemblait `{base}{MEDIA_URL}/{cle}` a la main. Or
        `servir_media` exige une signature horodatee, et repond `404` quand
        elle manque — volontairement indiscernable d'un fichier absent, pour ne
        pas devenir un oracle d'enumeration.

        Consequence : le bouton du courriel de livraison menait a une page
        d'erreur, et rien ne disait pourquoi. Ni les journaux ni le tableau de
        bord n'avaient de quoi alerter — la requete avait ete servie
        correctement, avec le code qu'on lui avait demande de rendre. La
        protection ne s'etait pas trompee ; c'est le producteur du lien qui
        n'avait pas suivi.

        Passer par `signatures.lien` plutot que de reconstruire l'adresse ici
        garantit qu'il n'existe qu'UNE facon de fabriquer une URL de media
        (regle 5) : la prochaine evolution du schema de signature n'aura pas a
        etre repercutee dans ce fichier.
        """
        from evkha import signatures  # noqa: PLC0415 — evite un cycle a l'import

        return f"{self._base_url}{signatures.lien(cle, duree_s)}"

    def generate(
        self, *, title: str, html: str, duree_lien_s: int | None = None
    ) -> PdfGenerationResult:
        from weasyprint import HTML as WeasyHTML

        digest = hashlib.sha256(f"{title}:{html[:256]}".encode()).hexdigest()[:16]

        html_key = f"artifacts/html/{digest}.html"
        pdf_key = f"artifacts/pdf/{digest}.pdf"
        html_url = self.url_de_telechargement(html_key, duree_lien_s)
        pdf_url = self.url_de_telechargement(pdf_key, duree_lien_s)

        html_dest = self._media_root / html_key
        pdf_dest = self._media_root / pdf_key
        html_dest.parent.mkdir(parents=True, exist_ok=True)
        pdf_dest.parent.mkdir(parents=True, exist_ok=True)

        html_dest.write_text(html, encoding="utf-8")
        # render() puis write_pdf() (equivalent au raccourci write_pdf(),
        # cf. doc WeasyPrint api_reference) : document.pages donne le nombre
        # de pages reel pour le controle des limites §2 (80/45 pages max).
        document = WeasyHTML(string=html).render()
        page_count = len(document.pages)
        pdf_bytes: bytes = document.write_pdf()
        pdf_dest.write_bytes(pdf_bytes)

        return PdfGenerationResult(
            html_storage_key=html_key,
            html_download_url=html_url,
            pdf_bytes=pdf_bytes,
            pdf_storage_key=pdf_key,
            pdf_download_url=pdf_url,
            page_count=page_count,
        )


def get_pdf_client() -> PdfClient:
    """Stub par défaut ; WeasyPrint quand EVKHA_USE_STUB_PDF=false.

    Le client réel requiert :
    - EVKHA_USE_STUB_PDF=false
    - MEDIA_ROOT configuré
    - EVKHA_BASE_URL pour construire les URLs absolues (Brevo a besoin d'URLs publiques)
    """
    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_PDF", True))
    if use_stub:
        return StubPdfClient()
    return WeasyPrintPdfClient(
        media_root=Path(str(settings.MEDIA_ROOT)),
        base_url=str(getattr(settings, "EVKHA_BASE_URL", "")),
    )
