"""Ce que l'audit de sécurité du 20/11/2026 avait trouvé sans le corriger.

La boutique et les formations avaient reçu leurs gardes ; quatre points
restaient ouverts ailleurs, nommés au rapport de mise en ligne :

1. **l'étude à l'unité** ne vérifiait ni le montant encaissé ni le mode de la
   session, et ne reconnaissait un rejeu qu'APRÈS avoir écrit ;
2. **la souscription et l'achat de crédits** ouvraient des sessions de
   paiement sans plafond par organisation ;
3. **les journaux et les incidents** de l'étude, de la boutique et des crédits
   portaient l'identifiant de session en entier — celui qui, présenté à une
   page de retour, ouvre la première session du compte né du paiement ;
4. **les pages de retour** répondaient « votre paiement a bien été reçu » à
   quelqu'un dont le prélèvement attendait la banque, ou qui n'avait rien payé.

Chaque test échoue sur le code d'avant (règle 6), et chaque garde a sa
contre-épreuve : ce qui est juste continue de passer.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from django.test.utils import override_settings
from paiement import achats, boutique

from monitoring.models import OperationalIncident
from organisations.models import (
    Encaissement,
    MouvementCredit,
    ObjetTentative,
    Organisation,
    TentativePaiement,
)
from tests.test_achat_a_l_unite import offre_a_l_unite
from tests.test_achat_a_l_unite import session_stripe as session_d_etude
from tests.test_achat_de_formation import (
    REGLAGES,
    _stripe_en_doublure,
    formation_en_vente,
)
from tests.test_achat_de_formation import session_stripe as session_de_formation
from tests.test_audit_des_formations_du_20_novembre import (
    RETOURS,
    _plafond_de_l_espace_a_deux,
    _poster,
    _relectures,
)
from tests.test_barriere_de_paiement import (
    SECRET_WEBHOOK,
    Inscrit,
    formule,
    poster_evenement,
)
from tests.test_boutique import produit_en_ligne
from tests.test_boutique import session_stripe as session_de_boutique
from tests.test_cycle_de_l_abonnement import Abonne

pytestmark = pytest.mark.django_db


def _evenement(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "type": "checkout.session.completed",
        "data": {"object": session},
    }


# ── 1. L'étude à l'unité : ce qui est livré est ce qui a été ouvert ──────────


@pytest.mark.parametrize(
    "ecart",
    [
        {"amount_total": 100},
        {"amount_total": None},
        {"currency": "usd"},
        {"mode": "subscription"},
        {"mode": "setup"},
    ],
)
def test_une_etude_n_est_pas_livree_pour_une_session_qui_n_est_pas_la_sienne(
    ecart: dict[str, Any],
) -> None:
    """Toute session payée portant le slug d'une étude versait son crédit."""
    session = session_d_etude(offre_a_l_unite())
    session.update(ecart)

    with pytest.raises(achats.AchatInexploitable):
        achats.livrer_l_achat(session)

    assert MouvementCredit.objects.count() == 0
    assert Encaissement.objects.count() == 0
    assert Organisation.objects.count() == 0


def test_contre_epreuve_le_prix_paye_au_clic_reste_livre_si_le_tarif_change() -> None:
    """Le montant de référence est celui du PANIER, quand il y en a un : qui a
    payé le prix affiché au clic n'est pas refusé parce que le tarif a bougé."""
    offre = offre_a_l_unite(prix=14_900)
    session = session_d_etude(offre)
    TentativePaiement.objects.create(
        objet=ObjetTentative.LIVRABLE,
        reference_session=session["id"],
        montant_cents=14_900,
        devise="EUR",
    )
    offre.prix_unitaire_cents = 19_900
    offre.save(update_fields=["prix_unitaire_cents"])

    achat = achats.livrer_l_achat(session)

    assert achat.nouveau is True
    assert MouvementCredit.objects.count() == 1


# ── 2. L'étude à l'unité : un rejeu n'écrit plus rien ────────────────────────


def test_le_rejeu_d_une_etude_livree_ne_repasse_pas_par_l_ouverture_d_espace(
    monkeypatch: Any,
) -> None:
    """`espace_de_l_acheteur` révoque des invitations et ouvre une organisation :
    un rejeu la traversait à chaque fois avant de reconnaître le crédit versé."""
    session = session_d_etude(offre_a_l_unite())
    premier = achats.livrer_l_achat(session)

    def interdit(*_: Any, **__: Any) -> Any:
        raise AssertionError("un rejeu a rouvert l'espace de l'acheteur")

    monkeypatch.setattr(achats, "espace_de_l_acheteur", interdit)
    rejeu = achats.livrer_l_achat(session)

    assert rejeu.nouveau is False
    assert rejeu.organisation == premier.organisation
    # Le compte né de CE paiement est retrouvé : la page de retour en a besoin
    # pour ouvrir la session quand le webhook est arrivé le premier.
    assert rejeu.compte is not None
    assert rejeu.compte.ne_de_l_achat == session["id"]
    assert MouvementCredit.objects.count() == 1


def test_le_rejeu_survit_au_retrait_de_l_offre() -> None:
    """Le rejeu d'un achat livré était refusé — « inexploitable », incident à
    l'appui — dès que l'offre avait été désactivée entre-temps."""
    offre = offre_a_l_unite()
    session = session_d_etude(offre)
    achats.livrer_l_achat(session)
    offre.is_active = False
    offre.save(update_fields=["is_active"])

    rejeu = achats.livrer_l_achat(session)

    assert rejeu.nouveau is False
    assert rejeu.offre == offre


def test_contre_epreuve_une_offre_retiree_ne_se_vend_toujours_pas() -> None:
    offre = offre_a_l_unite()
    offre.is_active = False
    offre.save(update_fields=["is_active"])

    with pytest.raises(achats.AchatInexploitable):
        achats.livrer_l_achat(session_d_etude(offre))


# ── 3. Souscription et crédits : le plafond par organisation ─────────────────


def _abonnee_au_credit_tarife() -> Abonne:
    """Sans tarif du crédit supplémentaire, l'achat est refusé avant Stripe."""
    abonnee = Abonne()
    abonnee.abonnement.formule.prix_credit_supplementaire_cents = 5_900
    abonnee.abonnement.formule.save()
    return abonnee


def _acheter_des_credits() -> tuple[Any, str, dict[str, Any]]:
    return _abonnee_au_credit_tarife(), "/api/espace/credits/acheter/", {"quantite": 1}


def _souscrire() -> tuple[Any, str, dict[str, Any]]:
    return Inscrit(), "/api/espace/paiement/", {"formule": formule().code}


@override_settings(**REGLAGES)
@pytest.mark.parametrize("cas", [_acheter_des_credits, _souscrire])
def test_la_souscription_et_les_credits_ont_le_plafond_de_l_espace(
    monkeypatch: Any, cas: Any
) -> None:
    """Les trois achats de l'espace avaient reçu ce plafond ; ces deux routes,
    qui ouvrent des sessions de paiement de la même façon, non."""
    cliente, adresse, charge = cas()
    envois = _stripe_en_doublure(monkeypatch)
    _plafond_de_l_espace_a_deux(monkeypatch)

    reponses = [_poster(adresse, charge, headers=cliente.entetes) for _ in range(3)]

    assert [r.status_code for r in reponses] == [200, 200, 429]
    assert reponses[2].json()["code"] == "trop_de_tentatives"
    assert len(envois) == 2, "le refus est parti chez Stripe quand même"


@override_settings(**REGLAGES)
def test_une_demande_refusee_avant_stripe_ne_consomme_pas_le_plafond(
    monkeypatch: Any,
) -> None:
    """Contre-épreuve : une quantité invalide n'a rien coûté, elle n'est pas
    comptée — sinon trois fautes de frappe fermeraient le paiement une heure."""
    abonnee = _abonnee_au_credit_tarife()
    _stripe_en_doublure(monkeypatch)
    _plafond_de_l_espace_a_deux(monkeypatch)
    adresse = "/api/espace/credits/acheter/"

    for _ in range(3):
        refus = _poster(adresse, {"quantite": 0}, headers=abonnee.entetes)
        assert refus.status_code == 400

    assert _poster(adresse, {"quantite": 1}, headers=abonnee.entetes).status_code == 200


# ── 4. Journaux et incidents : la référence n'y est plus entière ─────────────


@pytest.mark.parametrize(
    ("livrer", "session"),
    [
        (achats.livrer_l_achat, lambda: session_d_etude(offre_a_l_unite())),
        (boutique.livrer_le_produit, lambda: session_de_boutique(produit_en_ligne())),
    ],
)
@pytest.mark.parametrize(
    "defaut",
    [
        {"payment_status": "unpaid"},
        {"customer_details": {}},
        {"metadata": {"offre_slug": "inconnu", "produit_slug": "inconnu"}},
    ],
)
def test_le_motif_d_un_refus_ne_porte_pas_la_reference_entiere(
    livrer: Any, session: Any, defaut: dict[str, Any]
) -> None:
    """Le motif part dans le journal ET dans l'incident : il était écrit avec
    l'identifiant de session entier."""
    fabriquee = session()
    fabriquee.update(defaut)

    with pytest.raises(achats.AchatInexploitable) as refus:
        livrer(fabriquee)

    assert fabriquee["id"] not in str(refus.value)
    assert achats.reference_abregee(fabriquee["id"]) in str(refus.value)


def _etude_au_mauvais_montant() -> tuple[dict[str, Any], str]:
    session = session_d_etude(offre_a_l_unite())
    session["amount_total"] = 100
    return session, "Achat a l'unite inexploitable"


def _produit_au_mauvais_montant() -> tuple[dict[str, Any], str]:
    session = session_de_boutique(produit_en_ligne(), status="complete")
    session["amount_total"] = 100
    return session, "Achat de boutique inexploitable"


def _credits_sans_organisation() -> tuple[dict[str, Any], str]:
    return {
        "id": f"cs_test_{uuid.uuid4().hex[:16]}",
        "status": "complete",
        "mode": "payment",
        "payment_status": "paid",
        "metadata": {"achat": "credits", "quantite": "2", "organisation_id": ""},
    }, "Achat de credits inexploitable"


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
@pytest.mark.parametrize(
    "cas",
    [_etude_au_mauvais_montant, _produit_au_mauvais_montant, _credits_sans_organisation],
)
def test_l_incident_d_un_achat_inexploitable_abrege_la_session(cas: Any) -> None:
    """L'incident se lit dans l'administration : il portait la session entière.
    L'intention de paiement, elle, y est — c'est par elle qu'on retrouve le
    paiement chez le prestataire."""
    session, titre = cas()
    session["payment_intent"] = "pi_3QabcDEF456ghiJKL"

    reponse = poster_evenement(_evenement(session))

    assert reponse.status_code == 200, reponse.content
    incident = OperationalIncident.objects.get()
    assert incident.title == titre
    assert session["id"] not in json.dumps(incident.details)
    assert incident.details["session"] == achats.reference_abregee(session["id"])
    assert incident.details["paiement"] == "pi_3QabcDEF456ghiJKL"
    assert MouvementCredit.objects.count() == 0


# ── 5. Les pages de retour : ne dire « reçu » que de ce qui est encaissé ─────


def _session_de(nature: str) -> dict[str, Any]:
    if nature == "livrable":
        return session_d_etude(offre_a_l_unite())
    if nature == "produit":
        return session_de_boutique(produit_en_ligne())
    return session_de_formation(formation_en_vente())


@override_settings(**REGLAGES)
@pytest.mark.parametrize("nature", sorted(RETOURS))
@pytest.mark.parametrize(
    ("etat", "code"),
    [("complete", "paiement_en_attente"), ("open", "paiement_non_abouti")],
)
def test_un_paiement_non_encaisse_n_est_pas_annonce_comme_recu(
    monkeypatch: Any, nature: str, etat: str, code: str
) -> None:
    """Un prélèvement en attente de la banque recevait « votre paiement a bien
    été reçu, mais votre accès n'a pas pu être ouvert » ; une session jamais
    terminée aussi."""
    session = _session_de(nature)
    session.update({"status": etat, "payment_status": "unpaid"})
    _relectures(monkeypatch, session)

    reponse = _poster(RETOURS[nature], {"session": session["id"]})

    assert reponse.status_code == 409
    corps = reponse.json()
    assert corps["code"] == code
    phrase = corps["erreur"]
    assert "bien été reçu" not in phrase
    assert "n'a pas pu être rattaché" not in phrase
    assert "contact@evkha.fr" in phrase
    assert MouvementCredit.objects.count() == 0
    assert OperationalIncident.objects.count() == 0


@override_settings(**REGLAGES)
def test_contre_epreuve_un_etat_inconnu_reste_un_refus_bruyant(monkeypatch: Any) -> None:
    """Seul « unpaid » est traduit. Un état que personne n'a prévu continue
    vers la livraison, qui le refuse : on ne devine pas (règle 1)."""
    session = session_d_etude(offre_a_l_unite())
    session["payment_status"] = "no_payment_required"
    _relectures(monkeypatch, session)

    reponse = _poster(RETOURS["livrable"], {"session": session["id"]})

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "achat_inexploitable"


@override_settings(**REGLAGES)
def test_contre_epreuve_un_paiement_encaisse_est_toujours_livre(monkeypatch: Any) -> None:
    session = session_d_etude(offre_a_l_unite())
    _relectures(monkeypatch, session)

    reponse = _poster(RETOURS["livrable"], {"session": session["id"]})

    assert reponse.status_code == 200, reponse.content
    assert MouvementCredit.objects.count() == 1


# ── 6. Ce que les deux relectures du correctif ont ajouté ────────────────────


@override_settings(**REGLAGES)
def test_l_achat_public_d_une_etude_note_le_prix_ouvert(monkeypatch: Any) -> None:
    """La page publique était la seule ouverture à ne noter aucun panier : un
    tarif modifié pendant le paiement faisait refuser, après encaissement,
    quelqu'un qui avait payé le prix affiché."""
    offre = offre_a_l_unite(prix=14_900)
    _stripe_en_doublure(monkeypatch)

    ouverture = _poster("/api/public/acheter/", {"livrable": offre.slug})
    assert ouverture.status_code == 200, ouverture.content
    panier = TentativePaiement.objects.get()
    assert (panier.objet, panier.montant_cents) == (ObjetTentative.LIVRABLE, 14_900)

    offre.prix_unitaire_cents = 19_900
    offre.save(update_fields=["prix_unitaire_cents"])
    session = session_d_etude(offre, identifiant=panier.reference_session)
    session["amount_total"] = 14_900

    assert achats.livrer_l_achat(session).nouveau is True


@override_settings(**REGLAGES)
@pytest.mark.parametrize(
    ("adresse", "charge"),
    [
        ("/api/public/acheter/", lambda: {"livrable": offre_a_l_unite().slug}),
        ("/api/public/boutique/acheter/", lambda: {"produit": produit_en_ligne().slug}),
    ],
)
def test_une_saisie_qui_n_est_pas_une_adresse_ne_part_pas_chez_stripe(
    monkeypatch: Any, adresse: str, charge: Any
) -> None:
    """Transmise telle quelle, elle faisait refuser l'ouverture — et le message
    du prestataire, qui la cite saut de ligne compris, partait au journal."""
    envois = _stripe_en_doublure(monkeypatch)

    reponse = _poster(adresse, {**charge(), "email": "victime@exemple.fr\nligne forgée"})

    assert reponse.status_code == 200, reponse.content
    assert "customer_email" not in envois[0]
    assert TentativePaiement.objects.get().email == ""


@override_settings(**REGLAGES)
def test_contre_epreuve_une_vraie_adresse_prerempli_toujours_le_paiement(
    monkeypatch: Any,
) -> None:
    envois = _stripe_en_doublure(monkeypatch)

    _poster(
        "/api/public/acheter/",
        {"livrable": offre_a_l_unite().slug, "email": "camille@example.com"},
    )

    assert envois[0]["customer_email"] == "camille@example.com"


@override_settings(**REGLAGES)
def test_le_retour_d_un_achat_livre_a_un_compte_existant_n_ouvre_rien(
    monkeypatch: Any,
) -> None:
    """Le rejeu ne rend alors AUCUN compte : la page répond quand même, propose
    la connexion, et ne verse rien de plus."""
    cliente = Inscrit()
    session = session_d_etude(offre_a_l_unite(), email=cliente.contact.email)
    assert achats.livrer_l_achat(session).nouveau is True
    _relectures(monkeypatch, session)

    reponse = _poster(RETOURS["livrable"], {"session": session["id"]})

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["jeton"] is None
    assert reponse.json()["connexion_requise"] is True
    assert MouvementCredit.objects.count() == 1
    rejeu = achats.livrer_l_achat(session)
    assert rejeu.compte is None
    assert achats.prevenir_l_acheteur(rejeu) is False


def test_le_rejeu_survit_a_une_offre_renommee() -> None:
    """Un achat DÉJÀ livré ne devient pas « inexploitable » parce que le
    catalogue a bougé : le crédit a gardé le type de livrable."""
    offre = offre_a_l_unite()
    session = session_d_etude(offre)
    achats.livrer_l_achat(session)
    offre.slug = f"renommee-{uuid.uuid4().hex[:8]}"
    offre.save(update_fields=["slug"])

    rejeu = achats.livrer_l_achat(session)

    assert rejeu.nouveau is False
    assert rejeu.offre.deliverable_type == offre.deliverable_type


def _credits_payes(abonnee: Abonne, **ecart: Any) -> dict[str, Any]:
    """Deux crédits ouverts à 59 € l'un, tels que la vue les note en panier."""
    reference = f"cs_test_{uuid.uuid4().hex[:16]}"
    TentativePaiement.objects.create(
        organisation=abonnee.organisation,
        objet=ObjetTentative.CREDITS,
        quantite=2,
        montant_cents=11_800,
        devise="EUR",
        reference_session=reference,
    )
    session: dict[str, Any] = {
        "id": reference,
        "status": "complete",
        "mode": "payment",
        "payment_status": "paid",
        "amount_total": 11_800,
        "currency": "eur",
        "metadata": {
            "achat": "credits",
            "quantite": "2",
            "organisation_id": str(abonnee.organisation.id),
        },
    }
    session.update(ecart)
    return session


@pytest.mark.parametrize(
    "ecart",
    [{"amount_total": 100}, {"currency": "usd"}, {"mode": "subscription"}],
)
def test_des_credits_ne_sont_pas_verses_pour_un_autre_montant(ecart: dict[str, Any]) -> None:
    """Le seul des quatre achats qui versait sur la foi de la quantité des
    métadonnées, sans regarder ce qui avait été encaissé."""
    from paiement import abonnements  # noqa: PLC0415

    abonnee = Abonne()
    avant = MouvementCredit.objects.count()

    verdict = abonnements.sur_session_terminee(_credits_payes(abonnee, **ecart))

    assert verdict == "achat de credits inexploitable"
    assert MouvementCredit.objects.count() == avant
    incident = OperationalIncident.objects.get()
    assert "ne correspond pas" in incident.details["motif"] or "paiement unique" in (
        incident.details["motif"]
    )


def test_contre_epreuve_des_credits_au_bon_montant_sont_verses_une_fois() -> None:
    from paiement import abonnements  # noqa: PLC0415

    abonnee = Abonne()
    session = _credits_payes(abonnee)

    assert abonnements.sur_session_terminee(session) == "2 credits achetes"
    # Le rejeu sort avant la comparaison, même si le panier a disparu depuis.
    TentativePaiement.objects.all().delete()
    assert abonnements.sur_session_terminee(session) == "achat deja credite"
    assert OperationalIncident.objects.count() == 0
