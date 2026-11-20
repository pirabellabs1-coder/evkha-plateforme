"""Payer avec l'adresse de quelqu'un ne donne pas accès à son espace.

Audit du 19/11/2026, constat confirmé par trois lectures indépendantes puis à
la main. Les deux pages de retour de paiement ouvraient une session sur le
compte portant l'adresse de la session Stripe, au motif que « Stripe a prouvé
l'identité ». Stripe prouve qu'une carte a été encaissée. L'adresse, elle, est
saisie librement par le payeur — dans le formulaire public, ou sur la page de
paiement.

Il suffisait donc de payer l'étude la moins chère avec l'adresse d'une abonnée
pour recevoir un jeton de quatorze jours sur SON espace : ses clients, ses
documents, ses crédits, le droit d'inviter un second propriétaire. Et le même
identifiant de paiement, rejoué, rendait un jeton à chaque appel.

Ces tests échouent sur le code d'avant : les deux vues rendaient toujours un
`jeton`.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone
from paiement import achats, stripe_api

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from organisations import identifiants, services
from organisations.authentification import (
    FENETRE_APRES_ACHAT,
    creer_compte,
    ouvrir_la_session_d_un_achat,
)
from organisations.models import CompteClient, JetonAcces, MouvementCredit

pytestmark = pytest.mark.django_db

RETOUR = "/api/public/acheter/retour/"
ABONNEE = "claire@cabinet.example"
NOUVELLE = "porteuse@example.com"


def _offre() -> Offer:
    return Offer.objects.create(
        name="Étude de la concurrence",
        slug=f"etude-concurrence-{uuid.uuid4().hex[:8]}",
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
        prix_unitaire_cents=8_900,
        is_active=True,
    )


def _session(offre: Offer, email: str, identifiant: str = "") -> dict[str, Any]:
    return {
        "id": identifiant or f"cs_test_{uuid.uuid4().hex[:16]}",
        "status": "complete",
        "mode": "payment",
        "payment_status": "paid",
        "amount_total": offre.prix_unitaire_cents,
        "currency": "eur",
        "customer_details": {"email": email, "name": "Quelqu'un"},
        "metadata": {"achat": "livrable", "offre_slug": offre.slug},
    }


def _revenir(monkeypatch: pytest.MonkeyPatch, session: dict[str, Any]) -> Any:
    """Le navigateur revient de Stripe avec l'identifiant de cette session."""
    monkeypatch.setattr(stripe_api, "relire_la_session", lambda identifiant: session)
    return Client().post(
        RETOUR, data={"session": session["id"]}, content_type="application/json",
    )


def _abonnee_avec_mot_de_passe() -> CompteClient:
    contact = Customer.objects.create(email=ABONNEE)
    services.creer_organisation(raison_sociale="Cabinet Claire", contact=contact)
    return creer_compte(contact, mot_de_passe="un-mot-de-passe-solide-2026")


# ── Le défaut ───────────────────────────────────────────────────────────────


def test_payer_avec_l_adresse_d_une_abonnee_n_ouvre_pas_son_espace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compte = _abonnee_avec_mot_de_passe()

    reponse = _revenir(monkeypatch, _session(_offre(), ABONNEE))

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["jeton"] is None
    assert corps["connexion_requise"] is True
    assert not JetonAcces.objects.filter(compte=compte).exists()


def test_l_achat_est_quand_meme_livre_sur_le_compte_existant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuser la session n'est pas refuser l'achat : la carte a été encaissée."""
    _abonnee_avec_mot_de_passe()
    session = _session(_offre(), ABONNEE)

    _revenir(monkeypatch, session)

    assert MouvementCredit.objects.filter(reference=session["id"]).count() == 1


def test_une_invitee_jamais_connectee_n_est_pas_ouverte_non_plus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sans mot de passe et jamais connectée — mais ce compte n'est pas né de CE
    paiement : il donne accès à l'organisation qui l'a invitée."""
    proprietaire = Customer.objects.create(email="proprietaire@cabinet.example")
    organisation = services.creer_organisation(
        raison_sociale="Cabinet", contact=proprietaire,
    )
    invitee = Customer.objects.create(email="invitee@cabinet.example")
    services.inviter_membre(organisation, invitee)
    compte = identifiants.compte_sans_mot_de_passe(invitee)

    reponse = _revenir(monkeypatch, _session(_offre(), invitee.email))

    assert reponse.json()["jeton"] is None
    assert not JetonAcces.objects.filter(compte=compte).exists()


def test_rejouer_l_identifiant_de_paiement_ne_rend_pas_un_second_jeton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(_offre(), NOUVELLE)

    premier = _revenir(monkeypatch, session).json()
    second = _revenir(monkeypatch, session).json()

    assert premier["jeton"]
    assert second["jeton"] is None and second["connexion_requise"] is True
    assert JetonAcces.objects.count() == 1


# ── Les contre-épreuves : le parcours voulu marche toujours ─────────────────


def test_une_nouvelle_acheteuse_entre_sans_mot_de_passe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reponse = _revenir(monkeypatch, _session(_offre(), NOUVELLE))

    corps = reponse.json()
    assert corps["jeton"] and corps["connexion_requise"] is False
    compte = CompteClient.objects.get(customer__email=NOUVELLE)
    assert compte.jetons.count() == 1


def test_le_webhook_arrive_avant_le_navigateur_et_l_acheteuse_entre_quand_meme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stripe poste son événement et redirige le navigateur sans ordre garanti :
    le compte existe alors déjà au retour — créé par CE paiement."""
    session = _session(_offre(), NOUVELLE)
    achats.livrer_l_achat(session)

    reponse = _revenir(monkeypatch, session)

    assert reponse.json()["jeton"]


def test_un_compte_ne_d_un_AUTRE_paiement_n_est_pas_ouvert_par_celui_ci(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un premier achat jamais suivi de connexion, puis quelqu'un d'autre paie
    avec la même adresse : le second paiement n'ouvre pas le compte du premier."""
    offre = _offre()
    achats.livrer_l_achat(_session(offre, NOUVELLE))

    reponse = _revenir(monkeypatch, _session(offre, NOUVELLE))

    assert reponse.json()["jeton"] is None


def test_passe_une_heure_le_retour_n_ouvre_plus_rien() -> None:
    """La personne passe alors par le lien du courriel, qui prouve sa boîte."""
    session = _session(_offre(), NOUVELLE)
    achat = achats.livrer_l_achat(session)
    assert achat.compte is not None
    CompteClient.objects.filter(pk=achat.compte.pk).update(
        created_at=timezone.now() - FENETRE_APRES_ACHAT - timedelta(minutes=1),
    )

    assert ouvrir_la_session_d_un_achat(achat.compte, session["id"]) is None


def test_la_boutique_suit_la_meme_regle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les pages de retour partagent la fonction : aucune n'ouvre de session
    par un autre chemin. Celle des formations (20/11/2026) y est tenue aussi."""
    from pathlib import Path

    import organisations

    dossier = Path(organisations.__file__).parent
    for vue in ("vues_publiques.py", "vues_boutique.py", "vues_formations.py"):
        source = (dossier / vue).read_text(encoding="utf-8")
        retour = source.split("def retour", 1)[1].split("\ndef ", 1)[0]
        assert "ouvrir_la_session_d_un_achat" in retour, vue
        assert "ouvrir_session_sans_mot_de_passe" not in retour, vue


# ── Audit de sécurité : à qui va l'achat, et qui est « né » de lui ──────────


def _invitee_jamais_venue() -> tuple[Any, Customer, Any]:
    proprietaire = Customer.objects.create(email="inviteur@cabinet.example")
    organisation = services.creer_organisation(
        raison_sociale="Cabinet inviteur", contact=proprietaire,
    )
    invitee = Customer.objects.create(email="cible@example.com")
    membre = services.inviter_membre(organisation, invitee)
    identifiants.compte_sans_mot_de_passe(invitee)
    return organisation, invitee, membre


def test_l_achat_d_une_invitee_jamais_venue_ne_va_pas_a_qui_l_a_invitee() -> None:
    """Il suffisait d'inviter l'adresse de quelqu'un pour recevoir son achat :
    inviter rattache tout de suite, et l'achat public suivait ce rattachement."""
    from organisations import credits

    organisation, invitee, membre = _invitee_jamais_venue()
    session = _session(_offre(), invitee.email)

    achat = achats.livrer_l_achat(session)

    assert achat.organisation != organisation
    assert achat.organisation.contact == invitee
    assert credits.solde(organisation) == 0
    assert credits.solde(achat.organisation) == 1
    membre.refresh_from_db()
    assert membre.revoque_le is not None, "deux rattachements actifs pour une personne"


def test_une_collaboratrice_venue_dans_son_cabinet_achete_pour_lui() -> None:
    """Contre-épreuve : elle a suivi l'invitation et s'est connectée — c'est
    bien son espace, et un second n'a pas à s'ouvrir."""
    from organisations import credits

    organisation, invitee, membre = _invitee_jamais_venue()
    CompteClient.objects.filter(customer=invitee).update(
        derniere_connexion=timezone.now() + timedelta(minutes=1),
    )

    achat = achats.livrer_l_achat(_session(_offre(), invitee.email))

    assert achat.organisation == organisation
    assert credits.solde(organisation) == 1
    membre.refresh_from_db()
    assert membre.revoque_le is None


def test_une_connexion_d_avant_l_invitation_ne_vaut_pas_acceptation() -> None:
    """Un compte actif ailleurs, puis invité ici sans y être jamais venu : la
    connexion d'autrefois ne dit rien de cette invitation-ci."""
    organisation, invitee, _ = _invitee_jamais_venue()
    CompteClient.objects.filter(customer=invitee).update(
        derniere_connexion=timezone.now() - timedelta(days=30),
    )

    achat = achats.livrer_l_achat(_session(_offre(), invitee.email))

    assert achat.organisation != organisation


def test_un_second_achat_va_au_meme_espace_sans_connexion_entre_les_deux() -> None:
    """Contre-épreuve : l'espace qu'elle a ouvert par son premier achat est le
    sien — elle en est le contact —, même sans y être jamais entrée."""
    offre = _offre()
    premier = achats.livrer_l_achat(_session(offre, NOUVELLE))

    second = achats.livrer_l_achat(_session(offre, NOUVELLE))

    assert second.organisation == premier.organisation


def test_un_compte_neuf_dans_un_espace_ancien_n_ouvre_pas_de_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La marque « né de l'achat » se posait dès que l'identifiant de connexion
    était neuf. Une personne rattachée de longue date à un espace, et qui
    n'avait simplement jamais eu de compte, se faisait donc ouvrir CET espace
    par quiconque payait avec son adresse."""
    ancienne = Customer.objects.create(email="ancienne@cabinet.example")
    organisation = services.creer_organisation(
        raison_sociale="Espace d'avant les comptes", contact=ancienne,
    )
    assert not CompteClient.objects.filter(customer=ancienne).exists()
    session = _session(_offre(), ancienne.email)

    reponse = _revenir(monkeypatch, session)

    corps = reponse.json()
    assert corps["jeton"] is None and corps["connexion_requise"] is True
    assert not JetonAcces.objects.exists()
    # L'achat, lui, est bien livré à son espace.
    assert MouvementCredit.objects.get(
        reference=session["id"]
    ).portefeuille.organisation == organisation
