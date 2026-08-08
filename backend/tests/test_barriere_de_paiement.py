"""L'espace client se paie avant d'entrer, et le paiement se prouve.

Ces tests verrouillent la barriere ouverte le 06/08/2026. Chacun echoue sur le
code d'avant (regle 6) — la plupart de la pire facon possible : en repondant
200 la ou l'on attend un refus.

## Ce que le code d'avant faisait

Le decorateur `espace()` n'exigeait qu'un jeton, une adhesion et un role. Le
formulaire public, lui, delivrait une session **immediatement**
(`vues_publiques.py:148`). N'importe qui obtenait donc, en une requete, un acces
complet et permanent a l'espace client sans qu'un centime soit encaisse.

Ce qui retenait un compte non paye n'etait pas une barriere, c'etait un solde a
zero. La difference compte : le triple barrage credits repond a « ce
portefeuille couvre-t-il ce cout ? », jamais a « cette organisation a-t-elle
paye ? ». Toute la surete tenait a un seul booleen, `activer_abonnement=False`.

## Ce que ces tests refusent de laisser revenir

1. Un compte inscrit sans paiement qui accede a l'espace.
2. Un webhook de paiement qui accepte un evenement qu'il ne peut pas verifier.
3. Une dotation payee une fois et versee deux fois.
4. Un resilie a qui l'on ferme la porte sur des credits qu'il a ACHETES.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import pytest
import stripe
from django.test import Client
from django.test.utils import override_settings
from django.urls import URLPattern

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
from organisations.urls import urlpatterns as routes_espace

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"
SECRET_WEBHOOK = "whsec_secret_de_test_pour_la_suite"

#: La seule vue qui exige un abonnement, et c'est la seule qui engage EVKHA
#: dans une production payante.
#:
#: Ecrite ici pour etre COMPAREE au code, jamais importee de lui : une liste lue
#: depuis `vues_espace` s'accorderait toujours avec lui, y compris le jour ou
#: quelqu'un ferme une deuxieme vue par megarde (regle 9 — un controle ne doit
#: pas juger sur l'evidence qu'il controle).
EXIGENT_UN_ABONNEMENT = {"commander"}


# ── Fabriques ────────────────────────────────────────────────────────────────


class Inscrit:
    """Un compte cree par le formulaire public : aucun paiement, aucun credit."""

    def __init__(self, nom: str = "Cabinet Test", email: str = "essai@exemple.fr"):
        self.contact = Customer.objects.create(email=email, first_name=nom)
        self.organisation = services.creer_organisation(
            raison_sociale=nom, contact=self.contact
        )
        creer_compte(self.contact, mot_de_passe=MOT_DE_PASSE)
        self.jeton, _ = ouvrir_session(email, MOT_DE_PASSE)

    @property
    def entetes(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.jeton}"}


def formule(code: str = "pro", tarif_stripe: str = "price_de_test") -> Formule:
    objet, _ = Formule.objects.get_or_create(
        code=code,
        defaults={
            "libelle": code.capitalize(),
            "credits_par_echeance": 3,
            "prix_mensuel_cents": 18_900,
            "reference_paiement": tarif_stripe,
            "active": True,
        },
    )
    return objet


def signer(charge: dict[str, Any], secret: str = SECRET_WEBHOOK) -> tuple[bytes, str]:
    """Signe une charge comme Stripe le fait : HMAC du corps BRUT, horodate.

    Refaire ici le calcul de Stripe plutot que d'appeler notre propre code :
    un test qui signerait avec la fonction qu'il verifie ne prouverait que sa
    propre coherence.
    """
    corps = json.dumps(charge).encode("utf-8")
    horodatage = int(time.time())
    empreinte = hmac.new(
        secret.encode("utf-8"),
        f"{horodatage}.".encode() + corps,
        hashlib.sha256,
    ).hexdigest()
    return corps, f"t={horodatage},v1={empreinte}"


def poster_evenement(
    charge: dict[str, Any], *, signature: str | None = None
) -> Any:
    corps, entete = signer(charge)
    return Client().post(
        "/webhooks/stripe/",
        data=corps,
        content_type="application/json",
        headers={"Stripe-Signature": signature if signature is not None else entete},
    )


def evenement_session(organisation_id: str, code: str, abonnement: str) -> dict[str, Any]:
    return {
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": f"cs_{uuid.uuid4().hex[:16]}",
            "status": "complete",
            "subscription": abonnement,
            "client_reference_id": organisation_id,
            "metadata": {"organisation_id": organisation_id, "formule_code": code},
        }},
    }


def evenement_facture(organisation_id: str, code: str, abonnement: str) -> dict[str, Any]:
    return {
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "type": "invoice.paid",
        "data": {"object": {
            "id": f"in_{uuid.uuid4().hex[:16]}",
            "subscription": abonnement,
            "metadata": {"organisation_id": organisation_id, "formule_code": code},
        }},
    }


# ── 1. La porte est fermee ───────────────────────────────────────────────────


def _chemin(route: URLPattern) -> str:
    """Une adresse concrete pour cette route, arguments bouches si besoin.

    La valeur des arguments n'a aucune importance : la barriere se prononce
    AVANT que la vue ne cherche quoi que ce soit en base. C'est d'ailleurs une
    propriete a preserver — un 404 qui precede un 402 dirait a un inconnu si un
    identifiant existe.
    """
    motif = str(route.pattern)
    for nom in route.pattern.regex.groupindex:
        motif = motif.replace(f"<str:{nom}>", uuid.uuid4().hex)
        motif = motif.replace(f"<{nom}>", uuid.uuid4().hex)
    return f"/api/espace/{motif}"


def test_un_inscrit_sans_abonnement_ne_peut_pas_commander() -> None:
    """La barriere retient la MAIN, pas les yeux.

    Sur le code d'avant, commander repondait sans jamais demander si
    l'organisation avait paye : le seul obstacle etait un solde a zero, qui
    repond a « ce portefeuille couvre-t-il ce cout ? » et jamais a « cette
    organisation a-t-elle paye ? ».
    """
    inscrit = Inscrit()
    formule()

    reponse = Client().post(
        "/api/espace/commander/",
        data=json.dumps({"type": "market_study"}),
        content_type="application/json",
        headers=inscrit.entetes,
    )

    assert reponse.status_code == 402
    assert reponse.json()["code"] == "souscription_requise"


#: Toutes les routes de l'espace en LECTURE, hors celles a parametre : ce sont
#: elles que la cliente a demande de laisser ouvertes.
LECTURES_OUVERTES = [
    "/api/espace/moi/",
    "/api/espace/livrables/",
    "/api/espace/credits/",
    "/api/espace/consommation/",
    "/api/espace/clients-finaux/",
    "/api/espace/marque/",
    "/api/espace/catalogue/",
    "/api/espace/formules/",
    "/api/espace/demandes/",
    "/api/espace/equipe/",
    "/api/espace/fichiers/",
]


@pytest.mark.parametrize("chemin", LECTURES_OUVERTES)
def test_un_inscrit_sans_abonnement_voit_quand_meme_son_espace(chemin: str) -> None:
    """CONTRE-EPREUVE de la correction du 06/08/2026, et elle compte autant.

    J'avais ferme l'espace entier : ces onze routes repondaient 402 et
    l'interface les remplacait par un ecran de paiement. La cliente l'a corrige
    le jour meme — « meme si le forfait n'est pas actif ca devrait montrer les
    documents sans possibilite de commander ».

    Elle a raison sur le fond : quelqu'un dont l'abonnement s'arrete doit
    continuer a voir ce qu'il a deja commande. Ce test empeche la fermeture de
    revenir par megarde.
    """
    inscrit = Inscrit()

    reponse = Client().get(chemin, headers=inscrit.entetes)

    assert reponse.status_code == 200, (
        f"{chemin} refuse un compte sans abonnement : l'espace doit rester "
        f"consultable ({reponse.status_code})"
    )


def _routes_ou_le_navigateur_poste() -> list[tuple[str, URLPattern]]:
    """Les routes de l'espace qu'un navigateur POSTe reellement.

    Deux familles, et **pas** « toutes les routes » : la premiere version de ce
    test exigeait l'exemption partout, et neuf vues en lecture seule sont
    tombees. Elles avaient raison — aucun navigateur ne leur POSTe jamais, donc
    leur exemption ne protegerait de rien et son absence ne casse rien.

    - celles qui REFUSENT le GET (405) : elles n'existent que pour un POST ;
    - celles qui declarent un droit d'ecriture : elles servent GET *et* POST.

    Le critere est lu sur le comportement et sur la declaration du decorateur,
    jamais sur une liste de noms qui vieillirait sans prevenir.
    """
    client = Client()
    concernees = []
    for route in routes_espace:
        vue = route.callback
        if getattr(vue, "action_ecriture", ""):
            concernees.append((vue.__name__, route))
            continue
        if client.get(_chemin(route)).status_code == 405:
            concernees.append((vue.__name__, route))
    return concernees


@pytest.mark.parametrize(
    "nom,route",
    _routes_ou_le_navigateur_poste(),
    ids=[n for n, _ in _routes_ou_le_navigateur_poste()],
)
def test_aucune_vue_postee_par_le_navigateur_n_exige_de_jeton_csrf(
    nom: str, route: URLPattern
) -> None:
    """Propriete generale de l'espace, trouvee en REGARDANT L'ECRAN (regle 7).

    `ouvrir_le_paiement` avait seize tests verts et affichait « Erreur 403 »
    dans le navigateur : j'avais oublie `@csrf_exempt`. Le client de test Django
    n'applique PAS la verification CSRF par defaut — la suite ne pouvait donc
    pas voir le defaut, quoi qu'elle teste. C'est exactement le vert qui ne
    prouve rien sur ce que le client recoit.

    L'authentification de l'espace se fait par jeton porteur dans l'en-tete,
    jamais par cookie : il n'y a pas de requete intersite a forger, et toutes
    ces vues sont exemptees. Le test porte sur la FAMILLE et non sur la vue qui
    a fait mal (regle 4) — la prochaine vue POST ecrite un jour de fatigue sera
    rattrapee ici.

    `enforce_csrf_checks=True` est ce qui distingue ce test de tous les autres :
    sans lui, il passerait meme sur le code fautif.
    """
    inscrit = Inscrit()
    client = Client(enforce_csrf_checks=True)

    reponse = client.post(
        _chemin(route), data="{}", content_type="application/json",
        headers=inscrit.entetes,
    )

    assert not (
        reponse.status_code == 403 and b"CSRF" in reponse.content
    ), f"{nom} rejette un POST faute de jeton CSRF : ajoutez @csrf_exempt"


def test_une_seule_vue_exige_un_abonnement_et_c_est_la_commande() -> None:
    """Une deuxieme fermeture doit se voir, pas se glisser.

    C'est la contre-partie de la declaration au point d'usage : elle est locale
    et lisible, mais rien n'empeche de l'ecrire une fois de trop. Le jour ou
    quelqu'un ferme `livrables` « par prudence », ce test le dit — et la
    prudence en question reprendrait a un client la vue de ce qu'il a paye.
    """
    fermees = {
        route.callback.__name__
        for route in routes_espace
        if getattr(route.callback, "exige_abonnement", False)
    }
    assert fermees == EXIGENT_UN_ABONNEMENT


def test_un_inscrit_sans_paiement_lit_quand_meme_son_etat() -> None:
    """Contre-epreuve : la porte est fermee, pas murée.

    `moi` doit repondre — c'est elle qui apprend a l'interface qu'il faut
    payer. La fermer aurait donne un espace blanc sans explication.
    """
    inscrit = Inscrit()
    reponse = Client().get("/api/espace/moi/", headers=inscrit.entetes)

    assert reponse.status_code == 200
    assert reponse.json()["abonnement"] is None


# ── 2. Qui a paye entre, et y reste ──────────────────────────────────────────


def test_un_abonne_actif_n_est_jamais_bloque() -> None:
    """Contre-epreuve indispensable : le correctif ne doit rien casser."""
    inscrit = Inscrit()
    services.souscrire(inscrit.organisation, formule())

    reponse = Client().get("/api/espace/livrables/", headers=inscrit.entetes)
    assert reponse.status_code == 200


def test_un_resilie_garde_l_acces_a_ses_credits_achetes() -> None:
    """Le cas qui a fait corriger mon premier critere.

    J'avais ecrit « abonnement ACTIF » ; ce test echouait, et il avait raison.
    Des credits ACHETES sont perennes par construction — les encaisser puis en
    interdire l'usage serait une vente non honoree.
    """
    inscrit = Inscrit()
    services.souscrire(inscrit.organisation, formule())
    credits.crediter(
        inscrit.organisation, 2, type_mouvement=TypeMouvement.ACHAT,
        reference="achat-de-test", motif="Achat de credits supplementaires.",
    )
    services.resilier(inscrit.organisation, motif="Test.")

    assert AbonnementOrganisation.objects.filter(
        organisation=inscrit.organisation, statut=StatutAbonnement.ACTIF
    ).count() == 0

    reponse = Client().get("/api/espace/livrables/", headers=inscrit.entetes)
    assert reponse.status_code == 200, "un resilie perd l'usage de ce qu'il a achete"


def test_une_organisation_dotee_a_la_main_entre_sans_abonnement() -> None:
    """Geste commercial, depannage, compte de demonstration.

    Aucun abonnement, mais quelqu'un a decide qu'elle recoive quelque chose.
    """
    inscrit = Inscrit()
    credits.crediter(
        inscrit.organisation, 1, type_mouvement=TypeMouvement.GESTE,
        reference="geste-de-test", motif="Geste commercial.",
    )

    reponse = Client().get("/api/espace/livrables/", headers=inscrit.entetes)
    assert reponse.status_code == 200


# ── 3. Le webhook refuse ce qu'il ne peut pas prouver ────────────────────────


@override_settings(STRIPE_WEBHOOK_SECRET="")
def test_sans_secret_configure_le_webhook_refuse_tout() -> None:
    """LE test de securite de ce fichier. Fail-closed, jamais fail-open.

    `integrations.webhooks.is_webhook_authorized` rend `True` quand aucun secret
    n'est configure. Reprendre cette logique ici aurait voulu dire : « personne
    n'a encore branche Stripe, donc j'accepte que n'importe qui declare un
    paiement ». C'est la regle 1 exactement a l'envers, et le prix se compte en
    etudes livrees gratuitement.
    """
    inscrit = Inscrit()
    charge = evenement_session(str(inscrit.organisation.id), "pro", "sub_test")
    formule()

    reponse = poster_evenement(charge)

    assert reponse.status_code == 503
    assert not AbonnementOrganisation.objects.filter(
        organisation=inscrit.organisation
    ).exists()


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_une_signature_invalide_ne_cree_aucun_abonnement() -> None:
    inscrit = Inscrit()
    formule()
    charge = evenement_session(str(inscrit.organisation.id), "pro", "sub_test")

    reponse = poster_evenement(charge, signature="t=1,v1=deadbeef")

    assert reponse.status_code == 400
    assert not AbonnementOrganisation.objects.filter(
        organisation=inscrit.organisation
    ).exists()


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_une_signature_absente_est_refusee() -> None:
    inscrit = Inscrit()
    formule()
    charge = evenement_session(str(inscrit.organisation.id), "pro", "sub_test")

    reponse = poster_evenement(charge, signature="")

    assert reponse.status_code == 400


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_un_evenement_vieux_de_plus_d_une_heure_est_refuse() -> None:
    """Anti-rejeu : une charge authentique capturee ailleurs ne doit pas servir.

    C'est la raison pour laquelle la signature Stripe porte un horodatage, et la
    raison pour laquelle un simple jeton partage n'aurait rien protege ici.
    """
    inscrit = Inscrit()
    formule()
    charge = evenement_session(str(inscrit.organisation.id), "pro", "sub_test")
    corps = json.dumps(charge).encode("utf-8")
    vieux = int(time.time()) - 7200
    empreinte = hmac.new(
        SECRET_WEBHOOK.encode("utf-8"),
        f"{vieux}.".encode() + corps,
        hashlib.sha256,
    ).hexdigest()

    reponse = Client().post(
        "/webhooks/stripe/", data=corps, content_type="application/json",
        headers={"Stripe-Signature": f"t={vieux},v1={empreinte}"},
    )

    assert reponse.status_code == 400


# ── 4. Un paiement dote une fois, et une seule ───────────────────────────────


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_une_session_terminee_ouvre_l_abonnement_et_dote() -> None:
    inscrit = Inscrit()
    offre = formule()

    reponse = poster_evenement(
        evenement_session(str(inscrit.organisation.id), offre.code, "sub_abc")
    )

    assert reponse.status_code == 200
    abonnement = AbonnementOrganisation.objects.get(
        organisation=inscrit.organisation, statut=StatutAbonnement.ACTIF
    )
    assert abonnement.reference_paiement == "sub_abc"
    assert credits.solde(inscrit.organisation) == offre.credits_par_echeance

    # Et la porte s'ouvre reellement — c'est le document livre qui compte,
    # pas l'etat en base (regle 7, transposee).
    assert Client().get(
        "/api/espace/livrables/", headers=inscrit.entetes
    ).status_code == 200


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_le_rejeu_du_meme_evenement_ne_dote_pas_deux_fois() -> None:
    """Premiere barriere : la deduplication par identifiant d'evenement."""
    inscrit = Inscrit()
    offre = formule()
    charge = evenement_session(str(inscrit.organisation.id), offre.code, "sub_abc")

    premiere = poster_evenement(charge)
    seconde = poster_evenement(charge)

    assert premiere.status_code == 200
    assert seconde.status_code == 200
    assert seconde.json()["doublon"] is True
    assert credits.solde(inscrit.organisation) == offre.credits_par_echeance
    assert MouvementCredit.objects.filter(
        portefeuille__organisation=inscrit.organisation,
        type=TypeMouvement.DOTATION,
    ).count() == 1


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_deux_evenements_differents_pour_un_seul_paiement_ne_dotent_pas_deux_fois() -> None:
    """Seconde barriere, et la plus subtile.

    Stripe envoie DEUX evenements pour une premiere souscription —
    `checkout.session.completed` et `invoice.paid` — avec deux identifiants
    differents. La deduplication par identifiant ne les rapproche donc pas.

    Sans `assurer_abonnement`, chacun appellerait `services.souscrire`, qui cree
    un NOUVEL abonnement a chaque fois. Or la cle d'idempotence des credits est
    `f"{abonnement_id}:{periode}"` : deux abonnements, deux cles, deux
    dotations. Un paiement, deux fois les credits.
    """
    inscrit = Inscrit()
    offre = formule()
    organisation_id = str(inscrit.organisation.id)

    poster_evenement(evenement_session(organisation_id, offre.code, "sub_abc"))
    poster_evenement(evenement_facture(organisation_id, offre.code, "sub_abc"))

    assert credits.solde(inscrit.organisation) == offre.credits_par_echeance
    assert AbonnementOrganisation.objects.filter(
        organisation=inscrit.organisation
    ).count() == 1


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_l_ordre_d_arrivee_des_deux_evenements_est_indifferent() -> None:
    """Stripe ne garantit pas l'ordre. Le resultat doit etre le meme."""
    inscrit = Inscrit()
    offre = formule()
    organisation_id = str(inscrit.organisation.id)

    poster_evenement(evenement_facture(organisation_id, offre.code, "sub_xyz"))
    poster_evenement(evenement_session(organisation_id, offre.code, "sub_xyz"))

    assert credits.solde(inscrit.organisation) == offre.credits_par_echeance
    assert AbonnementOrganisation.objects.filter(
        organisation=inscrit.organisation
    ).count() == 1


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_un_paiement_pour_une_organisation_inconnue_n_explose_pas() -> None:
    """Authentique mais inexploitable : on repond 200 et on ouvre un incident.

    Repondre 500 ferait retenter Stripe pendant trois jours un evenement qui ne
    passera jamais. Se taire perdrait un paiement en silence.
    """
    from monitoring.models import OperationalIncident

    formule()
    reponse = poster_evenement(
        evenement_session(str(uuid.uuid4()), "pro", "sub_fantome")
    )

    assert reponse.status_code == 200
    assert reponse.json()["traite"] is False
    assert OperationalIncident.objects.filter(
        title="Evenement Stripe inexploitable"
    ).exists()


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_la_resiliation_prononcee_par_stripe_arrete_la_dotation() -> None:
    """L'argent ne rentre plus, la dotation mensuelle doit s'arreter.

    Sans cela, la tache horaire `appliquer_echeances` continuerait de doter un
    abonnement que Stripe ne preleve plus — elle ne regarde que le statut.
    """
    inscrit = Inscrit()
    offre = formule()
    organisation_id = str(inscrit.organisation.id)
    poster_evenement(evenement_session(organisation_id, offre.code, "sub_fin"))

    reponse = poster_evenement({
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_fin"}},
    })

    assert reponse.status_code == 200
    assert not AbonnementOrganisation.objects.filter(
        organisation=inscrit.organisation, statut=StatutAbonnement.ACTIF
    ).exists()


# ── 5. Ouvrir le paiement ────────────────────────────────────────────────────


@override_settings(STRIPE_SECRET_KEY="sk_test_x", EVKHA_APP_URL="https://exemple.fr")
def test_le_montant_ne_vient_jamais_du_navigateur(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """On ne lit qu'un CODE de formule ; le prix est celui du tarif Stripe.

    Accepter un montant depuis le client reviendrait a laisser choisir combien
    payer. Ce test le verifie par ce qui part chez Stripe, pas par ce que la
    vue promet.
    """
    inscrit = Inscrit()
    offre = formule(tarif_stripe="price_verrouille")
    vus: dict[str, Any] = {}

    def faux_create(**kwargs: Any) -> dict[str, Any]:
        vus.update(kwargs)
        return {"url": "https://checkout.stripe.com/c/pay/session"}

    monkeypatch.setattr(stripe.checkout.Session, "create", faux_create)

    reponse = Client().post(
        "/api/espace/paiement/",
        data=json.dumps({
            "formule": offre.code,
            "prix_mensuel_cents": 1,
            "montant": 1,
            "line_items": [{"price": "price_a_moi", "quantity": 1}],
        }),
        content_type="application/json",
        headers=inscrit.entetes,
    )

    assert reponse.status_code == 200
    assert vus["line_items"] == [{"price": "price_verrouille", "quantity": 1}]
    assert vus["mode"] == "subscription"
    # L'organisation voyage AUSSI dans les metadonnees de l'abonnement, sans
    # quoi les factures des mois suivants n'auraient plus a qui etre imputees.
    assert vus["subscription_data"]["metadata"]["organisation_id"] == str(
        inscrit.organisation.id
    )


@override_settings(STRIPE_SECRET_KEY="sk_test_x", EVKHA_APP_URL="https://exemple.fr")
def test_une_formule_sans_tarif_stripe_est_refusee_lisiblement() -> None:
    """Regle 1 : on echoue bruyamment plutot que d'ouvrir un paiement vide."""
    inscrit = Inscrit()
    offre = formule(code="sans-tarif", tarif_stripe="")

    reponse = Client().post(
        "/api/espace/paiement/",
        data=json.dumps({"formule": offre.code}),
        content_type="application/json",
        headers=inscrit.entetes,
    )

    assert reponse.status_code == 503
    assert reponse.json()["code"] == "paiement_indisponible"


@override_settings(STRIPE_SECRET_KEY="", EVKHA_APP_URL="https://exemple.fr")
def test_sans_cle_stripe_le_paiement_refuse_au_lieu_de_partir_anonyme() -> None:
    inscrit = Inscrit()
    offre = formule()

    reponse = Client().post(
        "/api/espace/paiement/",
        data=json.dumps({"formule": offre.code}),
        content_type="application/json",
        headers=inscrit.entetes,
    )

    assert reponse.status_code == 503


@override_settings(STRIPE_SECRET_KEY="sk_test_x", EVKHA_APP_URL="https://exemple.fr")
def test_un_abonne_actif_ne_peut_pas_souscrire_une_seconde_fois() -> None:
    """Sans ce refus, un abonne se retrouverait preleve deux fois."""
    inscrit = Inscrit()
    offre = formule()
    services.souscrire(inscrit.organisation, offre)

    reponse = Client().post(
        "/api/espace/paiement/",
        data=json.dumps({"formule": offre.code}),
        content_type="application/json",
        headers=inscrit.entetes,
    )

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "deja_abonne"
