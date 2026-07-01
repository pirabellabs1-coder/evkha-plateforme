from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from django.conf import settings

# Alias EVKHA (EVKHA_CLAUDE_MODEL) -> identifiant API Anthropic reel.
# L'identifiant exact peut etre surcharge via EVKHA_ANTHROPIC_MODEL_ID sans
# toucher au code (les references produit evoluent souvent).
_ANTHROPIC_MODEL_IDS: dict[str, str] = {
    "claude-sonnet": "claude-sonnet-4-6",
    "claude-opus": "claude-opus-4-8",
    "claude-haiku": "claude-haiku-4-5-20251001",
}
# 8000 tokens ≈ 6000 mots par section — cible 80 pages par livrable.
_DEFAULT_MAX_TOKENS = 8000


@dataclass(frozen=True)
class ClaudeResult:
    """Resultat normalise d'un appel de generation (independant du SDK)."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str


@runtime_checkable
class ClaudeClient(Protocol):
    """Contrat minimal du moteur de generation textuelle (Cle d'or: cout maitrise)."""

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> ClaudeResult: ...


def _resolve_model_alias() -> str:
    return str(getattr(settings, "EVKHA_CLAUDE_MODEL", "claude-sonnet"))


def _resolve_anthropic_model_id(alias: str) -> str:
    override = str(getattr(settings, "EVKHA_ANTHROPIC_MODEL_ID", "") or "")
    if override:
        return override
    return _ANTHROPIC_MODEL_IDS.get(alias, _ANTHROPIC_MODEL_IDS["claude-sonnet"])


class AnthropicClaudeClient:
    """Client reel. Le SDK et la cle ne sont charges qu'a l'usage (jamais en CI)."""

    def __init__(self, *, api_key: str | None = None, model_alias: str | None = None) -> None:
        self._api_key = api_key
        self._model_alias = model_alias or _resolve_model_alias()

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> ClaudeResult:
        import os

        import anthropic  # import paresseux : dependance optionnelle hors tests

        api_key = self._api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            msg = "ANTHROPIC_API_KEY manquante pour AnthropicClaudeClient."
            raise RuntimeError(msg)

        model_id = _resolve_anthropic_model_id(self._model_alias)
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        content = "".join(
            str(getattr(block, "text", ""))
            for block in message.content
            if getattr(block, "type", "") == "text"
        )
        return ClaudeResult(
            content=content,
            input_tokens=int(message.usage.input_tokens),
            output_tokens=int(message.usage.output_tokens),
            model=self._model_alias,
        )


class StubClaudeClient:
    """Client deterministe pour dev/CI : aucune dependance reseau, cout simule.

    Le contenu reprend le PROMPT_KEY et les premieres lignes du prompt afin que
    les tests d'integration verifient le cablage Context -> Generation -> Rendu.
    """

    def __init__(self, *, model_alias: str | None = None) -> None:
        self._model_alias = model_alias or _resolve_model_alias()

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> ClaudeResult:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        content = (
            "Contenu genere (mode demonstration EVKHA).\n\n"
            "Cette section synthetise les donnees chiffrees et sourcees attendues "
            "pour le chapitre courant, redigee dans le ton mentor EVKHA.\n\n"
            f"Empreinte de tracabilite: {digest}.\n\n"
            "Sources\n"
            "- EVKHA, methodologie interne (URL a confirmer)."
        )
        # Estimation grossiere (~4 caracteres par token) pour alimenter le Cost Engine.
        input_tokens = max(1, len(system) + len(prompt)) // 4
        output_tokens = max(1, len(content)) // 4
        return ClaudeResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self._model_alias,
        )


def get_claude_client() -> ClaudeClient:
    """Fabrique : client reel si autorise + cle presente, sinon stub deterministe."""
    import os

    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_AI", True))
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    if use_stub or not has_key:
        return StubClaudeClient()
    return AnthropicClaudeClient()
