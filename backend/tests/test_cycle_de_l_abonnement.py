"""L'abonnement se reconduit seul, et s'arrete sans demander la permission.

Ces tests verrouillent la reprise du 06/08/2026, apres la cartographie qui a
confirme douze manques sur cette seule dimension. Les trois plus chers :

1. **Resilier chez nous ne prevenait pas Stripe.** `services.resilier` bascule
   un statut en base ; la carte, elle, continuait d'etre debitee tous les mois.
   Un client parti restait payant, et s'en apercevait sur son relevé.

2. **La dotation mensuelle ignorait le paiement.** La tache horaire
   `appliquer_echeances` credite au 1er du mois sur la foi du calendrier. Une
   carte refusee le 3 n'empechait donc rien : le client produisait des etudes
   gratuitement pendant que Stripe retentait, puis recommencait le mois suivant.

3. **Un changement de formule se defaisait tout seul.** Il ne touchait pas
   Stripe : le prelevement suivant repartait sur l'ancien tarif.

Aucun de ces trois ne se voit sur un ecran. Ils se voient sur un compte en
banque, ce qui est exactement la raison d'etre de ces tests.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import stripe
from django.test import Client
from django.test.utils import override_settings

from customers.models import Customer
from organisations import credits, services
from organisations.authentification import creer_compte, ouvrir_session
from organisations.models import (
    AbonnementOrganisation,
    Formule,
    MouvementCredit,
    StatutAbonnement,
    TypeMouvement,
)
from organisations.tasks import appliquer_echeances

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"
STRIPE_REGLE = {"STRIPE_SECRET_KEY": "sk_test_x", "EVKHA_APP_URL": "https://exemple.fr"}


class Abonne:
    """Une organisation abonnee PAR CARTE, comme en production."""

    def __init__(self, nom: str = "Atelier Test", email: str = "abonne@exemple.fr"):
        self.contact = Customer.objects.create(email=email, first_name=nom)
        self.organisation = services.creer_organisation(
            raison_sociale=nom, contact=self.contact
        )
        creer_compte(self.contact, mot_de_passe=MOT_DE_PASSE)
        self.jeton, _ = ouvrir_session(email, MOT_DE_PASSE)
        self.formule = formule()
        self.abonnement = services.souscrire(self.organisation, self.formule)
        self.abonnement.reference_paiement = "sub_test"
        self.abonnement.save(update_fields=["reference_paiement"])

    @property
    def entetes(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.jeton}"}

    def relire(self) -> AbonnementOrganisation:
        return AbonnementOrganisation.objects.get(pk=self.abonnement.pk)


def formule(code: str = "pro", credits_mois: int = 3, prix: int = 18_900) -> Formule:
    objet, _ = Formule.objects.get_or_create(
        code=code,
        defaults={
            "libelle": code.capitalize(),
            "credits_par_echeance": credits_mois,
            "prix_mensuel_cents": prix,
            "reference_paiement": f"price_{code}",
            "active": True,
        },
    )
    return objet


class FauxStripe:
    """Enregistre ce qui PART chez Stripe, au lieu de l'envoyer.

    Ce que l'on verifie, ce n'est pas que la vue reponde 200 — c'est ce qu'elle
    demande a Stripe. Une vue qui repond 200 sans rien envoyer est exactement le
    defaut d'origine (regle 7, transposee : ce qui compte est ce que le
    prestataire recoit, pas ce que notre ecran affiche).
    """

    def __init__(self) -> None:
        self.modifications: list[dict[str, Any]] = []

    def modify(self, reference: str, **kwargs: Any) -> dict[str, Any]:
        self.modifications.append({"reference": reference, **kwargs})
        fin = int((datetime.now(tz=UTC) + timedelta(days=12)).timestamp())
        return {"id": reference, "current_period_end": fin, **kwargs}

    def retrieve(self, reference: str, **_: Any) -> dict[str, Any]:
        return {"id": reference, "items": {"data": [{"id": "si_test"}]}}


@pytest.fixture
def faux_stripe(monkeypatch: pytest.MonkeyPatch) -> FauxStripe:
    faux = FauxStripe()
    monkeypatch.setattr(stripe.Subscription, "modify", faux.modify)
    monkeypatch.setattr(stripe.Subscription, "retrieve", faux.retrieve)
    return faux


# ── 1. Arreter : la carte cesse d'etre debitee ───────────────────────────────


@override_settings(**STRIPE_REGLE)
def test_arreter_renvoie_vers_evkha_et_ne_coupe_RIEN(
    faux_stripe: FauxStripe,
) -> None:
    """LE test de ce fichier, retourne le 07/08/2026 sur decision de la cliente.

    Il verrouillait l'inverse : un clic coupait la reconduction chez Stripe. La
    cliente a tranche autrement — << l'annulation doit se faire manuellement,
    donc la personne doit la contacter >>. Elle traite ces demandes elle-meme,
    au moins au debut, et c'est aussi l'occasion de retenir un abonne qui part.

    Ce qui est verifie n'est pas la reponse HTTP mais l'ABSENCE d'appel
    sortant : rien ne doit partir chez Stripe. Un refus qui couperait quand
    meme serait le pire des deux mondes.
    """
    abonne = Abonne()

    reponse = Client().post(
        "/api/espace/abonnement/arreter/", data="{}",
        content_type="application/json", headers=abonne.entetes,
    )

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "arret_sur_demande"
    assert faux_stripe.modifications == []
    # Et l'abonnement est intact : ni statut, ni reconduction touches.
    relu = abonne.relire()
    assert relu.statut == StatutAbonnement.ACTIF
    assert relu.renouvellement_actif is True


@override_settings(**STRIPE_REGLE)
def test_le_refus_donne_l_adresse_ou_ecrire(faux_stripe: FauxStripe) -> None:
    """Un refus sans issue est un mur.

    L'abonne doit savoir a qui s'adresser dans le message meme, sans avoir a
    chercher : c'est le moment ou il est le plus dispose a renoncer.
    """
    from django.conf import settings

    abonne = Abonne()

    reponse = Client().post(
        "/api/espace/abonnement/arreter/", data="{}",
        content_type="application/json", headers=abonne.entetes,
    )

    assert settings.EVKHA_SENDER_EMAIL in reponse.json()["error"]
    assert not faux_stripe.modifications


@override_settings(**STRIPE_REGLE)
def test_le_refus_rappelle_l_engagement_en_cours(faux_stripe: FauxStripe) -> None:
    """Trois mois d'engagement, annonces sur la page et jamais appliques.

    Ce n'est pas un refus supplementaire — l'arret passe par EVKHA dans tous
    les cas — mais l'abonne a le droit de savoir jusqu'a quand il est engage
    AVANT d'ecrire, plutot que de l'apprendre en reponse a son courriel.
    """
    from organisations.vues_espace import MOIS_ENGAGEMENT

    abonne = Abonne()

    reponse = Client().post(
        "/api/espace/abonnement/arreter/", data="{}",
        content_type="application/json", headers=abonne.entetes,
    )

    message = reponse.json()["error"]
    assert f"{MOIS_ENGAGEMENT} mois" in message
    # Une date, pas une formule vague : << bientot >> ne se verifie pas.
    assert "/" in message.split("jusqu'au")[-1]


@override_settings(**STRIPE_REGLE)
def test_un_abonnement_ouvert_a_la_main_ne_pretend_pas_s_arreter(
    faux_stripe: FauxStripe
) -> None:
    """Regle 1 : on refuse en le disant, plutot que de faire semblant.

    Aucun prelevement derriere lui : repondre 200 laisserait croire que quelque
    chose a ete arrete.
    """
    abonne = Abonne()
    abonne.abonnement.reference_paiement = ""
    abonne.abonnement.save(update_fields=["reference_paiement"])

    reponse = Client().post(
        "/api/espace/abonnement/arreter/", data="{}",
        content_type="application/json", headers=abonne.entetes,
    )

    # Meme refus pour tout le monde depuis que l'arret est manuel : le client
    # n'a pas a savoir si son abonnement est adosse a une carte ou ouvert a la
    # main. Ce qui compte est qu'on ne pretende RIEN avoir arrete.
    assert reponse.status_code == 409
    assert reponse.json()["code"] == "arret_sur_demande"
    assert faux_stripe.modifications == []


# ── 2. La dotation suit l'argent, pas le calendrier ──────────────────────────


def test_la_tache_horaire_ne_dote_plus_un_abonnement_paye_par_carte() -> None:
    """Sans cela, un impaye produit des etudes gratuitement.

    La tache credite au 1er sur la foi du calendrier. Une carte refusee le 3
    n'empechait rien : Stripe retentait, abandonnait, et le mois suivant
    recommencait. C'est `invoice.paid` — donc l'encaissement reel — qui dote.
    """
    abonne = Abonne()
    # On efface la trace de la dotation initiale pour placer la tache dans les
    # conditions d'une nouvelle periode.
    abonne.abonnement.derniere_periode_dotee = ""
    abonne.abonnement.save(update_fields=["derniere_periode_dotee"])
    avant = MouvementCredit.objects.filter(
        portefeuille__organisation=abonne.organisation
    ).count()

    resultat = appliquer_echeances()

    assert resultat["payees_par_stripe"] == 1
    assert resultat["dotees"] == 0
    assert MouvementCredit.objects.filter(
        portefeuille__organisation=abonne.organisation
    ).count() == avant


def test_la_tache_horaire_dote_toujours_un_abonnement_ouvert_a_la_main() -> None:
    """CONTRE-EPREUVE : on n'a pas eteint la dotation pour tout le monde.

    Un abonnement cree depuis l'administration n'a aucun prelevement derriere
    lui. Personne d'autre que cette tache ne le dotera.

    Le montage n'efface PAS `derniere_periode_dotee` d'un abonnement deja dote :
    ma premiere version le faisait, et le test echouait — a raison. La cle
    d'idempotence de `credits.doter` vaut `f"{abonnement_id}:{periode}"` et vit
    en base, pas dans ce champ : effacer le champ ne supprime pas le mouvement.
    Les deux protections sont independantes, et c'est voulu (regle 9). On part
    donc d'un abonnement JAMAIS dote.
    """
    contact = Customer.objects.create(email="manuel@exemple.fr", first_name="Manuel")
    organisation = services.creer_organisation(
        raison_sociale="Cabinet Manuel", contact=contact
    )
    services.souscrire(organisation, formule(), doter_immediatement=False)

    resultat = appliquer_echeances()

    assert resultat["dotees"] == 1
    assert resultat["payees_par_stripe"] == 0
    assert credits.solde(organisation) == formule().credits_par_echeance


# ── 3. Changer de formule, chez Stripe aussi ─────────────────────────────────


@override_settings(**STRIPE_REGLE)
def test_changer_de_formule_bascule_le_tarif_chez_stripe(
    faux_stripe: FauxStripe
) -> None:
    """Sans cela, le prelevement suivant repart sur l'ancien tarif.

    Le changement se defaisait donc tout seul a l'echeance, sans que rien ne le
    signale — ni a nous, ni au client.
    """
    abonne = Abonne()
    superieure = formule(code="pro-plus", credits_mois=5, prix=24_900)

    reponse = Client().post(
        "/api/espace/abonnement/formule/",
        data=json.dumps({"formule": superieure.code}),
        content_type="application/json", headers=abonne.entetes,
    )

    assert reponse.status_code == 200
    envoye = faux_stripe.modifications[-1]
    assert envoye["reference"] == "sub_test"
    assert envoye["items"] == [{"id": "si_test", "price": "price_pro-plus"}]
    assert envoye["proration_behavior"] == "create_prorations"


@override_settings(**STRIPE_REGLE)
def test_changer_de_formule_ne_dote_pas_avant_d_avoir_encaisse(
    faux_stripe: FauxStripe
) -> None:
    """Le prorata est facture par Stripe ; c'est sa facture qui dote.

    Doter au clic donnerait les credits de la nouvelle formule avant que la
    difference soit encaissee, puis une seconde fois a l'arrivee de la facture.
    """
    abonne = Abonne()
    superieure = formule(code="pro-plus", credits_mois=5, prix=24_900)
    solde_avant = credits.solde(abonne.organisation)

    Client().post(
        "/api/espace/abonnement/formule/",
        data=json.dumps({"formule": superieure.code}),
        content_type="application/json", headers=abonne.entetes,
    )

    assert credits.solde(abonne.organisation) == solde_avant
    actif = AbonnementOrganisation.objects.get(
        organisation=abonne.organisation, statut=StatutAbonnement.ACTIF
    )
    assert actif.formule_id == superieure.pk
    # La reference Stripe SUIT la nouvelle ligne : sans cela, la tache horaire
    # se remettrait a doter cet abonnement en parallele de Stripe.
    assert actif.reference_paiement == "sub_test"


@override_settings(**STRIPE_REGLE)
def test_changer_pour_la_meme_formule_est_refuse(faux_stripe: FauxStripe) -> None:
    abonne = Abonne()

    reponse = Client().post(
        "/api/espace/abonnement/formule/",
        data=json.dumps({"formule": abonne.formule.code}),
        content_type="application/json", headers=abonne.entetes,
    )

    assert reponse.status_code == 409
    assert faux_stripe.modifications == []


# ── 4. Stripe reste l'autorite, meme quand la decision vient d'ailleurs ──────


SECRET = "whsec_secret_de_test_pour_la_suite"


def _poster(charge: dict[str, Any]) -> Any:
    import hashlib
    import hmac
    import time

    corps = json.dumps(charge).encode("utf-8")
    t = int(time.time())
    signature = hmac.new(
        SECRET.encode("utf-8"), f"{t}.".encode() + corps, hashlib.sha256
    ).hexdigest()
    return Client().post(
        "/webhooks/stripe/", data=corps, content_type="application/json",
        headers={"Stripe-Signature": f"t={t},v1={signature}"},
    )


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET)
def test_un_arret_prononce_depuis_stripe_se_voit_chez_nous() -> None:
    """La decision peut venir du tableau de bord Stripe, ou de Stripe lui-meme.

    Sans cet evenement, notre ecran continuerait d'annoncer « se reconduit
    chaque mois » a quelqu'un dont le prelevement est deja arrete.
    """
    abonne = Abonne()
    fin = int((datetime.now(tz=UTC) + timedelta(days=9)).timestamp())

    reponse = _poster({
        "id": "evt_maj",
        "type": "customer.subscription.updated",
        "data": {"object": {
            "id": "sub_test",
            "cancel_at_period_end": True,
            "current_period_end": fin,
        }},
    })

    assert reponse.status_code == 200
    relu = abonne.relire()
    assert relu.renouvellement_actif is False
    assert relu.fin_de_periode_le is not None


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET)
def test_une_mise_a_jour_d_abonnement_ne_dote_jamais() -> None:
    """Cet evenement part a chaque changement de carte et a chaque relance.

    Le traiter largement suffirait a crediter a chaque fois.
    """
    abonne = Abonne()
    avant = credits.solde(abonne.organisation)

    _poster({
        "id": "evt_maj_2",
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_test", "cancel_at_period_end": False}},
    })

    assert credits.solde(abonne.organisation) == avant


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET)
def test_la_fin_prononcee_par_stripe_resilie_pour_de_bon() -> None:
    """Au terme reel, l'abonnement s'eteint — et la dotation avec lui."""
    abonne = Abonne()

    _poster({
        "id": "evt_fin",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_test"}},
    })

    assert not AbonnementOrganisation.objects.filter(
        organisation=abonne.organisation, statut=StatutAbonnement.ACTIF
    ).exists()


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET)
def test_un_resilie_garde_ses_credits_achetes(faux_stripe: FauxStripe) -> None:
    """CONTRE-EPREUVE : la fin de l'abonnement ne confisque pas un achat."""
    abonne = Abonne()
    credits.crediter(
        abonne.organisation, 2, type_mouvement=TypeMouvement.ACHAT,
        reference="achat-test", motif="Achat de credits.",
    )

    _poster({
        "id": "evt_fin_2",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_test"}},
    })

    assert credits.solde(abonne.organisation) >= 2
