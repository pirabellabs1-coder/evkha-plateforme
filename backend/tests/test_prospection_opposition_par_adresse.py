"""L'opposition suit l'ADRESSE, pas la fiche (audit du 19/11/2026).

Un cabinet désinscrit dans la campagne A était recréé par la campagne B avec
`consentement_retire=False`, et ses messages partaient. L'opposition est
désormais inscrite à une table par adresse normalisée, qui survit à la
suppression de la fiche ; `_raison_de_refus` la lit quelle que soit la fiche.

Chaque test échoue sur le code d'avant ; les contre-épreuves vérifient que le
correctif ne bloque pas ce qui est correct (une autre adresse du même domaine,
les fiches sans adresse).
"""
from __future__ import annotations

import importlib
import json
from typing import Any

import pytest
from django.apps import apps as applications
from prospection import agents, services
from prospection.models import (
    Campagne,
    Message,
    Prospect,
    StatutMessage,
    StatutProspect,
)

from integrations.brevo import EmailSendResult

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


class _ClientEspion:
    def __init__(self) -> None:
        self.destinataires: list[str] = []

    def send_delivery_email(self, *, recipient_email: str, **_: Any) -> EmailSendResult:
        self.destinataires.append(recipient_email)
        return EmailSendResult(provider_message_id=f"brevo-{len(self.destinataires)}")


def _fiche(campagne_nom: str, email: str, raison: str = "Cabinet Dupont") -> Prospect:
    campagne = Campagne.objects.create(nom=campagne_nom)
    return Prospect.objects.create(campagne=campagne, raison_sociale=raison, email=email)


def _message_valide(prospect: Prospect) -> Message:
    return Message.objects.create(
        prospect=prospect, campagne=prospect.campagne, objet="Bonjour", corps="<p>x</p>",
        statut=StatutMessage.VALIDE, valide_par="Evangéline",
    )


def test_la_recherche_d_une_autre_campagne_recree_la_fiche_deja_desinscrite() -> None:
    """Le défaut d'origine : la campagne B recréait le cabinet, contactable."""
    services.desinscrire(_fiche("Campagne A", "contact@cabinet-dupont.fr"))
    campagne_b = Campagne.objects.create(nom="Campagne B")

    crees = agents._creer_les_prospects(
        campagne_b,
        # La même boîte aux lettres, écrite autrement : casse et espace.
        [{"raison_sociale": "Cabinet Dupont", "email": " Contact@Cabinet-Dupont.FR"}],
        10,
    )

    assert len(crees) == 1
    recreee = Prospect.objects.get(campagne=campagne_b)
    assert recreee.consentement_retire is True
    assert recreee.statut == StatutProspect.DESINSCRIT
    assert recreee.contactable is False


def test_la_saisie_manuelle_d_une_adresse_opposee_nait_desinscrite(client_admin: Any) -> None:
    services.desinscrire(_fiche("Campagne A", "contact@cabinet-dupont.fr"))
    campagne_b = Campagne.objects.create(nom="Campagne B")

    reponse = client_admin.post(
        f"{BASE}/prospects/",
        data=json.dumps({
            "campagne_id": str(campagne_b.id), "raison_sociale": "Cabinet Dupont",
            "email": "contact@cabinet-dupont.fr",
        }),
        content_type="application/json",
    )

    assert reponse.status_code == 201
    fiche = json.loads(reponse.content)
    assert fiche["contactable"] is False
    assert fiche["statut"] == StatutProspect.DESINSCRIT
    assert "désinscrit" in fiche["motif_non_contact"]


def test_la_desinscription_se_propage_aux_fiches_de_meme_adresse() -> None:
    """La fiche B existe DÉJÀ, message validé : la désinscription de A l'arrête."""
    fiche_a = _fiche("Campagne A", "contact@cabinet-dupont.fr")
    fiche_b = _fiche("Campagne B", "Contact@Cabinet-Dupont.fr")
    message_b = _message_valide(fiche_b)

    services.desinscrire(fiche_a)

    fiche_b.refresh_from_db()
    message_b.refresh_from_db()
    assert fiche_b.consentement_retire is True
    assert fiche_b.statut == StatutProspect.DESINSCRIT
    assert message_b.statut == StatutMessage.ANNULE


def test_l_envoi_est_refuse_a_une_adresse_opposee_quelle_que_soit_la_fiche() -> None:
    """L'invariant vit dans `_raison_de_refus`, pas dans le marquage des fiches.

    Une fiche écrite après coup SANS passer par les chemins qui marquent (ici
    l'ORM, demain un import) porte une adresse opposée : l'envoi doit refuser.
    Sur le code d'avant, le message partait.
    """
    services.desinscrire(_fiche("Campagne A", "contact@cabinet-dupont.fr"))
    fiche_b = _fiche("Campagne B", "contact@cabinet-dupont.fr")
    assert fiche_b.consentement_retire is False  # la fiche, elle, ne sait rien
    message = _message_valide(fiche_b)
    espion = _ClientEspion()

    with pytest.raises(services.EnvoiRefuseError, match="désinscrit"):
        services.envoyer_message(message, client=espion)

    assert espion.destinataires == []
    message.refresh_from_db()
    assert message.statut == StatutMessage.VALIDE


def test_l_opposition_survit_a_la_suppression_de_la_fiche() -> None:
    fiche_a = _fiche("Campagne A", "contact@cabinet-dupont.fr")
    services.desinscrire(fiche_a)
    assert fiche_a.campagne is not None
    fiche_a.campagne.delete()  # emporte la fiche (CASCADE)
    assert Prospect.objects.count() == 0

    campagne_b = Campagne.objects.create(nom="Campagne B")
    agents._creer_les_prospects(
        campagne_b, [{"raison_sociale": "Cabinet Dupont", "email": "contact@cabinet-dupont.fr"}], 10
    )

    assert Prospect.objects.get(campagne=campagne_b).consentement_retire is True


def test_le_lot_de_fiches_dit_lesquelles_sont_opposees(client_admin: Any) -> None:
    """L'écran lit `contactable` sur la table, pour toute la liste d'une campagne."""
    services.desinscrire(_fiche("Campagne A", "contact@cabinet-dupont.fr"))
    campagne_b = Campagne.objects.create(nom="Campagne B")
    Prospect.objects.create(
        campagne=campagne_b, raison_sociale="Opposé", email="contact@cabinet-dupont.fr"
    )
    Prospect.objects.create(campagne=campagne_b, raison_sociale="Libre", email="libre@autre.fr")

    detail = json.loads(client_admin.get(f"{BASE}/campagnes/{campagne_b.id}/").content)

    par_nom = {p["raison_sociale"]: p for p in detail["prospects_liste"]}
    assert par_nom["Opposé"]["contactable"] is False
    assert par_nom["Opposé"]["adresse_interdite"] == "desinscription"
    assert par_nom["Libre"]["contactable"] is True
    assert par_nom["Libre"]["adresse_interdite"] is None


# ── Contre-épreuves : le correctif ne bloque pas ce qui est correct ───────────


def test_une_autre_adresse_du_meme_domaine_reste_contactable() -> None:
    """L'opposition porte sur UNE boîte aux lettres, pas sur l'organisation."""
    services.desinscrire(_fiche("Campagne A", "contact@cabinet-dupont.fr"))
    autre = _fiche("Campagne B", "direction@cabinet-dupont.fr")
    message = _message_valide(autre)
    espion = _ClientEspion()

    services.envoyer_message(message, client=espion)

    assert espion.destinataires == ["direction@cabinet-dupont.fr"]
    autre.refresh_from_db()
    assert autre.consentement_retire is False


def test_desinscrire_une_fiche_sans_adresse_ne_touche_pas_les_autres() -> None:
    """Une adresse vide n'est pas une clé : elle ne s'inscrit jamais à la table."""
    from prospection.models import AdresseInterdite

    sans_adresse = _fiche("Campagne A", "")
    autre_sans_adresse = _fiche("Campagne B", "", raison="Autre")

    services.desinscrire(sans_adresse)

    assert AdresseInterdite.objects.count() == 0
    autre_sans_adresse.refresh_from_db()
    assert autre_sans_adresse.consentement_retire is False
    assert autre_sans_adresse.statut == StatutProspect.NOUVEAU


def test_la_date_de_la_premiere_opposition_fait_foi() -> None:
    fiche = _fiche("Campagne A", "contact@cabinet-dupont.fr")
    services.desinscrire(fiche)
    premiere = fiche.desinscrit_le

    services.desinscrire(fiche)

    assert fiche.desinscrit_le == premiere


# ── Reprise des oppositions d'avant l'audit ──────────────────────────────────


def test_la_reprise_inscrit_les_oppositions_deja_recues() -> None:
    """Une désinscription d'AVANT la table doit valoir pour la campagne suivante.

    La fiche est écrite comme le code d'avant l'écrivait : désinscrite, sans
    ligne dans la table. Sans la migration de reprise, l'adresse resterait
    contactable depuis toute autre fiche.
    """
    from prospection.models import AdresseInterdite

    campagne = Campagne.objects.create(nom="Avant l'audit")
    Prospect.objects.create(
        campagne=campagne, raison_sociale="Ancien", email=" Ancien@Cabinet.fr",
        consentement_retire=True, statut=StatutProspect.DESINSCRIT,
    )
    Prospect.objects.create(campagne=campagne, raison_sociale="Jamais opposé", email="ok@ok.fr")
    assert AdresseInterdite.objects.count() == 0

    reprise = importlib.import_module("prospection.migrations.0007_reprise_des_oppositions")
    reprise.reprendre_les_oppositions(applications, None)
    reprise.reprendre_les_oppositions(applications, None)  # rejouable sans doublon

    assert list(AdresseInterdite.objects.values_list("adresse", flat=True)) == [
        "ancien@cabinet.fr"
    ]
    nouvelle = _fiche("Campagne suivante", "ancien@cabinet.fr")
    with pytest.raises(services.EnvoiRefuseError, match="désinscrit"):
        services.envoyer_message(_message_valide(nouvelle), client=_ClientEspion())


def test_la_reprise_inscrit_aussi_les_plaintes_deja_recues() -> None:
    """Relecture du 19/11/2026. Le webhook traçait les plaintes depuis le
    début, sans effet : la fiche restait contactable. Sans leur reprise, la
    relance validée d'une personne qui s'est plainte partirait encore."""
    from prospection.models import AdresseInterdite, Evenement, Message, TypeEvenement

    campagne = Campagne.objects.create(nom="Avant l'audit, plainte")
    plaignant = Prospect.objects.create(
        campagne=campagne, raison_sociale="Plaignant", email="Direction@Plaignant.fr",
    )
    message = Message.objects.create(
        prospect=plaignant, campagne=campagne, etape=0, objet="Premier", corps="<p>x</p>",
    )
    Evenement.objects.create(
        message=message, type=TypeEvenement.PLAINTE, horodatage=message.created_at,
    )
    tranquille = Prospect.objects.create(
        campagne=campagne, raison_sociale="Sans plainte", email="ok@tranquille.fr",
    )
    autre = Message.objects.create(
        prospect=tranquille, campagne=campagne, etape=0, objet="Premier", corps="<p>x</p>",
    )
    Evenement.objects.create(
        message=autre, type=TypeEvenement.OUVERT, horodatage=autre.created_at,
    )

    reprise = importlib.import_module("prospection.migrations.0007_reprise_des_oppositions")
    reprise.reprendre_les_oppositions(applications, None)
    reprise.reprendre_les_oppositions(applications, None)  # rejouable sans doublon

    assert list(AdresseInterdite.objects.values_list("adresse", "motif")) == [
        ("direction@plaignant.fr", "plainte")
    ]


def test_la_tache_quotidienne_ne_paie_rien_pour_une_adresse_deja_opposee() -> None:
    """La recherche retrouve le cabinet désinscrit ailleurs : la fiche naît
    désinscrite, et ni la note ni la rédaction ne sont payées pour elle."""
    from datetime import UTC, datetime

    from prospection import tasks
    from prospection.models import ReglageAutomatisation

    from integrations.claude import StructuredResult
    from integrations.search import SearchResponse

    services.desinscrire(_fiche("Campagne A", "contact@cabinet-dupont.fr"))
    campagne_b = Campagne.objects.create(nom="Campagne B", secteur="Conseil")
    reglage = ReglageAutomatisation.charger()
    reglage.active, reglage.campagne = True, campagne_b
    reglage.save()
    appels: list[str] = []

    class _Client:
        def complete_structured(self, *, outil_nom: str, **_: Any) -> StructuredResult:
            appels.append(outil_nom)
            charges: dict[str, dict[str, Any]] = {
                "extraire_prospects": {"prospects": [
                    {"raison_sociale": "Cabinet Dupont", "email": "contact@cabinet-dupont.fr"},
                ]},
                "qualifier_prospect": {"score": 90, "raison": "cible 4"},
                "rediger_messages": {"messages": [{"objet": "O", "corps": "<p>C</p>"}]},
            }
            return StructuredResult(payload=dict(charges.get(outil_nom, {})),
                                    input_tokens=1, output_tokens=1, model="claude-opus")

    class _Recherche:
        def search(self, *, query: str, max_results: int = 5, **_: Any) -> SearchResponse:
            return SearchResponse(query=query, results=())

    resume = tasks.executer_si_du(
        maintenant=datetime(2026, 11, 16, 9, 0, tzinfo=UTC), recherche=_Recherche(),
        client=_Client(),
    )

    assert appels == ["extraire_prospects"], appels
    assert resume["crees"] == 1 and resume["non_contactables"] == 1
    fiche_b = Prospect.objects.get(campagne=campagne_b)
    assert fiche_b.statut == StatutProspect.DESINSCRIT
    assert Message.objects.filter(prospect=fiche_b).count() == 0
