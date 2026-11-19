"""Un envoi en échec n'est plus une impasse (audit du 19/11/2026).

Quand le fournisseur refuse, le message passe `echoue`. Il disparaissait alors
de l'écran (qui ne chargeait que les brouillons prêts et les validés) : ni
motif, ni bouton, et ses relances attendaient sans fin une étape qui ne
partirait pas.

Ce que le serveur offre désormais, et ce que ce fichier verrouille :

- le message en échec se LISTE, avec son motif (`error_message`) — ces deux
  points existaient déjà côté serveur, c'est l'écran qui ne les lisait pas :
  les tests correspondants passent aussi sur le code d'avant, ils sont là pour
  que l'écran puisse s'y fier ;
- il se COMPTE dans l'aperçu (`en_echec`) — neuf ;
- il se REVALIDE tel quel, s'ANNULE (déjà permis), ou se REMET EN BROUILLON
  pour être retouché (neuf).
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from prospection import services
from prospection.models import Campagne, Message, Prospect, StatutMessage

from integrations.brevo import EmailSendResult

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


class _ClientQuiRefuse:
    def send_delivery_email(self, **_: Any) -> EmailSendResult:
        raise RuntimeError("quota journalier du fournisseur atteint")


class _ClientEspion:
    def __init__(self) -> None:
        self.envois = 0

    def send_delivery_email(self, **_: Any) -> EmailSendResult:
        self.envois += 1
        return EmailSendResult(provider_message_id=f"envoi-{self.envois}")


def _poster(client_admin: Any, url: str, corps: dict[str, Any] | None = None) -> Any:
    return client_admin.post(url, data=json.dumps(corps or {}), content_type="application/json")


def _en_echec() -> tuple[Message, Message]:
    """Un premier mail que le fournisseur a refusé, et sa relance en brouillon."""
    campagne = Campagne.objects.create(nom="Échec")
    prospect = Prospect.objects.create(
        campagne=campagne, raison_sociale="Alpha", email="contact@alpha.fr"
    )
    premier = Message.objects.create(
        prospect=prospect, campagne=campagne, etape=0, objet="Premier", corps="<p>x</p>",
        statut=StatutMessage.VALIDE, valide_par="Evangéline",
    )
    relance = Message.objects.create(
        prospect=prospect, campagne=campagne, etape=1, objet="Relance", corps="<p>y</p>",
    )
    with pytest.raises(services.EnvoiRefuseError):
        services.envoyer_message(premier, client=_ClientQuiRefuse())
    premier.refresh_from_db()
    assert premier.statut == StatutMessage.ECHOUE
    return premier, relance


def test_le_message_en_echec_se_liste_avec_son_motif(client_admin: Any) -> None:
    """Ce que l'écran charge pour son bloc « En échec ». (Passait déjà côté serveur.)"""
    premier, _ = _en_echec()

    liste = json.loads(client_admin.get(f"{BASE}/messages/", {"statut": "echoue"}).content)

    assert [m["id"] for m in liste] == [str(premier.id)]
    assert "quota journalier" in liste[0]["error_message"]
    assert liste[0]["etape_libelle"] == "Premier message"
    assert liste[0]["prospect_nom"] == "Alpha"


def test_l_apercu_compte_les_messages_en_echec(client_admin: Any) -> None:
    """Sur le code d'avant : aucun compteur — l'échec n'apparaissait nulle part."""
    _en_echec()

    apercu = json.loads(client_admin.get(f"{BASE}/apercu/").content)

    assert apercu["en_echec"] == 1


def test_un_message_en_echec_se_revalide_puis_part(client_admin: Any) -> None:
    """« Revalider » : `valider_message` l'acceptait déjà ; on le verrouille."""
    premier, _ = _en_echec()

    r = _poster(client_admin, f"{BASE}/messages/{premier.id}/valider/", {"par": "Evangéline"})

    assert r.status_code == 200
    charge = json.loads(r.content)
    assert charge["statut"] == StatutMessage.VALIDE and charge["error_message"] == ""
    premier.refresh_from_db()
    espion = _ClientEspion()
    services.envoyer_message(premier, client=espion)
    assert espion.envois == 1


def test_un_message_en_echec_s_annule_et_sa_relance_est_dite_rompue(client_admin: Any) -> None:
    """« Annuler » : la relance n'attend plus sans fin, elle est ROMPUE et le dit."""
    premier, relance = _en_echec()

    r = _poster(client_admin, f"{BASE}/messages/{premier.id}/annuler/")

    assert r.status_code == 200 and json.loads(r.content)["statut"] == StatutMessage.ANNULE
    brouillons = json.loads(client_admin.get(f"{BASE}/messages/", {"statut": "brouillon"}).content)
    assert [(m["id"], m["rompue"]) for m in brouillons] == [(str(relance.id), True)]


def test_un_message_en_echec_se_remet_en_brouillon_pour_etre_retouche(client_admin: Any) -> None:
    """Sur le code d'avant : la route n'existait pas, et seul un brouillon s'édite."""
    premier, _ = _en_echec()

    r = _poster(client_admin, f"{BASE}/messages/{premier.id}/brouillon/")

    assert r.status_code == 200, r.content
    charge = json.loads(r.content)
    assert charge["statut"] == StatutMessage.BROUILLON
    # La validation est RETIRÉE : un texte retouché se relit et se revalide.
    assert charge["valide_par"] == "" and charge["valide_le"] is None
    # Le motif reste lisible tant que le message n'est pas revalidé.
    assert "quota journalier" in charge["error_message"]
    edition = client_admin.put(
        f"{BASE}/messages/{premier.id}/", data=json.dumps({"objet": "Premier, corrigé"}),
        content_type="application/json",
    )
    assert edition.status_code == 200 and json.loads(edition.content)["objet"] == "Premier, corrigé"
    # Et un brouillon ne part pas : l'invariant tient.
    with pytest.raises(services.EnvoiRefuseError, match="validé par un humain"):
        services.envoyer_message(Message.objects.get(pk=premier.pk), client=_ClientEspion())


@pytest.mark.parametrize("statut", [StatutMessage.ENVOYE, StatutMessage.ANNULE,
                                    StatutMessage.BROUILLON])
def test_seul_un_message_en_echec_ou_valide_revient_en_brouillon(
    client_admin: Any, statut: str
) -> None:
    """Contre-épreuve : la route ne ressuscite ni un envoyé, ni un annulé."""
    prospect = Prospect.objects.create(raison_sociale="Alpha", email="contact@alpha.fr")
    message = Message.objects.create(prospect=prospect, objet="O", corps="x", statut=statut)

    r = _poster(client_admin, f"{BASE}/messages/{message.id}/brouillon/")

    assert r.status_code == 409
    message.refresh_from_db()
    assert message.statut == statut


def test_un_identifiant_de_message_mal_forme_rend_404_pas_500(client_admin: Any) -> None:
    """`objects.get(id="abc")` lève `ValidationError`, qui n'est pas une `ValueError`."""
    r = _poster(client_admin, f"{BASE}/messages/pas-un-uuid/brouillon/")
    assert r.status_code == 404
    assert client_admin.get(f"{BASE}/prospects/pas-un-uuid/").status_code == 404
    assert client_admin.get(f"{BASE}/campagnes/pas-un-uuid/").status_code == 404
