"""Tests Phase 10 — continuation automatique sur troncature Claude (max_tokens).

Contexte : plusieurs livrables client etaient coupes en plein milieu d'un
chapitre (ex: liste de concurrents incomplete) car message.stop_reason ==
"max_tokens" n'etait jamais verifie. AnthropicClaudeClient.complete() doit
desormais relancer automatiquement (prefill du contenu deja genere) jusqu'a
_MAX_CONTINUATIONS fois pour livrer un contenu complet.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from integrations.claude import _MAX_CONTINUATIONS, AnthropicClaudeClient


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text: str, stop_reason: str, input_tokens: int, output_tokens: int) -> None:
        self.content = [_FakeBlock(text)]
        self.stop_reason = stop_reason
        self.usage = _FakeUsage(input_tokens, output_tokens)


class _FakeMessagesResource:
    def __init__(self, responses: list[_FakeMessage]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeMessage:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeAnthropicClient:
    def __init__(self, responses: list[_FakeMessage]) -> None:
        self.messages = _FakeMessagesResource(responses)


def _install_fake_anthropic(
    monkeypatch: pytest.MonkeyPatch, responses: list[_FakeMessage]
) -> _FakeAnthropicClient:
    holder: dict[str, _FakeAnthropicClient] = {}

    def _factory(*, api_key: str) -> _FakeAnthropicClient:
        client = _FakeAnthropicClient(responses)
        holder["client"] = client
        return client

    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = _factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return holder  # type: ignore[return-value]


def test_complete_returns_immediately_when_not_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [_FakeMessage("Reponse complete.", "end_turn", 100, 200)]
    holder: dict[str, _FakeAnthropicClient] = {}

    def _factory(**_: Any) -> _FakeAnthropicClient:
        return holder.setdefault("client", _FakeAnthropicClient(responses))

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_factory))

    client = AnthropicClaudeClient(api_key="fake-key")
    result = client.complete(system="sys", prompt="prompt")

    assert result.content == "Reponse complete."
    assert result.stop_reason == "end_turn"
    assert result.input_tokens == 100
    assert result.output_tokens == 200
    assert len(holder["client"].messages.calls) == 1
    system = holder["client"].messages.calls[0]["system"]
    assert system == [
        {
            "type": "text",
            "text": "sys",
            "cache_control": {"type": "ephemeral"},
        }
    ]


def test_complete_continues_on_max_tokens_and_merges_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        _FakeMessage("Debut de la reponse ", "max_tokens", 100, 500),
        _FakeMessage("et voici la fin.", "end_turn", 150, 200),
    ]
    holder = _install_fake_anthropic(monkeypatch, responses)

    client = AnthropicClaudeClient(api_key="fake-key")
    result = client.complete(system="sys", prompt="prompt")

    assert result.content == "Debut de la reponse et voici la fin."
    assert result.stop_reason == "end_turn"
    assert result.input_tokens == 250
    assert result.output_tokens == 700

    calls = holder["client"].messages.calls
    assert len(calls) == 2
    second_call_messages = calls[1]["messages"]
    assert second_call_messages[0] == {"role": "user", "content": "prompt"}
    assert second_call_messages[1] == {"role": "assistant", "content": "Debut de la reponse "}


def test_complete_stops_after_max_continuations(monkeypatch: pytest.MonkeyPatch) -> None:
    # Toujours tronque : le plafond de securite doit borner le nombre d'appels.
    responses = [
        _FakeMessage(f"partie{i} ", "max_tokens", 50, 300) for i in range(_MAX_CONTINUATIONS + 5)
    ]
    holder = _install_fake_anthropic(monkeypatch, responses)

    client = AnthropicClaudeClient(api_key="fake-key")
    result = client.complete(system="sys", prompt="prompt")

    assert len(holder["client"].messages.calls) == _MAX_CONTINUATIONS + 1
    assert result.stop_reason == "max_tokens"
    assert result.content == "".join(f"partie{i} " for i in range(_MAX_CONTINUATIONS + 1))
