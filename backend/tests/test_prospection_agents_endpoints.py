"""Les endpoints des agents (phase 3), vus à travers HTTP.

On vérifie trois choses : le jeton admin est exigé ; le garde-fou `confirmer`
empêche tout passage payant accidentel (sans lui, RIEN n'est appelé et rien
n'est créé) ; et un passage confirmé — fabriques de modèle doublées, aucun
réseau — crée bien les données et n'envoie toujours rien.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client
from prospection.models import (
    Campagne,
    Evenement,
    Message,
    Prospect,
    StatutMessage,
    StatutProspect,
)

from integrations.claude import StructuredResult
from integrations.search import SearchResponse, SearchResult

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


def _charge(reponse: Any) -> Any:
    return json.loads(reponse.content)


def _poster(client_admin: Any, url: str, corps: dict[str, Any]) -> Any:
    return client_admin.post(url, data=json.dumps(corps), content_type="application/json")


class _ClientFaux:
    def __init__(self, charges: dict[str, dict[str, Any]]) -> None:
        self._charges = charges

    def complete_structured(self, *, outil_nom: str, **_: Any) -> StructuredResult:
        return StructuredResult(
            payload=dict(self._charges.get(outil_nom, {})),
            input_tokens=1, output_tokens=1, model="claude-sonnet",
        )


class _RechercheFausse:
    def search(self, *, query: str, max_results: int = 5, **_: Any) -> SearchResponse:
        return SearchResponse(
            query=query,
            results=(SearchResult(title="X", url="https://x.fr", content="…"),),
        )


def _doubler(monkeypatch: Any, charges: dict[str, dict[str, Any]]) -> None:
    """Remplace les fabriques réelles par des doublures : aucun réseau, aucun coût."""
    monkeypatch.setattr("integrations.claude.get_claude_client", lambda: _ClientFaux(charges))
    monkeypatch.setattr("integrations.search.get_search_client", _RechercheFausse)


def _campagne() -> Campagne:
    return Campagne.objects.create(nom="Cabinets RH Lyon", secteur="RH", zone="Lyon")


def test_les_routes_agents_exigent_le_jeton() -> None:
    c = _campagne()
    p = Prospect.objects.create(campagne=c, raison_sociale="Alpha", email="a@alpha.fr")
    anon = Client()
    assert anon.post(f"{BASE}/campagnes/{c.id}/rechercher/").status_code in (401, 403)
    assert anon.post(f"{BASE}/prospects/{p.id}/qualifier/").status_code in (401, 403)
    assert anon.post(f"{BASE}/prospects/{p.id}/rediger/").status_code in (401, 403)


def test_la_recherche_sans_confirmer_ne_lance_rien(client_admin: Any, monkeypatch: Any) -> None:
    c = _campagne()
    # Fabriques qui lèveraient si on les appelait : la preuve que rien n'est appelé.
    def _interdit() -> Any:
        raise AssertionError("le modèle ne doit pas être appelé sans confirmation")
    monkeypatch.setattr("integrations.claude.get_claude_client", _interdit)
    monkeypatch.setattr("integrations.search.get_search_client", _interdit)

    r = _poster(client_admin, f"{BASE}/campagnes/{c.id}/rechercher/", {})
    assert r.status_code == 400 and _charge(r)["confirmation_requise"] is True
    assert Prospect.objects.count() == 0


def test_la_recherche_confirmee_cree_des_prospects(client_admin: Any, monkeypatch: Any) -> None:
    c = _campagne()
    _doubler(monkeypatch, {"extraire_prospects": {"prospects": [
        {"raison_sociale": "Alpha RH", "email": "contact@alpha.fr"},
    ]}})
    r = _poster(client_admin, f"{BASE}/campagnes/{c.id}/rechercher/", {"confirmer": True})
    assert r.status_code == 200 and _charge(r)["crees"] == 1
    assert Prospect.objects.filter(campagne=c, source="recherche-ia").count() == 1
    # La recherche ne prépare ni n'envoie rien.
    assert Message.objects.count() == 0 and Evenement.objects.count() == 0


def test_la_qualification_confirmee_pose_un_score(client_admin: Any, monkeypatch: Any) -> None:
    c = _campagne()
    p = Prospect.objects.create(campagne=c, raison_sociale="Alpha", statut=StatutProspect.NOUVEAU)
    _doubler(monkeypatch, {"qualifier_prospect": {"score": 83, "raison": "bon profil"}})
    r = _poster(client_admin, f"{BASE}/prospects/{p.id}/qualifier/", {"confirmer": True})
    assert r.status_code == 200
    p.refresh_from_db()
    assert p.score_adequation == 83 and p.statut == StatutProspect.QUALIFIE


def test_la_redaction_confirmee_cree_des_brouillons(client_admin: Any, monkeypatch: Any) -> None:
    c = _campagne()
    p = Prospect.objects.create(campagne=c, raison_sociale="Alpha", email="contact@alpha.fr")
    _doubler(monkeypatch, {"rediger_messages": {"messages": [
        {"objet": f"O{i}", "corps": f"<p>C{i}</p>"} for i in range(5)
    ]}})
    r = _poster(client_admin, f"{BASE}/prospects/{p.id}/rediger/", {"confirmer": True})
    assert r.status_code == 200 and _charge(r)["crees"] == 5
    # Tout est brouillon : rien n'est validé, rien n'est parti.
    assert Message.objects.filter(statut=StatutMessage.BROUILLON).count() == 5
    assert Message.objects.exclude(statut=StatutMessage.BROUILLON).count() == 0
    assert Evenement.objects.count() == 0


class _RechercheEnPanne:
    """Doublure qui simule une API Claude sans crédits (le 400 réel du 24/10)."""

    def search(self, *, query: str, max_results: int = 5, **_: Any) -> Any:
        msg = (
            "Error code: 400 - Your credit balance is too low to access the "
            "Anthropic API. Please go to Plans & Billing."
        )
        raise RuntimeError(msg)


def test_une_panne_de_credits_ia_ne_rend_pas_un_500(
    client_admin: Any, monkeypatch: Any
) -> None:
    """24/10/2026 : crédits Anthropic épuisés. « credit balance is too low »
    remontait en « Server Error (500) » nu sous le bouton, sans dire à la cliente
    quoi faire. L'action doit NOMMER la panne (502 + message clair) et ne rien
    créer.

    Sur le code d'avant — l'agent appelé sans capture — l'exception remontait :
    ce test échouait.
    """
    c = _campagne()
    monkeypatch.setattr("integrations.claude.get_claude_client", lambda: _ClientFaux({}))
    monkeypatch.setattr("integrations.search.get_search_client", _RechercheEnPanne)

    r = _poster(client_admin, f"{BASE}/campagnes/{c.id}/rechercher/", {"confirmer": True})

    assert r.status_code == 502, (r.status_code, r.content)
    assert "Crédits IA épuisés" in _charge(r)["erreur"]
    assert Prospect.objects.count() == 0
