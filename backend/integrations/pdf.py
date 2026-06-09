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


@runtime_checkable
class PdfClient(Protocol):
    """Génère un livrable PDF brandé à partir d'un titre et d'un corps HTML."""

    def generate(self, *, title: str, html: str) -> PdfGenerationResult: ...


class StubPdfClient:
    """Client PDF déterministe pour dev/CI : aucune écriture disque, URLs simulées.

    Le digest est calculé sur les 256 premiers caractères du HTML pour garantir
    la reproductibilité sans dépendre de WeasyPrint.
    """

    def generate(self, *, title: str, html: str) -> PdfGenerationResult:
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

    def __init__(
        self,
        media_root: Path,
        media_url: str,
        base_url: str = "",
    ) -> None:
        self._media_root = media_root
        self._media_url = media_url.rstrip("/")
        self._base_url = base_url.rstrip("/")

    def generate(self, *, title: str, html: str) -> PdfGenerationResult:
        from weasyprint import HTML as WeasyHTML

        digest = hashlib.sha256(f"{title}:{html[:256]}".encode()).hexdigest()[:16]

        html_key = f"artifacts/html/{digest}.html"
        pdf_key = f"artifacts/pdf/{digest}.pdf"
        html_url = f"{self._base_url}{self._media_url}/{html_key}"
        pdf_url = f"{self._base_url}{self._media_url}/{pdf_key}"

        html_dest = self._media_root / html_key
        pdf_dest = self._media_root / pdf_key
        html_dest.parent.mkdir(parents=True, exist_ok=True)
        pdf_dest.parent.mkdir(parents=True, exist_ok=True)

        html_dest.write_text(html, encoding="utf-8")
        pdf_bytes: bytes = WeasyHTML(string=html).write_pdf()
        pdf_dest.write_bytes(pdf_bytes)

        return PdfGenerationResult(
            html_storage_key=html_key,
            html_download_url=html_url,
            pdf_bytes=pdf_bytes,
            pdf_storage_key=pdf_key,
            pdf_download_url=pdf_url,
        )


def get_pdf_client() -> PdfClient:
    """Stub par défaut ; WeasyPrint quand EVKHA_USE_STUB_PDF=false.

    Le client réel requiert :
    - EVKHA_USE_STUB_PDF=false
    - MEDIA_ROOT et MEDIA_URL configurés
    - EVKHA_BASE_URL pour construire les URLs absolues (Brevo a besoin d'URLs publiques)
    """
    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_PDF", True))
    if use_stub:
        return StubPdfClient()
    return WeasyPrintPdfClient(
        media_root=Path(str(settings.MEDIA_ROOT)),
        media_url=str(getattr(settings, "MEDIA_URL", "/media/")),
        base_url=str(getattr(settings, "EVKHA_BASE_URL", "")),
    )
