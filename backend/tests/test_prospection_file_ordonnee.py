"""La file de validation suit l'ordre de la séquence (retour du 04/11/2026).

« On ne sait pas quel est le premier message, ni le second, ni le troisième » :
l'agent rédige le premier e-mail ET ses relances d'un coup, et la file les
montrait pêle-mêle. Une relance ne doit apparaître — ni partir — qu'après ce
qui la précède ; et une étape entière doit pouvoir se valider d'un clic.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from prospection import services
from prospection.file import DELAI_RELANCE_PAR_DEFAUT_JOURS, place
from prospection.models import (
    Campagne,
    Message,
    Prospect,
    Sequence,
    StatutMessage,
)

from integrations.brevo import EmailSendResult

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


class _ClientEspion:
    def __init__(self) -> None:
        self.envois = 0

    def send_delivery_email(self, **_: Any) -> EmailSendResult:
        self.envois += 1
        return EmailSendResult(provider_message_id=f"brevo-{self.envois}")


def _sequence_redigee(nom: str, email: str) -> list[Message]:
    """Ce que produit l'agent : le premier mail et deux relances, créés d'un coup."""
    campagne = Campagne.objects.create(nom=f"Campagne {nom}")
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale=nom, email=email)
    etapes = [
        Sequence.objects.create(campagne=campagne, ordre=i, delai_jours=0 if i == 0 else 3)
        for i in range(3)
    ]
    # Créés dans le désordre : la date de création ne doit pas décider de l'ordre.
    return [
        Message.objects.create(
            prospect=prospect, campagne=campagne, sequence=etapes[i],
            objet=f"{nom} étape {i}", corps="<p>x</p>",
        )
        for i in (2, 0, 1)
    ]


def _liste(client_admin: Any, **params: str) -> list[dict[str, Any]]:
    reponse = client_admin.get(f"{BASE}/messages/", params)
    assert reponse.status_code == 200
    resultat: list[dict[str, Any]] = json.loads(reponse.content)
    return resultat


def test_chaque_message_dit_son_etape_et_son_prospect(client_admin: Any) -> None:
    _sequence_redigee("Alpha", "a@alpha.fr")
    messages = _liste(client_admin, statut="brouillon")

    assert [m["etape"] for m in messages] == [0, 1, 2]
    assert [m["etape_libelle"] for m in messages] == [
        "Premier message", "Relance 1", "Relance 2",
    ]
    assert {m["prospect_nom"] for m in messages} == {"Alpha"}


def test_au_depart_seuls_les_premiers_mails_sont_a_valider(client_admin: Any) -> None:
    _sequence_redigee("Alpha", "a@alpha.fr")
    _sequence_redigee("Beta", "b@beta.fr")

    prets = _liste(client_admin, statut="brouillon", pret="1")

    assert [(m["prospect_nom"], m["etape"]) for m in prets] == [("Alpha", 0), ("Beta", 0)]


def test_une_relance_vient_a_son_tour_apres_l_envoi_et_le_delai(client_admin: Any) -> None:
    messages = _sequence_redigee("Alpha", "a@alpha.fr")
    premier = next(m for m in messages if m.sequence and m.sequence.ordre == 0)
    services.valider_message(premier, par="Evangéline")
    services.envoyer_message(premier, client=_ClientEspion())

    # Envoyé, mais le délai de 3 jours court encore.
    assert _liste(client_admin, statut="brouillon", pret="1") == []

    premier.refresh_from_db()
    assert premier.envoye_le is not None
    Message.objects.filter(pk=premier.pk).update(envoye_le=premier.envoye_le - timedelta(days=4))
    prets = _liste(client_admin, statut="brouillon", pret="1")

    assert [m["etape"] for m in prets] == [1]


def test_une_relance_ne_part_pas_avant_le_premier_mail() -> None:
    """L'invariant vit dans `envoyer_message`, pas dans l'écran."""
    messages = _sequence_redigee("Alpha", "a@alpha.fr")
    relance = next(m for m in messages if m.sequence and m.sequence.ordre == 1)
    services.valider_message(relance, par="Evangéline")
    espion = _ClientEspion()

    with pytest.raises(services.EnvoiRefuseError, match="étape précédente"):
        services.envoyer_message(relance, client=espion)
    assert espion.envois == 0


def _poster(client_admin: Any, url: str, corps: dict[str, Any]) -> Any:
    return client_admin.post(url, data=json.dumps(corps), content_type="application/json")


def test_une_etape_se_valide_d_un_clic(client_admin: Any) -> None:
    _sequence_redigee("Alpha", "a@alpha.fr")
    _sequence_redigee("Beta", "b@beta.fr")
    affiches = [m["id"] for m in _liste(client_admin, statut="brouillon", pret="1")]

    reponse = _poster(
        client_admin, f"{BASE}/messages/valider-lot/", {"ids": affiches, "par": "Evangéline"}
    )

    assert json.loads(reponse.content)["valides"] == 2
    valides = Message.objects.filter(statut=StatutMessage.VALIDE)
    assert {m.sequence.ordre for m in valides if m.sequence} == {0}
    assert Message.objects.filter(statut=StatutMessage.BROUILLON).count() == 4


def test_le_lot_ne_valide_pas_une_relance_qui_n_est_pas_a_son_tour(client_admin: Any) -> None:
    """Même si on lui passe une relance, le lot ne valide que ce qui est prêt."""
    tous = [str(m.id) for m in _sequence_redigee("Alpha", "a@alpha.fr")]

    reponse = _poster(client_admin, f"{BASE}/messages/valider-lot/", {"ids": tous, "par": "E."})

    assert json.loads(reponse.content)["valides"] == 1
    assert Message.objects.filter(statut=StatutMessage.VALIDE).count() == 1


def test_l_envoi_par_lot_exige_une_confirmation(client_admin: Any) -> None:
    reponse = client_admin.post(
        f"{BASE}/messages/envoyer-lot/", data=json.dumps({}), content_type="application/json",
    )
    assert reponse.status_code == 400
    assert json.loads(reponse.content)["confirmation_requise"] is True


def test_l_envoi_par_lot_passe_par_le_seul_chemin_d_envoi() -> None:
    _sequence_redigee("Alpha", "a@alpha.fr")
    _sequence_redigee("Beta", "b@beta.fr")
    services.valider_par_lot(list(Message.objects.all()), par="Evangéline")
    espion = _ClientEspion()

    envoyes, refus = services.envoyer_par_lot(
        list(Message.objects.filter(statut=StatutMessage.VALIDE)), client=espion
    )

    assert (envoyes, refus) == (2, [])
    assert espion.envois == 2


def test_le_compteur_a_valider_ne_compte_que_les_brouillons_a_leur_tour(
    client_admin: Any,
) -> None:
    """Le compteur comptait aussi les premiers mails DÉJÀ validés : la place se
    lit sur toute la séquence, le compte ne doit porter que sur les brouillons."""
    _sequence_redigee("Alpha", "a@alpha.fr")
    services.valider_par_lot(list(Message.objects.all()), par="Evangéline")

    apercu = json.loads(client_admin.get(f"{BASE}/apercu/").content)

    assert apercu["a_valider"] == 0
    assert apercu["relances_en_attente"] == 2


def test_un_lot_porte_exactement_les_messages_affiches(client_admin: Any) -> None:
    """Un brouillon arrivé APRÈS l'affichage n'est pas validé sans avoir été lu."""
    _sequence_redigee("Alpha", "a@alpha.fr")
    affiches = [m["id"] for m in _liste(client_admin, statut="brouillon", pret="1")]
    _sequence_redigee("Arrive-apres", "z@tard.fr")

    reponse = _poster(
        client_admin, f"{BASE}/messages/valider-lot/", {"ids": affiches, "par": "Evangéline"}
    )

    assert json.loads(reponse.content)["valides"] == 1
    assert not Message.objects.filter(
        prospect__raison_sociale="Arrive-apres", statut=StatutMessage.VALIDE
    ).exists()


def test_un_lot_sans_ids_est_refuse(client_admin: Any) -> None:
    reponse = _poster(client_admin, f"{BASE}/messages/valider-lot/", {"par": "E."})
    assert reponse.status_code == 400


def test_un_desinscrit_pendant_le_lot_ne_recoit_rien() -> None:
    """Les objets du lot datent de son début : le service relit avant d'envoyer."""
    messages = _sequence_redigee("Alpha", "a@alpha.fr")
    premier = next(m for m in messages if m.sequence and m.sequence.ordre == 0)
    services.valider_message(premier, par="Evangéline")
    lot = list(Message.objects.select_related("prospect", "sequence").filter(pk=premier.pk))
    services.desinscrire(premier.prospect)
    espion = _ClientEspion()

    envoyes, refus = services.envoyer_par_lot(lot, client=espion)

    assert (envoyes, espion.envois) == (0, 0)
    assert refus


def test_un_lot_n_envoie_pas_une_relance_avec_son_premier_mail() -> None:
    """Délai nul, relance validée, premier mail en tête du lot : un seul envoi."""
    campagne = Campagne.objects.create(nom="Sans délai")
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="P", email="p@p.fr")
    etapes = [
        Sequence.objects.create(campagne=campagne, ordre=i, delai_jours=0) for i in range(2)
    ]
    lot = [
        Message.objects.create(
            prospect=prospect, campagne=campagne, sequence=etapes[i], objet=f"m{i}",
            corps="x", statut=StatutMessage.VALIDE, valide_par="E.",
        )
        for i in range(2)
    ]
    espion = _ClientEspion()

    envoyes, _ = services.envoyer_par_lot(lot, client=espion)

    assert (envoyes, espion.envois) == (1, 1)


def test_sans_sequence_une_nouvelle_redaction_repart_au_premier_message() -> None:
    """Le chemin de l'agent sans campagne : brouillons annulés, puis nouvelle
    rédaction. Le nouveau premier mail devenait « Relance 3 », jamais prêt."""
    prospect = Prospect.objects.create(raison_sociale="Seul", email="s@s.fr")
    for i in range(3):
        Message.objects.create(
            prospect=prospect, etape=i, objet=f"ancien {i}", corps="x",
            statut=StatutMessage.ANNULE,
        )
    nouveaux = [
        Message.objects.create(prospect=prospect, etape=i, objet=f"neuf {i}", corps="x")
        for i in range(3)
    ]

    assert place(nouveaux[0]).etape == 0
    assert place(nouveaux[0]).pret is True
    assert place(nouveaux[1]).pret is False


def test_un_message_herite_annule_ne_decale_pas_les_suivants() -> None:
    """Contre-épreuve du repli par rang (messages sans étape ni séquence)."""
    prospect = Prospect.objects.create(raison_sociale="Hérité", email="h@h.fr")
    Message.objects.create(
        prospect=prospect, objet="annulé", corps="x", statut=StatutMessage.ANNULE
    )
    vivant = Message.objects.create(prospect=prospect, objet="vivant", corps="x")

    assert place(vivant).etape == 0


def test_un_second_premier_mail_n_est_pas_pret_si_le_premier_est_parti() -> None:
    prospect = Prospect.objects.create(raison_sociale="Deux", email="d@d.fr")
    parti = Message.objects.create(
        prospect=prospect, etape=0, objet="1", corps="x",
        statut=StatutMessage.VALIDE, valide_par="E.",
    )
    services.envoyer_message(parti, client=_ClientEspion())
    second = Message.objects.create(prospect=prospect, etape=0, objet="2", corps="x")

    assert place(second).pret is False


def test_une_relance_sans_sequence_attend_le_delai_par_defaut() -> None:
    prospect = Prospect.objects.create(raison_sociale="Défaut", email="f@f.fr")
    premier = Message.objects.create(
        prospect=prospect, etape=0, objet="1", corps="x",
        statut=StatutMessage.VALIDE, valide_par="E.",
    )
    services.envoyer_message(premier, client=_ClientEspion())
    relance = Message.objects.create(prospect=prospect, etape=1, objet="2", corps="x")

    assert DELAI_RELANCE_PAR_DEFAUT_JOURS > 0
    assert place(relance).pret is False


def test_une_relance_dont_le_premier_mail_est_annule_est_rompue(client_admin: Any) -> None:
    messages = _sequence_redigee("Alpha", "a@alpha.fr")
    premier = next(m for m in messages if m.sequence and m.sequence.ordre == 0)
    services.annuler_message(premier)

    apercu = json.loads(client_admin.get(f"{BASE}/apercu/").content)

    # Relance 1 rompue (étape 0 annulée) ; relance 2 attend la relance 1, vivante.
    assert apercu["relances_en_attente"] == 1


def test_les_premiers_mails_anciens_ne_sont_pas_affames_par_le_plafond(
    client_admin: Any,
) -> None:
    """Plafond appliqué avant les filtres : les 500 brouillons les plus récents
    étaient des relances, et les premiers mails anciens n'apparaissaient plus."""
    ancien = Prospect.objects.create(raison_sociale="Ancien", email="a@ancien.fr")
    premier = Message.objects.create(prospect=ancien, etape=0, objet="ancien", corps="x")
    Message.objects.filter(pk=premier.pk).update(created_at=datetime(2026, 1, 1, tzinfo=UTC))
    recent = Prospect.objects.create(raison_sociale="Récent", email="r@recent.fr")
    Message.objects.bulk_create([
        Message(prospect=recent, etape=1 + i, objet=f"relance {i}", corps="x")
        for i in range(510)
    ])

    prets = _liste(client_admin, statut="brouillon", pret="1")

    assert "ancien" in [m["objet"] for m in prets]
