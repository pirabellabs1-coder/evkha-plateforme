"""Resend devient le fournisseur de courriel — sans second chemin d'envoi.

Décision de la cliente le 07/08/2026 : « on utilise Resend tout simplement ».

Ce qui compte ici n'est pas qu'un client Resend existe, c'est qu'il se range
DERRIÈRE le port déjà en place. Tout le produit appelle
`get_transactional_email_client()` : l'invitation d'un collaborateur, le lien
de mot de passe, la confirmation d'adresse et la livraison du document. Si
Resend arrivait par un chemin à lui, il y aurait deux façons d'envoyer un
courriel dans le dépôt, et la question « d'où part ce message ? » n'aurait plus
de réponse unique (règle 5).

Les tests tiennent donc trois choses :

1. la fabrique rend bien Resend quand on le lui demande, et Brevo sinon ;
2. un nom inconnu ÉCHOUE — il ne retombe pas en silence sur un fournisseur que
   personne n'a choisi ;
3. la requête HTTP part avec ce que Resend attend, et pas avec la forme de
   Brevo : `from` en une seule chaîne, `to` en liste, `html`, et
   `Authorization: Bearer`.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import override_settings

from integrations.brevo import (
    BrevoApiClient,
    EmailAttachment,
    StubBrevoClient,
    TransactionalEmailClient,
    get_transactional_email_client,
)
from integrations.resend_api import ResendApiClient

# ── 1. La fabrique ───────────────────────────────────────────────────────────


@override_settings(EVKHA_USE_STUB_EMAIL=False, EVKHA_EMAIL_PROVIDER="resend")
def test_resend_est_le_fournisseur_demande() -> None:
    assert isinstance(get_transactional_email_client(), ResendApiClient)


@override_settings(EVKHA_USE_STUB_EMAIL=False, EVKHA_EMAIL_PROVIDER="brevo")
def test_brevo_reste_branchable_sans_redeploiement() -> None:
    """Le jour où Resend tombe, on repasse à Brevo depuis Coolify.

    C'est la raison d'être de la bascule : un incident de fournisseur ne doit
    pas imposer de rouvrir le code.
    """
    assert isinstance(get_transactional_email_client(), BrevoApiClient)


@override_settings(EVKHA_USE_STUB_EMAIL=True, EVKHA_EMAIL_PROVIDER="resend")
def test_la_doublure_prime_sur_le_fournisseur() -> None:
    """Contre-épreuve : en développement et en test, RIEN ne part.

    Les dossiers portent de vraies adresses client — c'est écrit noir sur blanc
    dans les règles du dépôt.
    """
    assert isinstance(get_transactional_email_client(), StubBrevoClient)


@override_settings(EVKHA_USE_STUB_EMAIL=False, EVKHA_EMAIL_PROVIDER="resnd")
def test_un_fournisseur_inconnu_echoue_bruyamment() -> None:
    """Une faute de frappe ne doit pas router le courrier ailleurs en silence.

    Sur une table ouverte avec repli, `EVKHA_EMAIL_PROVIDER=resnd` aurait
    envoyé tous les messages chez l'ancien prestataire sans que rien ne le
    signale — un échec déguisé en succès (règle 1).
    """
    with pytest.raises(RuntimeError, match="resnd"):
        get_transactional_email_client()


def test_les_deux_clients_honorent_le_protocole() -> None:
    """Sans cela, la bascule ne serait qu'un changement de nom."""
    assert isinstance(ResendApiClient(), TransactionalEmailClient)
    assert isinstance(BrevoApiClient(), TransactionalEmailClient)


# ── 2. La requête envoyée ────────────────────────────────────────────────────


class _Reponse:
    def __init__(self, corps: dict[str, Any]) -> None:
        self._corps = json.dumps(corps).encode("utf-8")

    def read(self) -> bytes:
        return self._corps

    def __enter__(self) -> _Reponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _intercepter(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Capture la requête sans jamais ouvrir de connexion."""
    import urllib.request

    vues: list[Any] = []

    def urlopen(requete: Any, timeout: int = 0) -> _Reponse:  # noqa: ARG001
        vues.append(requete)
        return _Reponse({"id": "resend-message-42"})

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return vues


@override_settings(
    RESEND_API_KEY="re_test_000",
    EVKHA_SENDER_EMAIL="contact@evkha.fr",
    EVKHA_SENDER_NAME="EVKHA",
)
def test_la_requete_a_la_forme_attendue_par_resend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Brevo attend `sender`/`htmlContent`, Resend attend `from`/`html`.

    Envoyer la forme de l'un à l'autre rend un 422 et aucun message. C'est
    exactement le genre de défaut qu'un test unitaire attrape et qu'une
    relecture laisse passer.
    """
    vues = _intercepter(monkeypatch)

    resultat = ResendApiClient().send_delivery_email(
        recipient_email="partenaire@exemple.fr",
        subject="Votre business plan est prêt",
        html_body="<p>Bonjour</p>",
        attachments=(EmailAttachment(filename="bp.docx", url="https://x/bp.docx"),),
    )

    assert resultat.provider_message_id == "resend-message-42"
    requete = vues[0]
    assert requete.full_url == "https://api.resend.com/emails"
    assert requete.get_header("Authorization") == "Bearer re_test_000"

    envoi = json.loads(requete.data.decode("utf-8"))
    assert envoi["from"] == "EVKHA <contact@evkha.fr>"
    assert envoi["to"] == ["partenaire@exemple.fr"]
    assert envoi["subject"] == "Votre business plan est prêt"
    assert envoi["html"] == "<p>Bonjour</p>"
    assert envoi["attachments"] == [
        {"path": "https://x/bp.docx", "filename": "bp.docx"}
    ]
    # Les champs de Brevo n'ont rien à faire ici.
    assert "sender" not in envoi
    assert "htmlContent" not in envoi


@override_settings(RESEND_API_KEY="re_test_000", EVKHA_SENDER_NAME="")
def test_un_expediteur_sans_nom_reste_une_adresse_valide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """« <contact@evkha.fr> » précédé d'un espace vide serait refusé."""
    vues = _intercepter(monkeypatch)

    ResendApiClient().send_delivery_email(
        recipient_email="a@b.fr", subject="s", html_body="h", attachments=(),
    )

    envoi = json.loads(vues[0].data.decode("utf-8"))
    assert not envoi["from"].startswith(" ")
    assert "<" not in envoi["from"]


@override_settings(RESEND_API_KEY="re_test_000")
def test_un_message_sans_piece_jointe_n_envoie_pas_le_champ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une invitation n'a rien à joindre ; `attachments: []` est du bruit."""
    vues = _intercepter(monkeypatch)

    ResendApiClient().send_delivery_email(
        recipient_email="a@b.fr", subject="s", html_body="h", attachments=(),
    )

    assert "attachments" not in json.loads(vues[0].data.decode("utf-8"))


@override_settings(RESEND_API_KEY="")
def test_une_cle_absente_echoue_au_lieu_d_envoyer_dans_le_vide() -> None:
    """Sans clé, l'appel part et revient 401 : autant le dire tout de suite.

    L'exception remonte à `deliver_job`, qui enregistre un lot FAILED et son
    incident. Se taire ferait passer un document jamais reçu pour un document
    livré.
    """
    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        ResendApiClient().send_delivery_email(
            recipient_email="a@b.fr", subject="s", html_body="h", attachments=(),
        )


# ── 3. L'expéditeur ne dépend pas du fournisseur ─────────────────────────────


@override_settings(
    RESEND_API_KEY="re_test_000",
    BREVO_API_KEY="xkeysib-test",
    EVKHA_SENDER_EMAIL="contact@evkha.fr",
    EVKHA_SENDER_NAME="EVKHA",
)
def test_les_deux_fournisseurs_ecrivent_de_la_meme_adresse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basculer de fournisseur ne doit pas changer l'expéditeur.

    Première version de ce correctif : `BREVO_SENDER_EMAIL = EVKHA_SENDER_EMAIL`
    dans les réglages. Le test l'a fait tomber, et il avait raison — c'était une
    COPIE prise au chargement, muette à toute modification ultérieure, et deux
    variables pour une seule vérité (règle 5). Les deux réglages propres à
    Brevo ont été supprimés : les deux clients lisent `EVKHA_SENDER_*`.

    La preuve est prise sur ce que chaque client ENVOIE, pas sur l'égalité de
    deux réglages : c'est l'en-tête reçu par le partenaire qui compte.
    """
    vues = _intercepter(monkeypatch)

    ResendApiClient().send_delivery_email(
        recipient_email="a@b.fr", subject="s", html_body="h", attachments=(),
    )
    BrevoApiClient().send_delivery_email(
        recipient_email="a@b.fr", subject="s", html_body="h", attachments=(),
    )

    chez_resend = json.loads(vues[0].data.decode("utf-8"))
    chez_brevo = json.loads(vues[1].data.decode("utf-8"))
    assert chez_resend["from"] == "EVKHA <contact@evkha.fr>"
    assert chez_brevo["sender"] == {"name": "EVKHA", "email": "contact@evkha.fr"}
