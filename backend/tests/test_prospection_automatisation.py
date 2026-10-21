"""La prospection automatique quotidienne (phase planification).

Doublures injectées : aucun réseau, aucun coût. On vérifie que rien ne tourne
tant que ce n'est pas activé (défaut), que l'exécution cherche/qualifie/prépare
(sans jamais envoyer), que c'est idempotent (une fois par jour), et que
l'endpoint pilote les réglages avec le garde-fou « campagne requise pour
activer ».
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from prospection import tasks
from prospection.models import (
    Campagne,
    Message,
    Prospect,
    ReglageAutomatisation,
    StatutMessage,
)

from integrations.claude import StructuredResult
from integrations.search import SearchResponse, SearchResult

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


class _ClientFaux:
    """Rend la bonne charge selon l'outil appelé (recherche, qualif, rédaction)."""

    def complete_structured(self, *, outil_nom: str, **_: Any) -> StructuredResult:
        charges: dict[str, dict[str, Any]] = {
            "extraire_prospects": {"prospects": [
                {"raison_sociale": f"Cible {i}", "email": f"c{i}@ex.fr"} for i in range(3)
            ]},
            "qualifier_prospect": {"score": 70, "raison": "ok"},
            "rediger_messages": {"messages": [
                {"objet": f"O{i}", "corps": f"<p>C{i}</p>"} for i in range(5)
            ]},
        }
        return StructuredResult(payload=dict(charges.get(outil_nom, {})),
                                input_tokens=1, output_tokens=1, model="claude-sonnet")


class _RechercheFausse:
    def search(self, *, query: str, max_results: int = 5, **_: Any) -> SearchResponse:
        return SearchResponse(query=query, results=(
            SearchResult(title="X", url="https://x.fr", content="…"),
        ))


_UN_LUNDI = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)  # lundi (weekday 0)


def _activer(campagne: Campagne, **kw: Any) -> ReglageAutomatisation:
    r = ReglageAutomatisation.charger()
    r.active = True
    r.campagne = campagne
    for k, v in kw.items():
        setattr(r, k, v)
    r.save()
    return r


# ── La tâche ──────────────────────────────────────────────────────────────────


def test_inactive_par_defaut_ne_fait_rien() -> None:
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI,
                                  recherche=_RechercheFausse(), client=_ClientFaux())
    assert resume == {"execute": False, "raison": "inactive"}
    assert Prospect.objects.count() == 0


def test_active_cherche_qualifie_et_prepare_sans_envoyer() -> None:
    campagne = Campagne.objects.create(nom="C", secteur="RH", zone="Lille")
    _activer(campagne, prospects_par_jour=3)
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI,
                                  recherche=_RechercheFausse(), client=_ClientFaux())
    assert resume["execute"] is True
    assert resume["crees"] == 3 and resume["qualifies"] == 3 and resume["rediges"] == 3
    # Des brouillons ont été préparés — et RIEN n'est parti.
    assert Message.objects.filter(statut=StatutMessage.BROUILLON).count() > 0
    assert Message.objects.exclude(statut=StatutMessage.BROUILLON).count() == 0


def test_idempotent_une_fois_par_jour() -> None:
    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne, prospects_par_jour=3)
    tasks.executer_si_du(maintenant=_UN_LUNDI, recherche=_RechercheFausse(), client=_ClientFaux())
    avant = Prospect.objects.count()
    # Deuxième passage le même jour : ne refait rien.
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI.replace(hour=14),
                                  recherche=_RechercheFausse(), client=_ClientFaux())
    assert resume == {"execute": False, "raison": "déjà exécuté aujourd'hui"}
    assert Prospect.objects.count() == avant


def test_jour_non_autorise_est_saute() -> None:
    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne, jours="5,6")  # seulement le week-end
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI,  # un lundi
                                  recherche=_RechercheFausse(), client=_ClientFaux())
    assert resume == {"execute": False, "raison": "jour non autorisé"}


def test_active_sans_campagne_ne_fait_rien() -> None:
    r = ReglageAutomatisation.charger()
    r.active = True
    r.save()
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI,
                                  recherche=_RechercheFausse(), client=_ClientFaux())
    assert resume == {"execute": False, "raison": "aucune campagne visée"}


# ── L'endpoint de réglages ────────────────────────────────────────────────────


def test_l_endpoint_exige_le_jeton() -> None:
    from django.test import Client
    assert Client().get(f"{BASE}/automatisation/").status_code in (401, 403)


def test_lire_puis_activer_avec_campagne(client_admin: Any) -> None:
    c = Campagne.objects.create(nom="Cible")
    d = json.loads(client_admin.get(f"{BASE}/automatisation/").content)
    assert d["active"] is False  # désactivée par défaut
    r = client_admin.put(
        f"{BASE}/automatisation/",
        data=json.dumps({"active": True, "campagne_id": str(c.id),
                         "prospects_par_jour": 30, "jours": [0, 1, 2, 3, 4]}),
        content_type="application/json",
    )
    assert r.status_code == 200
    d2 = json.loads(r.content)
    assert d2["active"] is True and d2["prospects_par_jour"] == 30
    assert d2["campagne_id"] == str(c.id) and d2["jours"] == [0, 1, 2, 3, 4]


def test_activer_sans_campagne_est_refuse(client_admin: Any) -> None:
    r = client_admin.put(
        f"{BASE}/automatisation/",
        data=json.dumps({"active": True}),
        content_type="application/json",
    )
    assert r.status_code == 400


def test_le_plafond_borne_les_prospects_par_jour(client_admin: Any) -> None:
    c = Campagne.objects.create(nom="Cible")
    r = client_admin.put(
        f"{BASE}/automatisation/",
        data=json.dumps({"active": True, "campagne_id": str(c.id), "prospects_par_jour": 999}),
        content_type="application/json",
    )
    assert json.loads(r.content)["prospects_par_jour"] == 50  # borné
