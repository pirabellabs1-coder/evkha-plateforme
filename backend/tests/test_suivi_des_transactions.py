"""Une session de paiement abandonnée ne laissait aucune trace.

On demandait une adresse à Stripe, on la donnait au client, et s'il
abandonnait, personne ne le savait jamais. Un panier abandonné est pourtant
l'information commerciale la plus utile de la plateforme : quelqu'un a voulu
payer et s'est arrêté en chemin.

Demandé par la cliente le 07/08/2026 : « l'admin doit pouvoir suivre les
paiements ou paniers abandonnés, celui qui veut changer de formule mais n'a pas
finalisé, celui qui veut acheter du crédit mais n'a pas finalisé […] pour
pouvoir contacter ces gens manuellement avec un bouton de relance ».

Ce que ces tests tiennent :

1. la tentative naît à l'OUVERTURE du paiement, pas à son aboutissement —
   c'est tout l'intérêt ;
2. le webhook la referme, sinon une souscription réussie resterait affichée
   comme panier abandonné et la cliente relancerait quelqu'un qui a payé ;
3. l'abandon est CALCULÉ sur l'âge, pas reçu de Stripe ;
4. la relance ne renvoie pas de lien de paiement, et se compte.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from organisations.models import EtatTentative, ObjetTentative, TentativePaiement

from .test_cycle_de_l_abonnement import STRIPE_REGLE, Abonne


@pytest.fixture(autouse=True)
def _sans_appel_reseau(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    import stripe

    envoyees: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> dict[str, Any]:
        envoyees.append(kwargs)
        return {"id": "cs_suivi_1", "url": "https://checkout.stripe.com/x"}

    monkeypatch.setattr(stripe.checkout.Session, "create", create)
    return envoyees


@pytest.mark.django_db
@override_settings(**STRIPE_REGLE)
def test_ouvrir_un_achat_laisse_une_trace_avant_tout_paiement() -> None:
    """Sur le code d'avant, cette session ne laissait RIEN derrière elle."""
    abonne = Abonne()
    abonne.abonnement.formule.prix_credit_supplementaire_cents = 5_500
    abonne.abonnement.formule.save()

    Client().post(
        "/api/espace/credits/acheter/",
        data=json.dumps({"quantite": 2}),
        content_type="application/json",
        headers=abonne.entetes,
    )

    tentative = TentativePaiement.objects.get()
    assert tentative.etat == EtatTentative.OUVERTE
    assert tentative.objet == ObjetTentative.CREDITS
    assert tentative.quantite == 2
    assert tentative.montant_cents == 11_000
    assert tentative.organisation_id == abonne.organisation.id
    assert tentative.payee_le is None


@pytest.mark.django_db
def test_le_webhook_referme_la_tentative() -> None:
    """Sans cela, un paiement réussi resterait un panier abandonné à l'écran.

    La cliente relancerait alors quelqu'un qui a déjà payé — un suivi qui se
    trompe est pire qu'un suivi absent (règle 2).
    """
    from paiement import abonnements

    abonne = Abonne()
    TentativePaiement.objects.create(
        organisation=abonne.organisation,
        objet=ObjetTentative.CREDITS,
        quantite=1,
        montant_cents=5_500,
        reference_session="cs_suivi_1",
    )

    abonnements.sur_session_terminee({
        "id": "cs_suivi_1",
        "status": "complete",
        "metadata": {
            "achat": "credits",
            "quantite": "1",
            "organisation_id": str(abonne.organisation.id),
        },
    })

    tentative = TentativePaiement.objects.get()
    assert tentative.etat == EtatTentative.PAYEE
    assert tentative.payee_le is not None


@pytest.mark.django_db
def test_l_abandon_est_calcule_sur_l_age() -> None:
    """Stripe n'envoie `checkout.session.expired` que si l'on s'y abonne.

    Faire dépendre une information commerciale d'un réglage facultatif
    reviendrait à la perdre le jour où quelqu'un le décoche, sans que rien ne
    le signale.
    """
    abonne = Abonne()
    tentative = TentativePaiement.objects.create(
        organisation=abonne.organisation,
        objet=ObjetTentative.ABONNEMENT,
        montant_cents=18_900,
        reference_session="cs_vieille",
    )
    assert tentative.abandonnee is False

    TentativePaiement.objects.filter(pk=tentative.pk).update(
        created_at=timezone.now() - timedelta(hours=25)
    )
    tentative.refresh_from_db()

    assert tentative.abandonnee is True


@pytest.mark.django_db
def test_une_tentative_payee_n_est_jamais_abandonnee() -> None:
    """Contre-épreuve : l'âge ne doit pas ressusciter un panier réglé."""
    abonne = Abonne()
    tentative = TentativePaiement.objects.create(
        organisation=abonne.organisation,
        objet=ObjetTentative.ABONNEMENT,
        montant_cents=18_900,
        reference_session="cs_payee",
        etat=EtatTentative.PAYEE,
    )
    TentativePaiement.objects.filter(pk=tentative.pk).update(
        created_at=timezone.now() - timedelta(days=30)
    )
    tentative.refresh_from_db()

    assert tentative.abandonnee is False


@pytest.mark.django_db
def test_la_relance_ne_renvoie_aucun_lien_de_paiement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LE piège de cette fonctionnalité.

    Une session Checkout expire au bout de vingt-quatre heures. Renvoyer son
    lien dans un courriel de relance donnerait un lien MORT au moment précis où
    l'on cherche à rassurer — l'impression d'un service en panne. On renvoie
    vers l'espace, où le geste est à un clic et toujours valable.
    """
    from organisations import courriels

    envoyes: list[dict[str, Any]] = []
    monkeypatch.setattr(
        courriels,
        "_envoyer",
        lambda **kwargs: (envoyes.append(kwargs), True)[1],
    )

    courriels.relancer_un_paiement(
        destinataire="a@b.fr",
        organisation="Agence Test",
        objet="Achat de crédits supplémentaires",
        montant_cents=11_000,
    )

    corps = envoyes[0]["corps_html"]
    assert "checkout.stripe.com" not in corps
    assert "/espace" in corps
    # Le montant est dit : une relance sans chiffre oblige a rouvrir son compte
    # pour savoir de quoi on parle.
    assert "110,00" in corps


@pytest.mark.django_db
def test_relancer_compte_et_date_les_envois(monkeypatch: pytest.MonkeyPatch) -> None:
    """La cliente doit voir qu'elle a déjà écrit deux fois avant d'écrire une troisième."""
    from dashboard import supervision
    from organisations import courriels

    monkeypatch.setattr(courriels, "_envoyer", lambda **_: True)
    monkeypatch.setattr(supervision, "_json", supervision._json)

    abonne = Abonne()
    tentative = TentativePaiement.objects.create(
        organisation=abonne.organisation,
        objet=ObjetTentative.ABONNEMENT,
        montant_cents=18_900,
        reference_session="cs_relance",
    )

    from django.test import RequestFactory

    requete = RequestFactory().post("/")
    supervision.relancer_la_transaction(requete, str(tentative.id))
    supervision.relancer_la_transaction(requete, str(tentative.id))

    tentative.refresh_from_db()
    assert tentative.relances == 2
    assert tentative.relancee_le is not None


@pytest.mark.django_db
def test_on_ne_relance_pas_un_paiement_abouti(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contre-épreuve : écrire à quelqu'un qui a payé est le pire message possible."""
    from django.test import RequestFactory

    from dashboard import supervision
    from organisations import courriels

    envoyes: list[Any] = []
    monkeypatch.setattr(
        courriels, "_envoyer", lambda **k: (envoyes.append(k), True)[1]
    )

    abonne = Abonne()
    tentative = TentativePaiement.objects.create(
        organisation=abonne.organisation,
        objet=ObjetTentative.ABONNEMENT,
        montant_cents=18_900,
        reference_session="cs_deja_payee",
        etat=EtatTentative.PAYEE,
    )

    reponse = supervision.relancer_la_transaction(
        RequestFactory().post("/"), str(tentative.id)
    )

    assert reponse.status_code == 409
    assert envoyes == []
