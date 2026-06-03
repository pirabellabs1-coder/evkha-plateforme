from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from django.conf import settings


@dataclass(frozen=True)
class DocExportResult:
    """Reference d'un document genere cote stockage (Google Docs/Drive)."""

    storage_key: str
    download_url: str


@runtime_checkable
class GoogleDocsClient(Protocol):
    """Contrat d'export d'un livrable assemble vers un support partageable."""

    def export(self, *, title: str, markdown: str) -> DocExportResult: ...


class StubGoogleDocsClient:
    """Export deterministe pour dev/CI : aucun appel reseau, URL simulee."""

    def export(self, *, title: str, markdown: str) -> DocExportResult:
        digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:16]
        storage_key = f"stub/{digest}"
        return DocExportResult(
            storage_key=storage_key,
            download_url=f"https://docs.evkha.local/{digest}",
        )


class GoogleDocsApiClient:
    """Export reel via l'API Google.

    Le cablage OAuth/Service Account depend de credentials confidentiels (NDA)
    fournis cote infrastructure. Tant que GOOGLE_CLIENT_ID/SECRET ne sont pas
    configures, on echoue explicitement plutot que de simuler une livraison.
    """

    def export(self, *, title: str, markdown: str) -> DocExportResult:
        msg = (
            "Export Google Docs reel non configure : renseigner les credentials "
            "Google (OAuth/Service Account) et cabler l'API Drive/Docs."
        )
        raise NotImplementedError(msg)


def get_google_docs_client() -> GoogleDocsClient:
    """Stub par defaut ; client reel quand les credentials Google sont presents."""
    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_DOCS", True))
    if use_stub:
        return StubGoogleDocsClient()
    return GoogleDocsApiClient()
