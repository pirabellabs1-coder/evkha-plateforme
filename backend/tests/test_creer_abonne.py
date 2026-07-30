"""Ouvrir un abonné depuis l'espace administrateur.

`services.creer_organisation` existait et n'était appelée **par rien** hors des
tests : l'espace administrateur savait souscrire une formule, suspendre,
réactiver, mais aucun chemin du produit ne créait une organisation ni son compte
de connexion. Un abonné ne pouvait donc pas être accueilli sans écrire du Python
dans un terminal — et le premier essai réel l'a montré : il n'existait aucun
identifiant à donner au client (règle 8, chercher dans le dépôt avant de
conclure).

Ces tests verrouillent le geste **et ses refus**. Le cas heureux seul laisserait
passer une organisation créée sans crédits, ou deux organisations pour la même
personne — deux défauts qui ne se voient qu'à l'usage.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from customers.models import Customer, CustomerType
from organisations import authentification, credits, services
from organisations.models import (
    Formule,
    MembreOrganisation,
    Organisation,
    ReportCredits,
    RoleOrganisation,
)

pytestmark = pytest.mark.django_db

URL = "/api/dashboard/supervision/abonnes/"

#: Assez long et non trivial pour passer les validateurs du projet.
MOT_DE_PASSE = "Tournesol-Vertige-2026"


@pytest.fixture
def formule() -> Formule:
    return Formule.objects.create(
        code="pro",
        libelle="Pro",
        credits_par_echeance=3,
        prix_mensuel_cents=18_900,
        devise="EUR",
        report_credits=ReportCredits.AUCUN,
        plafond_report=0,
        regenerations_offertes=1,
        active=True,
    )


def _poster(client: Client, **champs: Any) -> Any:
    return client.post(URL, data=json.dumps(champs), content_type="application/json")


# ── Le geste complet ─────────────────────────────────────────────────────────


def test_cree_organisation_proprietaire_compte_et_credits(
    client: Client, formule: Formule
) -> None:
    """Les quatre effets à la fois : c'est tout l'intérêt du geste."""
    reponse = _poster(
        client,
        raison_sociale="Cabinet Lumière",
        email="eva@cabinet-lumiere.fr",
        mot_de_passe=MOT_DE_PASSE,
        formule="pro",
    )
    assert reponse.status_code == 201, reponse.content

    organisation = Organisation.objects.get(raison_sociale="Cabinet Lumière")

    # 1. le contact, marqué B2B
    contact = Customer.objects.get(email="eva@cabinet-lumiere.fr")
    assert contact.customer_type == CustomerType.B2B

    # 2. le propriétaire
    membre = MembreOrganisation.objects.get(organisation=organisation)
    assert membre.role == RoleOrganisation.PROPRIETAIRE
    assert membre.revoque_le is None

    # 3. les identifiants fonctionnent vraiment — pas seulement en base
    jeton, _ = authentification.ouvrir_session("eva@cabinet-lumiere.fr", MOT_DE_PASSE)
    assert jeton

    # 4. les crédits de la formule sont dotés
    assert credits.solde(organisation) == 3


def test_les_identifiants_ouvrent_reellement_l_espace_client(
    client: Client, formule: Formule
) -> None:
    """Contre-épreuve de bout en bout : le compte créé traverse le décorateur.

    Un compte valide en base mais que `espace()` refuse serait un compte
    inutile. C'est exactement ce qui manquait, et un test qui s'arrête à la
    ligne en base ne l'aurait pas vu (règle 7).
    """
    _poster(
        client,
        raison_sociale="Atelier Nord",
        email="pilote@atelier-nord.fr",
        mot_de_passe=MOT_DE_PASSE,
        formule="pro",
    )
    jeton, _ = authentification.ouvrir_session("pilote@atelier-nord.fr", MOT_DE_PASSE)

    reponse = client.get(
        "/api/espace/moi/", HTTP_AUTHORIZATION=f"Bearer {jeton}"
    )
    assert reponse.status_code == 200, reponse.content
    charge = reponse.json()
    assert charge["organisation"]["raison_sociale"] == "Atelier Nord"


def test_sans_formule_l_organisation_existe_mais_sans_credit(client: Client) -> None:
    """La formule est facultative : on peut ouvrir puis souscrire plus tard."""
    reponse = _poster(
        client,
        raison_sociale="Sans Formule",
        email="attente@exemple.fr",
        mot_de_passe=MOT_DE_PASSE,
    )
    assert reponse.status_code == 201
    assert reponse.json()["formule"] is None
    assert credits.solde(Organisation.objects.get(raison_sociale="Sans Formule")) == 0


def test_le_mot_de_passe_n_est_jamais_renvoye(
    client: Client, formule: Formule
) -> None:
    """Contre-épreuve : la réponse ne recopie pas le secret qu'on vient de poser."""
    reponse = _poster(
        client,
        raison_sociale="Discrétion",
        email="discret@exemple.fr",
        mot_de_passe=MOT_DE_PASSE,
        formule="pro",
    )
    assert MOT_DE_PASSE not in reponse.content.decode("utf-8")


# ── Les refus ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("champs", "code_attendu"),
    [
        ({"email": "a@b.fr", "mot_de_passe": MOT_DE_PASSE}, "raison_sociale_manquante"),
        ({"raison_sociale": "X", "mot_de_passe": MOT_DE_PASSE}, "email_invalide"),
        (
            {"raison_sociale": "X", "email": "pas-une-adresse", "mot_de_passe": MOT_DE_PASSE},
            "email_invalide",
        ),
        ({"raison_sociale": "X", "email": "a@b.fr"}, "mot_de_passe_manquant"),
    ],
)
def test_refuse_les_saisies_incompletes(
    client: Client, champs: dict[str, Any], code_attendu: str
) -> None:
    reponse = _poster(client, **champs)
    assert reponse.status_code == 400
    assert reponse.json()["code"] == code_attendu


def test_refuse_un_mot_de_passe_faible(client: Client) -> None:
    """Les validateurs du projet décident, pas une règle réécrite ici."""
    reponse = _poster(
        client,
        raison_sociale="Faible",
        email="faible@exemple.fr",
        mot_de_passe="12345678",
    )
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "mot_de_passe_faible"
    assert not Organisation.objects.filter(raison_sociale="Faible").exists()


def test_refuse_une_formule_inconnue_sans_rien_creer(client: Client) -> None:
    """Et surtout : ne laisse pas derrière lui une organisation à moitié ouverte."""
    reponse = _poster(
        client,
        raison_sociale="Fantome",
        email="fantome@exemple.fr",
        mot_de_passe=MOT_DE_PASSE,
        formule="inexistante",
    )
    assert reponse.status_code == 404
    assert reponse.json()["code"] == "formule_introuvable"
    assert not Organisation.objects.filter(raison_sociale="Fantome").exists()
    assert not Customer.objects.filter(email="fantome@exemple.fr").exists()


def test_refuse_une_personne_deja_membre_d_une_organisation(
    client: Client, formule: Formule
) -> None:
    """Deux adhésions rendraient l'espace imprévisible.

    `espace()` retient la PREMIERE adhésion trouvée : la même personne dans deux
    organisations verrait parfois l'une, parfois l'autre. Refuser est la seule
    réponse qui ne mente pas.
    """
    contact = Customer.objects.create(email="deja@exemple.fr")
    services.creer_organisation(raison_sociale="Première", contact=contact)

    reponse = _poster(
        client,
        raison_sociale="Seconde",
        email="deja@exemple.fr",
        mot_de_passe=MOT_DE_PASSE,
        formule="pro",
    )
    assert reponse.status_code == 409
    assert reponse.json()["code"] == "deja_membre"
    assert "Première" in reponse.json()["error"]
    assert not Organisation.objects.filter(raison_sociale="Seconde").exists()


def test_l_adresse_est_normalisee_avant_le_controle_de_doublon(
    client: Client, formule: Formule
) -> None:
    """Contre-épreuve du refus précédent : une majuscule ne doit pas le contourner.

    Sinon `Deja@Exemple.fr` créerait la seconde organisation que le contrôle
    prétend empêcher — la classe du défaut, pas son orthographe (règle 4).
    """
    contact = Customer.objects.create(email="doublon@exemple.fr")
    services.creer_organisation(raison_sociale="Origine", contact=contact)

    reponse = _poster(
        client,
        raison_sociale="Contournement",
        email="  DOUBLON@Exemple.FR  ",
        mot_de_passe=MOT_DE_PASSE,
        formule="pro",
    )
    assert reponse.status_code == 409
    assert not Organisation.objects.filter(raison_sociale="Contournement").exists()


def test_refuse_les_autres_methodes_que_post(client: Client) -> None:
    assert client.get(URL).status_code == 405


# ── Autorisation ─────────────────────────────────────────────────────────────
#
# Ces deux tests forcent les réglages au lieu de subir ceux de l'environnement.
# Le `.env` de développement porte `EVKHA_DASHBOARD_AUTH_DISABLED=true` : tous
# les tests ci-dessus passaient donc avec l'authentification DÉSACTIVÉE, sans
# rien prouver de la protection d'un point d'entrée qui crée des comptes. Un
# contrôle qui ne regarde pas l'autorisation ne la garantit pas (règle 9).

_JETON = "f" * 64


@override_settings(EVKHA_DASHBOARD_AUTH_DISABLED=False, EVKHA_DASHBOARD_TOKEN=_JETON)
def test_refuse_sans_jeton_quand_l_authentification_est_active(client: Client) -> None:
    reponse = _poster(
        client,
        raison_sociale="Intrus",
        email="intrus@exemple.fr",
        mot_de_passe=MOT_DE_PASSE,
    )
    assert reponse.status_code == 401
    assert not Organisation.objects.filter(raison_sociale="Intrus").exists()


@override_settings(EVKHA_DASHBOARD_AUTH_DISABLED=False, EVKHA_DASHBOARD_TOKEN=_JETON)
def test_accepte_avec_le_bon_jeton(client: Client, formule: Formule) -> None:
    """Contre-épreuve : le contrôle ne refuse pas aussi l'appel légitime."""
    reponse = client.post(
        URL,
        data=json.dumps(
            {
                "raison_sociale": "Légitime",
                "email": "legitime@exemple.fr",
                "mot_de_passe": MOT_DE_PASSE,
                "formule": "pro",
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {_JETON}",
    )
    assert reponse.status_code == 201, reponse.content
    assert Organisation.objects.filter(raison_sociale="Légitime").exists()


def test_la_route_est_nommee() -> None:
    """Le nom de route est l'interface du front : le figer évite un lien mort."""
    assert reverse("dashboard:supervision-creer-abonne") == URL
