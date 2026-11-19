"""Rebond et plainte ne restent plus sans effet (audit du 19/11/2026).

`webhooks._tracer_sur_message` ne déclenchait d'action que pour la
désinscription. Une PLAINTE (signalement comme indésirable) était tracée, et
les relances continuaient ; un REBOND DÉFINITIF aussi, vers une boîte qui
n'existe pas. Et les simples RETARDS (`deferred`, `soft_bounce`,
`email.delivery_delayed`) étaient rangés en rebond : ils gonflaient le compteur.

Trois familles, trois traitements : la plainte vaut opposition ; le rebond
définitif invalide l'adresse ; le retard ne compte pas et ne bloque rien.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
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

from integrations.brevo import EmailSendResult

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


class _ClientEspion:
    def __init__(self) -> None:
        self.destinataires: list[str] = []

    def send_delivery_email(self, *, recipient_email: str, **_: Any) -> EmailSendResult:
        self.destinataires.append(recipient_email)
        return EmailSendResult(provider_message_id=f"envoi-{len(self.destinataires)}")


def _parti_avec_relance(
    email: str = "contact@alpha.fr", campagne_nom: str = "C", provider_id: str = "msg-1"
) -> tuple[Prospect, Message, Message]:
    """Un prospect dont le premier mail est RÉELLEMENT parti, et sa relance validée."""
    campagne = Campagne.objects.create(nom=campagne_nom)
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="Alpha", email=email)
    premier = Message.objects.create(
        prospect=prospect, campagne=campagne, etape=0, objet="Premier", corps="<p>x</p>",
        statut=StatutMessage.VALIDE, valide_par="Evangéline",
    )
    services.envoyer_message(premier, client=_ClientEspion())
    Message.objects.filter(pk=premier.pk).update(provider_message_id=provider_id)
    relance = Message.objects.create(
        prospect=prospect, campagne=campagne, etape=1, objet="Relance", corps="<p>y</p>",
        statut=StatutMessage.VALIDE, valide_par="Evangéline",
    )
    return prospect, premier, relance


def _rebonds_comptes(client_admin: Any) -> int:
    return int(json.loads(client_admin.get(f"{BASE}/metriques/").content)["rebonds"])


# ── La plainte vaut opposition ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "tracer",
    [
        lambda: enregistrer_evenement_brevo({"event": "spam", "message-id": "msg-1"}),
        lambda: enregistrer_evenement_brevo({"event": "complaint", "message-id": "msg-1"}),
        lambda: enregistrer_evenement_resend(
            {"type": "email.complained", "data": {"email_id": "msg-1"}}
        ),
    ],
    ids=["brevo-spam", "brevo-complaint", "resend-complained"],
)
def test_une_plainte_vaut_opposition(tracer: Any) -> None:
    """Sur le code d'avant : l'événement était tracé, la relance restait validée."""
    prospect, _, relance = _parti_avec_relance()

    evenement = tracer()

    assert evenement is not None and evenement.type == TypeEvenement.PLAINTE
    prospect.refresh_from_db()
    relance.refresh_from_db()
    assert prospect.consentement_retire is True
    assert prospect.statut == StatutProspect.DESINSCRIT
    assert relance.statut == StatutMessage.ANNULE


def test_une_plainte_suit_l_adresse_dans_une_autre_campagne() -> None:
    """Même traitement que la désinscription : l'opposition suit l'adresse."""
    _parti_avec_relance(email="contact@alpha.fr")
    ailleurs = Prospect.objects.create(
        campagne=Campagne.objects.create(nom="Autre campagne"),
        raison_sociale="Alpha", email="contact@alpha.fr",
    )
    message = Message.objects.create(
        prospect=ailleurs, campagne=ailleurs.campagne, objet="O", corps="x",
        statut=StatutMessage.VALIDE, valide_par="E.",
    )

    enregistrer_evenement_brevo({"event": "spam", "message-id": "msg-1"})

    espion = _ClientEspion()
    with pytest.raises(services.EnvoiRefuseError):
        services.envoyer_message(message, client=espion)
    assert espion.destinataires == []


# ── Le rebond définitif invalide l'adresse ───────────────────────────────────


@pytest.mark.parametrize(
    "tracer",
    [
        lambda: enregistrer_evenement_brevo({"event": "hard_bounce", "message-id": "msg-1"}),
        lambda: enregistrer_evenement_brevo({"event": "invalid_email", "message-id": "msg-1"}),
        lambda: enregistrer_evenement_resend(
            {"type": "email.bounced", "data": {"email_id": "msg-1"}}
        ),
        lambda: enregistrer_evenement_resend({
            "type": "email.bounced",
            "data": {"email_id": "msg-1", "bounce": {"type": "Permanent"}},
        }),
    ],
    ids=["brevo-hard", "brevo-invalid", "resend-bounced", "resend-permanent"],
)
def test_un_rebond_definitif_annule_la_file_et_refuse_l_envoi(tracer: Any) -> None:
    """Sur le code d'avant : la relance restait validée et partait à son tour."""
    prospect, _, relance = _parti_avec_relance()

    evenement = tracer()

    assert evenement is not None and evenement.type == TypeEvenement.REBOND
    relance.refresh_from_db()
    assert relance.statut == StatutMessage.ANNULE
    # Un message validé APRÈS le rebond ne part pas davantage, et dit pourquoi.
    nouveau = Message.objects.create(
        prospect=prospect, campagne=prospect.campagne, etape=0, objet="Encore", corps="x",
        statut=StatutMessage.VALIDE, valide_par="E.",
    )
    espion = _ClientEspion()
    with pytest.raises(services.EnvoiRefuseError, match="rebond"):
        services.envoyer_message(nouveau, client=espion)
    assert espion.destinataires == []
    # Personne ne s'est opposé : la fiche n'est PAS désinscrite.
    prospect.refresh_from_db()
    assert prospect.consentement_retire is False
    assert prospect.statut != StatutProspect.DESINSCRIT


def test_un_rebond_definitif_se_lit_sur_la_fiche(client_admin: Any) -> None:
    prospect, _, _ = _parti_avec_relance()
    enregistrer_evenement_brevo({"event": "hard_bounce", "message-id": "msg-1"})

    fiche = json.loads(client_admin.get(f"{BASE}/prospects/{prospect.id}/").content)

    assert fiche["contactable"] is False
    assert fiche["adresse_interdite"] == "rebond_definitif"
    assert "rebond" in fiche["motif_non_contact"]


def test_corriger_l_adresse_leve_le_rebond_et_l_ancien_rebond_ne_frappe_pas_la_nouvelle(
    client_admin: Any,
) -> None:
    """L'interdiction tient à l'adresse morte, pas à l'organisation.

    Et un rebond de l'ANCIENNE adresse arrivé après la correction frappe
    l'adresse où le message est parti (`Message.destinataire`), pas celle que
    la fiche porte désormais.
    """
    prospect, _, _ = _parti_avec_relance(email="faute@alpha.fr")

    reponse = client_admin.put(
        f"{BASE}/prospects/{prospect.id}/",
        data=json.dumps({"email": "contact@alpha.fr"}),
        content_type="application/json",
    )
    assert reponse.status_code == 200
    enregistrer_evenement_brevo({"event": "hard_bounce", "message-id": "msg-1"})

    prospect.refresh_from_db()
    assert services.interdictions(["faute@alpha.fr"]) == {"faute@alpha.fr": "rebond_definitif"}
    assert services.motif_de_non_contact(prospect) is None
    nouveau = Message.objects.create(
        prospect=prospect, campagne=prospect.campagne, etape=5, objet="Neuf", corps="x",
        statut=StatutMessage.BROUILLON,
    )
    assert nouveau.prospect.contactable is True


# ── Un retard n'est pas un rebond ────────────────────────────────────────────


@pytest.mark.parametrize(
    "tracer",
    [
        lambda: enregistrer_evenement_brevo({"event": "deferred", "message-id": "msg-1"}),
        lambda: enregistrer_evenement_brevo({"event": "soft_bounce", "message-id": "msg-1"}),
        lambda: enregistrer_evenement_resend(
            {"type": "email.delivery_delayed", "data": {"email_id": "msg-1"}}
        ),
        lambda: enregistrer_evenement_resend({
            "type": "email.bounced",
            "data": {"email_id": "msg-1", "bounce": {"type": "Transient"}},
        }),
    ],
    ids=["brevo-deferred", "brevo-soft", "resend-delayed", "resend-transient"],
)
def test_un_retard_ne_compte_pas_comme_rebond_et_ne_bloque_rien(
    tracer: Any, client_admin: Any
) -> None:
    """Sur le code d'avant : rangé en REBOND, le retard gonflait le compteur."""
    prospect, _, relance = _parti_avec_relance()

    evenement = tracer()

    assert _rebonds_comptes(client_admin) == 0
    # Il est TRACÉ (on ne jette pas la source), sous son propre type.
    assert evenement is not None and evenement.type == "retard"
    assert evenement.type == TypeEvenement.RETARD
    relance.refresh_from_db()
    prospect.refresh_from_db()
    assert relance.statut == StatutMessage.VALIDE
    assert prospect.contactable is True


def test_un_non_remis_de_cause_indeterminee_se_compte_sans_condamner_l_adresse(
    client_admin: Any,
) -> None:
    """Contre-épreuve : `blocked` peut venir de l'expéditeur. Compté, pas interdit —
    sinon une panne de compte invaliderait toutes les adresses du fichier."""
    prospect, _, relance = _parti_avec_relance()

    for libelle in ("blocked", "error"):
        evenement = enregistrer_evenement_brevo({"event": libelle, "message-id": "msg-1"})
        assert evenement is not None and evenement.type == TypeEvenement.REBOND
    indetermine = enregistrer_evenement_resend({
        "type": "email.bounced",
        "data": {"email_id": "msg-1", "bounce": {"type": "Undetermined"}},
    })
    assert indetermine is not None and indetermine.type == TypeEvenement.REBOND

    assert _rebonds_comptes(client_admin) == 1  # un seul MESSAGE non remis
    relance.refresh_from_db()
    prospect.refresh_from_db()
    assert relance.statut == StatutMessage.VALIDE
    assert prospect.contactable is True


def test_les_evenements_ordinaires_ne_declenchent_rien() -> None:
    """Contre-épreuve : ouvert, cliqué, délivré restent de simples traces."""
    prospect, _, relance = _parti_avec_relance()

    for libelle in ("delivered", "opened", "click"):
        assert enregistrer_evenement_brevo({"event": libelle, "message-id": "msg-1"}) is not None

    relance.refresh_from_db()
    prospect.refresh_from_db()
    assert relance.statut == StatutMessage.VALIDE
    assert prospect.consentement_retire is False
    assert Evenement.objects.filter(type=TypeEvenement.REBOND).count() == 0


# ── L'identifiant du fournisseur, sous ses deux écritures ───────────────────


@pytest.mark.parametrize(
    "enregistre", ["<msg-9@smtp-relay.brevo.com>", "msg-9@smtp-relay.brevo.com"]
)
def test_un_evenement_brevo_retrouve_son_message_avec_ou_sans_chevrons(enregistre: str) -> None:
    """Relecture du 19/11/2026. Brevo rend l'identifiant ENTRE CHEVRONS à
    l'envoi, et c'est ainsi qu'il est enregistré ; son webhook est lu sans.
    Cherché sous une seule forme, aucun événement Brevo ne retrouvait son
    message : la plainte rendait `None` et la relance partait."""
    prospect, _, relance = _parti_avec_relance(provider_id=enregistre)

    evenement = enregistrer_evenement_brevo(
        {"event": "spam", "message-id": "<msg-9@smtp-relay.brevo.com>"}
    )

    assert evenement is not None
    relance.refresh_from_db()
    assert relance.statut == StatutMessage.ANNULE


def test_un_identifiant_inconnu_ne_trace_toujours_rien() -> None:
    """Contre-épreuve : la recherche élargie ne rattache pas un événement au
    premier message venu."""
    _parti_avec_relance(provider_id="msg-1")

    assert enregistrer_evenement_brevo({"event": "spam", "message-id": "<autre>"}) is None
