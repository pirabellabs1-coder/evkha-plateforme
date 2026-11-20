"""Audit de sécurité du 20/11/2026 sur la vente des formations par Stripe.

Neuf constats, et la règle 4 : quand le défaut est commun aux trois circuits
d'achat — l'étude à l'unité, la boutique, la formation —, le correctif et son
test les couvrent tous les trois.

1. les pages de retour refusent, AVANT tout appel à Stripe, un identifiant qui
   n'a pas la forme d'une session, et portent un plafond commun par adresse ;
2. les achats ouverts depuis l'espace ont un plafond par organisation ;
3. un plafond est compté AVANT l'appel à Stripe : un refus du prestataire
   compte aussi ;
4. ce qui est livré est ce qui a été ouvert : mode, montant, devise ;
5. un rejeu ne modifie plus rien — ni organisation, ni invitation, ni compte ;
6. un accès se retire, il ne s'efface pas ;
7. un remboursement ou une contestation ouvre un incident, sans rien retirer ;
8. les journaux ne portent ni adresse, ni référence entière, ni message brut ;
9. le refus « déjà achetée » nomme l'entrée du menu.

Chaque test a été vu ROUGE sur le code d'avant, et chaque refus a sa
contre-épreuve : le cas voisin légitime passe.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

import pytest
import stripe
from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import Client
from django.test.utils import override_settings
from paiement import abonnements, boutique, formations, stripe_api

from catalog.models import (
    AchatFormation,
    AchatProduit,
    DeliverableType,
    Formation,
    Offer,
    ProduitBoutique,
)
from customers.models import Customer
from monitoring.models import OperationalIncident
from organisations import (
    limitation,
    services,
    vues_boutique,
    vues_espace,
    vues_formations,
    vues_publiques,
)
from organisations.models import (
    CompteClient,
    Encaissement,
    MembreOrganisation,
    Organisation,
    TentativePaiement,
)
from tests.test_achat_de_formation import (
    REGLAGES,
    _courriels_en_doublure,
    _stripe_en_doublure,
    formation_en_vente,
    session_stripe,
)
from tests.test_barriere_de_paiement import SECRET_WEBHOOK, Inscrit, poster_evenement
from tests.test_boutique import produit_en_ligne
from tests.test_boutique import session_stripe as session_de_boutique

pytestmark = pytest.mark.django_db

#: Les trois pages de retour, par nature d'achat (`metadata.achat`).
RETOURS = {
    "formation": "/api/public/formations/retour/",
    "produit": "/api/public/boutique/retour/",
    "livrable": "/api/public/acheter/retour/",
}
ADMIN = "/api/dashboard/formations/"
ESPACE = "/api/espace/formations/"
ESPACE_ACHETER = "/api/espace/formations/acheter/"


def _poster(adresse: str, charge: Any, **plus: Any) -> Any:
    return Client().post(
        adresse, json.dumps(charge), content_type="application/json", **plus
    )


def _offre() -> Offer:
    return Offer.objects.create(
        name="Étude de la concurrence",
        slug=f"etude-concurrence-{uuid.uuid4().hex[:8]}",
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
        prix_unitaire_cents=8_900,
        is_active=True,
    )


def _reference() -> str:
    """Un identifiant qui a la forme d'une session Checkout."""
    return f"cs_test_{uuid.uuid4().hex[:16]}"


def _relectures(monkeypatch: Any, session: dict[str, Any] | None = None) -> list[Any]:
    """Remplace la relecture chez Stripe, et note chaque identifiant qui y PART.

    Sans session à rendre, Stripe « ne connaît pas » l'identifiant.
    """
    parties: list[Any] = []

    def relire(identifiant: Any) -> dict[str, Any]:
        parties.append(identifiant)
        if session is None:
            raise stripe_api.PaiementIndisponible("Ce paiement n'a pas pu être vérifié.")
        return session

    monkeypatch.setattr(stripe_api, "relire_la_session", relire)
    return parties


# ── 1. Les pages de retour ───────────────────────────────────────────────────


@pytest.mark.parametrize("nature", list(RETOURS))
@pytest.mark.parametrize(
    "identifiant",
    [
        "cs_devinee",
        "cs_test_court",
        "pi_3QabcDEF456ghiJKL789",
        "cs_prod_a1b2c3d4e5f6g7h8",
        "cs_test_abc/../v1/customers",
        "cs_test_a1b2c3d4e5f6?expand[]=customer",
        "cs_test_" + "a" * 201,
        "cs_test_a1b2c3d4e5f6\nX-Injecte: 1",
        1234567890123456,
        ["cs_test_a1b2c3d4e5f6g7h8"],
        {"id": "cs_test_a1b2c3d4e5f6g7h8"},
    ],
    ids=[
        "trop_court", "court_apres_le_prefixe", "autre_objet", "autre_mode",
        "chemin", "parametres", "trop_long", "saut_de_ligne", "nombre", "liste",
        "dictionnaire",
    ],
)
def test_un_identifiant_qui_n_a_pas_la_forme_d_une_session_ne_part_pas_chez_stripe(
    monkeypatch: Any, nature: str, identifiant: Any
) -> None:
    """Il arrive par l'adresse de retour, donc de l'extérieur : ce qui n'a pas
    la forme d'une session n'a pas à être présenté au prestataire avec notre clé."""
    parties = _relectures(monkeypatch)

    reponse = _poster(RETOURS[nature], {"session": identifiant})

    assert parties == [], "un identifiant mal formé est parti chez Stripe"
    assert (reponse.status_code, reponse.json()["code"]) == (400, "session_absente")


@pytest.mark.parametrize("nature", list(RETOURS))
@pytest.mark.parametrize("prefixe", ["cs_test_", "cs_live_"])
def test_contre_epreuve_un_identifiant_bien_forme_est_relu_chez_stripe(
    monkeypatch: Any, nature: str, prefixe: str
) -> None:
    """Les deux environnements de Stripe, et la longueur d'un vrai identifiant."""
    identifiant = prefixe + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u1V2w3X4y5Z6a7B8c9"
    parties = _relectures(monkeypatch)

    reponse = _poster(RETOURS[nature], {"session": f"  {identifiant}  "})

    assert parties == [identifiant]
    assert (reponse.status_code, reponse.json()["code"]) == (503, "session_illisible")


def test_le_plafond_des_retours_est_commun_interroge_ET_compte(monkeypatch: Any) -> None:
    """Chaque appel compte, réussi ou non : un script qui présente des
    identifiants au hasard fait relire chacun chez Stripe avec notre clé."""
    parties = _relectures(monkeypatch)
    adresses = list(RETOURS.values())

    codes: list[int] = []
    for tour in range(200):
        # Un identifiant mal formé, puis un bien formé que Stripe ne connaît
        # pas : les deux échecs comptent, sur les trois pages tour à tour.
        identifiant = "cs_devinee" if tour % 2 else _reference()
        reponse = _poster(adresses[tour % 3], {"session": identifiant})
        codes.append(reponse.status_code)
        if reponse.status_code == 429:
            break

    assert codes[-1] == 429, "aucun plafond : deux cents retours ont été acceptés"
    assert reponse.json()["code"] == "trop_de_tentatives"
    assert set(codes[:-1]) == {400, 503}
    from organisations import retours  # noqa: PLC0415

    assert len(codes) - 1 == retours.RETOURS_PAR_HEURE.maximum
    # COMMUN aux trois pages : épuisé sur l'une, il ferme les deux autres, et
    # plus rien ne part chez Stripe.
    avant = len(parties)
    for adresse in adresses:
        assert _poster(adresse, {"session": _reference()}).status_code == 429
    assert len(parties) == avant

    # Contre-épreuve : le plafond tient à l'adresse d'origine, pas au serveur.
    ailleurs = Client(REMOTE_ADDR="203.0.113.9").post(
        adresses[0], json.dumps({"session": _reference()}),
        content_type="application/json",
    )
    assert ailleurs.status_code == 503


@pytest.mark.parametrize("nature", list(RETOURS))
def test_un_identifiant_refuse_n_est_pas_ecrit_dans_les_journaux(
    monkeypatch: Any, caplog: Any, nature: str
) -> None:
    """Un saut de ligne dans l'identifiant fabriquait une fausse ligne de journal."""
    faux = "cs_test_a1b2c3d4e5f6\nERROR faux incident fabrique"
    # Stripe « rendrait » une session de la bonne nature, non payée : sur le
    # code d'avant, la livraison échouait et l'identifiant brut était journalisé.
    _relectures(monkeypatch, {
        "id": faux, "mode": "payment", "payment_status": "unpaid",
        "metadata": {"achat": nature},
    })
    caplog.set_level(logging.DEBUG)

    reponse = _poster(RETOURS[nature], {"session": faux})

    assert reponse.status_code == 400
    assert "faux incident fabrique" not in caplog.text


# ── 2. Le plafond des achats ouverts depuis l'espace ─────────────────────────


def _achat_de_formation_dans_l_espace() -> tuple[str, dict[str, str]]:
    return ESPACE_ACHETER, {"formation": formation_en_vente().slug}


def _achat_de_produit_dans_l_espace() -> tuple[str, dict[str, str]]:
    return "/api/espace/achats/acheter/", {"produit": produit_en_ligne().slug}


def _achat_d_etude_dans_l_espace() -> tuple[str, dict[str, str]]:
    return "/api/espace/etudes/acheter/", {"etude": _offre().slug}


ACHATS_DE_L_ESPACE = [
    _achat_de_formation_dans_l_espace,
    _achat_de_produit_dans_l_espace,
    _achat_d_etude_dans_l_espace,
]


def _plafond_de_l_espace_a_deux(monkeypatch: Any) -> None:
    # `raising=False` : sur le code d'avant le plafond n'existait pas, et le
    # test doit échouer sur le COMPORTEMENT, pas sur un nom absent.
    monkeypatch.setattr(
        vues_espace,
        "OUVERTURES_PAR_ORGANISATION",
        limitation.Plafond("ouvertures-espace-de-test", maximum=2, fenetre_s=3600),
        raising=False,
    )


@override_settings(**REGLAGES)
@pytest.mark.parametrize("cas", ACHATS_DE_L_ESPACE)
def test_les_achats_ouverts_depuis_l_espace_ont_un_plafond_par_organisation(
    monkeypatch: Any, cas: Callable[[], tuple[str, dict[str, str]]]
) -> None:
    """Un compte ouvert gratuitement suffisait à faire créer des sessions de
    paiement sans limite : le plafond par adresse ne couvre que les pages
    publiques."""
    cliente = Inscrit()
    voisine = Inscrit(nom="Cabinet voisin", email="voisine@exemple.fr")
    adresse, charge = cas()
    envois = _stripe_en_doublure(monkeypatch)
    _plafond_de_l_espace_a_deux(monkeypatch)

    reponses = [_poster(adresse, charge, headers=cliente.entetes) for _ in range(3)]

    assert [r.status_code for r in reponses] == [200, 200, 429]
    assert reponses[2].json()["code"] == "trop_de_tentatives"
    assert reponses[2].json()["error"]
    assert len(envois) == 2, "le refus est parti chez Stripe quand même"
    assert TentativePaiement.objects.count() == 2

    # Contre-épreuve : le plafond est celui d'UNE organisation.
    chez_la_voisine = _poster(adresse, charge, headers=voisine.entetes)
    assert chez_la_voisine.status_code == 200, chez_la_voisine.content


@override_settings(**REGLAGES)
def test_le_plafond_de_l_espace_est_commun_aux_trois_achats(monkeypatch: Any) -> None:
    """Un plafond par route se contournerait en changeant de route."""
    cliente = Inscrit()
    _stripe_en_doublure(monkeypatch)
    _plafond_de_l_espace_a_deux(monkeypatch)

    codes = [
        _poster(adresse, charge, headers=cliente.entetes).status_code
        for adresse, charge in (cas() for cas in ACHATS_DE_L_ESPACE)
    ]

    assert codes == [200, 200, 429]


@override_settings(**REGLAGES)
@pytest.mark.parametrize("cas", ACHATS_DE_L_ESPACE)
def test_un_refus_de_stripe_compte_aussi_dans_l_espace(
    monkeypatch: Any, cas: Callable[[], tuple[str, dict[str, str]]]
) -> None:
    cliente = Inscrit()
    adresse, charge = cas()
    _plafond_de_l_espace_a_deux(monkeypatch)
    panne: Any = stripe.APIConnectionError

    def en_panne(**_: Any) -> Any:
        raise panne("hors service")

    monkeypatch.setattr(stripe.checkout.Session, "create", en_panne)

    codes = [
        _poster(adresse, charge, headers=cliente.entetes).status_code for _ in range(3)
    ]

    assert codes == [503, 503, 429]


@override_settings(**REGLAGES)
def test_contre_epreuve_une_demande_refusee_avant_stripe_ne_compte_pas(
    monkeypatch: Any,
) -> None:
    """Une faute de frappe dans un slug ne consomme le quota de personne."""
    cliente = Inscrit()
    adresse, charge = _achat_de_formation_dans_l_espace()
    _stripe_en_doublure(monkeypatch)
    _plafond_de_l_espace_a_deux(monkeypatch)

    for _ in range(5):
        inconnue = _poster(adresse, {"formation": "inconnue"}, headers=cliente.entetes)
        assert inconnue.status_code == 404

    assert _poster(adresse, charge, headers=cliente.entetes).status_code == 200


# ── 3. Compter avant d'appeler ───────────────────────────────────────────────


def _ouverture_publique_de_formation() -> tuple[str, dict[str, str], limitation.Plafond]:
    return (
        "/api/public/formations/acheter/",
        {"formation": formation_en_vente().slug},
        vues_formations.ACHATS_PAR_HEURE,
    )


def _ouverture_publique_de_produit() -> tuple[str, dict[str, str], limitation.Plafond]:
    return (
        "/api/public/boutique/acheter/",
        {"produit": produit_en_ligne().slug},
        vues_boutique.ACHATS_PAR_HEURE,
    )


def _ouverture_publique_d_etude() -> tuple[str, dict[str, str], limitation.Plafond]:
    return (
        "/api/public/acheter/",
        {"livrable": _offre().slug},
        vues_publiques.PAIEMENTS_PAR_HEURE,
    )


OUVERTURES_PUBLIQUES = [
    _ouverture_publique_de_formation,
    _ouverture_publique_de_produit,
    _ouverture_publique_d_etude,
]


def _compte(plafond: limitation.Plafond, identifiant: str = "127.0.0.1") -> int:
    """Le compteur lu dans le cache, sans passer par `depasse`."""
    from django.core.cache import cache  # noqa: PLC0415

    return int(cache.get(plafond.cle(identifiant)) or 0)


@override_settings(**REGLAGES)
@pytest.mark.parametrize("cas", OUVERTURES_PUBLIQUES)
def test_une_ouverture_que_stripe_refuse_est_comptee(
    monkeypatch: Any, cas: Callable[[], tuple[str, dict[str, str], limitation.Plafond]]
) -> None:
    """Compté APRÈS l'appel, le plafond ne voyait ni les refus du prestataire
    ni les requêtes parties ensemble : chacune lisait zéro."""
    adresse, charge, plafond = cas()
    panne: Any = stripe.APIConnectionError

    def en_panne(**_: Any) -> Any:
        raise panne("hors service")

    monkeypatch.setattr(stripe.checkout.Session, "create", en_panne)

    reponse = _poster(adresse, charge)

    assert reponse.status_code == 503
    assert _compte(plafond) == 1


@override_settings(**REGLAGES)
@pytest.mark.parametrize("cas", OUVERTURES_PUBLIQUES)
def test_le_compteur_est_ecrit_AVANT_que_stripe_ne_reponde(
    monkeypatch: Any, cas: Callable[[], tuple[str, dict[str, str], limitation.Plafond]]
) -> None:
    """Vu de l'intérieur de l'appel : c'est ce que lirait une requête parallèle."""
    adresse, charge, plafond = cas()
    vus: list[int] = []

    def faux_create(**_: Any) -> dict[str, Any]:
        vus.append(_compte(plafond))
        return {"id": "cs_test_ouverte", "url": "https://checkout.stripe.com/c/pay/x"}

    monkeypatch.setattr(stripe.checkout.Session, "create", faux_create)

    reponse = _poster(adresse, charge)

    assert reponse.status_code == 200, reponse.content
    assert vus == [1]
    # Contre-épreuve : une ouverture réussie n'est comptée qu'UNE fois.
    assert _compte(plafond) == 1


@override_settings(**REGLAGES)
@pytest.mark.parametrize("cas", OUVERTURES_PUBLIQUES)
def test_contre_epreuve_un_slug_inconnu_n_est_pas_compte(
    monkeypatch: Any, cas: Callable[[], tuple[str, dict[str, str], limitation.Plafond]]
) -> None:
    adresse, charge, plafond = cas()
    _stripe_en_doublure(monkeypatch)

    reponse = _poster(adresse, dict.fromkeys(charge, "inconnu"))

    assert reponse.status_code == 404
    assert _compte(plafond) == 0


# ── 4. Ce qui est livré est ce qui a été ouvert ──────────────────────────────


def _cas_formation() -> tuple[Any, dict[str, Any], Callable[[dict[str, Any]], Any]]:
    formation = formation_en_vente()
    return formation, session_stripe(formation), formations.livrer_la_formation


def _cas_produit() -> tuple[Any, dict[str, Any], Callable[[dict[str, Any]], Any]]:
    produit = produit_en_ligne()
    return produit, session_de_boutique(produit), boutique.livrer_le_produit


LIVRAISONS = [_cas_formation, _cas_produit]


def _rien_n_est_livre() -> None:
    assert AchatFormation.objects.count() == 0
    assert AchatProduit.objects.count() == 0
    assert Organisation.objects.count() == 0
    assert Encaissement.objects.count() == 0
    assert CompteClient.objects.count() == 0


def _noter(objet: Any, reference: str) -> None:
    """Le panier tel que l'ouverture du paiement l'enregistre."""
    ouverte = stripe_api.SessionOuverte(reference, "https://checkout.test/x")
    if isinstance(objet, Formation):
        formations.noter_la_tentative(session=ouverte, formation=objet)
    else:
        boutique.noter_la_tentative(session=ouverte, produit=objet)


def _changer_le_prix(objet: Any, prix_cents: int) -> None:
    modele = Formation if isinstance(objet, Formation) else ProduitBoutique
    modele.objects.filter(pk=objet.pk).update(prix_cents=prix_cents)


@pytest.mark.parametrize("cas", LIVRAISONS)
@pytest.mark.parametrize("mode", ["subscription", "setup", "", None])
def test_une_session_qui_n_est_pas_un_paiement_unique_ne_livre_rien(
    cas: Callable[[], Any], mode: Any
) -> None:
    """Une session d'abonnement dont les métadonnées diraient « formation »
    ouvrirait l'accès pour le prix d'une première mensualité."""
    _, session, livrer = cas()
    session["mode"] = mode

    with pytest.raises(formations.AchatInexploitable, match="paiement unique"):
        livrer(session)

    _rien_n_est_livre()


@pytest.mark.parametrize("cas", LIVRAISONS)
@pytest.mark.parametrize(
    "ecart",
    [
        {"amount_total": 100},
        {"amount_total": 0},
        {"amount_total": None},
        {"amount_total": "beaucoup"},
        {"currency": "usd"},
        {"currency": None},
    ],
    ids=["moins", "zero", "sans_montant", "illisible", "autre_devise", "sans_devise"],
)
def test_un_montant_ou_une_devise_qui_ne_sont_pas_ceux_du_prix_ne_livrent_rien(
    cas: Callable[[], Any], ecart: dict[str, Any]
) -> None:
    """Sans panier enregistré, la référence est le prix du catalogue."""
    _, session, livrer = cas()
    session.update(ecart)

    with pytest.raises(formations.AchatInexploitable, match="ne correspond pas"):
        livrer(session)

    _rien_n_est_livre()


@pytest.mark.parametrize("cas", LIVRAISONS)
def test_le_prix_qui_fait_foi_est_celui_du_moment_de_l_ouverture(
    cas: Callable[[], Any],
) -> None:
    """Contre-épreuve : le prix du catalogue peut changer entre l'ouverture et
    l'encaissement. Qui a payé le prix affiché au clic est livré."""
    objet, session, livrer = cas()
    _noter(objet, session["id"])
    _changer_le_prix(objet, 199_000)

    resultat = livrer(session)

    assert resultat.nouveau is True
    assert resultat.achat.montant_cents == session["amount_total"]


@pytest.mark.parametrize("cas", LIVRAISONS)
def test_le_prix_courant_ne_rattrape_pas_un_ecart_avec_le_panier(
    cas: Callable[[], Any],
) -> None:
    """Le panier existe : c'est à LUI que la session est comparée. Un prix
    baissé depuis ne rend pas juste un montant qui n'est pas celui ouvert."""
    objet, session, livrer = cas()
    _noter(objet, session["id"])
    _changer_le_prix(objet, 100)
    session["amount_total"] = 100

    with pytest.raises(formations.AchatInexploitable, match="ne correspond pas"):
        livrer(session)

    assert Organisation.objects.count() == 0


@pytest.mark.parametrize(
    ("cas", "titre"),
    [
        (_cas_formation, "Achat de formation inexploitable"),
        (_cas_produit, "Achat de boutique inexploitable"),
    ],
)
def test_au_webhook_un_ecart_de_montant_ouvre_un_incident(
    cas: Callable[[], Any], titre: str
) -> None:
    """L'argent est pris : le refus doit se voir (règle 1)."""
    _, session, _ = cas()
    session.update(status="complete", amount_total=100)

    abonnements.sur_session_terminee(session)

    incident = OperationalIncident.objects.get()
    assert incident.title == titre
    assert incident.severity == "high"
    assert "ne correspond pas" in incident.details["motif"]
    _rien_n_est_livre()


# ── 5. L'idempotence d'abord ─────────────────────────────────────────────────


def _etat_des_comptes() -> dict[str, int]:
    return {
        "organisations": Organisation.objects.count(),
        "personnes": Customer.objects.count(),
        "comptes": CompteClient.objects.count(),
        "rattachements": MembreOrganisation.objects.count(),
        "rattachements_actifs": MembreOrganisation.objects.filter(
            revoque_le__isnull=True
        ).count(),
        "recettes": Encaissement.objects.count(),
        "achats": AchatFormation.objects.count() + AchatProduit.objects.count(),
    }


@pytest.mark.parametrize("cas", LIVRAISONS)
def test_un_rejeu_ne_modifie_ni_organisation_ni_invitation_ni_compte(
    cas: Callable[[], Any],
) -> None:
    """Stripe rejoue ses événements pendant trois jours, et l'identifiant de
    session se rejoue à volonté sur la page de retour.

    La livraison cherchait d'abord « l'espace de l'acheteur » — qui révoque des
    invitations et crée une organisation — et ne regardait qu'ENSUITE si la
    session était déjà livrée. Entre-temps l'acheteuse a changé d'adresse, et
    l'ancienne a été invitée ailleurs : le rejeu révoquait cette invitation et
    ouvrait un second espace.
    """
    _, session, livrer = cas()
    premier = livrer(session)
    acheteuse = premier.compte.customer
    ancienne_adresse = acheteuse.email
    # Le changement d'adresse porte sur la personne ET sur son identifiant de
    # connexion, comme le fait la confirmation d'une nouvelle adresse.
    nouvelle_adresse = "nouvelle.adresse@example.com"
    Customer.objects.filter(pk=acheteuse.pk).update(email=nouvelle_adresse)
    get_user_model().objects.filter(pk=premier.compte.user_id).update(
        username=nouvelle_adresse, email=nouvelle_adresse
    )
    inviteur = Inscrit(nom="Cabinet inviteur", email="inviteur@cabinet.example")
    homonyme = Customer.objects.create(email=ancienne_adresse)
    invitation = services.inviter_membre(inviteur.organisation, homonyme)
    avant = _etat_des_comptes()

    second = livrer(session)

    assert _etat_des_comptes() == avant
    invitation.refresh_from_db()
    assert invitation.revoque_le is None, "le rejeu a révoqué une invitation"
    assert second.nouveau is False
    assert second.achat == premier.achat
    assert second.organisation == premier.organisation
    assert second.compte == premier.compte


@pytest.mark.parametrize("cas", LIVRAISONS)
def test_contre_epreuve_le_rejeu_rend_le_compte_ne_de_l_achat(
    cas: Callable[[], Any],
) -> None:
    """Le webhook livre, puis le navigateur revient : la page de retour doit
    toujours pouvoir ouvrir la première session de CE compte."""
    from organisations.authentification import ouvrir_la_session_d_un_achat  # noqa: PLC0415

    _, session, livrer = cas()
    livrer(session)

    rejeu = livrer(session)

    assert rejeu.compte is not None
    assert rejeu.compte.ne_de_l_achat == session["id"]
    assert ouvrir_la_session_d_un_achat(rejeu.compte, session["id"])


# ── 6. Un accès se retire, il ne s'efface pas ────────────────────────────────


def _acheter_pour(cliente: Inscrit, formation: Formation) -> AchatFormation:
    session = session_stripe(formation)
    session["metadata"]["organisation_id"] = str(cliente.organisation.id)
    achat: AchatFormation = formations.livrer_la_formation(session).achat
    return achat


def _retirer(client_admin: Any, achat: AchatFormation, **charge: Any) -> Any:
    return client_admin.post(
        f"{ADMIN}achats/{achat.id}/",
        data=json.dumps({"revoque": True, **charge}),
        content_type="application/json",
    )


def _retablir(client_admin: Any, achat: AchatFormation) -> Any:
    return client_admin.post(
        f"{ADMIN}achats/{achat.id}/",
        data=json.dumps({"revoque": False}),
        content_type="application/json",
    )


def _lues(cliente: Inscrit) -> list[str]:
    reponse = Client().get(ESPACE, headers=cliente.entetes)
    assert reponse.status_code == 200, reponse.content
    return [f["slug"] for f in reponse.json()["formations"]]


def test_l_administration_liste_les_achats_d_une_formation(client_admin: Any) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    formation_en_vente(titre="Une autre")
    achat = _acheter_pour(cliente, formation)
    reference = achat.reference_paiement

    reponse = client_admin.get(f"{ADMIN}{formation.id}/achats/")

    assert reponse.status_code == 200, reponse.content
    assert reponse.json() == {
        "achats": [
            {
                "id": str(achat.id),
                "organisation": "Cabinet Test",
                "organisation_id": str(cliente.organisation.id),
                "email": achat.email,
                "montant_cents": formation.prix_cents,
                "devise": "EUR",
                "achete_le": achat.created_at.isoformat(),
                "revoque_le": None,
                "motif_de_revocation": "",
                # Ajoutés avec la durée d'accès : le dernier jour (sans limite
                # par défaut) et le verdict, que l'écran ne recalcule pas.
                "acces_jusqu_au": None,
                "acces": "ouvert",
                "reference_paiement": f"{reference[:12]}…{reference[-4:]}",
            }
        ]
    }
    assert reference not in reponse.content.decode()


def test_retirer_un_acces_le_ferme_sans_rien_effacer(client_admin: Any) -> None:
    cliente = Inscrit()
    voisine = Inscrit(nom="Cabinet voisin", email="voisine@exemple.fr")
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    _acheter_pour(voisine, formation)
    assert _lues(cliente) == [formation.slug]

    reponse = _retirer(client_admin, achat, motif="  Remboursée le 20/11.  ")

    assert reponse.status_code == 200, reponse.content
    rendu = reponse.json()["achat"]
    assert rendu["id"] == str(achat.id)
    assert rendu["revoque_le"]
    assert rendu["motif_de_revocation"] == "Remboursée le 20/11."
    assert _lues(cliente) == []
    # Rien n'est effacé : la ligne, sa référence et son montant restent.
    achat.refresh_from_db()
    assert achat.revoque_le is not None
    assert achat.montant_cents == formation.prix_cents
    assert AchatFormation.objects.count() == 2
    # Contre-épreuve : l'autre organisation lit toujours la sienne.
    assert _lues(voisine) == [formation.slug]
    # La liste d'administration montre l'achat retiré ; le compteur ne le
    # compte plus.
    liste = client_admin.get(f"{ADMIN}{formation.id}/achats/").json()["achats"]
    assert sorted(bool(a["revoque_le"]) for a in liste) == [False, True]
    (fiche,) = client_admin.get(ADMIN).json()["formations"]
    assert fiche["nombre_d_achats"] == 1
    modifiee = client_admin.post(
        f"{ADMIN}{formation.id}/", data={"accroche": "Neuve"},
        content_type="application/json",
    )
    assert modifiee.json()["formation"]["nombre_d_achats"] == 1


def test_retablir_un_acces_le_rouvre(client_admin: Any) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    _retirer(client_admin, achat, motif="Erreur de ma part")

    reponse = _retablir(client_admin, achat)

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["achat"]["revoque_le"] is None
    assert reponse.json()["achat"]["motif_de_revocation"] == ""
    assert _lues(cliente) == [formation.slug]


def test_retirer_deux_fois_garde_la_premiere_date(client_admin: Any) -> None:
    cliente = Inscrit()
    achat = _acheter_pour(cliente, formation_en_vente())
    premiere = _retirer(client_admin, achat, motif="Remboursée").json()["achat"]

    seconde = _retirer(client_admin, achat, motif="Autre motif")

    assert seconde.status_code == 200
    assert seconde.json()["achat"]["revoque_le"] == premiere["revoque_le"]
    assert seconde.json()["achat"]["motif_de_revocation"] == "Remboursée"


def test_rejouer_la_session_d_un_achat_retire_ne_le_retablit_pas(
    client_admin: Any,
) -> None:
    """Le rejeu est à la portée de l'acheteur remboursé : il lui suffit de
    rouvrir son adresse de retour."""
    cliente = Inscrit()
    formation = formation_en_vente()
    session = session_stripe(formation)
    session["metadata"]["organisation_id"] = str(cliente.organisation.id)
    achat = formations.livrer_la_formation(session).achat
    _retirer(client_admin, achat, motif="Remboursée")

    rejeu = formations.livrer_la_formation(session)
    abonnements.sur_session_terminee({**session, "status": "complete"})

    assert (rejeu.nouveau, rejeu.en_double) == (False, False)
    assert rejeu.achat == achat
    assert rejeu.achat.revoque_le is not None
    assert AchatFormation.objects.count() == 1
    assert _lues(cliente) == []
    assert OperationalIncident.objects.count() == 0


def test_un_nouvel_achat_paye_retablit_l_acces_sur_une_nouvelle_ligne(
    client_admin: Any,
) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    ancien = _acheter_pour(cliente, formation)
    _retirer(client_admin, ancien, motif="Remboursée")
    seconde = session_stripe(formation)
    seconde["metadata"]["organisation_id"] = str(cliente.organisation.id)

    resultat = formations.livrer_la_formation(seconde)

    assert (resultat.nouveau, resultat.en_double) == (True, False)
    assert resultat.achat != ancien
    assert resultat.achat.revoque_le is None
    assert AchatFormation.objects.filter(organisation=cliente.organisation).count() == 2
    assert _lues(cliente) == [formation.slug]
    # Ce n'est PAS un double paiement : l'ancien achat ne donnait plus accès.
    assert OperationalIncident.objects.count() == 0
    ancien.refresh_from_db()
    assert ancien.revoque_le is not None

    # Rétablir l'ancien ferait deux accès pour un couple : refusé, et dit.
    refuse = _retablir(client_admin, ancien)

    assert (refuse.status_code, refuse.json()["code"]) == (409, "formation_rachetee")
    ancien.refresh_from_db()
    assert ancien.revoque_le is not None


def test_la_base_tolere_un_achat_retire_et_un_actif_mais_pas_deux_actifs() -> None:
    """La contrainte porte sur les achats qui DONNENT accès."""
    from django.db import IntegrityError, transaction  # noqa: PLC0415
    from django.utils import timezone  # noqa: PLC0415

    cliente = Inscrit()
    formation = formation_en_vente()
    ancien = _acheter_pour(cliente, formation)

    with pytest.raises(IntegrityError), transaction.atomic():
        AchatFormation.objects.create(
            organisation=cliente.organisation, formation=formation,
            reference_paiement="cs_test_deux_actifs",
        )

    AchatFormation.objects.filter(pk=ancien.pk).update(revoque_le=timezone.now())
    AchatFormation.objects.create(
        organisation=cliente.organisation, formation=formation,
        reference_paiement="cs_test_un_retire_un_actif",
    )
    assert AchatFormation.objects.count() == 2


@override_settings(**REGLAGES)
def test_le_refus_deja_achetee_nomme_le_menu_et_tombe_avec_le_retrait(
    monkeypatch: Any, client_admin: Any
) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    envois = _stripe_en_doublure(monkeypatch)

    refuse = _poster(ESPACE_ACHETER, {"formation": formation.slug}, headers=cliente.entetes)

    assert (refuse.status_code, refuse.json()["code"]) == (409, "formation_deja_achetee")
    assert refuse.json()["error"] == (
        "Vous avez déjà cette formation : elle est dans votre espace, dans "
        "« Mes formations »."
    )
    assert envois == []

    # Un achat RETIRÉ ne donne plus accès : il ne bloque plus le rachat.
    _retirer(client_admin, achat, motif="Remboursée")
    rachat = _poster(ESPACE_ACHETER, {"formation": formation.slug}, headers=cliente.entetes)

    assert rachat.status_code == 200, rachat.content
    assert len(envois) == 1


def test_une_organisation_qui_a_un_achat_ne_se_supprime_plus() -> None:
    """En cascade, supprimer l'organisation effaçait la trace d'un paiement."""
    cliente = Inscrit()
    _acheter_pour(cliente, formation_en_vente())

    with pytest.raises(ProtectedError):
        cliente.organisation.delete()

    assert AchatFormation.objects.count() == 1


def test_les_achats_ne_se_suppriment_pas_et_exigent_le_jeton(client_admin: Any) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    liste, un = f"{ADMIN}{formation.id}/achats/", f"{ADMIN}achats/{achat.id}/"

    assert client_admin.delete(liste).status_code == 405
    assert client_admin.delete(un).status_code == 405
    assert client_admin.post(liste).status_code == 405
    assert client_admin.get(un).status_code == 405
    assert Client().get(liste).status_code == 401
    sans_jeton = Client().post(
        un, data=json.dumps({"revoque": True}), content_type="application/json"
    )
    assert sans_jeton.status_code == 401
    # Le jeton d'un CLIENT n'est pas celui de l'administration.
    assert Client().get(liste, headers=cliente.entetes).status_code == 401
    achat.refresh_from_db()
    assert achat.revoque_le is None
    assert AchatFormation.objects.count() == 1


@pytest.mark.parametrize(
    ("charge", "statut", "code"),
    [
        ({}, 400, "revoque_manquant"),
        ({"revoque": "peut-être"}, 400, "revoque_manquant"),
        ({"motif": "Remboursée"}, 400, "revoque_manquant"),
        ({"revoque": True, "motif": "x" * 201}, 400, "motif_trop_long"),
        ({"revoque": True, "motif": ["a"]}, 400, "motif_illisible"),
    ],
)
def test_une_demande_de_retrait_illisible_ne_retire_rien(
    client_admin: Any, charge: dict[str, Any], statut: int, code: str
) -> None:
    achat = _acheter_pour(Inscrit(), formation_en_vente())

    reponse = client_admin.post(
        f"{ADMIN}achats/{achat.id}/", data=json.dumps(charge),
        content_type="application/json",
    )

    assert (reponse.status_code, reponse.json()["code"]) == (statut, code)
    assert reponse.json()["erreur"]
    achat.refresh_from_db()
    assert achat.revoque_le is None


@pytest.mark.parametrize("identifiant", [str(uuid.uuid4()), "pas-un-identifiant"])
def test_un_achat_ou_une_formation_inconnus_rendent_404(
    client_admin: Any, identifiant: str
) -> None:
    liste = client_admin.get(f"{ADMIN}{identifiant}/achats/")
    un = client_admin.post(
        f"{ADMIN}achats/{identifiant}/", data=json.dumps({"revoque": True}),
        content_type="application/json",
    )

    assert (liste.status_code, liste.json()["code"]) == (404, "formation_inconnue")
    assert (un.status_code, un.json()["code"]) == (404, "achat_inconnu")


# ── 7. Remboursement et contestation ─────────────────────────────────────────

ADRESSE_DU_PAYEUR = "camille.durand@example.com"


def _evenement(type_evenement: str, objet: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "type": type_evenement,
        "data": {"object": objet},
    }


def _remboursement(intention: str, *, rembourse: int = 85_000) -> dict[str, Any]:
    """`charge.refunded` : l'objet est le PRÉLÈVEMENT, qui cite l'intention."""
    return _evenement("charge.refunded", {
        "id": "ch_3QabcDEF456ghiJKL",
        "object": "charge",
        "payment_intent": intention,
        "amount": 85_000,
        "amount_refunded": rembourse,
        "currency": "eur",
        "refunded": rembourse >= 85_000,
        "billing_details": {"email": ADRESSE_DU_PAYEUR, "name": "Camille Durand"},
        "receipt_email": ADRESSE_DU_PAYEUR,
    })


def _contestation(intention: str) -> dict[str, Any]:
    """`charge.dispute.created` : l'objet est le LITIGE."""
    return _evenement("charge.dispute.created", {
        "id": "dp_1QabcDEF456ghiJKL",
        "object": "dispute",
        "charge": "ch_3QabcDEF456ghiJKL",
        "payment_intent": intention,
        "amount": 85_000,
        "currency": "eur",
        "reason": "fraudulent",
        "status": "needs_response",
        "evidence": {"customer_email_address": ADRESSE_DU_PAYEUR},
    })


def _achat_avec_intention(cliente: Inscrit, intention: str) -> AchatFormation:
    formation = formation_en_vente()
    session = session_stripe(formation, payment_intent=intention)
    session["metadata"]["organisation_id"] = str(cliente.organisation.id)
    achat: AchatFormation = formations.livrer_la_formation(session).achat
    return achat


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
@pytest.mark.parametrize(
    ("fabrique", "titre", "gravite"),
    [
        (_remboursement, "Paiement remboursé", "medium"),
        (_contestation, "Paiement contesté", "high"),
    ],
)
def test_un_remboursement_ou_une_contestation_ouvre_un_incident_SANS_rien_retirer(
    fabrique: Callable[[str], dict[str, Any]], titre: str, gravite: str
) -> None:
    """Ces événements n'étaient pas écoutés : un acheteur remboursé gardait son
    accès sans que personne le sache. La décision de le retirer reste humaine."""
    cliente = Inscrit()
    intention = "pi_3QabcDEF456ghiJKL789"
    achat = _achat_avec_intention(cliente, intention)

    reponse = poster_evenement(fabrique(intention))

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["traite"] is True
    incident = OperationalIncident.objects.get()
    assert (incident.title, incident.severity) == (titre, gravite)
    details = incident.details
    assert details["paiement"] == intention
    assert details["montant_cents"] == "85000"
    assert details["devise"] == "EUR"
    # L'achat est retrouvé par l'intention de paiement notée à la livraison.
    assert details["achat"] == str(achat.id)
    assert details["organisation"] == str(cliente.organisation.id)
    assert details["formation"] == achat.formation.slug
    assert "administration" in details["a_faire"]
    assert ADRESSE_DU_PAYEUR not in json.dumps(details)
    assert cliente.contact.email not in json.dumps(details)
    # AUCUN retrait automatique : l'accès tient jusqu'à la décision de la gérante.
    achat.refresh_from_db()
    assert achat.revoque_le is None
    assert _lues(cliente) == [achat.formation.slug]


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_un_remboursement_que_l_on_ne_sait_pas_rattacher_le_DIT() -> None:
    """Un abonnement, une étude, un achat d'avant : l'événement ne cite que
    l'intention de paiement, et la retrouver demanderait d'interroger Stripe."""
    _achat_avec_intention(Inscrit(), "pi_3QautreAUTRE456autre")

    reponse = poster_evenement(_remboursement("pi_3QinconnuINCONNU789", rembourse=20_000))

    assert reponse.status_code == 200
    incident = OperationalIncident.objects.get()
    assert incident.title == "Paiement remboursé"
    assert incident.details["paiement"] == "pi_3QinconnuINCONNU789"
    assert incident.details["rembourse_cents"] == "20000"
    assert incident.details["remboursement_total"] == "non"
    assert "achat" not in incident.details
    assert "pas été retrouvé" in incident.details["rattachement"]
    assert AchatFormation.objects.filter(revoque_le__isnull=False).count() == 0


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_un_remboursement_sans_intention_ne_fait_pas_tomber_le_webhook() -> None:
    evenement = _remboursement("")
    del evenement["data"]["object"]["payment_intent"]

    reponse = poster_evenement(evenement)

    assert reponse.status_code == 200
    incident = OperationalIncident.objects.get()
    assert incident.details["prelevement"] == "ch_3QabcDEF456ghiJKL"
    assert "achat" not in incident.details


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
@pytest.mark.parametrize(
    "type_evenement", ["charge.updated", "charge.dispute.closed", "refund.created", ""]
)
def test_contre_epreuve_un_evenement_inconnu_ne_fait_rien(type_evenement: str) -> None:
    """La liste des traitements reste fermée."""
    reponse = poster_evenement(
        _evenement(type_evenement, {"id": "ch_x", "payment_intent": "pi_x"})
    )

    assert reponse.status_code == 200
    assert reponse.json()["traite"] is True
    assert "non traite" in reponse.json()["verdict"]
    assert OperationalIncident.objects.count() == 0


# ── 8. Les journaux ──────────────────────────────────────────────────────────


@override_settings(**REGLAGES)
def test_ni_adresse_ni_reference_entiere_dans_les_journaux_ni_les_incidents(
    monkeypatch: Any, caplog: Any
) -> None:
    """Un paiement, son retour, son rejeu, puis un second paiement de la même
    formation — tout le circuit, lu dans ce qu'il laisse derrière lui."""
    _courriels_en_doublure(monkeypatch)
    formation = formation_en_vente()
    adresse = "camille.durand@example.com"
    premiere = session_stripe(formation)
    premiere["customer_details"]["email"] = adresse
    seconde = session_stripe(formation)
    seconde["customer_details"]["email"] = adresse
    caplog.set_level(logging.DEBUG)

    for session in (premiere, premiere, seconde):
        monkeypatch.setattr(stripe_api, "relire_la_session", lambda _, s=session: s)
        assert _poster(RETOURS["formation"], {"session": session["id"]}).status_code == 200
    # Et un retour inexploitable, qui est journalisé en erreur.
    non_payee = session_stripe(formation, payment_status="unpaid")
    non_payee["customer_details"]["email"] = adresse
    monkeypatch.setattr(stripe_api, "relire_la_session", lambda _: non_payee)
    assert _poster(RETOURS["formation"], {"session": non_payee["id"]}).status_code == 409

    journal = caplog.text
    assert "Formation livrée" in journal, "le journal n'a pas été capturé"
    incident = OperationalIncident.objects.get(title=formations.INCIDENT_PAYEE_DEUX_FOIS)
    traces = journal + json.dumps(incident.details, ensure_ascii=False)
    assert adresse not in traces
    for session in (premiere, seconde, non_payee):
        assert session["id"] not in traces, "une référence de session entière"
    # L'organisation, elle, y est : c'est par elle que l'on retrouve l'acheteur.
    organisation = AchatFormation.objects.get().organisation
    assert str(organisation.id) in journal
    assert incident.details["organisation"] == str(organisation.id)
    reference = seconde["id"]
    assert incident.details["session"] == f"{reference[:12]}…{reference[-4:]}"


@override_settings(**REGLAGES)
def test_le_message_brut_de_stripe_ne_va_pas_dans_les_journaux(
    monkeypatch: Any, caplog: Any
) -> None:
    """Il cite volontiers une clé, un identifiant de requête, une adresse."""
    formation = formation_en_vente()
    interne = "Invalid API Key provided: sk_test_x ; request req_INTERNE_42"
    panne: Any = stripe.APIConnectionError

    def en_panne(*_: Any, **__: Any) -> Any:
        raise panne(interne)

    monkeypatch.setattr(stripe.checkout.Session, "create", en_panne)
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", en_panne)
    caplog.set_level(logging.DEBUG)

    ouverture = _poster(
        "/api/public/formations/acheter/",
        {"formation": formation.slug, "email": "camille.durand@example.com"},
    )
    reference = _reference()
    retour = _poster(RETOURS["formation"], {"session": reference})

    assert (ouverture.status_code, retour.status_code) == (503, 503)
    journal = caplog.text
    for fuite in ("sk_test", "req_INTERNE_42", "Invalid API Key", "camille.durand", reference):
        assert fuite not in journal, fuite
    # Contre-épreuve : le TYPE de l'erreur y est, lui — c'est ce qui permet
    # de diagnostiquer, et ce qui prouve que le journal a bien été capturé.
    assert journal.count("APIConnectionError") >= 2
