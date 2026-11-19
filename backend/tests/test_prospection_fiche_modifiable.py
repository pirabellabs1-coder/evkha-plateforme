"""Une fiche se CORRIGE, se saisit avec une adresse valide, et on ne rédige pas
pour une fiche sans adresse (audit du 19/11/2026).

Aucune route ne modifiait un prospect : une fiche créée sans adresse, ou avec
une adresse fautive, restait telle quelle. La création manuelle enregistrait la
chaîne reçue sans la regarder. Et la tâche quotidienne payait la rédaction
d'une séquence entière pour des fiches sans adresse, dont l'envoi est refusé.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from prospection import agents, services, tasks
from prospection.models import (
    Campagne,
    Message,
    Prospect,
    ReglageAutomatisation,
    StatutProspect,
)

from integrations.claude import StructuredResult
from integrations.search import SearchResponse

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


def _modifier(client_admin: Any, prospect: Prospect, corps: dict[str, Any]) -> Any:
    return client_admin.put(
        f"{BASE}/prospects/{prospect.id}/", data=json.dumps(corps),
        content_type="application/json",
    )


def _creer(client_admin: Any, corps: dict[str, Any]) -> Any:
    return client_admin.post(
        f"{BASE}/prospects/", data=json.dumps(corps), content_type="application/json"
    )


# ── Modifier une fiche ───────────────────────────────────────────────────────


def test_une_fiche_se_corrige_adresse_contact_et_notes(client_admin: Any) -> None:
    """Sur le code d'avant : 405, la route ne savait que lire."""
    prospect = Prospect.objects.create(raison_sociale="BGE Lille")

    reponse = _modifier(client_admin, prospect, {
        "email": " Contact@BGE-Lille.fr ", "nom_contact": "Claire Martin",
        "fonction": "Responsable création", "notes": "Vue au salon du 12/11.",
    })

    assert reponse.status_code == 200, reponse.content
    fiche = json.loads(reponse.content)
    assert fiche["email"] == "contact@bge-lille.fr"  # normalisée
    assert fiche["contactable"] is True
    prospect.refresh_from_db()
    assert (prospect.nom_contact, prospect.fonction) == ("Claire Martin", "Responsable création")
    assert prospect.notes == "Vue au salon du 12/11."


def test_seuls_les_champs_envoyes_sont_touches(client_admin: Any) -> None:
    prospect = Prospect.objects.create(
        raison_sociale="BGE Lille", email="contact@bge-lille.fr", nom_contact="Claire Martin",
        score_adequation=80, statut=StatutProspect.QUALIFIE,
    )

    reponse = _modifier(client_admin, prospect, {"notes": "Rappeler en janvier."})

    assert reponse.status_code == 200
    prospect.refresh_from_db()
    assert prospect.email == "contact@bge-lille.fr"
    assert prospect.nom_contact == "Claire Martin"
    # Ce qu'un humain ne corrige pas par ce formulaire reste intact.
    assert (prospect.score_adequation, prospect.statut) == (80, StatutProspect.QUALIFIE)


@pytest.mark.parametrize(
    "adresse", ["non communiqué", "contact@", "contact", "contact@bge", "a b@c.fr x", 42]
)
def test_une_adresse_sans_forme_d_adresse_est_refusee(client_admin: Any, adresse: Any) -> None:
    prospect = Prospect.objects.create(raison_sociale="BGE Lille", email="bon@bge-lille.fr")

    reponse = _modifier(client_admin, prospect, {"email": adresse})

    assert reponse.status_code == 400
    prospect.refresh_from_db()
    assert prospect.email == "bon@bge-lille.fr"


def test_l_adresse_se_vide(client_admin: Any) -> None:
    """Contre-épreuve : retirer une adresse fautive est permis (la fiche reste)."""
    prospect = Prospect.objects.create(raison_sociale="BGE Lille", email="faux@bge-lille.fr")

    reponse = _modifier(client_admin, prospect, {"email": ""})

    assert reponse.status_code == 200
    fiche = json.loads(reponse.content)
    assert fiche["email"] == "" and fiche["contactable"] is False
    assert "adresse" in fiche["motif_non_contact"]


def test_corriger_vers_une_adresse_opposee_desinscrit_la_fiche(client_admin: Any) -> None:
    """L'opposition suit l'adresse : la corriger vers une adresse opposée ne la contourne pas."""
    ailleurs = Prospect.objects.create(raison_sociale="Autre fiche", email="stop@cabinet.fr")
    services.desinscrire(ailleurs)
    prospect = Prospect.objects.create(raison_sociale="Cabinet", email="ancien@cabinet.fr")

    reponse = _modifier(client_admin, prospect, {"email": "stop@cabinet.fr"})

    assert reponse.status_code == 200
    fiche = json.loads(reponse.content)
    assert fiche["contactable"] is False and fiche["statut"] == StatutProspect.DESINSCRIT


def test_une_raison_sociale_ne_se_vide_pas(client_admin: Any) -> None:
    prospect = Prospect.objects.create(raison_sociale="BGE Lille")

    assert _modifier(client_admin, prospect, {"raison_sociale": "  "}).status_code == 400
    assert _modifier(client_admin, prospect, {}).status_code == 400
    prospect.refresh_from_db()
    assert prospect.raison_sociale == "BGE Lille"


def test_modifier_une_fiche_exige_le_jeton() -> None:
    from django.test import Client

    prospect = Prospect.objects.create(raison_sociale="BGE Lille")
    reponse = Client().put(
        f"{BASE}/prospects/{prospect.id}/", data=json.dumps({"notes": "x"}),
        content_type="application/json",
    )
    assert reponse.status_code in (401, 403)


# ── Ajouter une fiche à la main ──────────────────────────────────────────────


def test_la_saisie_manuelle_refuse_une_adresse_sans_forme(client_admin: Any) -> None:
    """Sur le code d'avant : 201, et « non communiqué » enregistré comme adresse."""
    reponse = _creer(client_admin, {"raison_sociale": "BGE Lille", "email": "non communiqué"})

    assert reponse.status_code == 400
    assert Prospect.objects.count() == 0


def test_la_saisie_manuelle_normalise_l_adresse(client_admin: Any) -> None:
    reponse = _creer(client_admin, {
        "raison_sociale": "BGE Lille", "email": " Contact@BGE-Lille.FR", "nom_contact": "Claire",
    })

    assert reponse.status_code == 201
    fiche = json.loads(reponse.content)
    assert fiche["email"] == "contact@bge-lille.fr"
    assert fiche["source"] == "manuel" and fiche["contactable"] is True


# ── Ne pas rédiger pour une fiche sans adresse ───────────────────────────────


class _ClientCompteur:
    """Rend de quoi qualifier et rédiger ; COMPTE les rédactions payées."""

    def __init__(self, fiches: list[dict[str, Any]] | None = None) -> None:
        self._fiches = fiches or []
        self.appels: list[str] = []

    def complete_structured(self, *, outil_nom: str, **_: Any) -> StructuredResult:
        self.appels.append(outil_nom)
        charges: dict[str, dict[str, Any]] = {
            "extraire_prospects": {"prospects": self._fiches},
            "qualifier_prospect": {"score": 70, "raison": "ok"},
            "rediger_messages": {"messages": [
                {"objet": f"O{i}", "corps": f"<p>C{i}</p>"} for i in range(5)
            ]},
        }
        return StructuredResult(payload=dict(charges.get(outil_nom, {})),
                                input_tokens=1, output_tokens=1, model="claude-opus")


class _RechercheVide:
    def search(self, *, query: str, max_results: int = 5, **_: Any) -> SearchResponse:
        return SearchResponse(query=query, results=())


def test_l_agent_ne_redige_pas_pour_une_fiche_sans_adresse() -> None:
    """Sur le code d'avant : le modèle était appelé, cinq brouillons créés pour rien."""
    prospect = Prospect.objects.create(raison_sociale="Sans adresse")
    client = _ClientCompteur()

    with pytest.raises(RuntimeError, match="adresse"):
        agents.rediger_les_messages(prospect, client=client)

    assert client.appels == [], "aucun appel payant ne doit partir"
    assert Message.objects.count() == 0


def test_l_ecran_recoit_un_refus_metier_pas_une_panne(client_admin: Any, monkeypatch: Any) -> None:
    """409 (« ajoutez une adresse »), pas 502 (« le service IA n'a pas pu… »)."""
    prospect = Prospect.objects.create(raison_sociale="Sans adresse")
    client = _ClientCompteur()
    monkeypatch.setattr("integrations.claude.get_claude_client", lambda: client)

    reponse = client_admin.post(
        f"{BASE}/prospects/{prospect.id}/rediger/", data=json.dumps({"confirmer": True}),
        content_type="application/json",
    )

    assert reponse.status_code == 409
    assert "adresse" in json.loads(reponse.content)["erreur"]
    assert client.appels == []


def test_la_tache_quotidienne_ne_paie_pas_la_redaction_des_fiches_sans_adresse() -> None:
    """Sur le code d'avant : deux rédactions payées, dont une pour la fiche sans adresse."""
    campagne = Campagne.objects.create(nom="Auto", secteur="Accompagnement")
    reglage = ReglageAutomatisation.charger()
    reglage.active, reglage.campagne = True, campagne
    reglage.save()
    client = _ClientCompteur([
        {"raison_sociale": "Avec adresse", "email": "contact@avec.fr"},
        {"raison_sociale": "Sans adresse"},
    ])

    resume = tasks.executer_si_du(
        maintenant=datetime(2026, 11, 16, 9, 0, tzinfo=UTC),  # un lundi
        recherche=_RechercheVide(), client=client,
    )

    assert resume["crees"] == 2 and resume["qualifies"] == 2
    assert client.appels.count("rediger_messages") == 1
    assert resume["rediges"] == 1 and resume["non_contactables"] == 1
    sans = Prospect.objects.get(raison_sociale="Sans adresse")
    assert sans.messages.count() == 0
    # Contre-épreuve : la fiche qui a une adresse, elle, a bien sa séquence.
    assert Prospect.objects.get(raison_sociale="Avec adresse").messages.count() == 5
