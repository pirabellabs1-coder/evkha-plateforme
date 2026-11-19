"""« A répondu », « Converti », « Exclu » ARRÊTENT les relances (audit du 19/11/2026).

`dashboard/prospection.py::prospect_statut` changeait le statut sans toucher aux
messages ni tracer d'événement : les relances déjà rédigées partaient vers
quelqu'un qui avait répondu, et le taux de réponse valait toujours 0 — les
métriques comptent `TypeEvenement.REPONDU`, que rien n'écrivait.

Tout passe désormais par `services.classer_prospect`, et `_raison_de_refus`
refuse l'envoi à un prospect répondu ou converti.
"""
from __future__ import annotations

import json
from datetime import timedelta
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

from integrations.brevo import EmailSendResult

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


class _ClientEspion:
    def __init__(self) -> None:
        self.envois = 0

    def send_delivery_email(self, **_: Any) -> EmailSendResult:
        self.envois += 1
        return EmailSendResult(provider_message_id=f"envoi-{self.envois}")


def _classer(client_admin: Any, prospect: Prospect, statut: str) -> Any:
    return client_admin.post(
        f"{BASE}/prospects/{prospect.id}/statut/",
        data=json.dumps({"statut": statut}),
        content_type="application/json",
    )


def _sequence_en_cours() -> tuple[Prospect, Message, Message, Message]:
    """Premier mail PARTI, relance 1 validée, relance 2 en brouillon."""
    campagne = Campagne.objects.create(nom="Classement")
    prospect = Prospect.objects.create(
        campagne=campagne, raison_sociale="Alpha", email="contact@alpha.fr"
    )
    premier = Message.objects.create(
        prospect=prospect, campagne=campagne, etape=0, objet="Premier", corps="x",
        statut=StatutMessage.VALIDE, valide_par="Evangéline",
    )
    services.envoyer_message(premier, client=_ClientEspion())
    # Le délai de la relance est écoulé : rien d'autre que le classement ne la retient.
    assert premier.envoye_le is not None
    Message.objects.filter(pk=premier.pk).update(envoye_le=premier.envoye_le - timedelta(days=10))
    relance_1 = Message.objects.create(
        prospect=prospect, campagne=campagne, etape=1, objet="Relance 1", corps="y",
        statut=StatutMessage.VALIDE, valide_par="Evangéline",
    )
    relance_2 = Message.objects.create(
        prospect=prospect, campagne=campagne, etape=2, objet="Relance 2", corps="z",
    )
    return prospect, premier, relance_1, relance_2


@pytest.mark.parametrize("statut", ["a_repondu", "converti", "exclu"])
def test_classer_un_prospect_annule_ses_relances(client_admin: Any, statut: str) -> None:
    """Sur le code d'avant : le statut changeait, les deux relances restaient en file."""
    prospect, premier, relance_1, relance_2 = _sequence_en_cours()

    reponse = _classer(client_admin, prospect, statut)

    assert reponse.status_code == 200 and json.loads(reponse.content)["statut"] == statut
    for message in (premier, relance_1, relance_2):
        message.refresh_from_db()
    assert relance_1.statut == StatutMessage.ANNULE
    assert relance_2.statut == StatutMessage.ANNULE
    # Ce qui est parti reste parti : on n'efface pas l'histoire.
    assert premier.statut == StatutMessage.ENVOYE


@pytest.mark.parametrize("statut", ["a_repondu", "converti"])
def test_l_envoi_est_refuse_a_un_prospect_qui_a_repondu_ou_converti(statut: str) -> None:
    """L'invariant vit dans `_raison_de_refus` : même un message validé APRÈS
    le classement ne part pas. Sur le code d'avant, la relance partait."""
    prospect, _, relance_1, _ = _sequence_en_cours()
    Prospect.objects.filter(pk=prospect.pk).update(statut=statut)  # sans passer par le service
    espion = _ClientEspion()

    with pytest.raises(services.EnvoiRefuseError, match="répondu|converti"):
        services.envoyer_message(relance_1, client=espion)

    assert espion.envois == 0
    relance_1.refresh_from_db()
    assert relance_1.statut == StatutMessage.VALIDE


def test_a_repondu_trace_la_reponse_et_le_taux_n_est_plus_nul(client_admin: Any) -> None:
    """Sur le code d'avant : `reponses` et `taux_reponse` valaient 0, toujours."""
    prospect, premier, _, _ = _sequence_en_cours()

    _classer(client_admin, prospect, "a_repondu")

    reponses = Evenement.objects.filter(type=TypeEvenement.REPONDU)
    assert [e.message_id for e in reponses] == [premier.id]
    metriques = json.loads(client_admin.get(f"{BASE}/metriques/").content)
    assert metriques["reponses"] == 1
    assert metriques["taux_reponse"] == 100.0  # 1 réponse pour 1 message envoyé


def test_la_reponse_ne_se_compte_qu_une_fois(client_admin: Any) -> None:
    """Contre-épreuve : deux clics sur « A répondu » ne font pas deux réponses."""
    prospect, _, _, _ = _sequence_en_cours()

    _classer(client_admin, prospect, "a_repondu")
    _classer(client_admin, prospect, "a_repondu")

    assert Evenement.objects.filter(type=TypeEvenement.REPONDU).count() == 1


@pytest.mark.parametrize("statut", ["converti", "exclu"])
def test_converti_et_exclu_ne_tracent_pas_de_reponse(client_admin: Any, statut: str) -> None:
    """Contre-épreuve : seul « A répondu » nourrit le taux de réponse."""
    prospect, _, _, _ = _sequence_en_cours()

    _classer(client_admin, prospect, statut)

    assert Evenement.objects.filter(type=TypeEvenement.REPONDU).count() == 0


def test_a_repondu_sans_message_envoye_ne_plante_pas(client_admin: Any) -> None:
    """Une réponse venue d'ailleurs (téléphone, salon) : rien à quoi la rattacher."""
    prospect = Prospect.objects.create(raison_sociale="Jamais écrit", email="x@y.fr")
    brouillon = Message.objects.create(prospect=prospect, etape=0, objet="O", corps="x")

    reponse = _classer(client_admin, prospect, "a_repondu")

    assert reponse.status_code == 200
    assert Evenement.objects.count() == 0
    brouillon.refresh_from_db()
    assert brouillon.statut == StatutMessage.ANNULE


@pytest.mark.parametrize("statut", ["nouveau", "qualifie", "contacte", "en_relance"])
def test_un_statut_d_avancement_n_annule_rien(client_admin: Any, statut: str) -> None:
    """Contre-épreuve : avancer dans le pipeline n'arrête pas la séquence."""
    prospect, _, relance_1, relance_2 = _sequence_en_cours()

    reponse = _classer(client_admin, prospect, statut)

    assert reponse.status_code == 200
    relance_1.refresh_from_db()
    relance_2.refresh_from_db()
    assert relance_1.statut == StatutMessage.VALIDE
    assert relance_2.statut == StatutMessage.BROUILLON
    # Et la relance validée, à son tour, part toujours.
    espion = _ClientEspion()
    services.envoyer_message(relance_1, client=espion)
    assert espion.envois == 1


def test_un_desinscrit_ne_se_reclasse_pas(client_admin: Any) -> None:
    """L'opposition est définitive : « Converti » ne la défait pas."""
    prospect, _, _, _ = _sequence_en_cours()
    services.desinscrire(prospect)

    reponse = _classer(client_admin, prospect, "contacte")

    assert reponse.status_code == 409
    prospect.refresh_from_db()
    assert prospect.statut == StatutProspect.DESINSCRIT
    assert prospect.consentement_retire is True


def test_desinscrire_par_le_statut_passe_par_le_service(client_admin: Any) -> None:
    """Contre-épreuve : le statut « désinscrit » garde son chemin (opposition par adresse)."""
    prospect, _, relance_1, _ = _sequence_en_cours()

    reponse = _classer(client_admin, prospect, "desinscrit")

    assert reponse.status_code == 200
    prospect.refresh_from_db()
    relance_1.refresh_from_db()
    assert prospect.consentement_retire is True
    assert relance_1.statut == StatutMessage.ANNULE
