"""Payer une etude sur evkha.fr ouvre un espace, et un seul credit.

C'est le parcours du public direct, celui des quatre boutons de
`evkha.fr/etudedemarche` : cliquer, payer, entrer, ecrire son brief. Personne
ne s'inscrit avant, personne ne saisit de mot de passe, et personne ne recoit
de formulaire externe a remplir.

## Ce que le code d'avant faisait

Rien. C'est le sujet meme de ces tests : apres le paiement, la plateforme
n'ouvrait aucun compte, ne versait aucun credit et n'envoyait rien. L'argent
etait pris chez le prestataire et le parcours s'arretait la.

Chacun de ces tests echoue donc sur le code d'avant (regle 6) — la plupart a
l'import, `paiement.achats` n'existant pas.

## Ce qu'ils refusent de laisser revenir

1. Un paiement encaisse qui ne produit ni compte ni credit.
2. Un versement double, parce que le webhook et la page de retour se croisent.
   Stripe rejoue ses evenements pendant trois jours, et la page de retour peut
   etre rafraichie a volonte.
3. Une session NON PAYEE qui livrerait quand meme — l'identifiant arrive par
   l'adresse de retour, donc de l'exterieur.
4. Un second achat qui ouvrirait un second espace, laissant la personne avec
   deux historiques et un credit dans celui ou elle n'est pas connectee.
5. Un acheteur a l'unite a qui l'on proposerait de souscrire, de changer de
   formule ou d'acheter des credits — trois gestes qui supposent une formule,
   donc un tarif, qu'il n'a pas.

Et la contre-epreuve, sans laquelle le point 5 n'aurait aucune valeur : une
ABONNEE passe toujours par ces memes routes.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.test import Client
from paiement import achats

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from organisations import credits
from organisations.authentification import creer_compte, ouvrir_session
from organisations.models import (
    CompteClient,
    Encaissement,
    MembreOrganisation,
    MouvementCredit,
    Organisation,
    TypeDeCompte,
    TypeMouvement,
)
from tests.aides_abonnement import abonner

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"
ACHETEUSE = "porteuse.de.projet@example.com"


def offre_a_l_unite(prix: int = 14_900) -> Offer:
    return Offer.objects.create(
        name="Étude de marché",
        slug=f"etude-marche-{uuid.uuid4().hex[:8]}",
        deliverable_type=DeliverableType.MARKET_STUDY,
        prix_unitaire_cents=prix,
        is_active=True,
    )


def session_stripe(
    offre: Offer,
    *,
    email: str = ACHETEUSE,
    payee: bool = True,
    identifiant: str = "",
) -> dict[str, Any]:
    """Une session Checkout telle que Stripe la rend, reduite a ce qu'on lit."""
    return {
        "id": identifiant or f"cs_test_{uuid.uuid4().hex[:16]}",
        "status": "complete",
        "payment_status": "paid" if payee else "unpaid",
        "amount_total": offre.prix_unitaire_cents,
        "currency": "eur",
        "customer_details": {"email": email, "name": "Camille Porteuse"},
        "metadata": {"achat": "livrable", "offre_slug": offre.slug},
    }


# ── 1. Ce qu'un paiement produit ─────────────────────────────────────────────


def test_un_paiement_ouvre_un_espace_et_verse_un_credit() -> None:
    offre = offre_a_l_unite()

    achat = achats.livrer_l_achat(session_stripe(offre))

    assert achat.nouveau is True
    assert achat.organisation.type_de_compte == TypeDeCompte.A_L_UNITE
    assert credits.solde(achat.organisation) == 1
    assert CompteClient.objects.filter(
        customer__email=ACHETEUSE
    ).exists(), "sans compte de connexion, l'acheteuse ne peut pas entrer"


def test_le_credit_verse_est_un_ACHAT_et_non_une_dotation() -> None:
    """Une dotation EXPIRE en fin de periode.

    Quelqu'un qui achete son etude le 30 verrait son credit disparaitre le 31,
    apres avoir paye : `credits.ENTREES_PERENNES` distingue les deux natures et
    seul `ACHAT` survit a l'expiration.
    """
    offre = offre_a_l_unite()
    achat = achats.livrer_l_achat(session_stripe(offre))

    mouvement = MouvementCredit.objects.get(
        portefeuille__organisation=achat.organisation
    )
    assert mouvement.type == TypeMouvement.ACHAT


def test_le_paiement_apparait_au_chiffre_d_affaires_reel() -> None:
    """Sans encaissement, l'argent percu est invisible de la supervision."""
    offre = offre_a_l_unite(prix=8_900)
    achat = achats.livrer_l_achat(session_stripe(offre))

    encaissement = Encaissement.objects.get(organisation=achat.organisation)
    assert encaissement.montant_cents == 8_900


# ── 2. Le webhook et la page de retour se croisent ───────────────────────────


def test_rejouer_la_meme_session_ne_credite_pas_deux_fois() -> None:
    offre = offre_a_l_unite()
    session = session_stripe(offre)

    premier = achats.livrer_l_achat(session)
    second = achats.livrer_l_achat(session)

    assert premier.nouveau is True
    assert second.nouveau is False, "le second appel doit se declarer sans effet"
    assert second.organisation.id == premier.organisation.id
    assert credits.solde(premier.organisation) == 1
    assert Encaissement.objects.count() == 1, (
        "deux encaissements pour un paiement gonfleraient le chiffre d'affaires"
    )


# ── 3. Ce que le navigateur pretend ne prouve rien ───────────────────────────


def test_une_session_non_payee_ne_livre_rien() -> None:
    offre = offre_a_l_unite()

    with pytest.raises(achats.AchatInexploitable):
        achats.livrer_l_achat(session_stripe(offre, payee=False))

    assert not Organisation.objects.exists()
    assert not MouvementCredit.objects.exists()


def test_une_session_sans_adresse_ne_livre_rien() -> None:
    """Sans adresse, le paiement n'est rattachable a personne.

    Echouer bruyamment vaut mieux qu'ouvrir un espace anonyme que son
    proprietaire ne retrouvera jamais (regle 1).
    """
    offre = offre_a_l_unite()
    session = session_stripe(offre)
    session["customer_details"] = {}

    with pytest.raises(achats.AchatInexploitable):
        achats.livrer_l_achat(session)


def test_une_offre_inconnue_ne_livre_rien() -> None:
    offre = offre_a_l_unite()
    session = session_stripe(offre)
    session["metadata"] = {"achat": "livrable", "offre_slug": "offre-qui-n-existe-pas"}

    with pytest.raises(achats.AchatInexploitable):
        achats.livrer_l_achat(session)


# ── 4. Deux achats, un seul espace ───────────────────────────────────────────


def test_un_second_achat_credite_l_espace_existant() -> None:
    premiere = offre_a_l_unite()
    seconde = offre_a_l_unite(prix=18_500)

    un = achats.livrer_l_achat(session_stripe(premiere))
    deux = achats.livrer_l_achat(session_stripe(seconde))

    assert deux.organisation.id == un.organisation.id, (
        "un second espace laisserait la personne avec deux historiques"
    )
    assert credits.solde(un.organisation) == 2
    assert Organisation.objects.count() == 1


def test_une_abonnee_qui_achete_a_l_unite_reste_abonnee() -> None:
    """Acheter une etude en plus de sa dotation ne declasse pas un compte."""
    contact = Customer.objects.create(email=ACHETEUSE)
    from organisations import services  # noqa: PLC0415

    organisation = services.creer_organisation(
        raison_sociale="Agence Partenaire", contact=contact
    )
    abonner(organisation)

    achat = achats.livrer_l_achat(session_stripe(offre_a_l_unite()))

    assert achat.organisation.id == organisation.id
    assert achat.organisation.type_de_compte == TypeDeCompte.ABONNE
    assert credits.solde(organisation) == 1


# ── 5. Ce qu'un compte a l'unite n'a pas le droit de faire ───────────────────

#: Les cinq gestes qui supposent une formule, donc un tarif.
ROUTES_D_ABONNE: tuple[tuple[str, dict[str, Any]], ...] = (
    ("/api/espace/paiement/", {"formule": "pro"}),
    ("/api/espace/credits/acheter/", {"quantite": 2}),
    ("/api/espace/abonnement/arreter/", {}),
    ("/api/espace/abonnement/reprendre/", {}),
    ("/api/espace/abonnement/formule/", {"formule": "pro"}),
)


def _espace_de(type_de_compte: str) -> tuple[Client, Organisation]:
    from organisations import services  # noqa: PLC0415

    contact = Customer.objects.create(email=f"{uuid.uuid4().hex[:8]}@example.com")
    organisation = services.creer_organisation(
        raison_sociale="Espace de test", contact=contact
    )
    organisation.type_de_compte = type_de_compte
    organisation.save(update_fields=["type_de_compte"])
    if type_de_compte == TypeDeCompte.ABONNE:
        abonner(organisation)

    creer_compte(contact, mot_de_passe=MOT_DE_PASSE)
    jeton, _ = ouvrir_session(contact.email, MOT_DE_PASSE)
    client = Client(HTTP_AUTHORIZATION=f"Bearer {jeton}")
    return client, organisation


@pytest.mark.parametrize(("route", "corps"), ROUTES_D_ABONNE)
def test_un_compte_a_l_unite_est_refuse_sur_les_routes_d_abonnement(
    route: str, corps: dict[str, Any]
) -> None:
    client, _ = _espace_de(TypeDeCompte.A_L_UNITE)

    reponse = client.post(route, data=corps, content_type="application/json")

    assert reponse.status_code == 409, (
        f"{route} doit refuser un compte a l'unite, obtenu {reponse.status_code}"
    )
    assert reponse.json()["code"] == "compte_a_l_unite"


@pytest.mark.parametrize(("route", "corps"), ROUTES_D_ABONNE)
def test_contre_epreuve_une_abonnee_n_est_pas_refusee_pour_son_type(
    route: str, corps: dict[str, Any]
) -> None:
    """Le refus vise le TYPE de compte, et rien d'autre.

    Sans cette contre-epreuve, un decorateur qui refuserait tout le monde
    passerait le test precedent avec les honneurs (regle 6).
    """
    client, _ = _espace_de(TypeDeCompte.ABONNE)

    reponse = client.post(route, data=corps, content_type="application/json")

    assert reponse.status_code != 409 or reponse.json().get("code") != "compte_a_l_unite"


def test_un_compte_a_l_unite_garde_l_acces_a_ses_livrables() -> None:
    """La restriction ferme l'abonnement, PAS l'espace.

    Fermer la lecture reprendrait ce qui est livre — le defaut corrige le
    06/08/2026 sur la barriere de paiement, qu'on ne va pas reintroduire par
    une autre porte.
    """
    client, _ = _espace_de(TypeDeCompte.A_L_UNITE)

    for route in ("/api/espace/moi/", "/api/espace/livrables/", "/api/espace/credits/"):
        assert client.get(route).status_code == 200, route


def test_le_type_de_compte_est_expose_a_l_interface() -> None:
    """Sans lui, le menu ne peut pas eviter d'afficher une porte qui se ferme."""
    client, _ = _espace_de(TypeDeCompte.A_L_UNITE)

    charge = client.get("/api/espace/moi/").json()

    assert charge["organisation"]["type_de_compte"] == TypeDeCompte.A_L_UNITE


# ── 6. Le catalogue public ───────────────────────────────────────────────────


def test_le_catalogue_public_ne_montre_que_ce_qui_se_vend_seul() -> None:
    vendable = offre_a_l_unite()
    Offer.objects.create(
        name="Abonnement Pro", slug="abonnement-pro-test",
        deliverable_type="", prix_unitaire_cents=0, is_subscription=True,
    )

    charge = Client().get("/api/public/livrables/").json()

    slugs = {ligne["slug"] for ligne in charge["livrables"]}
    assert slugs == {vendable.slug}


def test_le_prix_affiche_vient_de_la_table() -> None:
    """Une page qui annonce 149 EUR et un paiement qui prend 189 est le pire
    defaut possible sur ce parcours. Un seul endroit porte le tarif (regle 5).
    """
    offre = offre_a_l_unite(prix=19_500)

    charge = Client().get("/api/public/livrables/").json()

    assert charge["livrables"][0]["prix_cents"] == 19_500
    assert charge["livrables"][0]["prix_cents"] == offre.prix_unitaire_cents


def test_acheter_une_offre_inconnue_est_refuse() -> None:
    reponse = Client().post(
        "/api/public/acheter/",
        data={"livrable": "offre-qui-n-existe-pas"},
        content_type="application/json",
    )

    assert reponse.status_code == 404
    assert reponse.json()["code"] == "livrable_inconnu"


def test_acheter_une_offre_sans_tarif_est_refuse() -> None:
    """Une offre a zero euro ouvrirait un paiement de zero euro.

    Elle serait acceptee par Stripe, produirait un credit, et livrerait une
    etude a plusieurs euros de cout de production sans contrepartie.
    """
    Offer.objects.create(
        name="Étude sans tarif", slug="etude-sans-tarif",
        deliverable_type=DeliverableType.MARKET_STUDY, prix_unitaire_cents=0,
    )

    reponse = Client().post(
        "/api/public/acheter/",
        data={"livrable": "etude-sans-tarif"},
        content_type="application/json",
    )

    assert reponse.status_code == 404


def test_le_membre_de_l_espace_est_bien_la_proprietaire() -> None:
    achat = achats.livrer_l_achat(session_stripe(offre_a_l_unite()))

    membre = MembreOrganisation.objects.get(organisation=achat.organisation)
    assert membre.customer.email == ACHETEUSE


# ── 7. L'inscription depuis la page « Nos etudes » ───────────────────────────
#
# Le visiteur cree son compte AVANT de payer, comme sur la page partenaires.
# Le compte doit donc naitre « a l'unite » : entre l'inscription et le retour
# de Stripe, la personne est deja dans son espace, et elle y verrait sinon un
# menu « Abonnement » que le serveur lui refuse.


def _inscrire(**extras: Any) -> Any:
    corps = {
        "raison_sociale": "Atelier de test",
        "email": f"{uuid.uuid4().hex[:8]}@example.com",
        "mot_de_passe": "un-mot-de-passe-solide-2026",
        **extras,
    }
    return Client().post(
        "/api/public/inscription/", data=corps, content_type="application/json"
    )


def test_s_inscrire_pour_une_etude_ouvre_un_compte_a_l_unite() -> None:
    offre = offre_a_l_unite()

    reponse = _inscrire(livrable=offre.slug)

    assert reponse.status_code == 201, reponse.content
    charge = reponse.json()
    assert charge["livrable_demande"] == offre.slug, (
        "sans ce rappel, l'interface ne sait pas vers quel paiement enchainer"
    )
    organisation = Organisation.objects.get(id=charge["organisation"]["id"])
    assert organisation.type_de_compte == TypeDeCompte.A_L_UNITE


def test_contre_epreuve_une_inscription_sans_etude_reste_un_compte_d_abonne() -> None:
    """Sans cette contre-epreuve, marquer TOUS les comptes « a l'unite »
    passerait le test precedent avec les honneurs (regle 6).
    """
    reponse = _inscrire()

    assert reponse.status_code == 201, reponse.content
    charge = reponse.json()
    assert charge["livrable_demande"] is None
    organisation = Organisation.objects.get(id=charge["organisation"]["id"])
    assert organisation.type_de_compte == TypeDeCompte.ABONNE


def test_s_inscrire_pour_une_etude_ne_credite_RIEN() -> None:
    """Le compte existe, l'etude n'est pas payee : aucun credit.

    C'est le defaut que la barriere de paiement a ferme le 06/08/2026, et il
    reviendrait par cette porte-ci si l'inscription creditait : n'importe qui
    obtiendrait un livrable a plusieurs euros de production en remplissant un
    formulaire.
    """
    offre = offre_a_l_unite()

    reponse = _inscrire(livrable=offre.slug)

    organisation = Organisation.objects.get(id=reponse.json()["organisation"]["id"])
    assert credits.solde(organisation) == 0


def test_une_etude_inconnue_refuse_l_inscription() -> None:
    """L'adresse se retouche a la main : un slug invente ne doit pas ouvrir un
    compte sur rien.
    """
    reponse = _inscrire(livrable="etude-qui-n-existe-pas")

    assert reponse.status_code == 404
    assert reponse.json()["code"] == "livrable_introuvable"
    assert not Organisation.objects.exists()


def test_le_paiement_credite_le_compte_deja_ouvert_par_l_inscription() -> None:
    """Bout en bout : inscription, puis retour de Stripe sur la MEME adresse.

    Un second espace laisserait la personne avec deux historiques et son
    credit dans celui ou elle n'est pas connectee.
    """
    offre = offre_a_l_unite()
    adresse = f"{uuid.uuid4().hex[:8]}@example.com"
    inscrite = _inscrire(livrable=offre.slug, email=adresse)
    organisation_id = inscrite.json()["organisation"]["id"]

    achat = achats.livrer_l_achat(session_stripe(offre, email=adresse))

    assert str(achat.organisation.id) == organisation_id
    assert achat.organisation.type_de_compte == TypeDeCompte.A_L_UNITE
    assert credits.solde(achat.organisation) == 1
    assert Organisation.objects.count() == 1


# ── 8. Racheter une etude depuis son espace ──────────────────────────────────
#
# Un acheteur a l'unite n'a ni formule ni credits a racheter : les cinq routes
# d'abonnement lui sont fermees. Sans ce chemin-ci, son espace ne lui
# proposerait RIEN — alors que reprendre une etude est le parcours le plus
# frequent du public direct : l'etude de marche, puis le business plan au
# moment d'aller voir la banque.


def test_l_espace_propose_les_etudes_a_l_unite() -> None:
    offre = offre_a_l_unite()
    client, _ = _espace_de(TypeDeCompte.A_L_UNITE)

    charge = client.get("/api/espace/etudes/").json()

    assert [e["slug"] for e in charge["etudes"]] == [offre.slug]
    assert charge["etudes"][0]["prix_cents"] == offre.prix_unitaire_cents


def test_une_offre_sans_tarif_n_est_pas_proposee_au_rachat() -> None:
    """Une offre a zero euro ouvrirait un paiement de zero euro.

    Accepte par Stripe, il produirait un credit et livrerait une etude a
    plusieurs euros de cout de production sans contrepartie.
    """
    Offer.objects.create(
        name="Étude sans tarif", slug="sans-tarif-espace",
        deliverable_type=DeliverableType.MARKET_STUDY, prix_unitaire_cents=0,
    )
    client, _ = _espace_de(TypeDeCompte.A_L_UNITE)

    charge = client.get("/api/espace/etudes/").json()

    assert charge["etudes"] == []


def test_racheter_une_etude_inconnue_est_refuse() -> None:
    client, _ = _espace_de(TypeDeCompte.A_L_UNITE)

    reponse = client.post(
        "/api/espace/etudes/acheter/",
        data={"etude": "etude-qui-n-existe-pas"},
        content_type="application/json",
    )

    assert reponse.status_code == 404
    assert reponse.json()["code"] == "etude_inconnue"


def test_le_rachat_credite_l_organisation_designee_et_non_l_adresse() -> None:
    """L'organisation voyage dans les metadonnees, et elle l'emporte.

    Stripe laisse MODIFIER l'adresse sur sa page de paiement. Un acheteur
    connecte qui la corrige, ou qui paie avec celle de sa societe, verrait
    sinon s'ouvrir un second espace : il aurait paye, tout serait en regle, et
    son credit l'attendrait la ou il ne se connectera jamais.
    """
    offre = offre_a_l_unite()
    _, organisation = _espace_de(TypeDeCompte.A_L_UNITE)
    avant = Organisation.objects.count()

    session = session_stripe(offre, email="adresse.tapee.chez.stripe@example.com")
    session["metadata"]["organisation_id"] = str(organisation.id)
    achat = achats.livrer_l_achat(session)

    assert achat.organisation.id == organisation.id
    assert credits.solde(organisation) == 1
    assert Organisation.objects.count() == avant, (
        "aucun second espace ne doit s'ouvrir quand l'organisation est designee"
    )


def test_une_organisation_designee_mais_disparue_retombe_sur_l_adresse() -> None:
    """Elle a ete supprimee entre l'ouverture du paiement et l'encaissement.

    On ne perd pas l'achat pour autant : le rattachement par adresse reprend
    la main, et le motif part au journal (regle 1 — le dire, pas se taire).
    """
    offre = offre_a_l_unite()
    session = session_stripe(offre)
    session["metadata"]["organisation_id"] = str(uuid.uuid4())

    achat = achats.livrer_l_achat(session)

    assert achat.nouveau is True
    assert credits.solde(achat.organisation) == 1


# ── 9. Un credit paye pour UNE etude ne sert qu'a celle-la ───────────────────
#
# Le prix affiche sur la page de vente cesserait de vouloir dire quoi que ce
# soit si 89 EUR verses pour une etude de concurrence ouvraient une strategie
# a 195 EUR. La regle porte sur le CREDIT et non sur le type de compte : un
# credit type ne sert qu'a son etude, un credit fongible sert a tout.


def _offre(type_livrable: str, prix: int = 14_900) -> Offer:
    return Offer.objects.create(
        name=f"Offre {type_livrable}",
        slug=f"{type_livrable}-{uuid.uuid4().hex[:8]}",
        deliverable_type=type_livrable,
        prix_unitaire_cents=prix,
        is_active=True,
    )


def test_le_credit_achete_porte_l_etude_payee() -> None:
    achat = achats.livrer_l_achat(
        session_stripe(_offre(DeliverableType.COMPETITOR_STUDY, 8_900))
    )

    mouvement = MouvementCredit.objects.get(
        portefeuille__organisation=achat.organisation
    )
    assert mouvement.livrable == DeliverableType.COMPETITOR_STUDY


def test_une_etude_payee_n_en_ouvre_pas_une_autre() -> None:
    """Le defaut que ce verrou existe pour fermer."""
    achat = achats.livrer_l_achat(
        session_stripe(_offre(DeliverableType.COMPETITOR_STUDY, 8_900))
    )

    autorise, motif = credits.peut_commander_ce_livrable(
        achat.organisation, DeliverableType.BUSINESS_STRATEGY
    )

    assert autorise is False
    # Le message NOMME ce qui est commandable : un refus qui ne dit pas quoi
    # faire ensuite envoie chercher un administrateur (regle 2).
    assert "concurrence" in motif.lower()


def test_contre_epreuve_l_etude_payee_reste_commandable() -> None:
    """Sans elle, un verrou qui refuse tout passerait le test precedent."""
    achat = achats.livrer_l_achat(
        session_stripe(_offre(DeliverableType.COMPETITOR_STUDY, 8_900))
    )

    autorise, _ = credits.peut_commander_ce_livrable(
        achat.organisation, DeliverableType.COMPETITOR_STUDY
    )

    assert autorise is True


def test_contre_epreuve_une_abonnee_commande_ce_qu_elle_veut() -> None:
    """Ses dotations sont FONGIBLES : les typer lui reprendrait la souplesse
    qu'elle paie tous les mois.
    """
    contact = Customer.objects.create(email=f"{uuid.uuid4().hex[:8]}@example.com")
    from organisations import services  # noqa: PLC0415

    organisation = services.creer_organisation(
        raison_sociale="Agence", contact=contact
    )
    abonner(organisation)
    credits.crediter(organisation, 3, motif="Dotation du mois")

    for type_livrable in DeliverableType.values:
        autorise, motif = credits.peut_commander_ce_livrable(
            organisation, type_livrable
        )
        assert autorise is True, f"{type_livrable} refuse a une abonnee : {motif}"


def test_un_credit_verse_avant_le_marquage_n_est_pas_bloque() -> None:
    """Il ne dit pas quelle etude il a payee.

    Le traiter comme un droit nul reviendrait a reprendre a quelqu'un ce qu'il
    a regle, sur la foi d'une information que nous n'avons pas conservee.
    """
    contact = Customer.objects.create(email=f"{uuid.uuid4().hex[:8]}@example.com")
    from organisations import services  # noqa: PLC0415

    organisation = services.creer_organisation(
        raison_sociale="Compte ancien", contact=contact
    )
    organisation.type_de_compte = TypeDeCompte.A_L_UNITE
    organisation.save(update_fields=["type_de_compte"])
    # Un credit sans `livrable`, comme ceux d'avant.
    credits.crediter(
        organisation, 1, motif="Achat", type_mouvement=TypeMouvement.ACHAT
    )

    autorise, _ = credits.peut_commander_ce_livrable(
        organisation, DeliverableType.BUSINESS_PLAN
    )

    assert autorise is True


def test_deux_etudes_payees_donnent_deux_droits_distincts() -> None:
    marche = _offre(DeliverableType.MARKET_STUDY, 14_900)
    plan = _offre(DeliverableType.BUSINESS_PLAN, 18_500)

    achat = achats.livrer_l_achat(session_stripe(marche))
    achats.livrer_l_achat(session_stripe(plan))

    droits = credits.droits_par_livrable(achat.organisation)
    assert droits == {
        DeliverableType.MARKET_STUDY: 1,
        DeliverableType.BUSINESS_PLAN: 1,
    }
    for vise in (DeliverableType.MARKET_STUDY, DeliverableType.BUSINESS_PLAN):
        assert credits.peut_commander_ce_livrable(achat.organisation, vise)[0]
    assert not credits.peut_commander_ce_livrable(
        achat.organisation, DeliverableType.BUSINESS_STRATEGY
    )[0]


def test_le_droit_s_epuise_quand_l_etude_est_lancee() -> None:
    """Sans soustraction du debit, un meme credit ouvrirait deux etudes.

    Le droit disparait, et c'est ensuite le SOLDE qui refuse — pas le verrou
    par livrable, qui n'a plus rien a arbitrer. Les deux controles disent des
    choses differentes et ne doivent pas se marcher dessus : « solde
    insuffisant » est la phrase juste pour un portefeuille vide.
    """
    achat = achats.livrer_l_achat(
        session_stripe(_offre(DeliverableType.MARKET_STUDY))
    )

    credits.debiter(
        achat.organisation, 1,
        reference=f"job-{uuid.uuid4().hex[:8]}",
        motif="Génération",
        livrable=DeliverableType.MARKET_STUDY,
    )

    assert credits.droits_par_livrable(achat.organisation) == {}
    assert credits.solde(achat.organisation) == 0
    possible, raison = credits.peut_commander(achat.organisation, 1)
    assert possible is False
    assert "insuffisant" in raison


def test_le_verrou_se_tait_sur_un_portefeuille_vide() -> None:
    """Il arbitre entre des credits TYPES. Sans droit en reserve, rien a dire.

    Repondre « choisissez une etude depuis votre espace » a une abonnee a court
    de credits en milieu de mois decrirait une situation qui n'est pas la
    sienne, et l'enverrait au mauvais endroit (regle 2).
    """
    contact = Customer.objects.create(email=f"{uuid.uuid4().hex[:8]}@example.com")
    from organisations import services  # noqa: PLC0415

    organisation = services.creer_organisation(
        raison_sociale="Portefeuille vide", contact=contact
    )

    autorise, motif = credits.peut_commander_ce_livrable(
        organisation, DeliverableType.MARKET_STUDY
    )

    assert autorise is True
    assert motif == ''


def test_le_catalogue_de_l_espace_ne_couvre_que_l_etude_payee() -> None:
    """L'ecran de commande proposait quatre etudes a qui n'en avait paye
    qu'une : il choisissait, remplissait le questionnaire, et se faisait
    refuser a la fin.
    """
    offre = _offre(DeliverableType.COMPETITOR_STUDY, 8_900)
    contact = Customer.objects.create(email="catalogue.essai@example.com")
    from organisations import services  # noqa: PLC0415

    organisation = services.creer_organisation(
        raison_sociale="Catalogue", contact=contact
    )
    organisation.type_de_compte = TypeDeCompte.A_L_UNITE
    organisation.save(update_fields=["type_de_compte"])
    creer_compte(contact, mot_de_passe=MOT_DE_PASSE)
    jeton, _ = ouvrir_session(contact.email, MOT_DE_PASSE)
    client = Client(HTTP_AUTHORIZATION=f"Bearer {jeton}")

    session = session_stripe(offre, email=contact.email)
    session["metadata"]["organisation_id"] = str(organisation.id)
    achats.livrer_l_achat(session)

    charge = client.get("/api/espace/catalogue/").json()
    couverture = {d["type"]: d["couvert"] for d in charge["documents"]}

    assert couverture[DeliverableType.COMPETITOR_STUDY] is True
    assert couverture[DeliverableType.MARKET_STUDY] is False
    assert couverture[DeliverableType.BUSINESS_PLAN] is False
