from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from django.conf import settings


@dataclass(frozen=True)
class GammaPresentation:
    presentation_id: str
    theme_id: str
    title: str


@dataclass(frozen=True)
class GammaExportResult:
    pdf_url: str
    pptx_url: str
    presentation_url: str


@runtime_checkable
class GammaClient(Protocol):
    def create_presentation(
        self,
        *,
        title: str,
        markdown: str,
        theme_id: str,
    ) -> GammaPresentation: ...

    def wait_until_ready(self, *, presentation_id: str) -> None: ...

    def export(self, *, presentation: GammaPresentation) -> GammaExportResult: ...


class StubGammaClient:
    """Client Gamma deterministe pour dev/CI : aucun appel reseau, presentation simulee.

    create_presentation genere un ID stable base sur le contenu (hash) pour
    permettre la rejoue deterministe des tests.
    """

    def create_presentation(
        self,
        *,
        title: str,
        markdown: str,
        theme_id: str,
    ) -> GammaPresentation:
        digest = hashlib.sha256(f"{title}:{theme_id}:{markdown}".encode()).hexdigest()[:16]
        return GammaPresentation(
            presentation_id=f"gamma-{digest}",
            theme_id=theme_id,
            title=title,
        )

    def wait_until_ready(self, *, presentation_id: str) -> None:
        return

    def export(self, *, presentation: GammaPresentation) -> GammaExportResult:
        base = f"https://gamma.evkha.local/{presentation.presentation_id}"
        return GammaExportResult(
            pdf_url=f"{base}.pdf",
            pptx_url=f"{base}.pptx",
            presentation_url=base,
        )


class GammaApiClient:
    def create_presentation(
        self,
        *,
        title: str,
        markdown: str,
        theme_id: str,
    ) -> GammaPresentation:
        msg = (
            "Generation Gamma reelle non configuree : renseigner la cle API Gamma, "
            "les IDs de themes et cabler les endpoints create/poll/export."
        )
        raise NotImplementedError(msg)

    def wait_until_ready(self, *, presentation_id: str) -> None:
        msg = "Polling Gamma reel non configure."
        raise NotImplementedError(msg)

    def export(self, *, presentation: GammaPresentation) -> GammaExportResult:
        msg = "Export Gamma reel non configure."
        raise NotImplementedError(msg)


def get_gamma_client() -> GammaClient:
    """Stub par defaut ; client reel quand EVKHA_USE_STUB_GAMMA=false."""
    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_GAMMA", True))
    if use_stub:
        return StubGammaClient()
    return GammaApiClient()
