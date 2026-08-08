"""S'inscrire depuis la page partenaires, sans qu'un humain ouvre le compte.

Jusqu'ici, seule l'administration savait ouvrir un abonné : un visiteur qui
cliquait « Souscrire » ne pouvait rien faire seul. Ce point d'entrée comble le
trou.

Le test qui compte n'est pas « le compte est créé » — c'est **« aucun crédit
n'est délivré »**. Le prestataire de paiement n'est pas branché : créditer à
l'inscription ferait des livrables gratuits à qui remplit un formulaire. Et
c'est le genre de défaut qu'on ne découvre qu'en lisant la facture.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client

pytestmark = pytest.mark.django_db

SAISIE = {
    "raison_sociale": "Cabinet Duval",
    "email": "claire@cabinet-duval.fr",
    "prenom": "Claire",
    "nom": "Duval",
    "mot_de_passe": "un-mot-de-passe-assez-long-42",
    "formule": "pro",
}


@pytest.fixture(autouse=True)
def _decor(db: object) -> None:
    """Formules semées, compteur de tentatives remis à zéro.

    Sans le vidage du cache, le plafond horaire d'un test se reporterait sur le
    suivant et l'ordre d'exécution changerait le résultat.
    """
    call_command("seed_formules", "--forcer", verbosity=0)
    cache.clear()


def _inscrire(client: Client, **surcharges: Any) -> Any:
    return client.post(
        "/api/public/inscription/",
        data=json.dumps({**SAISIE, **surcharges}),
        content_type="application/json",
    )


# ── Ce que l'inscription doit produire ───────────────────────────────────────


def test_une_inscription_ouvre_le_compte_et_la_session(client: Client) -> None:
    reponse = _inscrire(client)
    assert reponse.status_code == 201, reponse.content
    charge = reponse.json()
    assert charge["jeton"], "aucune session ouverte"
    assert charge["organisation"]["raison_sociale"] == "Cabinet Duval"


def test_le_jeton_rendu_ouvre_reellement_l_espace(client: Client) -> None:
    """Règle 3 : vérifier ce que la personne obtient, pas ce qu'on lui annonce.

    Un jeton renvoyé mais inopérant laisserait le visiteur devant un écran
    vide juste après avoir choisi son mot de passe.
    """
    jeton = _inscrire(client).json()["jeton"]
    moi = client.get("/api/espace/moi/", HTTP_AUTHORIZATION=f"Bearer {jeton}")
    assert moi.status_code == 200, moi.content


# ── Ce que l'inscription ne doit SURTOUT pas produire ────────────────────────


def test_aucun_credit_n_est_delivre_avant_paiement(client: Client) -> None:
    """Le test central. Sans lui, un formulaire vaut trois livrables gratuits."""
    from organisations import credits
    from organisations.models import Organisation

    reponse = _inscrire(client)
    assert reponse.json()["abonnement_actif"] is False

    organisation = Organisation.objects.get(id=reponse.json()["organisation"]["id"])
    assert credits.solde(organisation) == 0, "des credits ont ete delivres"


def test_aucun_abonnement_n_est_active(client: Client) -> None:
    from organisations.models import AbonnementOrganisation, StatutAbonnement

    _inscrire(client)
    assert not AbonnementOrganisation.objects.filter(
        statut=StatutAbonnement.ACTIF
    ).exists()


def test_l_intention_est_memorisee_sans_rien_demander(client: Client) -> None:
    """La formule choisie est MÉMORISÉE, elle n'est plus DEMANDÉE.

    Ce test verrouillait l'inverse : l'inscription ouvrait une
    `DemandeCommerciale` qu'un humain devait accorder. C'était juste avant
    Stripe. Depuis, le visiteur paie lui-même et ses crédits arrivent par le
    webhook — la demande n'attendait plus rien de personne et polluait une file
    censée ne contenir que ce qui réclame une décision. La cliente l'a dit le
    07/08/2026 : « elle n'a pas besoin d'accorder quoi que ce soit ».

    L'intention, elle, sert encore : sans elle, le visiteur devrait rechoisir
    après son inscription la formule qu'il venait de choisir.
    """
    from organisations.models import DemandeCommerciale, Organisation

    _inscrire(client)

    organisation = Organisation.objects.get()
    assert organisation.formule_pressentie is not None
    assert organisation.formule_pressentie.code == "pro"
    # Et RIEN n'atterrit dans la file d'attente de l'administration.
    assert not DemandeCommerciale.objects.exists()


# ── Refus ────────────────────────────────────────────────────────────────────


def test_un_mot_de_passe_faible_est_refuse(client: Client) -> None:
    reponse = _inscrire(client, mot_de_passe="1234")
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "mot_de_passe_faible"


def test_une_formule_inconnue_est_refusee(client: Client) -> None:
    reponse = _inscrire(client, formule="offre-fantome")
    assert reponse.status_code == 404
    assert reponse.json()["code"] == "formule_introuvable"


def test_une_adresse_deja_membre_ne_revele_pas_son_organisation(
    client: Client,
) -> None:
    """Sur un point d'entrée PUBLIC, nommer l'organisation serait une fuite.

    N'importe qui pourrait sonder des adresses pour découvrir qui travaille où.
    L'administration, elle, a le droit de la nommer — c'est son information
    utile — et un autre test le vérifie.
    """
    _inscrire(client)
    reponse = _inscrire(client, raison_sociale="Autre cabinet")
    assert reponse.status_code == 409
    assert reponse.json()["code"] == "deja_membre"
    assert "Cabinet Duval" not in reponse.json()["erreur"]


def test_une_organisation_sans_raison_sociale_est_refusee(client: Client) -> None:
    reponse = _inscrire(client, raison_sociale="  ")
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "raison_sociale_manquante"


def test_un_refus_ne_laisse_aucune_organisation_derriere_lui(client: Client) -> None:
    """Contre-épreuve : un échec ne doit pas créer la moitié d'un compte.

    L'ouverture est transactionnelle ; ce test le vérifie sur ce que la base
    contient, pas sur la présence du décorateur.
    """
    from organisations.models import Organisation

    avant = Organisation.objects.count()
    _inscrire(client, mot_de_passe="1234")
    assert Organisation.objects.count() == avant


# ── Un point d'entrée ouvert doit se protéger ────────────────────────────────


def test_le_nombre_d_inscriptions_par_heure_est_plafonne(client: Client) -> None:
    """Sans plafond, un formulaire public ouvert crée mille comptes en une nuit."""
    from organisations.vues_publiques import INSCRIPTIONS_PAR_HEURE

    for rang in range(INSCRIPTIONS_PAR_HEURE.maximum):
        reponse = _inscrire(
            client,
            email=f"essai{rang}@exemple.fr",
            raison_sociale=f"Cabinet {rang}",
        )
        assert reponse.status_code == 201, (rang, reponse.content)

    debordement = _inscrire(
        client, email="de-trop@exemple.fr", raison_sociale="De trop"
    )
    assert debordement.status_code == 429
    assert debordement.json()["code"] == "trop_de_tentatives"


def test_les_echecs_ne_consomment_pas_le_plafond(client: Client) -> None:
    """Contre-épreuve : se tromper de mot de passe ne doit pas fermer la porte.

    Compter les échecs punirait quelqu'un qui hésite sur son mot de passe, et
    le laisserait sans recours pendant une heure.
    """
    from organisations.vues_publiques import INSCRIPTIONS_PAR_HEURE

    for _ in range(INSCRIPTIONS_PAR_HEURE.maximum + 3):
        assert _inscrire(client, mot_de_passe="1234").status_code == 400

    assert _inscrire(client).status_code == 201


def test_seul_le_post_est_accepte(client: Client) -> None:
    assert client.get("/api/public/inscription/").status_code == 405


# ── Ce que la personne lit en arrivant dans son espace ───────────────────────


def test_l_espace_annonce_la_souscription_en_attente(client: Client) -> None:
    """Défaut vécu : le tableau de bord répondait « Contactez EVKHA pour
    souscrire » à quelqu'un qui venait de le faire.

    Sa demande existait en base, l'espace n'en disait rien, et la personne
    pouvait croire son inscription perdue. Le système savait — il devait le
    dire (règle 1). Constaté en parcourant l'inscription dans le navigateur,
    pas en relisant le code (règle 7).
    """
    jeton = _inscrire(client).json()["jeton"]
    moi = client.get("/api/espace/moi/", HTTP_AUTHORIZATION=f"Bearer {jeton}").json()

    assert moi["abonnement"] is None, "rien ne doit etre actif avant paiement"
    attente = moi["souscription_en_attente"]
    assert attente is not None, "la demande est invisible depuis l'espace"
    assert attente["code"] == "pro"
    assert attente["formule"] == "Pro"


def test_un_espace_sans_demande_n_annonce_rien(client: Client) -> None:
    """Contre-épreuve : le champ ne doit pas apparaître à tort.

    Sans elle, une organisation qui n'a jamais rien demandé afficherait une
    souscription fantôme.
    """
    reponse = _inscrire(client, formule="")
    jeton = reponse.json()["jeton"]
    moi = client.get("/api/espace/moi/", HTTP_AUTHORIZATION=f"Bearer {jeton}").json()
    assert moi["souscription_en_attente"] is None


def test_une_souscription_activee_ne_reste_pas_affichee_en_attente(
    client: Client,
) -> None:
    """Une fois la formule payée, l'espace montre l'abonnement, pas l'attente.

    Sinon la personne lirait « en cours de validation » sur un abonnement déjà
    actif — un motif faux est pire qu'un motif absent (règle 2).
    """
    from organisations.models import Organisation

    jeton = _inscrire(client).json()["jeton"]
    Organisation.objects.update(formule_pressentie=None)

    moi = client.get("/api/espace/moi/", HTTP_AUTHORIZATION=f"Bearer {jeton}").json()
    assert moi["souscription_en_attente"] is None
