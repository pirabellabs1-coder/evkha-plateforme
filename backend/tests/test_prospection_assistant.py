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
    corps = json.dumps({"message": "x"})
    r = Client().post(f"{BASE}/assistant/", data=corps, content_type="application/json")
    assert r.status_code in (401, 403)


def test_l_endpoint_assistant_repond_et_garde_en_memoire(
    client_admin: Any, monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "integrations.claude.get_claude_client",
        lambda: _ClientFaux({"reponse": "Bonjour, quel est votre secteur ?"}),
    )
    r = client_admin.post(
        f"{BASE}/assistant/",
        data=json.dumps({"message": "Aidez-moi"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    d = json.loads(r.content)
    assert d["reponse"] == "Bonjour, quel est votre secteur ?"
    # La discussion est gardée : un id, et l'échange (user + assistant) enregistré.
    cid = d["conversation_id"]
    assert cid
    assert [m["role"] for m in d["messages"]] == ["user", "assistant"]
    # On la retrouve dans la liste et on peut la rouvrir avec tout l'historique.
    liste = json.loads(client_admin.get(f"{BASE}/conversations/").content)
    assert any(c["id"] == cid for c in liste)
    detail = json.loads(client_admin.get(f"{BASE}/conversations/{cid}/").content)
    assert len(detail["messages"]) == 2


def test_l_endpoint_assistant_continue_une_discussion(
    client_admin: Any, monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "integrations.claude.get_claude_client",
        lambda: _ClientFaux({"reponse": "Compris."}),
    )
    r1 = client_admin.post(f"{BASE}/assistant/", data=json.dumps({"message": "Premier"}),
                           content_type="application/json")
    cid = json.loads(r1.content)["conversation_id"]
    # Deuxième tour sur la MÊME discussion.
    r2 = client_admin.post(
        f"{BASE}/assistant/",
        data=json.dumps({"message": "Deuxième", "conversation_id": cid}),
        content_type="application/json",
    )
    d2 = json.loads(r2.content)
    assert d2["conversation_id"] == cid
    # L'historique cumule les deux tours (4 messages : 2 user + 2 assistant).
    assert len(d2["messages"]) == 4


def test_l_endpoint_assistant_refuse_sans_message(client_admin: Any) -> None:
    r = client_admin.post(f"{BASE}/assistant/", data="{}", content_type="application/json")
    assert r.status_code == 400


def test_les_conversations_exigent_le_jeton() -> None:
    from django.test import Client
    assert Client().get(f"{BASE}/conversations/").status_code in (401, 403)


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
