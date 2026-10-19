"""La prospection n'envoie RIEN sans une validation humaine — l'invariant du sous-système.

Demande de l'utilisateur (18/10/2026) : « les messages ne partent pas » sans
qu'un humain les ait relus et validés. Et règle de sécurité du système : un
envoi d'e-mail est un acte, jamais un effet de bord. Ce fichier verrouille le
seul chemin d'envoi (`services.envoyer_message`).
"""
from __future__ import annotations

from typing import Any

import pytest
from prospection import services
from prospection.models import (
    Campagne,
    Evenement,
    Message,
    Prospect,
    Sequence,
    StatutMessage,
    StatutProspect,
    TypeEvenement,
)

from integrations.brevo import EmailSendResult

pytestmark = pytest.mark.django_db


class _ClientEspion:
    """Un client d'e-mail qui COMPTE les envois — pour prouver qu'on n'envoie pas."""

    def __init__(self) -> None:
        self.envois = 0

    def send_delivery_email(self, **_: Any) -> EmailSendResult:
        self.envois += 1
        return EmailSendResult(provider_message_id="brevo-test-1")


def _prospect(email: str = "contact@cible.fr", **extra: Any) -> Prospect:
    campagne = Campagne.objects.create(nom="Campagne test")
    return Prospect.objects.create(
        campagne=campagne, raison_sociale="Cible SARL", email=email, **extra
    )


def _brouillon(prospect: Prospect | None = None) -> Message:
    prospect = prospect or _prospect()
    return Message.objects.create(
        prospect=prospect, campagne=prospect.campagne, objet="Bonjour", corps="<p>Test</p>",
    )


def test_un_brouillon_ne_part_jamais() -> None:
    """Le cœur de l'invariant : sans validation, aucun envoi."""
    message = _brouillon()
    client = _ClientEspion()

    with pytest.raises(services.EnvoiRefuseError, match="validé par un humain"):
        services.envoyer_message(message, client=client)

    assert client.envois == 0, "le client n'a pas été appelé"
    message.refresh_from_db()
    assert message.statut == StatutMessage.BROUILLON


def test_un_message_valide_par_un_humain_part() -> None:
    message = _brouillon()
    services.valider_message(message, par="Evangéline")
    client = _ClientEspion()

    services.envoyer_message(message, client=client)

    assert client.envois == 1
    message.refresh_from_db()
    assert message.statut == StatutMessage.ENVOYE
    assert message.provider_message_id == "brevo-test-1"
    assert message.envoye_le is not None
    assert Evenement.objects.filter(message=message, type=TypeEvenement.ENVOYE).exists()
    message.prospect.refresh_from_db()
    assert message.prospect.statut == StatutProspect.CONTACTE


def test_une_validation_sans_auteur_est_refusee() -> None:
    """Une validation est un acte NOMINATIF : sans auteur, elle n'autorise rien."""
    message = _brouillon()
    with pytest.raises(services.EnvoiRefuseError, match="nominative"):
        services.valider_message(message, par="   ")
    message.refresh_from_db()
    assert message.statut == StatutMessage.BROUILLON


def test_un_prospect_desinscrit_ne_recoit_rien_meme_valide() -> None:
    """La désinscription prime sur une validation déjà donnée."""
    prospect = _prospect()
    message = _brouillon(prospect)
    services.valider_message(message, par="Evangéline")

    services.desinscrire(prospect)

    client = _ClientEspion()
    with pytest.raises(services.EnvoiRefuseError, match="désinscrit"):
        services.envoyer_message(message, client=client)
    assert client.envois == 0
    message.refresh_from_db()
    assert message.statut == StatutMessage.ANNULE, "le message en file a été annulé"


def test_un_prospect_sans_email_ne_recoit_rien() -> None:
    message = _brouillon(_prospect(email=""))
    services.valider_message(message, par="Evangéline")
    client = _ClientEspion()
    with pytest.raises(services.EnvoiRefuseError, match="e-mail"):
        services.envoyer_message(message, client=client)
    assert client.envois == 0


def test_un_message_deja_envoye_ne_se_renvoie_pas() -> None:
    """Contre-épreuve : on ne revalide ni ne renvoie un message parti."""
    message = _brouillon()
    services.valider_message(message, par="Evangéline")
    services.envoyer_message(message, client=_ClientEspion())

    with pytest.raises(services.EnvoiRefuseError):
        services.valider_message(message, par="Evangéline")
    client = _ClientEspion()
    with pytest.raises(services.EnvoiRefuseError):
        services.envoyer_message(message, client=client)
    assert client.envois == 0


def test_un_echec_du_fournisseur_est_trace_pas_masque() -> None:
    message = _brouillon()
    services.valider_message(message, par="Evangéline")

    class _ClientQuiTombe:
        def send_delivery_email(self, **_: Any) -> EmailSendResult:
            raise RuntimeError("Brevo indisponible")

    with pytest.raises(services.EnvoiRefuseError):
        services.envoyer_message(message, client=_ClientQuiTombe())
    message.refresh_from_db()
    assert message.statut == StatutMessage.ECHOUE
    assert "Brevo indisponible" in message.error_message


def test_une_relance_fait_passer_le_prospect_en_relance() -> None:
    campagne = Campagne.objects.create(nom="Relances")
    prospect = Prospect.objects.create(
        campagne=campagne, raison_sociale="Cible SARL", email="relance@cible.fr"
    )
    premier = Sequence.objects.create(campagne=campagne, ordre=0)
    relance = Sequence.objects.create(campagne=campagne, ordre=1, delai_jours=4)

    m0 = Message.objects.create(
        prospect=prospect, campagne=campagne, sequence=premier, objet="1", corps="x"
    )
    services.valider_message(m0, par="Evangéline")
    services.envoyer_message(m0, client=_ClientEspion())
    prospect.refresh_from_db()
    assert prospect.statut == StatutProspect.CONTACTE

    m1 = Message.objects.create(
        prospect=prospect, campagne=campagne, sequence=relance, objet="2", corps="y"
    )
    services.valider_message(m1, par="Evangéline")
    services.envoyer_message(m1, client=_ClientEspion())
    prospect.refresh_from_db()
    assert prospect.statut == StatutProspect.EN_RELANCE
