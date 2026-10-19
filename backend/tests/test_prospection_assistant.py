"""L'assistant conversationnel de prospection et la recherche par critères.

Doublures déterministes injectées : aucun réseau, aucun coût. On vérifie que
l'assistant rend une réponse et, le cas échéant, une proposition de recherche ;
que l'endpoint exige le jeton ; et que les critères affinent bien la requête web.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from prospection import agents, assistant
from prospection.models import Campagne, Prospect

from integrations.claude import StructuredResult
from integrations.search import SearchResponse

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


class _ClientFaux:
    def __init__(self, charge: dict[str, Any]) -> None:
        self._charge = charge

    def complete_structured(self, **_: Any) -> StructuredResult:
        return StructuredResult(payload=dict(self._charge), input_tokens=1,
                                output_tokens=1, model="claude-sonnet")


class _RechercheEspionne:
    def __init__(self) -> None:
        self.derniere_requete = ""

    def search(self, *, query: str, max_results: int = 5, **_: Any) -> SearchResponse:
        self.derniere_requete = query
        return SearchResponse(query=query, results=())


# ── L'assistant (fonction) ────────────────────────────────────────────────────


def test_l_assistant_repond_sans_proposition() -> None:
    out = assistant.repondre(
        [{"role": "user", "content": "Qui cibler ?"}],
        client=_ClientFaux({"reponse": "Quel secteur visez-vous ?"}),
    )
    assert out["reponse"] == "Quel secteur visez-vous ?"
    assert out["proposition_recherche"] is None


def test_l_assistant_propose_une_recherche_quand_la_cible_est_claire() -> None:
    out = assistant.repondre(
        [{"role": "user", "content": "Des cabinets RH à Lyon qui recrutent."}],
        client=_ClientFaux({
            "reponse": "Je vous propose cette recherche.",
            "proposition_recherche": {"criteres": "cabinets RH Lyon en recrutement", "limite": 8},
        }),
    )
    assert out["proposition_recherche"]["criteres"] == "cabinets RH Lyon en recrutement"
    assert out["proposition_recherche"]["limite"] == 8


def test_l_assistant_ne_plante_pas_sur_une_charge_vide() -> None:
    out = assistant.repondre([{"role": "user", "content": "Bonjour"}], client=_ClientFaux({}))
    assert isinstance(out["reponse"], str) and out["reponse"]
    assert out["proposition_recherche"] is None


# ── L'endpoint ────────────────────────────────────────────────────────────────


def test_l_endpoint_assistant_exige_le_jeton() -> None:
    from django.test import Client
    corps = json.dumps({"messages": [{"role": "user", "content": "x"}]})
    r = Client().post(f"{BASE}/assistant/", data=corps, content_type="application/json")
    assert r.status_code in (401, 403)


def test_l_endpoint_assistant_repond(client_admin: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "integrations.claude.get_claude_client",
        lambda: _ClientFaux({"reponse": "Bonjour, quel est votre secteur ?"}),
    )
    r = client_admin.post(
        f"{BASE}/assistant/",
        data=json.dumps({"messages": [{"role": "user", "content": "Aidez-moi"}]}),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert json.loads(r.content)["reponse"] == "Bonjour, quel est votre secteur ?"


def test_l_endpoint_assistant_refuse_sans_messages(client_admin: Any) -> None:
    r = client_admin.post(f"{BASE}/assistant/", data="{}", content_type="application/json")
    assert r.status_code == 400


# ── La recherche par critères ────────────────────────────────────────────────


def test_les_criteres_affinent_la_requete() -> None:
    campagne = Campagne.objects.create(nom="C", secteur="RH", zone="Lyon")
    espion = _RechercheEspionne()
    agents.rechercher_des_prospects(
        campagne, criteres="qui recrutent activement",
        recherche=espion, client=_ClientFaux({"prospects": []}),
    )
    assert "RH" in espion.derniere_requete and "recrutent" in espion.derniere_requete
    assert Prospect.objects.count() == 0
