"""Phase 4 : suivi Brevo (webhook → Evenement) et désinscription publique.

On vérifie trois choses : un événement Brevo se trace sur le bon message et une
désinscription Brevo retire le consentement ; le lien public de désinscription
opère en un clic, sans jamais planter ; et tout e-mail qui part porte un lien de
désinscription (conformité), sans que le brouillon validé soit modifié.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client
from prospection import services
from prospection.models import (
    Campagne,
    Evenement,
    Message,
    Prospect,
    StatutMessage,
    StatutProspect,
    TypeEvenement,
)
from prospection.webhooks import enregistrer_evenement_brevo, enregistrer_evenement_resend

pytestmark = pytest.mark.django_db


def _message(provider_id: str = "brevo-msg-1", statut: str = StatutMessage.ENVOYE) -> Message:
    campagne = Campagne.objects.create(nom="C", secteur="RH")
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="Alpha",
                                       email="a@alpha.fr")
    return Message.objects.create(
        prospect=prospect, campagne=campagne, objet="O", corps="<p>Bonjour</p>",
        statut=statut, provider_message_id=provider_id,
    )


# ── Suivi Brevo (fonction pure) ──────────────────────────────────────────────


def test_un_evenement_brevo_se_trace_sur_le_bon_message() -> None:
    m = _message()
    evt = enregistrer_evenement_brevo({"event": "opened", "message-id": "brevo-msg-1"})
    assert evt is not None and evt.type == TypeEvenement.OUVERT and evt.message_id == m.id


def test_une_desinscription_brevo_retire_le_consentement() -> None:
    m = _message(statut=StatutMessage.ENVOYE)
    # Un brouillon encore en file doit être annulé par la désinscription.
    brouillon = Message.objects.create(prospect=m.prospect, objet="X", corps="y",
                                       statut=StatutMessage.VALIDE)
    evt = enregistrer_evenement_brevo({"event": "unsubscribed", "message-id": "brevo-msg-1"})
    assert evt is not None and evt.type == TypeEvenement.DESINSCRIT
    m.prospect.refresh_from_db()
    assert m.prospect.consentement_retire is True
    assert m.prospect.statut == StatutProspect.DESINSCRIT
    brouillon.refresh_from_db()
    assert brouillon.statut == StatutMessage.ANNULE


def test_un_message_inconnu_ne_plante_pas() -> None:
    _message(provider_id="connu")
    assert enregistrer_evenement_brevo({"event": "opened", "message-id": "INCONNU"}) is None
    assert Evenement.objects.count() == 0


def test_un_type_non_suivi_est_ignore() -> None:
    _message()
    assert enregistrer_evenement_brevo({"event": "request", "message-id": "brevo-msg-1"}) is None


def test_le_meme_evenement_ne_cree_pas_de_doublon() -> None:
    _message()
    charge = {"event": "opened", "message-id": "brevo-msg-1", "ts": 1700000000}
    enregistrer_evenement_brevo(charge)
    enregistrer_evenement_brevo(charge)
    assert Evenement.objects.filter(type=TypeEvenement.OUVERT).count() == 1


# ── Webhook Brevo (HTTP, public) ─────────────────────────────────────────────


def test_le_webhook_brevo_accepte_et_trace() -> None:
    _message()
    r = Client().post(
        "/webhooks/brevo/prospection/",
        data=json.dumps({"event": "delivered", "message-id": "brevo-msg-1"}),
        content_type="application/json",
    )
    assert r.status_code == 202
    corps = json.loads(r.content)
    assert corps["traces"] == 1
    assert Evenement.objects.filter(type=TypeEvenement.DELIVRE).count() == 1


def test_le_webhook_brevo_traite_un_lot() -> None:
    _message()
    r = Client().post(
        "/webhooks/brevo/prospection/",
        data=json.dumps([
            {"event": "delivered", "message-id": "brevo-msg-1"},
            {"event": "opened", "message-id": "brevo-msg-1"},
        ]),
        content_type="application/json",
    )
    assert r.status_code == 202 and json.loads(r.content)["traces"] == 2


# ── Suivi Resend (le fournisseur actif) ──────────────────────────────────────


def test_un_evenement_resend_se_trace_sur_le_bon_message() -> None:
    m = _message()
    evt = enregistrer_evenement_resend(
        {"type": "email.opened", "data": {"email_id": "brevo-msg-1"}}
    )
    assert evt is not None and evt.type == TypeEvenement.OUVERT and evt.message_id == m.id


def test_un_type_resend_inconnu_est_ignore() -> None:
    _message()
    charge = {"type": "email.sent", "data": {"email_id": "brevo-msg-1"}}
    assert enregistrer_evenement_resend(charge) is None


def test_le_webhook_resend_accepte_sans_secret() -> None:
    """Fail-open tant que le secret n'est pas posé : mise en route immédiate."""
    _message()
    r = Client().post(
        "/webhooks/resend/prospection/",
        data=json.dumps({"type": "email.delivered", "data": {"email_id": "brevo-msg-1"}}),
        content_type="application/json",
    )
    assert r.status_code == 202 and json.loads(r.content)["traces"] == 1
    assert Evenement.objects.filter(type=TypeEvenement.DELIVRE).count() == 1


def test_le_webhook_resend_refuse_une_signature_absente_si_secret_pose() -> None:
    from django.test import override_settings
    with override_settings(RESEND_WEBHOOK_SECRET="whsec_c2VjcmV0"):
        r = Client().post(
            "/webhooks/resend/prospection/",
            data=json.dumps({"type": "email.opened", "data": {"email_id": "x"}}),
            content_type="application/json",
        )
    assert r.status_code == 401


def test_le_webhook_resend_accepte_une_signature_valide() -> None:
    import base64
    import hashlib
    import hmac

    from django.test import override_settings

    m = _message()
    secret_b64 = base64.b64encode(b"super-secret").decode()
    corps = json.dumps({"type": "email.clicked", "data": {"email_id": "brevo-msg-1"}})
    svix_id, svix_ts = "msg_1", "1700000000"
    signe = f"{svix_id}.{svix_ts}.{corps}".encode()
    sig = base64.b64encode(
        hmac.new(base64.b64decode(secret_b64), signe, hashlib.sha256).digest()
    ).decode()
    with override_settings(RESEND_WEBHOOK_SECRET=f"whsec_{secret_b64}"):
        r = Client().post(
            "/webhooks/resend/prospection/",
            data=corps,
            content_type="application/json",
            headers={
                "svix-id": svix_id,
                "svix-timestamp": svix_ts,
                "svix-signature": f"v1,{sig}",
            },
        )
    assert r.status_code == 202
    assert Evenement.objects.filter(message=m, type=TypeEvenement.CLIQUE).count() == 1


def test_les_secrets_de_webhook_email_sont_declares_dans_les_reglages() -> None:
    """Sans déclaration dans settings, `getattr(settings, …)` rend "" et le
    contrôle de signature est silencieusement inerte. On vérifie qu'ils EXISTENT."""
    from django.conf import settings
    assert hasattr(settings, "RESEND_WEBHOOK_SECRET")
    assert hasattr(settings, "BREVO_WEBHOOK_SECRET")


# ── Désinscription publique ──────────────────────────────────────────────────


def test_le_lien_public_desinscrit_en_un_clic() -> None:
    m = _message(statut=StatutMessage.VALIDE)
    jeton = m.prospect.jeton_desinscription
    r = Client().get(f"/p/desinscription/{jeton}/")
    assert r.status_code == 200
    m.prospect.refresh_from_db()
    assert m.prospect.consentement_retire is True
    m.refresh_from_db()
    assert m.statut == StatutMessage.ANNULE  # file annulée


def test_un_jeton_inconnu_rend_une_page_polie_sans_planter() -> None:
    r = Client().get("/p/desinscription/00000000-0000-0000-0000-000000000000/")
    assert r.status_code == 404
    assert b"introuvable" in r.content.lower()


def test_la_desinscription_est_idempotente() -> None:
    m = _message()
    jeton = m.prospect.jeton_desinscription
    c = Client()
    assert c.get(f"/p/desinscription/{jeton}/").status_code == 200
    assert c.get(f"/p/desinscription/{jeton}/").status_code == 200


# ── Conformité : tout envoi porte le lien de désinscription ──────────────────


class _ClientEspionEnvoi:
    """Capture le html_body transmis au fournisseur, sans rien envoyer pour de vrai."""

    def __init__(self) -> None:
        self.html_body = ""

    def send_delivery_email(self, *, recipient_email: str, subject: str,
                            html_body: str, attachments: Any = ()) -> Any:
        self.html_body = html_body
        from integrations.brevo import EmailSendResult  # noqa: PLC0415
        return EmailSendResult(provider_message_id="brevo-envoye-1")


def test_tout_envoi_porte_le_lien_de_desinscription() -> None:
    campagne = Campagne.objects.create(nom="C")
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="Alpha",
                                       email="a@alpha.fr")
    message = Message.objects.create(prospect=prospect, campagne=campagne, objet="O",
                                     corps="<p>Bonjour</p>", statut=StatutMessage.VALIDE)
    espion = _ClientEspionEnvoi()
    services.envoyer_message(message, client=espion)

    assert f"/p/desinscription/{prospect.jeton_desinscription}/" in espion.html_body
    assert "désinscrire" in espion.html_body.lower()
    # L'e-mail envoyé est MIS EN PAGE dans le gabarit, pas du HTML nu : en-tête
    # de marque, document complet, et le corps rédigé à l'intérieur.
    assert "<!DOCTYPE html>" in espion.html_body
    assert "EVKHA" in espion.html_body
    assert "<p>Bonjour</p>" in espion.html_body  # le corps du brouillon, intact
    # Le brouillon validé n'a PAS été modifié : la mise en page est ajoutée à l'envoi.
    message.refresh_from_db()
    assert message.corps == "<p>Bonjour</p>" and "DOCTYPE" not in message.corps
