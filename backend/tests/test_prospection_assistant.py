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


# ── Une panne du modèle ne rend pas un 500 nu, et ne perd rien ───────────────
#
# Audit du 19/11/2026 : l'assistant appelait le modèle HORS de
# `_executer_agent` (500 nu, là où les autres agents rendent un 502 lisible),
# et créait la discussion AVANT l'appel sans y écrire le tour de l'humain —
# une discussion vide de plus à chaque essai, et le texte saisi perdu.


class _ClientEnPanne:
    def complete_structured(self, **_: Any) -> StructuredResult:
        msg = (
            "Error code: 400 - Your credit balance is too low to access the "
            "Anthropic API. Please go to Plans & Billing."
        )
        raise RuntimeError(msg)


def _ecrire(client_admin: Any, corps: dict[str, Any]) -> Any:
    return client_admin.post(
        f"{BASE}/assistant/", data=json.dumps(corps), content_type="application/json"
    )


def test_une_panne_du_modele_rend_un_502_lisible_et_garde_le_texte(
    client_admin: Any, monkeypatch: Any,
) -> None:
    """Sur le code d'avant : l'exception remontait (500), la discussion restait vide."""
    from prospection.models import Conversation

    monkeypatch.setattr("integrations.claude.get_claude_client", _ClientEnPanne)

    r = _ecrire(client_admin, {"message": "Des BGE à Lille"})

    assert r.status_code == 502, (r.status_code, r.content)
    d = json.loads(r.content)
    assert "Crédits IA épuisés" in d["erreur"]
    # Le texte saisi est GARDÉ, dans une discussion que l'écran peut rouvrir.
    assert d["conversation_id"]
    assert [(m["role"], m["content"]) for m in d["messages"]] == [("user", "Des BGE à Lille")]
    assert Conversation.objects.count() == 1


def test_reessayer_ne_double_ni_la_discussion_ni_le_texte(
    client_admin: Any, monkeypatch: Any,
) -> None:
    """Sur le code d'avant : chaque essai en panne créait une discussion vide de plus."""
    from prospection.models import Conversation

    monkeypatch.setattr("integrations.claude.get_claude_client", _ClientEnPanne)
    premier = json.loads(_ecrire(client_admin, {"message": "Des BGE à Lille"}).content)
    cid = premier["conversation_id"]
    second = _ecrire(client_admin, {"message": "Des BGE à Lille", "conversation_id": cid})
    assert second.status_code == 502

    # Le modèle revient : le même texte, renvoyé, obtient sa réponse.
    monkeypatch.setattr(
        "integrations.claude.get_claude_client",
        lambda: _ClientFaux({"reponse": "Quelle taille de structure ?"}),
    )
    troisieme = _ecrire(client_admin, {"message": "Des BGE à Lille", "conversation_id": cid})

    assert troisieme.status_code == 200
    d = json.loads(troisieme.content)
    assert d["conversation_id"] == cid
    assert [(m["role"], m["content"]) for m in d["messages"]] == [
        ("user", "Des BGE à Lille"),
        ("assistant", "Quelle taille de structure ?"),
    ]
    assert Conversation.objects.count() == 1


def test_le_meme_texte_redit_apres_une_reponse_est_bien_un_nouveau_tour(
    client_admin: Any, monkeypatch: Any,
) -> None:
    """Contre-épreuve : on ne dédoublonne que le tour resté SANS réponse.

    « Oui » deux fois de suite, chacun après une réponse de l'assistant, ce sont
    deux tours — le correctif ne doit pas en avaler un.
    """
    monkeypatch.setattr(
        "integrations.claude.get_claude_client", lambda: _ClientFaux({"reponse": "D'accord."})
    )
    cid = json.loads(_ecrire(client_admin, {"message": "Oui"}).content)["conversation_id"]

    d = json.loads(_ecrire(client_admin, {"message": "Oui", "conversation_id": cid}).content)

    assert [m["role"] for m in d["messages"]] == ["user", "assistant", "user", "assistant"]


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
