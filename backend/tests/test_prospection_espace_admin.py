"""Les écrans de prospection de l'espace admin (phase 2).

Routes sous `/api/dashboard/prospection/…` : protégées par le jeton admin, elles
pilotent campagnes, prospects, séquence et la FILE DE VALIDATION. L'envoi passe
par le service — l'invariant « rien ne part sans validation » tient à travers
la couche HTTP.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client
from prospection.models import Message, Prospect, StatutMessage, StatutProspect

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


def _charge(reponse: Any) -> Any:
    return json.loads(reponse.content)


def _poster(client_admin: Any, url: str, corps: dict[str, Any]) -> Any:
    return client_admin.post(url, data=json.dumps(corps), content_type="application/json")


def _campagne(client_admin: Any, nom: str = "Cabinets RH Lyon") -> str:
    r = _poster(client_admin, f"{BASE}/campagnes/", {"nom": nom, "secteur": "RH", "zone": "Lyon"})
    assert r.status_code == 201
    return str(_charge(r)["id"])


def _prospect(client_admin: Any, campagne_id: str, email: str = "contact@cible.fr") -> str:
    r = _poster(client_admin, f"{BASE}/prospects/", {
        "campagne_id": campagne_id, "raison_sociale": "Cible SARL", "email": email,
    })
    assert r.status_code == 201
    return str(_charge(r)["id"])


def _brouillon(client_admin: Any, prospect_id: str) -> str:
    r = _poster(client_admin, f"{BASE}/messages/", {
        "prospect_id": prospect_id, "objet": "Bonjour", "corps": "<p>Proposition</p>",
    })
    assert r.status_code == 201
    corps = _charge(r)
    assert corps["statut"] == StatutMessage.BROUILLON
    return str(corps["id"])


def test_les_routes_exigent_le_jeton() -> None:
    assert Client().get(f"{BASE}/apercu/").status_code in (401, 403)
    assert Client().get(f"{BASE}/campagnes/").status_code in (401, 403)


def test_on_cree_et_liste_une_campagne(client_admin: Any) -> None:
    cid = _campagne(client_admin)
    liste = _charge(client_admin.get(f"{BASE}/campagnes/"))
    assert any(c["id"] == cid for c in liste)
    detail = _charge(client_admin.get(f"{BASE}/campagnes/{cid}/"))
    assert detail["secteur"] == "RH" and detail["sequence"] == []


def test_on_definit_la_sequence_de_relances(client_admin: Any) -> None:
    cid = _campagne(client_admin)
    r = client_admin.put(
        f"{BASE}/campagnes/{cid}/sequence/",
        data=json.dumps({"etapes": [
            {"objet_gabarit": "Découverte EVKHA", "corps_gabarit": "Bonjour {{contact}}"},
            {"delai_jours": 4, "objet_gabarit": "Relance 1"},
            {"delai_jours": 7, "objet_gabarit": "Relance 2"},
        ]}),
        content_type="application/json",
    )
    assert r.status_code == 200
    etapes = _charge(r)
    assert [e["ordre"] for e in etapes] == [0, 1, 2]
    assert etapes[0]["est_une_relance"] is False and etapes[1]["est_une_relance"] is True


def test_on_cree_un_prospect_et_le_consulte(client_admin: Any) -> None:
    cid = _campagne(client_admin)
    pid = _prospect(client_admin, cid)
    detail = _charge(client_admin.get(f"{BASE}/prospects/{pid}/"))
    assert detail["contactable"] is True and detail["messages"] == []


def test_un_brouillon_est_dans_la_file_de_validation(client_admin: Any) -> None:
    cid = _campagne(client_admin)
    pid = _prospect(client_admin, cid)
    mid = _brouillon(client_admin, pid)
    file = _charge(client_admin.get(f"{BASE}/messages/?statut=brouillon"))
    assert any(m["id"] == mid for m in file)
    apercu = _charge(client_admin.get(f"{BASE}/apercu/"))
    assert apercu["a_valider"] >= 1


def test_envoyer_un_brouillon_est_refuse_par_l_api(client_admin: Any) -> None:
    """L'invariant tient à travers HTTP : un brouillon ne part pas."""
    cid = _campagne(client_admin)
    pid = _prospect(client_admin, cid)
    mid = _brouillon(client_admin, pid)
    r = client_admin.post(f"{BASE}/messages/{mid}/envoyer/")
    assert r.status_code == 409 and "validé" in _charge(r)["erreur"]
    assert Message.objects.get(id=mid).statut == StatutMessage.BROUILLON


def test_valider_puis_envoyer(client_admin: Any) -> None:
    cid = _campagne(client_admin)
    pid = _prospect(client_admin, cid)
    mid = _brouillon(client_admin, pid)

    v = _poster(client_admin, f"{BASE}/messages/{mid}/valider/", {"par": "Evangéline"})
    assert v.status_code == 200 and _charge(v)["statut"] == StatutMessage.VALIDE
    assert _charge(v)["valide_par"] == "Evangéline"

    e = client_admin.post(f"{BASE}/messages/{mid}/envoyer/")
    assert e.status_code == 200 and _charge(e)["statut"] == StatutMessage.ENVOYE
    assert _charge(e)["provider_message_id"]
    assert Prospect.objects.get(id=pid).statut == StatutProspect.CONTACTE

    ev = _charge(client_admin.get(f"{BASE}/messages/{mid}/evenements/"))
    assert ev["resume"]["envoye"] == 1


def test_editer_un_brouillon_avant_validation(client_admin: Any) -> None:
    cid = _campagne(client_admin)
    pid = _prospect(client_admin, cid)
    mid = _brouillon(client_admin, pid)
    r = client_admin.put(
        f"{BASE}/messages/{mid}/", data=json.dumps({"objet": "Objet revu"}),
        content_type="application/json",
    )
    assert r.status_code == 200 and _charge(r)["objet"] == "Objet revu"


def test_desinscrire_annule_les_messages_en_file(client_admin: Any) -> None:
    cid = _campagne(client_admin)
    pid = _prospect(client_admin, cid)
    mid = _brouillon(client_admin, pid)
    _poster(client_admin, f"{BASE}/messages/{mid}/valider/", {"par": "Evangéline"})

    r = client_admin.post(f"{BASE}/prospects/{pid}/desinscrire/")
    assert r.status_code == 200 and _charge(r)["statut"] == StatutProspect.DESINSCRIT

    assert Message.objects.get(id=mid).statut == StatutMessage.ANNULE
    e = client_admin.post(f"{BASE}/messages/{mid}/envoyer/")
    assert e.status_code == 409


def test_un_prospect_sans_email_n_est_pas_contactable(client_admin: Any) -> None:
    cid = _campagne(client_admin)
    r = _poster(client_admin, f"{BASE}/prospects/", {
        "campagne_id": cid, "raison_sociale": "Sans mail",
    })
    assert r.status_code == 201 and _charge(r)["contactable"] is False


def test_on_fait_avancer_un_prospect_dans_le_pipeline(client_admin: Any) -> None:
    cid = _campagne(client_admin)
    pid = _prospect(client_admin, cid)
    r = _poster(client_admin, f"{BASE}/prospects/{pid}/statut/", {"statut": "a_repondu"})
    assert r.status_code == 200 and _charge(r)["statut"] == StatutProspect.A_REPONDU
    # Un statut inconnu est refusé.
    r2 = _poster(client_admin, f"{BASE}/prospects/{pid}/statut/", {"statut": "n_importe_quoi"})
    assert r2.status_code == 400
