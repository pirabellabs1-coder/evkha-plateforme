"""Une formation se paie par Stripe, et se lit dans l'espace de qui l'a payée.

Décision de la cliente du 20/11/2026 : ni lien de paiement extérieur, ni vente
par courriel. Ce fichier verrouille le circuit, décliné de celui de la
boutique (`test_boutique.py`) :

- **on n'encaisse pas pour rien** : une formation hors ligne, sans prix ou
  sans leçon n'ouvre aucun paiement, et le montant ne vient jamais du corps ;
- **un paiement, un accès** : la livraison est rejouable, et payer deux fois
  la même formation n'ouvre pas un second accès — mais se voit ;
- **le contenu payant ne sort que par une porte** : l'espace de l'organisation
  qui porte l'achat.

Stripe n'est jamais appelé : il est remplacé par `monkeypatch`. Chaque refus a
sa contre-épreuve — le cas voisin légitime passe.
"""
from __future__ import annotations

import io
import json
import uuid
from typing import Any

import pytest
import stripe
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import Client
from django.test.utils import CaptureQueriesContext, override_settings
from paiement import abonnements, boutique, formations, stripe_api

from catalog import formations as regles
from catalog.models import (
    AchatFormation,
    AchatProduit,
    Formation,
    LeconDeFormation,
    ModuleDeFormation,
)
from evkha import signatures
from monitoring.models import OperationalIncident
from organisations import courriels, limitation, vues_boutique, vues_espace, vues_formations
from organisations.models import (
    CompteClient,
    Encaissement,
    EtatTentative,
    JetonAcces,
    ObjetTentative,
    Organisation,
    TentativePaiement,
    TypeDeCompte,
)
from tests.test_barriere_de_paiement import SECRET_WEBHOOK, Inscrit, poster_evenement
from tests.test_boutique import produit_en_ligne
from tests.test_boutique import session_stripe as session_de_boutique

pytestmark = pytest.mark.django_db

ACHETER = "/api/public/formations/acheter/"
RETOUR = "/api/public/formations/retour/"
ESPACE = "/api/espace/formations/"
ESPACE_ACHETER = "/api/espace/formations/acheter/"
ADMIN = "/api/dashboard/formations/"

VIDEO = "https://vimeo.com/secret-246810"
TEXTE = "TEXTE-RESERVE-AUX-ACHETEURS"
#: Réglages factices : la clé n'ouvre rien, Stripe est en doublure.
REGLAGES = {"STRIPE_SECRET_KEY": "sk_test_x", "EVKHA_APP_URL": "https://exemple.fr"}


# ── Fabriques ────────────────────────────────────────────────────────────────


def formation_en_vente(**surcharges: Any) -> Formation:
    """Une formation réellement vendable : en ligne, un prix, une leçon présente."""
    defauts: dict[str, Any] = {
        "titre": "Méthode P.O.P",
        "slug": f"formation-{uuid.uuid4().hex[:8]}",
        "sous_titre": "Poser, Offrir, Prospecter",
        "accroche": "Sept heures pour trouver ses premiers clients.",
        "prix_cents": 85_000,
        "duree_heures": 7,
        "en_ligne": True,
    }
    defauts.update(surcharges)
    formation = Formation.objects.create(**defauts)
    module = ModuleDeFormation.objects.create(
        formation=formation, titre="Poser son offre", description="Le socle.", rang=0
    )
    LeconDeFormation.objects.create(
        module=module,
        titre="Choisir sa cible",
        nature="video",
        adresse_video=VIDEO,
        texte=TEXTE,
        duree_minutes=12,
        rang=0,
    )
    return formation


def session_stripe(formation: Formation, **surcharges: Any) -> dict[str, Any]:
    """Une session de paiement telle que le prestataire la rend."""
    session: dict[str, Any] = {
        "id": f"cs_test_{uuid.uuid4().hex[:16]}",
        # Le mode fait partie de ce que la livraison vérifie (audit du
        # 20/11/2026) : une formation est un paiement unique.
        "mode": "payment",
        "status": "complete",
        "payment_status": "paid",
        "amount_total": formation.prix_cents,
        "currency": "eur",
        "customer_details": {
            "email": f"{uuid.uuid4().hex[:8]}@example.com",
            "name": "Camille Durand",
        },
        "metadata": {"achat": "formation", "formation_slug": formation.slug},
    }
    session.update(surcharges)
    return session


def _poster(adresse: str, charge: dict[str, Any], **plus: Any) -> Any:
    return Client().post(
        adresse, json.dumps(charge), content_type="application/json", **plus
    )


def _stripe_en_doublure(monkeypatch: Any) -> list[dict[str, Any]]:
    """Remplace l'appel à Stripe, et RIEN d'autre. Rend ce qui lui est envoyé.

    La doublure est posée sur `stripe.checkout.Session.create` et non sur
    notre fonction : ce qui est observé est ce qui PARTIRAIT chez le
    prestataire, pas ce que la vue promet.
    """
    envois: list[dict[str, Any]] = []

    def faux_create(**kwargs: Any) -> dict[str, Any]:
        envois.append(kwargs)
        return {
            "id": f"cs_test_ouverte_{len(envois)}",
            "url": "https://checkout.stripe.com/c/pay/session",
        }

    monkeypatch.setattr(stripe.checkout.Session, "create", faux_create)
    return envois


def _revenir(monkeypatch: Any, session: dict[str, Any], adresse: str = RETOUR) -> Any:
    """Le navigateur revient de Stripe avec l'identifiant de cette session."""
    monkeypatch.setattr(stripe_api, "relire_la_session", lambda identifiant: session)
    return _poster(adresse, {"session": session["id"]})


def _courriels_en_doublure(monkeypatch: Any) -> list[dict[str, str]]:
    partis: list[dict[str, str]] = []

    def faux_envoi(**kwargs: str) -> bool:
        partis.append(kwargs)
        return True

    monkeypatch.setattr(courriels, "_envoyer", faux_envoi)
    return partis


def _cles(valeur: Any) -> set[str]:
    """Toutes les clés d'une réponse, à toute profondeur."""
    if isinstance(valeur, dict):
        return set(valeur) | {c for v in valeur.values() for c in _cles(v)}
    if isinstance(valeur, list):
        return {c for v in valeur for c in _cles(v)}
    return set()


def _incidents_de_double_paiement() -> Any:
    return OperationalIncident.objects.filter(title=formations.INCIDENT_PAYEE_DEUX_FOIS)


# ── 1. L'ouverture du paiement ───────────────────────────────────────────────


@override_settings(**REGLAGES)
def test_le_montant_part_du_MODELE_et_jamais_du_corps(monkeypatch: Any) -> None:
    """On ne lit qu'un slug. Vérifié sur ce qui part chez Stripe."""
    formation = formation_en_vente(prix_cents=149_000, devise="EUR")
    envois = _stripe_en_doublure(monkeypatch)

    reponse = _poster(ACHETER, {
        "formation": formation.slug,
        "email": "porteuse@example.fr",
        "prix_cents": 1,
        "montant": 1,
        "unit_amount": 1,
        "devise": "USD",
        "line_items": [{"price": "price_a_moi", "quantity": 1}],
        "metadata": {"organisation_id": str(uuid.uuid4())},
        "organisation_id": str(uuid.uuid4()),
    })

    assert reponse.status_code == 200, reponse.content
    assert reponse.json() == {"adresse": "https://checkout.stripe.com/c/pay/session"}
    (envoi,) = envois
    assert envoi["mode"] == "payment"
    assert envoi["line_items"] == [{
        "price_data": {
            "currency": "eur",
            "unit_amount": 149_000,
            "product_data": {"name": "Formation — Méthode P.O.P"},
        },
        "quantity": 1,
    }]
    # Aucune organisation : au moment du clic, le visiteur n'est personne — et
    # celle qu'il glisse dans le corps ne voyage pas.
    assert envoi["metadata"] == {"achat": "formation", "formation_slug": formation.slug}
    assert envoi["success_url"] == (
        "https://exemple.fr/formations/retour?session={CHECKOUT_SESSION_ID}"
    )
    assert envoi["cancel_url"] == "https://exemple.fr/formations?paiement=abandon"
    assert envoi["customer_email"] == "porteuse@example.fr"


@override_settings(**REGLAGES)
def test_l_adresse_est_facultative_et_une_saisie_fausse_est_ecartee(
    monkeypatch: Any,
) -> None:
    """Transmise telle quelle, une faute de frappe faisait refuser l'ouverture
    par le prestataire : le visiteur lisait « paiement indisponible »."""
    formation = formation_en_vente()
    envois = _stripe_en_doublure(monkeypatch)

    sans = _poster(ACHETER, {"formation": formation.slug})
    fausse = _poster(ACHETER, {"formation": formation.slug, "email": "pas une adresse"})
    liste = _poster(ACHETER, {"formation": formation.slug, "email": ["a@b.fr"]})

    assert [r.status_code for r in (sans, fausse, liste)] == [200, 200, 200]
    assert all("customer_email" not in envoi for envoi in envois)


@override_settings(**REGLAGES)
@pytest.mark.parametrize(
    "surcharges",
    [
        {"en_ligne": False},
        {"en_ligne": False, "prix_cents": 0},
    ],
    ids=["hors_ligne", "sans_prix"],
)
def test_une_formation_qui_n_est_pas_publiee_n_ouvre_aucun_paiement(
    monkeypatch: Any, surcharges: dict[str, Any]
) -> None:
    """Hors ligne ou sans prix : pour le visiteur, elle n'existe pas."""
    formation = formation_en_vente(**surcharges)
    envois = _stripe_en_doublure(monkeypatch)

    reponse = _poster(ACHETER, {"formation": formation.slug})

    assert reponse.status_code == 404
    assert reponse.json()["code"] == "formation_inconnue"
    assert reponse.json()["erreur"]
    assert envois == [], "Stripe a été appelé pour une formation non vendable"
    assert TentativePaiement.objects.count() == 0


@override_settings(**REGLAGES)
@pytest.mark.parametrize("charge", [{}, {"formation": "inconnue"}, {"formation": 12},
                                    {"formation": ["a"]}, {"formation": None}])
def test_une_formation_inconnue_ou_illisible_rend_404(
    monkeypatch: Any, charge: dict[str, Any]
) -> None:
    formation_en_vente()
    envois = _stripe_en_doublure(monkeypatch)

    reponse = _poster(ACHETER, charge)

    assert reponse.status_code == 404
    assert reponse.json()["code"] == "formation_inconnue"
    assert envois == []


@override_settings(**REGLAGES)
@pytest.mark.parametrize("retrait", ["aucune_lecon", "lecon_retiree", "module_retire"])
def test_une_formation_SANS_LECON_presente_n_est_pas_encaissee(
    monkeypatch: Any, retrait: str
) -> None:
    """Elle reste affichée — son achat, lui, est refusé.

    C'est le cas d'une formation en ligne dont la cliente retire la dernière
    leçon : 1 490 € pour un espace vide.
    """
    formation = formation_en_vente()
    if retrait == "aucune_lecon":
        LeconDeFormation.objects.all().delete()
    elif retrait == "lecon_retiree":
        LeconDeFormation.objects.update(retire_le="2026-11-01T10:00:00Z")
    else:
        ModuleDeFormation.objects.update(retire_le="2026-11-01T10:00:00Z")
    envois = _stripe_en_doublure(monkeypatch)

    reponse = _poster(ACHETER, {"formation": formation.slug})

    assert reponse.status_code == 409, reponse.content
    assert reponse.json()["code"] == "formation_sans_programme"
    assert envois == [], "Stripe a été appelé pour une formation vide"
    # Elle est bien toujours AFFICHÉE : le refus ne vient pas d'une disparition.
    publiques = Client().get("/api/public/formations/").json()["formations"]
    assert [f["slug"] for f in publiques] == [formation.slug]


@override_settings(**REGLAGES)
def test_la_fonction_qui_parle_a_stripe_refuse_ELLE_AUSSI_une_formation_vide(
    monkeypatch: Any,
) -> None:
    """Un troisième appelant ne doit pas pouvoir vendre un espace vide."""
    vide = Formation.objects.create(
        titre="Vide", slug="vide", prix_cents=85_000, en_ligne=True
    )
    garnie = formation_en_vente()
    envois = _stripe_en_doublure(monkeypatch)

    with pytest.raises(stripe_api.PaiementIndisponible):
        stripe_api.creer_paiement_de_formation(formation=vide)
    assert envois == []

    # Contre-épreuve : la même fonction ouvre le paiement d'une formation garnie.
    ouverte = stripe_api.creer_paiement_de_formation(formation=garnie)
    assert ouverte.identifiant == "cs_test_ouverte_1"
    assert len(envois) == 1


@override_settings(**REGLAGES)
def test_le_plafond_est_interroge_ET_compte(monkeypatch: Any) -> None:
    """Un plafond lu sans être compté ne s'atteint jamais (vu deux fois)."""
    formation = formation_en_vente()
    _stripe_en_doublure(monkeypatch)
    monkeypatch.setattr(
        vues_formations,
        "ACHATS_PAR_HEURE",
        limitation.Plafond("formations-de-test", maximum=2, fenetre_s=3600),
    )

    reponses = [_poster(ACHETER, {"formation": formation.slug}) for _ in range(3)]

    assert [r.status_code for r in reponses] == [200, 200, 429]
    assert reponses[2].json()["code"] == "trop_de_tentatives"
    # Le refus ne laisse ni panier ni session de plus.
    assert TentativePaiement.objects.count() == 2


def test_le_plafond_des_formations_n_est_pas_celui_de_la_boutique() -> None:
    """Propre aux formations : épuiser l'un ne ferme pas l'autre."""
    limitation.enregistrer(vues_formations.ACHATS_PAR_HEURE, "203.0.113.7")

    assert vues_formations.ACHATS_PAR_HEURE.nom != vues_boutique.ACHATS_PAR_HEURE.nom
    assert vues_formations.ACHATS_PAR_HEURE.cle("203.0.113.7") != (
        vues_boutique.ACHATS_PAR_HEURE.cle("203.0.113.7")
    )
    assert vues_formations.ACHATS_PAR_HEURE.maximum > 1


@override_settings(**REGLAGES)
def test_stripe_en_panne_rend_503_SANS_detail(monkeypatch: Any) -> None:
    """Le message du prestataire cite volontiers une clé ou un identifiant."""
    formation = formation_en_vente()
    interne = "Invalid API Key provided: sk_test_x ; request req_INTERNE_42"

    # `Any` : le constructeur de Stripe n'est pas annoté.
    panne_de_stripe: Any = stripe.APIConnectionError

    def en_panne(**_: Any) -> Any:
        raise panne_de_stripe(interne)

    monkeypatch.setattr(stripe.checkout.Session, "create", en_panne)

    reponse = _poster(ACHETER, {"formation": formation.slug})

    assert reponse.status_code == 503
    assert reponse.json()["code"] == "paiement_indisponible"
    texte = reponse.content.decode()
    for fuite in ("sk_test", "req_INTERNE_42", "API Key", "APIConnectionError"):
        assert fuite not in texte, fuite
    # Aucun panier n'a été ouvert. L'appel, lui, est COMPTÉ : il est parti chez
    # le prestataire, et un plafond qui ne compterait que les réussites ne
    # verrait pas un script dont toutes les ouvertures échouent (audit du
    # 20/11/2026 — ce test exigeait l'inverse).
    assert TentativePaiement.objects.count() == 0
    assert limitation.depasse(
        limitation.Plafond(vues_formations.ACHATS_PAR_HEURE.nom, 1, 3600), "127.0.0.1"
    )


@override_settings(STRIPE_SECRET_KEY="", EVKHA_APP_URL="https://exemple.fr")
def test_sans_cle_stripe_l_achat_refuse_au_lieu_de_partir_anonyme() -> None:
    formation = formation_en_vente()

    reponse = _poster(ACHETER, {"formation": formation.slug})

    assert reponse.status_code == 503
    assert reponse.json()["code"] == "paiement_indisponible"


@pytest.mark.parametrize("corps", ['{"formation": ', "[1, 2]", '"texte"'])
def test_un_corps_illisible_est_refuse(corps: str) -> None:
    for adresse in (ACHETER, RETOUR):
        reponse = Client().post(adresse, data=corps, content_type="application/json")
        assert reponse.status_code == 400, adresse
        assert reponse.json()["code"] == "corps_invalide"


@override_settings(**REGLAGES)
@pytest.mark.parametrize("adresse", [ACHETER, RETOUR])
def test_les_routes_publiques_postees_n_exigent_pas_de_jeton_csrf(
    monkeypatch: Any, adresse: str
) -> None:
    """Le client de test n'applique PAS la vérification CSRF par défaut : sans
    `enforce_csrf_checks`, ce test passerait sur une vue non exemptée — c'est
    ainsi qu'une page de paiement a affiché « Erreur 403 » avec seize tests
    verts (`test_barriere_de_paiement`)."""
    formation = formation_en_vente()
    _stripe_en_doublure(monkeypatch)
    session = session_stripe(formation)
    monkeypatch.setattr(stripe_api, "relire_la_session", lambda identifiant: session)

    reponse = Client(enforce_csrf_checks=True).post(
        adresse,
        json.dumps({"formation": formation.slug, "session": session["id"]}),
        content_type="application/json",
    )

    assert reponse.status_code == 200, reponse.content


def test_l_achat_ne_se_lit_pas_en_GET() -> None:
    assert Client().get(ACHETER).status_code == 405
    assert Client().get(RETOUR).status_code == 405


# ── 2. Le panier dans le suivi des transactions ──────────────────────────────


@override_settings(**REGLAGES)
def test_un_panier_de_formation_est_visible_puis_solde(
    client_admin: Any, monkeypatch: Any
) -> None:
    """Ouvert, il se voit ; payé, il ne se relance plus."""
    formation = formation_en_vente()
    _stripe_en_doublure(monkeypatch)

    _poster(ACHETER, {"formation": formation.slug, "email": "hesitante@example.fr"})

    tentative = TentativePaiement.objects.get()
    assert tentative.objet == ObjetTentative.FORMATION
    assert tentative.formation == formation
    assert tentative.reference_session == "cs_test_ouverte_1"
    lignes = client_admin.get("/api/dashboard/supervision/transactions/").json()
    (panier,) = lignes["transactions"]
    assert panier["formation"] == formation.titre
    assert panier["produit"] == ""
    assert panier["objet"] == "formation"
    assert panier["objet_libelle"] == "Achat d'une formation"
    assert panier["etat"] == "ouverte"
    assert panier["organisation"] == "Visiteur"
    assert panier["contact"] == "hesitante@example.fr"
    assert panier["montant_cents"] == formation.prix_cents

    formations.livrer_la_formation(session_stripe(formation, id="cs_test_ouverte_1"))

    lignes = client_admin.get("/api/dashboard/supervision/transactions/").json()
    (panier,) = lignes["transactions"]
    assert panier["etat"] == "payee"
    assert panier["organisation"] != "Visiteur"
    assert lignes["resume"]["encaisse_cents"] == formation.prix_cents


def test_un_panier_de_formation_abandonne_se_relance(client_admin: Any) -> None:
    """La relance écrit à l'adresse saisie : il n'y a pas encore d'organisation."""
    formation = formation_en_vente()
    formations.noter_la_tentative(
        session=stripe_api.SessionOuverte("cs_test_abandon", "https://checkout.test/x"),
        formation=formation,
        email="hesitante@example.fr",
    )
    tentative = TentativePaiement.objects.get()
    assert tentative.etat == EtatTentative.OUVERTE

    reponse = client_admin.post(
        f"/api/dashboard/supervision/transactions/{tentative.id}/relancer/",
        content_type="application/json",
    )

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["relances"] == 1


# ── 3. La livraison ──────────────────────────────────────────────────────────


def test_le_paiement_ouvre_l_acces_le_compte_et_compte_la_recette() -> None:
    formation = formation_en_vente()
    session = session_stripe(formation)
    formations.noter_la_tentative(
        session=stripe_api.SessionOuverte(session["id"], "https://checkout.test/x"),
        formation=formation,
    )

    resultat = formations.livrer_la_formation(session)

    assert (resultat.nouveau, resultat.en_double) == (True, False)
    assert resultat.formation == formation
    assert resultat.organisation.type_de_compte == TypeDeCompte.A_L_UNITE
    achat = AchatFormation.objects.get()
    assert achat == resultat.achat
    assert (achat.organisation, achat.formation) == (resultat.organisation, formation)
    assert achat.reference_paiement == session["id"]
    assert (achat.montant_cents, achat.devise) == (formation.prix_cents, "EUR")
    assert achat.email == session["customer_details"]["email"]
    compte = CompteClient.objects.get()
    assert compte == resultat.compte
    assert compte.ne_de_l_achat == session["id"]
    assert not compte.user.has_usable_password()
    encaissement = Encaissement.objects.get()
    assert encaissement.reference_facture == session["id"]
    assert encaissement.montant_cents == formation.prix_cents
    assert encaissement.organisation == resultat.organisation
    assert encaissement.formule_code == formation.slug
    tentative = TentativePaiement.objects.get()
    assert tentative.etat == EtatTentative.PAYEE
    assert tentative.organisation == resultat.organisation
    assert _incidents_de_double_paiement().count() == 0


def test_la_livraison_ne_verse_AUCUN_credit() -> None:
    """Rien n'est à produire : un crédit ici offrirait une étude."""
    from organisations import credits  # noqa: PLC0415

    resultat = formations.livrer_la_formation(session_stripe(formation_en_vente()))

    assert credits.solde(resultat.organisation) == 0
    assert AchatProduit.objects.count() == 0


def test_la_livraison_est_rejouable_sans_compter_deux_fois() -> None:
    """Le webhook et la page de retour se croisent : c'est le cas NORMAL."""
    session = session_stripe(formation_en_vente())

    premier = formations.livrer_la_formation(session)
    second = formations.livrer_la_formation(session)

    assert (premier.nouveau, second.nouveau) == (True, False)
    assert second.achat == premier.achat
    assert second.en_double is False
    assert AchatFormation.objects.count() == 1
    assert Organisation.objects.count() == 1
    assert Encaissement.objects.count() == 1
    assert _incidents_de_double_paiement().count() == 0


@pytest.mark.parametrize("etat", ["unpaid", "no_payment_required", ""])
def test_une_session_non_payee_ne_livre_rien(etat: str) -> None:
    """`status: complete` dit que le formulaire est allé au bout, pas que
    l'argent est là."""
    session = session_stripe(formation_en_vente(), payment_status=etat)

    with pytest.raises(formations.AchatInexploitable, match="non payée"):
        formations.livrer_la_formation(session)

    assert AchatFormation.objects.count() == 0
    assert Organisation.objects.count() == 0
    assert Encaissement.objects.count() == 0


def test_une_formation_inconnue_est_refusee_bruyamment() -> None:
    """L'argent a été pris : se taire serait le pire (règle 1)."""
    session = session_stripe(formation_en_vente())
    session["metadata"]["formation_slug"] = "formation-qui-n-existe-pas"

    with pytest.raises(formations.AchatInexploitable, match="inconnue"):
        formations.livrer_la_formation(session)

    assert AchatFormation.objects.count() == 0


def test_une_session_sans_adresse_ou_sans_identifiant_est_inexploitable() -> None:
    formation = formation_en_vente()

    with pytest.raises(formations.AchatInexploitable, match="adresse"):
        formations.livrer_la_formation(session_stripe(formation, customer_details={}))
    with pytest.raises(formations.AchatInexploitable, match="identifiant"):
        formations.livrer_la_formation(session_stripe(formation, id=""))

    assert AchatFormation.objects.count() == 0


def test_une_formation_mise_hors_ligne_PENDANT_le_paiement_est_quand_meme_livree() -> None:
    """Contre-épreuve du refus à l'ouverture : ce qui est payé est dû."""
    formation = formation_en_vente()
    session = session_stripe(formation)
    Formation.objects.filter(pk=formation.pk).update(en_ligne=False)

    resultat = formations.livrer_la_formation(session)

    assert resultat.nouveau is True
    assert AchatFormation.objects.filter(formation=formation).count() == 1


def test_l_organisation_designee_l_emporte_sur_l_adresse() -> None:
    """L'achat parti de l'espace va à l'organisation du compte, même si
    l'adresse collectée par le prestataire est une autre."""
    cliente = Inscrit()
    formation = formation_en_vente()
    session = session_stripe(formation)
    session["customer_details"]["email"] = "adresse.differente@example.com"
    session["metadata"]["organisation_id"] = str(cliente.organisation.id)
    avant = Organisation.objects.count()

    resultat = formations.livrer_la_formation(session)

    assert resultat.organisation == cliente.organisation
    assert Organisation.objects.count() == avant
    assert AchatFormation.objects.get().organisation == cliente.organisation


def test_l_achat_d_une_invitee_jamais_venue_ne_va_pas_a_qui_l_a_invitee() -> None:
    """Le rattachement passe par `espace_de_l_acheteur`, jamais par le courriel
    brut : inviter l'adresse de quelqu'un ne donne pas sa formation."""
    from customers.models import Customer  # noqa: PLC0415
    from organisations import services  # noqa: PLC0415

    inviteur = Inscrit(nom="Cabinet inviteur", email="inviteur@cabinet.example")
    invitee = Customer.objects.create(email="cible@example.com")
    services.inviter_membre(inviteur.organisation, invitee)
    session = session_stripe(formation_en_vente())
    session["customer_details"]["email"] = invitee.email

    resultat = formations.livrer_la_formation(session)

    assert resultat.organisation != inviteur.organisation
    assert resultat.organisation.contact == invitee
    assert not AchatFormation.objects.filter(organisation=inviteur.organisation).exists()


def test_payer_DEUX_FOIS_la_meme_formation_ouvre_un_seul_acces_et_un_incident() -> None:
    """L'argent est pris deux fois : la recette le dit, et quelqu'un rembourse."""
    formation = formation_en_vente()
    adresse = "camille@example.com"
    premiere = session_stripe(formation)
    premiere["customer_details"]["email"] = adresse
    seconde = session_stripe(formation)
    seconde["customer_details"]["email"] = adresse
    formations.noter_la_tentative(
        session=stripe_api.SessionOuverte(seconde["id"], "https://checkout.test/x"),
        formation=formation,
        email=adresse,
    )

    a = formations.livrer_la_formation(premiere)
    b = formations.livrer_la_formation(seconde)

    assert (a.nouveau, a.en_double) == (True, False)
    assert (b.nouveau, b.en_double) == (False, True)
    assert b.achat == a.achat, "le second paiement rend l'achat EXISTANT"
    assert b.organisation == a.organisation
    assert AchatFormation.objects.count() == 1
    assert AchatFormation.objects.get().reference_paiement == premiere["id"]
    assert sorted(Encaissement.objects.values_list("reference_facture", flat=True)) == sorted(
        [premiere["id"], seconde["id"]]
    )
    incident = _incidents_de_double_paiement().get()
    assert incident.severity == "high"
    # Références ABRÉGÉES, et aucune adresse : l'incident se lit dans
    # l'administration, et l'identifiant entier d'une session ouvre la première
    # session du compte né du paiement (audit du 20/11/2026).
    assert incident.details["session"] == f"{seconde['id'][:12]}…{seconde['id'][-4:]}"
    assert incident.details["premier_paiement"] == (
        f"{premiere['id'][:12]}…{premiere['id'][-4:]}"
    )
    assert adresse not in json.dumps(incident.details)
    assert incident.details["formation"] == formation.slug
    assert incident.details["organisation"] == str(a.organisation.id)
    assert "Remboursez" in incident.details["a_faire"]
    # Son panier est soldé : on ne relance pas quelqu'un qui a payé deux fois.
    assert TentativePaiement.objects.get().etat == EtatTentative.PAYEE

    # Rejoué (le webhook ET la page de retour passent), il ne compte ni ne
    # signale une seconde fois.
    c = formations.livrer_la_formation(seconde)

    assert (c.nouveau, c.en_double) == (False, True)
    assert AchatFormation.objects.count() == 1
    assert Encaissement.objects.count() == 2
    assert _incidents_de_double_paiement().count() == 1


def test_acheter_une_AUTRE_formation_n_est_pas_un_double_paiement() -> None:
    """Contre-épreuve : la contrainte porte sur le couple, pas sur l'acheteur."""
    adresse = "camille@example.com"
    premiere = session_stripe(formation_en_vente())
    premiere["customer_details"]["email"] = adresse
    seconde = session_stripe(formation_en_vente(titre="Créer son entreprise"))
    seconde["customer_details"]["email"] = adresse

    a = formations.livrer_la_formation(premiere)
    b = formations.livrer_la_formation(seconde)

    assert (b.nouveau, b.en_double) == (True, False)
    assert a.organisation == b.organisation
    assert AchatFormation.objects.filter(organisation=a.organisation).count() == 2
    assert _incidents_de_double_paiement().count() == 0


def test_deux_organisations_achetent_la_meme_formation() -> None:
    """Contre-épreuve : la même formation se vend à chacune."""
    formation = formation_en_vente()

    a = formations.livrer_la_formation(session_stripe(formation))
    b = formations.livrer_la_formation(session_stripe(formation))

    assert a.organisation != b.organisation
    assert (a.nouveau, b.nouveau) == (True, True)
    assert _incidents_de_double_paiement().count() == 0


def test_la_base_refuse_deux_achats_de_la_meme_formation() -> None:
    """Le dernier rempart : ce qui écrirait sans passer par la livraison."""
    resultat = formations.livrer_la_formation(session_stripe(formation_en_vente()))

    with pytest.raises(IntegrityError), transaction.atomic():
        AchatFormation.objects.create(
            organisation=resultat.organisation,
            formation=resultat.formation,
            reference_paiement="cs_test_autre_reference",
        )


# ── 4. Le webhook, de bout en bout ───────────────────────────────────────────


def _evenement(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "type": "checkout.session.completed",
        "data": {"object": session},
    }


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_un_evenement_SIGNE_livre_la_formation_et_previent_une_fois(
    monkeypatch: Any,
) -> None:
    partis = _courriels_en_doublure(monkeypatch)
    formation = formation_en_vente()
    session = session_stripe(formation)

    reponse = poster_evenement(_evenement(session))

    assert reponse.status_code == 200, reponse.content
    assert reponse.json() == {
        "recu": True,
        "traite": True,
        "verdict": f"formation livree ({formation.slug})",
    }
    achat = AchatFormation.objects.get()
    assert achat.reference_paiement == session["id"]
    assert Encaissement.objects.count() == 1
    assert OperationalIncident.objects.count() == 0
    assert len(partis) == 1

    # Un AUTRE événement pour la même session (Stripe en envoie) : rien de plus.
    second = poster_evenement(_evenement(session))

    assert second.json()["verdict"] == "formation deja livree"
    assert AchatFormation.objects.count() == 1
    assert len(partis) == 1


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_un_evenement_mal_signe_ne_livre_rien() -> None:
    """Contre-épreuve : c'est bien la signature qui ouvre la porte."""
    session = session_stripe(formation_en_vente())

    reponse = poster_evenement(_evenement(session), signature="t=1,v1=faux")

    assert reponse.status_code == 400
    assert AchatFormation.objects.count() == 0


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_un_paiement_en_attente_ne_livre_rien_et_n_ouvre_pas_d_incident() -> None:
    """Un prélèvement termine la session « unpaid » et se confirme plus tard."""
    session = session_stripe(formation_en_vente(), payment_status="unpaid")

    reponse = poster_evenement(_evenement(session))

    assert reponse.status_code == 200
    assert AchatFormation.objects.count() == 0
    assert OperationalIncident.objects.count() == 0

    # La confirmation différée repasse par le même traitement, et livre.
    session["payment_status"] = "paid"
    confirme = {**_evenement(session), "type": "checkout.session.async_payment_succeeded"}
    poster_evenement(confirme)

    assert AchatFormation.objects.count() == 1


def test_une_formation_inconnue_au_webhook_ouvre_un_incident() -> None:
    session = session_stripe(formation_en_vente())
    session["metadata"]["formation_slug"] = "disparue"

    verdict = abonnements.sur_session_terminee(session)

    assert verdict == "achat de formation inexploitable"
    incident = OperationalIncident.objects.get()
    assert incident.title == "Achat de formation inexploitable"
    # Abrégée : l'identifiant entier ne s'écrit plus dans un incident (audit
    # du 20/11/2026).
    assert incident.details["session"] == f"{session['id'][:12]}…{session['id'][-4:]}"
    assert session["id"] not in json.dumps(incident.details)


def test_le_webhook_dit_qu_un_paiement_est_en_double(monkeypatch: Any) -> None:
    partis = _courriels_en_doublure(monkeypatch)
    formation = formation_en_vente()
    premiere = session_stripe(formation)
    seconde = session_stripe(formation, customer_details=premiere["customer_details"])

    abonnements.sur_session_terminee(premiere)
    verdict = abonnements.sur_session_terminee(seconde)

    assert verdict == f"formation payee deux fois ({formation.slug})"
    assert len(partis) == 1, "le second paiement n'annonce pas un second accès"


# ── 5. Le courriel ───────────────────────────────────────────────────────────


def test_le_courriel_annonce_la_formation_et_non_une_etude_a_lancer(
    monkeypatch: Any, settings: Any
) -> None:
    settings.EVKHA_APP_URL = "https://app.exemple.fr"
    partis = _courriels_en_doublure(monkeypatch)
    formation = formation_en_vente(titre="Méthode P.O.P")
    resultat = formations.livrer_la_formation(session_stripe(formation))

    assert formations.prevenir_l_acheteur(resultat) is True

    assert resultat.compte is not None
    (message,) = partis
    assert message["destinataire"] == resultat.compte.customer.email
    assert message["sujet"] == "Votre formation « Méthode P.O.P » est disponible"
    corps = message["corps_html"]
    assert "disponible" in corps and "espace client" in corps
    assert "https://app.exemple.fr/definir-mot-de-passe?id=" in corps
    # Vouvoiement, et rien du message rédigé pour une étude à produire.
    assert "Votre formation" in corps and "Choisissez votre mot de passe" in corps
    for intrus in ("à lancer", "la production", "votre document", " tu ", " ton ", " ta "):
        assert intrus not in corps, intrus


def test_le_courriel_part_UNE_fois_et_pas_au_rejeu(monkeypatch: Any) -> None:
    """Par la page de retour comme par le webhook, dans n'importe quel ordre."""
    partis = _courriels_en_doublure(monkeypatch)
    session = session_stripe(formation_en_vente())

    premier = _revenir(monkeypatch, session)
    abonnements.sur_session_terminee(session)
    second = _revenir(monkeypatch, session)

    assert (premier.status_code, second.status_code) == (200, 200)
    assert len(partis) == 1


# ── 6. Le retour du paiement ─────────────────────────────────────────────────


def test_le_retour_livre_et_ouvre_la_session_du_compte_ne_de_ce_paiement(
    monkeypatch: Any,
) -> None:
    """De bout en bout : le jeton rendu lit la formation dans l'espace."""
    _courriels_en_doublure(monkeypatch)
    formation = formation_en_vente()
    session = session_stripe(formation)

    reponse = _revenir(monkeypatch, session)

    assert reponse.status_code == 200, reponse.content
    corps = reponse.json()
    assert set(corps) == {"jeton", "connexion_requise", "titre", "slug"}
    assert corps["jeton"] and corps["connexion_requise"] is False
    assert (corps["titre"], corps["slug"]) == (formation.titre, formation.slug)
    # La réponse publique ne porte aucun contenu de leçon.
    assert VIDEO not in reponse.content.decode() and TEXTE not in reponse.content.decode()

    espace = Client().get(ESPACE, headers={"Authorization": f"Bearer {corps['jeton']}"})

    assert espace.status_code == 200, espace.content
    (lue,) = espace.json()["formations"]
    assert lue["slug"] == formation.slug
    assert lue["modules"][0]["lecons"][0]["adresse_video"] == VIDEO


def test_rejouer_le_retour_ne_rend_pas_un_second_jeton(monkeypatch: Any) -> None:
    _courriels_en_doublure(monkeypatch)
    session = session_stripe(formation_en_vente())

    premier = _revenir(monkeypatch, session).json()
    second = _revenir(monkeypatch, session).json()

    assert premier["jeton"]
    assert second["jeton"] is None and second["connexion_requise"] is True
    assert JetonAcces.objects.count() == 1
    assert AchatFormation.objects.count() == 1


def test_payer_avec_l_adresse_d_une_cliente_n_ouvre_pas_son_espace(
    monkeypatch: Any,
) -> None:
    """Stripe prouve qu'une carte a été encaissée — pas que le payeur possède
    l'adresse qu'il a saisie. L'achat, lui, est bien livré à son espace."""
    _courriels_en_doublure(monkeypatch)
    cliente = Inscrit(email="claire@cabinet.example")
    jetons_avant = JetonAcces.objects.count()
    session = session_stripe(formation_en_vente())
    session["customer_details"]["email"] = "claire@cabinet.example"

    reponse = _revenir(monkeypatch, session)

    assert reponse.status_code == 200
    assert reponse.json()["jeton"] is None
    assert reponse.json()["connexion_requise"] is True
    assert JetonAcces.objects.count() == jetons_avant
    assert AchatFormation.objects.get().organisation == cliente.organisation


def test_une_session_de_BOUTIQUE_est_refusee_au_retour_des_formations(
    monkeypatch: Any,
) -> None:
    """Chaque page de retour ne traite que SON achat."""
    session = session_de_boutique(produit_en_ligne())

    reponse = _revenir(monkeypatch, session)

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "achat_autre"
    assert AchatFormation.objects.count() == 0
    assert AchatProduit.objects.count() == 0
    assert Organisation.objects.count() == 0


@pytest.mark.parametrize(
    "adresse", ["/api/public/boutique/retour/", "/api/public/acheter/retour/"]
)
def test_une_session_de_FORMATION_est_refusee_aux_autres_retours(
    monkeypatch: Any, adresse: str
) -> None:
    """Dans l'autre sens : ni fichier de boutique, ni crédit d'étude."""
    from organisations.models import MouvementCredit  # noqa: PLC0415

    session = session_stripe(formation_en_vente())

    reponse = _revenir(monkeypatch, session, adresse)

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "achat_autre"
    assert AchatFormation.objects.count() == 0
    assert AchatProduit.objects.count() == 0
    assert MouvementCredit.objects.count() == 0
    assert Organisation.objects.count() == 0


def test_la_fonction_de_boutique_ne_livre_pas_une_formation() -> None:
    """Même appelée directement : le slug d'une formation n'est pas un produit."""
    session = session_stripe(formation_en_vente())

    with pytest.raises(boutique.AchatInexploitable):
        boutique.livrer_le_produit(session)

    assert boutique.est_un_achat_de_produit(session) is False
    assert formations.est_un_achat_de_formation(session) is True
    assert formations.est_un_achat_de_formation(session_de_boutique(produit_en_ligne())) is False


def test_un_retour_sans_session_ou_non_paye_ne_livre_rien(monkeypatch: Any) -> None:
    formation = formation_en_vente()

    sans = _poster(RETOUR, {})
    non_payee = _revenir(monkeypatch, session_stripe(formation, payment_status="unpaid"))

    assert (sans.status_code, sans.json()["code"]) == (400, "session_absente")
    # Terminée mais non encaissée : la banque doit encore confirmer. Ce n'est
    # plus annoncé comme un paiement « qu'on n'a pas pu rattacher »
    # (`retours.refus_si_non_encaisse`).
    assert (non_payee.status_code, non_payee.json()["code"]) == (409, "paiement_en_attente")
    assert AchatFormation.objects.count() == 0


def test_une_session_que_stripe_ne_connait_pas_rend_503(monkeypatch: Any) -> None:
    """L'identifiant vient de l'adresse de retour, donc de l'extérieur."""

    def inconnue(identifiant: str) -> Any:
        raise stripe_api.PaiementIndisponible("Ce paiement n'a pas pu être vérifié.")

    monkeypatch.setattr(stripe_api, "relire_la_session", inconnue)

    # Un identifiant qui a la FORME d'une session : les autres ne partent plus
    # chez Stripe (`test_audit_des_formations_du_20_novembre`).
    reponse = _poster(RETOUR, {"session": "cs_test_a1b2c3d4e5f6g7h8"})

    assert (reponse.status_code, reponse.json()["code"]) == (503, "session_illisible")
    assert AchatFormation.objects.count() == 0


# ── 7. L'achat depuis l'espace ───────────────────────────────────────────────


@override_settings(**REGLAGES)
def test_l_achat_depuis_l_espace_designe_l_organisation_du_COMPTE(
    monkeypatch: Any,
) -> None:
    cliente = Inscrit()
    autre = Inscrit(nom="Autre cabinet", email="autre@exemple.fr")
    formation = formation_en_vente()
    envois = _stripe_en_doublure(monkeypatch)

    reponse = _poster(
        ESPACE_ACHETER,
        {
            "formation": formation.slug,
            "organisation_id": str(autre.organisation.id),
            "prix_cents": 1,
            "email": "ailleurs@example.com",
        },
        headers=cliente.entetes,
    )

    assert reponse.status_code == 200, reponse.content
    assert reponse.json() == {"adresse": "https://checkout.stripe.com/c/pay/session"}
    (envoi,) = envois
    assert envoi["metadata"] == {
        "achat": "formation",
        "formation_slug": formation.slug,
        "organisation_id": str(cliente.organisation.id),
    }
    assert envoi["customer_email"] == cliente.contact.email
    assert envoi["line_items"][0]["price_data"]["unit_amount"] == formation.prix_cents
    tentative = TentativePaiement.objects.get()
    assert tentative.organisation == cliente.organisation
    assert (tentative.objet, tentative.formation) == (ObjetTentative.FORMATION, formation)


@override_settings(**REGLAGES)
def test_une_formation_DEJA_achetee_n_ouvre_pas_un_second_paiement(
    monkeypatch: Any,
) -> None:
    cliente = Inscrit()
    autre = Inscrit(nom="Autre cabinet", email="autre@exemple.fr")
    formation = formation_en_vente()
    session = session_stripe(formation)
    session["metadata"]["organisation_id"] = str(cliente.organisation.id)
    formations.livrer_la_formation(session)
    envois = _stripe_en_doublure(monkeypatch)

    reponse = _poster(ESPACE_ACHETER, {"formation": formation.slug}, headers=cliente.entetes)

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "formation_deja_achetee"
    assert reponse.json()["error"]
    assert envois == []

    # Contre-épreuve : une autre organisation l'achète, elle.
    libre = _poster(ESPACE_ACHETER, {"formation": formation.slug}, headers=autre.entetes)
    assert libre.status_code == 200, libre.content
    assert len(envois) == 1


@override_settings(**REGLAGES)
def test_l_espace_applique_la_MEME_regle_de_vente_que_la_page_publique(
    monkeypatch: Any,
) -> None:
    cliente = Inscrit()
    vide = Formation.objects.create(
        titre="Vide", slug="vide", prix_cents=85_000, en_ligne=True
    )
    hors_ligne = formation_en_vente(en_ligne=False)
    envois = _stripe_en_doublure(monkeypatch)

    sans_programme = _poster(ESPACE_ACHETER, {"formation": vide.slug}, headers=cliente.entetes)
    introuvable = _poster(
        ESPACE_ACHETER, {"formation": hors_ligne.slug}, headers=cliente.entetes
    )

    assert (sans_programme.status_code, sans_programme.json()["code"]) == (
        409, "formation_sans_programme",
    )
    assert (introuvable.status_code, introuvable.json()["code"]) == (404, "formation_inconnue")
    assert envois == []


def test_l_achat_depuis_l_espace_exige_une_session() -> None:
    formation = formation_en_vente()

    reponse = _poster(ESPACE_ACHETER, {"formation": formation.slug})

    assert reponse.status_code == 401
    assert reponse.json()["code"] == "unauthorized"


def test_l_achat_depuis_l_espace_est_ferme_a_l_assistance() -> None:
    """Le garde-fou est porté par le décorateur, pas par une promesse."""
    vue = vues_espace.acheter_une_formation

    assert vue.interdit_en_assistance is True
    assert (vue.action_lecture, vue.action_ecriture) == ("commander", "commander")
    # Mêmes droits que l'achat de boutique, qui est le modèle.
    modele = vues_espace.acheter_un_produit
    assert (vue.action_lecture, vue.action_ecriture, vue.interdit_en_assistance) == (
        modele.action_lecture, modele.action_ecriture, modele.interdit_en_assistance,
    )


# ── 8. L'espace de l'acheteur ────────────────────────────────────────────────


def _acheter_pour(cliente: Inscrit, formation: Formation) -> AchatFormation:
    session = session_stripe(formation)
    session["metadata"]["organisation_id"] = str(cliente.organisation.id)
    return formations.livrer_la_formation(session).achat


def _programme_complet() -> Formation:
    """Deux modules présents, des éléments retirés, un document joint."""
    formation = formation_en_vente(
        slug="methode-pop", heures_de_coaching=2, titre="Méthode P.O.P"
    )
    premier = formation.modules.get()
    ModuleDeFormation.objects.filter(pk=premier.pk).update(rang=3)
    LeconDeFormation.objects.filter(module=premier).update(rang=4)
    document = LeconDeFormation.objects.create(
        module=premier, titre="Le support", nature="document", rang=7
    )
    # Le chemin seul : aucun fichier n'est écrit, la signature ne lit pas le disque.
    LeconDeFormation.objects.filter(pk=document.pk).update(
        fichier="formations/methode-pop/support-reserve.pdf"
    )
    LeconDeFormation.objects.create(
        module=premier, titre="Leçon retirée", rang=0, texte="RETIREE",
        retire_le="2026-11-01T10:00:00Z",
    )
    retire = ModuleDeFormation.objects.create(
        formation=formation, titre="Module retiré", rang=0,
        retire_le="2026-11-01T10:00:00Z",
    )
    LeconDeFormation.objects.create(module=retire, titre="Leçon d'un module retiré")
    second = ModuleDeFormation.objects.create(formation=formation, titre="Prospecter", rang=9)
    LeconDeFormation.objects.create(module=second, titre="Le premier message", texte="Bonjour.")
    return formation


def test_l_espace_rend_le_contenu_a_l_organisation_qui_l_a_paye(settings: Any) -> None:
    settings.EVKHA_BASE_URL = "https://api2.evkha.fr"
    cliente = Inscrit()
    formation = _programme_complet()
    achat = _acheter_pour(cliente, formation)
    video, document = LeconDeFormation.objects.filter(
        module__titre="Poser son offre", retire_le__isnull=True
    ).order_by("rang")

    reponse = Client().get(ESPACE, headers=cliente.entetes)

    assert reponse.status_code == 200, reponse.content
    (lue,) = reponse.json()["formations"]
    lien = lue["modules"][0]["lecons"][1]["fichier"]
    assert lue == {
        "slug": "methode-pop",
        "titre": "Méthode P.O.P",
        "sous_titre": "Poser, Offrir, Prospecter",
        "accroche": "Sept heures pour trouver ses premiers clients.",
        "image": "",
        "duree_heures": 7,
        "heures_de_coaching": 2,
        "achetee_le": achat.created_at.isoformat(),
        # Le suivi de l'élève (Qualiopi) : son accès, et où il en est. Trois
        # leçons PRÉSENTES — ni la leçon retirée, ni celle du module retiré.
        "acces": "ouvert",
        "acces_jusqu_au": None,
        "progression": {"terminees": 0, "total": 3, "pourcent": 0},
        "seances": [],
        "modules": [
            {
                "rang": 1,
                "titre": "Poser son offre",
                "description": "Le socle.",
                "lecons": [
                    {
                        "id": str(video.id),
                        "rang": 1,
                        "titre": "Choisir sa cible",
                        "nature": "video",
                        "duree_minutes": 12,
                        "adresse_video": VIDEO,
                        "texte": TEXTE,
                        "fichier": "",
                        "fichier_nom": "",
                        "terminee": False,
                    },
                    {
                        "id": str(document.id),
                        "rang": 2,
                        "titre": "Le support",
                        "nature": "document",
                        "duree_minutes": 0,
                        "adresse_video": "",
                        "texte": "",
                        "fichier": lien,
                        "fichier_nom": "support-reserve.pdf",
                        "terminee": False,
                    },
                ],
            },
            {
                "rang": 2,
                "titre": "Prospecter",
                "description": "",
                "lecons": [
                    {
                        "id": str(LeconDeFormation.objects.get(titre="Le premier message").id),
                        "rang": 1,
                        "titre": "Le premier message",
                        "nature": "texte",
                        "duree_minutes": 0,
                        "adresse_video": "",
                        "texte": "Bonjour.",
                        "fichier": "",
                        "fichier_nom": "",
                        "terminee": False,
                    }
                ],
            },
        ],
    }
    # Les éléments retirés n'y sont sous aucune forme.
    texte = reponse.content.decode()
    for retire in ("Leçon retirée", "RETIREE", "Module retiré", "Leçon d'un module retiré"):
        assert retire not in texte, retire


def test_le_lien_du_document_est_SIGNE_ABSOLU_et_court(settings: Any) -> None:
    """Relatif, il rendrait la page de l'application à la place du document ;
    nu, il servirait le support à qui devine son chemin."""
    settings.EVKHA_BASE_URL = "https://api2.evkha.fr"
    cliente = Inscrit()
    _acheter_pour(cliente, _programme_complet())
    chemin = "formations/methode-pop/support-reserve.pdf"

    lien = Client().get(ESPACE, headers=cliente.entetes).json()["formations"][0][
        "modules"
    ][0]["lecons"][1]["fichier"]

    prefixe = f"https://api2.evkha.fr/media/{chemin}?{signatures.PARAMETRE}="
    assert lien.startswith(prefixe), lien
    signature = lien[len(prefixe):]
    assert signatures.signature_valable(chemin, signature)
    # La signature ne vaut que pour CE fichier.
    assert not signatures.signature_valable("formations/methode-pop/autre.pdf", signature)
    # Courte : une heure au plus, et non le repli d'une semaine.
    assert signatures._duree_portee(signature) == vues_espace.VIE_DU_LIEN_DE_LECON_S
    assert 0 < vues_espace.VIE_DU_LIEN_DE_LECON_S <= 3600
    # Jamais stocké : la base ne garde que le chemin.
    assert LeconDeFormation.objects.get(titre="Le support").fichier.name == chemin


def test_une_AUTRE_organisation_ne_voit_rien() -> None:
    """Le cloisonnement : la requête part de l'achat, jamais de la formation."""
    cliente = Inscrit()
    voisine = Inscrit(nom="Cabinet voisin", email="voisine@exemple.fr")
    _acheter_pour(cliente, formation_en_vente())

    chez_la_voisine = Client().get(ESPACE, headers=voisine.entetes)

    assert chez_la_voisine.status_code == 200
    assert chez_la_voisine.json() == {"formations": []}
    assert VIDEO not in chez_la_voisine.content.decode()
    # Contre-épreuve : la propriétaire, elle, la lit — la liste vide ne vient
    # pas d'une vue qui ne rendrait jamais rien.
    chez_elle = Client().get(ESPACE, headers=cliente.entetes).json()["formations"]
    assert len(chez_elle) == 1


def test_une_formation_en_ligne_NON_achetee_n_apparait_pas() -> None:
    """Être publiée ne donne aucun accès : seul l'achat en donne."""
    cliente = Inscrit()
    achetee = formation_en_vente(titre="Achetée")
    formation_en_vente(titre="Seulement publiée")
    _acheter_pour(cliente, achetee)

    lues = Client().get(ESPACE, headers=cliente.entetes).json()["formations"]

    assert [f["titre"] for f in lues] == ["Achetée"]


def test_une_formation_mise_HORS_LIGNE_reste_lisible_par_qui_l_a_payee() -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    Formation.objects.filter(pk=formation.pk).update(en_ligne=False)

    lues = Client().get(ESPACE, headers=cliente.entetes).json()["formations"]

    assert [f["slug"] for f in lues] == [formation.slug]
    assert lues[0]["modules"][0]["lecons"][0]["texte"] == TEXTE
    # Et le public, lui, ne la voit plus.
    assert Client().get("/api/public/formations/").json()["formations"] == []


def test_sans_session_l_espace_des_formations_est_ferme() -> None:
    cliente = Inscrit()
    _acheter_pour(cliente, formation_en_vente())

    sans = Client().get(ESPACE)
    faux = Client().get(ESPACE, headers={"Authorization": "Bearer un-jeton-invente"})

    for reponse in (sans, faux):
        assert reponse.status_code == 401
        assert reponse.json()["code"] == "unauthorized"
        assert VIDEO not in reponse.content.decode()
    assert Client().post(ESPACE, headers=cliente.entetes).status_code == 405


def test_les_pages_PUBLIQUES_ne_rendent_toujours_pas_le_contenu_payant(
    monkeypatch: Any,
) -> None:
    """L'espace est le SEUL endroit : ni le catalogue, ni le retour de paiement."""
    _courriels_en_doublure(monkeypatch)
    formation = _programme_complet()

    catalogue = Client().get("/api/public/formations/")
    retour = _revenir(monkeypatch, session_stripe(formation))

    for reponse in (catalogue, retour):
        texte = reponse.content.decode()
        for secret in ("secret-246810", TEXTE, "support-reserve", "/media/formations/"):
            assert secret not in texte, secret
        assert not (_cles(reponse.json()) & set(regles.CONTENU_PAYANT))
    # Contre-épreuve : les deux réponses ne sont pas vides.
    assert "Choisir sa cible" in catalogue.content.decode()
    assert retour.json()["slug"] == formation.slug


def test_l_espace_ne_coute_pas_une_requete_de_plus_par_formation() -> None:
    """Achats, modules, leçons : le nombre de requêtes ne suit pas le volume.

    Comparé à lui-même plutôt qu'à un nombre : la reconnaissance de la session
    en compte quelques-unes, qui ne sont pas l'objet de ce test.
    """
    cliente = Inscrit()
    _acheter_pour(cliente, formation_en_vente())

    def compter() -> tuple[int, int]:
        with CaptureQueriesContext(connection) as capture:
            reponse = Client().get(ESPACE, headers=cliente.entetes)
        return len(capture), len(reponse.json()["formations"])

    requetes_pour_une, lues_pour_une = compter()
    for _ in range(4):
        _acheter_pour(cliente, formation_en_vente())
    requetes_pour_cinq, lues_pour_cinq = compter()

    assert (lues_pour_une, lues_pour_cinq) == (1, 5)
    assert requetes_pour_cinq == requetes_pour_une


# ── 9. L'administration ──────────────────────────────────────────────────────


def test_la_fiche_d_administration_compte_les_achats_sans_requete_de_plus(
    client_admin: Any, django_assert_num_queries: Any
) -> None:
    """Formations, modules, leçons : le compte vient avec la première."""
    vendue_deux_fois = formation_en_vente(titre="Vendue deux fois", rang=0)
    vendue_une_fois = formation_en_vente(titre="Vendue une fois", rang=1)
    formation_en_vente(titre="Jamais vendue", rang=2)
    for _ in range(2):
        formations.livrer_la_formation(session_stripe(vendue_deux_fois))
    formations.livrer_la_formation(session_stripe(vendue_une_fois))

    with django_assert_num_queries(3):
        fiches = client_admin.get(ADMIN).json()["formations"]

    assert {f["titre"]: f["nombre_d_achats"] for f in fiches} == {
        "Vendue deux fois": 2,
        "Vendue une fois": 1,
        "Jamais vendue": 0,
    }
    assert all(f["publiable"] for f in fiches)


def test_la_fiche_rendue_apres_une_modification_compte_aussi(client_admin: Any) -> None:
    formation = formation_en_vente()
    formations.livrer_la_formation(session_stripe(formation))

    reponse = client_admin.post(
        f"{ADMIN}{formation.id}/", data={"accroche": "Neuve"}, content_type="application/json"
    )

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["formation"]["nombre_d_achats"] == 1


# ── 10. L'amorçage ───────────────────────────────────────────────────────────


def test_l_amorcage_ne_pose_plus_de_lien_d_achat_exterieur() -> None:
    """Les pages de paiement de l'ancien site n'existent plus."""
    from catalog.management.commands import seed_formations  # noqa: PLC0415

    call_command("seed_formations", stdout=io.StringIO())

    assert Formation.objects.count() == 3
    assert set(Formation.objects.values_list("lien_d_achat", flat=True)) == {""}
    assert not any(
        isinstance(valeur, str) and "://" in valeur
        for ligne in seed_formations.FORMATIONS
        for valeur in ligne
    )
    # Le champ, lui, reste dans la réponse publique : les pages en lisent la clé.
    formation_en_vente()
    assert Client().get("/api/public/formations/").json()["formations"][0]["lien_d_achat"] == ""
