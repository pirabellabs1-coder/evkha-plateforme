"""La page annonçait le prix du crédit supplémentaire. On ne pouvait pas l'acheter.

« Crédit supplémentaire : 59 € » figure sur chaque formule de la page publique
depuis le premier jour. Le type de mouvement `ACHAT` existait en base, avec une
propriété soigneusement écrite — ces crédits-là **ne périment pas**, contrairement
à la dotation mensuelle. Mais aucun chemin ne permettait de les payer : ni
bouton, ni route, ni session Stripe. Un partenaire à court de crédits en milieu
de mois n'avait qu'à attendre le suivant.

Relevé le 07/08/2026, sur question du développeur : « on a pensé à ceux qui
veulent prendre des crédits en plus ? »

Ce que ces tests tiennent :

1. le prix vient de la FORMULE, jamais du navigateur ;
2. la quantité est bornée — une quantité venue du client ne se croit pas ;
3. les crédits versés sont de type `ACHAT`, donc **impérissables** : les verser
   en dotation les ferait expirer à la fin du mois, et le client aurait payé
   59 € pour un crédit qui disparaît le 31 ;
4. un événement rejoué ne double pas les crédits.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client, override_settings

from organisations import credits
from organisations.models import MouvementCredit, TypeMouvement

from .test_cycle_de_l_abonnement import STRIPE_REGLE, Abonne


@pytest.fixture(autouse=True)
def _sans_appel_reseau(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture les sessions Checkout au lieu de les creer chez Stripe.

    On verifie ce qui PART — le montant, la quantite, les metadonnees — et non
    que la vue reponde 200. Une vue qui repond 200 en envoyant le mauvais
    montant est exactement le defaut qu'on veut exclure.
    """
    import stripe

    envoyees: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> dict[str, Any]:
        envoyees.append(kwargs)
        return {"id": "cs_test_cree", "url": "https://checkout.stripe.com/test"}

    monkeypatch.setattr(stripe.checkout.Session, "create", create)
    return envoyees


def _demander(abonne: Abonne, quantite: Any) -> Any:
    return Client().post(
        "/api/espace/credits/acheter/",
        data=json.dumps({"quantite": quantite}),
        content_type="application/json",
        headers=abonne.entetes,
    )


# ── L'ouverture du paiement ─────────────────────────────────────────────────


@pytest.mark.django_db
@override_settings(**STRIPE_REGLE)
def test_le_montant_vient_de_la_formule_et_non_du_navigateur(
    _sans_appel_reseau: list[dict[str, Any]],
) -> None:
    """Accepter un montant du client reviendrait à laisser choisir combien payer."""
    abonne = Abonne()
    abonne.abonnement.formule.prix_credit_supplementaire_cents = 5_500
    abonne.abonnement.formule.save()

    reponse = Client().post(
        "/api/espace/credits/acheter/",
        # Le navigateur tente d'imposer un prix : il doit etre ignore.
        data=json.dumps({"quantite": 2, "montant_cents": 1, "prix": 0}),
        content_type="application/json",
        headers=abonne.entetes,
    )

    assert reponse.status_code == 200
    assert reponse.json()["url"]

    envoye = _sans_appel_reseau[0]
    ligne = envoye["line_items"][0]
    assert ligne["price_data"]["unit_amount"] == 5_500
    assert ligne["quantity"] == 2
    assert envoye["mode"] == "payment"
    assert envoye["metadata"]["achat"] == "credits"
    assert envoye["metadata"]["quantite"] == "2"


@pytest.mark.django_db
@override_settings(**STRIPE_REGLE)
@pytest.mark.parametrize("quantite", [0, -3, 51, "beaucoup", None])
def test_une_quantite_hors_bornes_est_refusee(quantite: Any) -> None:
    """Une quantité venue du navigateur ne se croit pas.

    `quantite = 100000` produirait une facture de six millions d'euros que
    personne ne paiera — mais aussi une session Stripe absurde dans le journal.
    """
    reponse = _demander(Abonne(), quantite)

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "quantite_invalide"


@pytest.mark.django_db
@override_settings(**STRIPE_REGLE)
def test_sans_abonnement_il_n_y_a_aucun_tarif_a_appliquer() -> None:
    """Ce n'est pas une restriction commerciale, c'est une absence de prix.

    Le tarif du crédit supplémentaire vit dans la formule. Sans abonnement, il
    n'y a aucune formule — et en inventer une par défaut ferait payer à
    quelqu'un un tarif que personne ne lui a annoncé.
    """
    abonne = Abonne()
    abonne.abonnement.delete()

    reponse = _demander(abonne, 2)

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "sans_abonnement"


# ── Le versement, au retour du paiement ─────────────────────────────────────


def _session(*, quantite: int = 2, reference: str = "cs_test_1") -> dict[str, Any]:
    return {
        "id": reference,
        "status": "complete",
        "mode": "payment",
        "client_reference_id": "",
        "metadata": {
            "organisation_id": "",
            "achat": "credits",
            "quantite": str(quantite),
        },
    }


@pytest.mark.django_db
def test_les_credits_achetes_ne_perissent_pas() -> None:
    """LE test de ce fichier.

    Les verser en `DOTATION` les ferait expirer à la fin du mois : le client
    aurait payé 59 € pour un crédit qui disparaît le 31. La distinction existait
    déjà dans `credits.ENTREES_PERENNES` — elle n'attendait que d'être employée.
    """
    from paiement import abonnements

    abonne = Abonne()
    session = _session(quantite=3)
    session["metadata"]["organisation_id"] = str(abonne.organisation.id)

    resultat = abonnements._crediter_l_achat(session)

    assert "3 credits achetes" in resultat
    mouvement = MouvementCredit.objects.get(reference="cs_test_1")
    assert mouvement.type == TypeMouvement.ACHAT
    assert mouvement.quantite == 3
    assert TypeMouvement.ACHAT in credits.ENTREES_PERENNES


@pytest.mark.django_db
def test_un_evenement_rejoue_ne_double_pas_les_credits() -> None:
    """Stripe réémet ses événements pendant trois jours en cas d'erreur."""
    from paiement import abonnements

    abonne = Abonne()
    session = _session(quantite=2)
    session["metadata"]["organisation_id"] = str(abonne.organisation.id)

    for _ in range(3):
        abonnements._crediter_l_achat(session)

    assert MouvementCredit.objects.filter(reference="cs_test_1").count() == 1
    assert credits.solde(abonne.organisation) == 2 + _solde_initial(abonne)


@pytest.mark.django_db
def test_deux_achats_distincts_s_additionnent() -> None:
    """Contre-épreuve : la garde ne doit pas avaler un second achat sincère."""
    from paiement import abonnements

    abonne = Abonne()
    depart = _solde_initial(abonne)
    for reference in ("cs_a", "cs_b"):
        session = _session(quantite=1, reference=reference)
        session["metadata"]["organisation_id"] = str(abonne.organisation.id)
        abonnements._crediter_l_achat(session)

    assert credits.solde(abonne.organisation) == depart + 2


@pytest.mark.django_db
def test_un_achat_sans_organisation_ouvre_un_incident() -> None:
    """On ne devine pas à qui créditer. Se taire perdrait l'argent du client."""
    from paiement import abonnements

    from monitoring.models import OperationalIncident

    session = _session()
    session["metadata"]["organisation_id"] = ""

    resultat = abonnements._crediter_l_achat(session)

    assert "inexploitable" in resultat
    assert OperationalIncident.objects.filter(
        title="Achat de credits inexploitable"
    ).exists()
    assert not MouvementCredit.objects.filter(reference="cs_test_1").exists()


@pytest.mark.django_db
def test_un_achat_n_est_pas_traite_comme_une_souscription() -> None:
    """Sans aiguillage, l'achat passerait pour un abonnement.

    `checkout.session.completed` sert aux deux. Traité comme une souscription,
    l'achat ne trouverait aucun abonnement Stripe, ouvrirait un incident — et
    le client aurait payé sans rien recevoir.
    """
    from paiement import abonnements

    abonne = Abonne()
    session = _session(quantite=1)
    session["metadata"]["organisation_id"] = str(abonne.organisation.id)

    resultat = abonnements.sur_session_terminee(session)

    assert "credits achetes" in resultat
    assert MouvementCredit.objects.filter(
        reference="cs_test_1", type=TypeMouvement.ACHAT
    ).exists()


def _solde_initial(abonne: Abonne) -> int:
    """Le solde déjà présent avant l'achat, quel qu'il soit."""
    return credits.solde(abonne.organisation) - sum(
        m.quantite
        for m in MouvementCredit.objects.filter(
            portefeuille__organisation=abonne.organisation,
            type=TypeMouvement.ACHAT,
        )
    )
