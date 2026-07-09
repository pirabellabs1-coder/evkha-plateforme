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
# 5000 tokens ≈ 3750 mots par section. Hausse de 3500 → 5000 justifiee par :
# 1. Sections denses (ec.03.a 3800 mots ≈ 5067 tokens) passent en 1 seul appel
#    au lieu de 2 avec l'ancienne limite, limitant les continuations et les ruptures.
# 2. Budgets adaptatifs (EM=4€, BP=3€) absorbent le surcout Sonnet :
#    pire cas EM (30 appels sans continuation) ≈ 2.27 EUR < budget 4.00 EUR.
# 3. La boucle de continuation reste active (stop_reason=max_tokens) si une section
#    depasse 5000 tokens — cas rare apres les corrections SECTION_MAX_WORDS.
# Toute troncature residuelle (chapitre a HTML dense) est neutralisee par le
# sanitizer close_dangling_html_tags() de rendering.py, qui ferme les balises
# orphelines pour eviter qu'un <table> ou <style> tronque "aspire" les
# chapitres suivants dans le PDF final.
_DEFAULT_MAX_TOKENS = 5000

# Anthropic Messages API : message.stop_reason vaut "max_tokens" quand la
# reponse est coupee par la limite de sortie (cf. doc API Anthropic, champ
# stop_reason). Sans verification de ce champ, un contenu tronque (chapitre,
# liste de concurrents...) est livre tel quel sans que rien ne le detecte.
# Correctif : quand stop_reason == "max_tokens", on relance un appel en
# ajoutant le contenu deja genere comme tour "assistant" (prefill) : l'API
# poursuit alors la reponse exactement la ou elle s'est arretee, sans la
# reecrire depuis le debut. Plafond de securite : _MAX_CONTINUATIONS appels
# supplementaires max, pour borner le cout meme en cas de contenu anormalement
# long (le Cost Engine tient compte de ce plafond, cf. generation/cost.py).
_MAX_CONTINUATIONS = 1


@dataclass(frozen=True)
class ClaudeResult:
    """Resultat normalise d'un appel de generation (independant du SDK)."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str = "end_turn"


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

        content_parts: list[str] = []
        total_input = 0
        total_output = 0
        stop_reason = "end_turn"
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

        for _ in range(_MAX_CONTINUATIONS + 1):
            message = client.messages.create(
                model=model_id,
                max_tokens=max_tokens,
                system=system,
                messages=messages,  # type: ignore[arg-type]
            )
            chunk = "".join(
                str(getattr(block, "text", ""))
                for block in message.content
                if getattr(block, "type", "") == "text"
            )
            content_parts.append(chunk)
            total_input += int(message.usage.input_tokens)
            total_output += int(message.usage.output_tokens)
            stop_reason = str(message.stop_reason)

            if stop_reason != "max_tokens":
                break

            # Continuation multi-tour (pas de prefill : claude-sonnet-4-6 et
            # les modeles recents rejettent les conversations terminant sur un
            # tour assistant). On conserve le tour assistant tronque puis on
            # ajoute un tour user qui demande de poursuivre : Claude reprend
            # exactement apres le dernier mot sans repeter le debut.
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "".join(content_parts)},
                {
                    "role": "user",
                    "content": (
                        "Continue ta réponse depuis le point exact où tu t'es arrêté. "
                        "Ne répète rien de ce qui a déjà été écrit. "
                        "Reprends immédiatement après le dernier mot ou caractère."
                    ),
                },
            ]

        return ClaudeResult(
            content="".join(content_parts),
            input_tokens=total_input,
            output_tokens=total_output,
            model=self._model_alias,
            stop_reason=stop_reason,
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
