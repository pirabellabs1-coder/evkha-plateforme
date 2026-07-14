from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from django.conf import settings

# API Gamma Generations v1.0 (developers.gamma.app).
_GAMMA_BASE_URL = "https://public-api.gamma.app/v1.0"
_GAMMA_POLL_INTERVAL_SECONDS = 5.0
_GAMMA_MAX_POLLS = 60  # 60 x 5s = 5 min de plafond (generation typique 1-3 min)
_GAMMA_HTTP_TIMEOUT_SECONDS = 30.0


class GammaError(RuntimeError):
    """Echec de l'API Gamma (creation, polling, export, timeout)."""


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
    """Client reel Gamma Generations API v1.0.

    Flux : POST /generations (textMode=preserve : Gamma met en page le contenu
    deja redige par Claude, sans le reecrire ; format=document ; exportAs=pdf)
    -> GET /generations/{id} en polling jusqu'a `completed` -> exportUrl (PDF)
    + gammaUrl (lien de consultation). Le resultat du polling est memorise
    pour qu'`export` le relise sans nouvel appel.

    Import paresseux de httpx (dependance optionnelle, jamais chargee en CI).
    """

    def __init__(self, *, api_key: str | None = None, theme_id: str | None = None) -> None:
        self._api_key = api_key
        self._theme_id = theme_id
        # generationId -> payload complet du dernier statut `completed`.
        self._completed: dict[str, dict[str, object]] = {}

    def _headers(self) -> dict[str, str]:
        import os

        api_key = self._api_key or os.environ.get("GAMMA_API_KEY", "") or str(
            getattr(settings, "GAMMA_API_KEY", "")
        )
        if not api_key:
            raise GammaError("GAMMA_API_KEY manquante pour GammaApiClient.")
        return {"X-API-KEY": api_key, "Content-Type": "application/json"}

    def create_presentation(
        self,
        *,
        title: str,
        markdown: str,
        theme_id: str,
    ) -> GammaPresentation:
        import httpx  # import paresseux

        body: dict[str, object] = {
            "inputText": markdown,
            "textMode": "preserve",
            "format": "document",
            "exportAs": "pdf",
            "cardSplit": "auto",
            "title": title,
        }
        effective_theme = theme_id or self._theme_id or str(
            getattr(settings, "GAMMA_THEME_ID", "")
        )
        if effective_theme:
            body["themeId"] = effective_theme

        try:
            response = httpx.post(
                f"{_GAMMA_BASE_URL}/generations",
                headers=self._headers(),
                json=body,
                timeout=_GAMMA_HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise GammaError(f"Echec creation Gamma : {exc}") from exc

        generation_id = str(payload.get("generationId", "")).strip()
        if not generation_id:
            raise GammaError(f"Reponse Gamma sans generationId : {payload!r}")
        return GammaPresentation(
            presentation_id=generation_id,
            theme_id=effective_theme,
            title=title,
        )

    def wait_until_ready(self, *, presentation_id: str) -> None:
        import httpx  # import paresseux

        url = f"{_GAMMA_BASE_URL}/generations/{presentation_id}"
        headers = self._headers()
        for _ in range(_GAMMA_MAX_POLLS):
            try:
                response = httpx.get(url, headers=headers, timeout=_GAMMA_HTTP_TIMEOUT_SECONDS)
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPError as exc:
                raise GammaError(f"Echec polling Gamma : {exc}") from exc

            status = str(payload.get("status", "")).lower()
            if status == "completed":
                self._completed[presentation_id] = payload
                return
            if status == "failed":
                raise GammaError(f"Generation Gamma en echec (id {presentation_id}).")
            time.sleep(_GAMMA_POLL_INTERVAL_SECONDS)

        raise GammaError(
            f"Timeout Gamma : generation {presentation_id} non terminee apres "
            f"{_GAMMA_MAX_POLLS} sondages."
        )

    def export(self, *, presentation: GammaPresentation) -> GammaExportResult:
        payload = self._completed.get(presentation.presentation_id)
        if payload is None:
            raise GammaError(
                "export() appele avant wait_until_ready() ou statut non memorise."
            )
        export_url = str(payload.get("exportUrl", "")).strip()
        gamma_url = str(payload.get("gammaUrl", "")).strip()
        if not export_url:
            raise GammaError(f"Reponse Gamma sans exportUrl : {payload!r}")
        # L'API exporte un seul format par generation (exportAs=pdf) : pas de
        # PPTX ici (une seconde generation doublerait le cout). pptx_url reste
        # vide et n'est pas persiste (cf. _persist_gamma_artifacts).
        return GammaExportResult(
            pdf_url=export_url,
            pptx_url="",
            presentation_url=gamma_url,
        )


def get_gamma_client() -> GammaClient:
    """Stub par defaut ; client reel quand EVKHA_USE_STUB_GAMMA=false + cle.

    Robustesse : le flag reel sans cle retombe sur le stub (le pipeline ne
    casse jamais faute de configuration ; WeasyPrint reste le livrable)."""
    import os

    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_GAMMA", True))
    has_key = bool(
        os.environ.get("GAMMA_API_KEY", "") or str(getattr(settings, "GAMMA_API_KEY", ""))
    )
    if use_stub or not has_key:
        return StubGammaClient()
    return GammaApiClient()
