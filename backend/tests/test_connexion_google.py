"""Se connecter — ou s'inscrire — avec un compte Google.

Un seul point d'entrée pour les deux : au moment où la personne clique, ni elle
ni nous ne savons si le compte existe.

Les tests qui comptent ne sont pas « ça marche ». Ce sont ceux qui verrouillent
ce qu'un jeton Google ne doit PAS permettre :

- un jeton émis pour une AUTRE application ne doit rien ouvrir ici — c'est la
  faille classique de cette intégration ;
- une adresse non vérifiée par Google ne doit rien ouvrir non plus, sans quoi
  n'importe qui crée un compte Google au nom d'autrui et récupère son espace ;
- et Google ne doit jamais écraser ce que la personne a saisi elle-même.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client

pytestmark = pytest.mark.django_db

CLIENT_ID = "123456789-evkha.apps.googleusercontent.com"


class FausseReponse:
    """Réponse de `tokeninfo`, telle que Google la rend."""

    def __init__(self, charge: dict[str, Any], statut: int = 200) -> None:
        self._charge = charge
        self.status_code = statut

    def json(self) -> dict[str, Any]:
        return self._charge


def _google_rend(monkeypatch: Any, charge: dict[str, Any], statut: int = 200) -> None:
    """Remplace l'appel réseau à Google.

    On ne teste pas Google : on teste ce que NOUS faisons de sa réponse. Un
    test qui appellerait vraiment Google serait lent, faillible, et ne
    pourrait pas produire les cas qui comptent — un jeton émis pour une autre
    application, par exemple.
    """
    # Cible nommee explicitement : passer par `organisations.google.httpx`
    # remonterait au module `httpx` lui-meme et le patcherait pour TOUT le
    # processus, bien au-dela de ce que ce test veut simuler.
    monkeypatch.setattr(
        "httpx.get", lambda *a, **k: FausseReponse(charge, statut)
    )


@pytest.fixture(autouse=True)
def _decor(db: object, settings: Any) -> None:
    settings.EVKHA_GOOGLE_CLIENT_ID = CLIENT_ID
    call_command("seed_formules", "--forcer", verbosity=0)
    cache.clear()


def _poster(client: Client, **charge: Any) -> Any:
    return client.post(
        "/api/public/google/",
        data=json.dumps({"jeton_google": "jeton-de-test", **charge}),
        content_type="application/json",
    )


CHARGE_VALIDE = {
    "aud": CLIENT_ID,
    "email": "claire@cabinet-duval.fr",
    "email_verified": "true",
    "given_name": "Claire",
    "family_name": "Duval",
}


# ── Ce qu'un jeton Google ne doit PAS permettre ──────────────────────────────


def test_un_jeton_emis_pour_une_autre_application_est_refuse(
    client: Client, monkeypatch: Any
) -> None:
    """La faille classique de cette intégration.

    Sans ce contrôle, un jeton obtenu par n'importe quel autre site Google
    ouvrirait une session ici : il suffirait de faire cliquer la personne sur
    son propre site pour récupérer son espace EVKHA.
    """
    _google_rend(monkeypatch, {**CHARGE_VALIDE, "aud": "un-autre-site.apps.googleusercontent.com"})
    reponse = _poster(client, raison_sociale="Cabinet Duval")
    assert reponse.status_code == 401
    assert reponse.json()["code"] == "jeton_autre_application"


def test_une_adresse_non_verifiee_est_refusee(
    client: Client, monkeypatch: Any
) -> None:
    """Sinon on crée un compte Google au nom d'autrui pour prendre son espace."""
    _google_rend(monkeypatch, {**CHARGE_VALIDE, "email_verified": "false"})
    reponse = _poster(client, raison_sociale="Cabinet Duval")
    assert reponse.status_code == 403
    assert reponse.json()["code"] == "email_non_verifie"


def test_un_jeton_rejete_par_google_est_refuse(
    client: Client, monkeypatch: Any
) -> None:
    _google_rend(monkeypatch, {"error": "invalid_token"}, statut=400)
    assert _poster(client, raison_sociale="X").status_code == 401


def test_sans_identifiant_d_application_rien_ne_passe(
    client: Client, monkeypatch: Any, settings: Any
) -> None:
    """Un réglage absent doit refuser, jamais accepter par défaut (règle 1)."""
    settings.EVKHA_GOOGLE_CLIENT_ID = ""
    _google_rend(monkeypatch, CHARGE_VALIDE)
    reponse = _poster(client, raison_sociale="X")
    assert reponse.status_code == 503
    assert reponse.json()["code"] == "google_non_configure"


def test_google_indisponible_ne_casse_pas_la_plateforme(
    client: Client, monkeypatch: Any
) -> None:
    """Contre-épreuve : une panne de Google ferme SA porte, pas les autres.

    Le mot de passe doit rester un chemin valide — c'est tout l'intérêt de ne
    pas dépendre d'un seul fournisseur d'identité.
    """
    import httpx

    def tombe(*a: Any, **k: Any) -> None:
        raise httpx.ConnectError("injoignable")

    monkeypatch.setattr("httpx.get", tombe)
    reponse = _poster(client, raison_sociale="X")
    assert reponse.status_code == 503
    assert reponse.json()["code"] == "google_injoignable"
    assert "mot de passe" in reponse.json()["erreur"]


# ── Inscription par Google ───────────────────────────────────────────────────


def test_une_adresse_inconnue_cree_le_compte_sans_credit(
    client: Client, monkeypatch: Any
) -> None:
    """Mêmes garanties que le formulaire : rien n'est crédité, rien n'est activé."""
    from organisations import credits
    from organisations.models import Organisation

    _google_rend(monkeypatch, CHARGE_VALIDE)
    reponse = _poster(client, raison_sociale="Cabinet Duval", formule="pro")
    assert reponse.status_code == 201, reponse.content

    charge = reponse.json()
    assert charge["compte_cree"] is True
    assert charge["abonnement_actif"] is False
    organisation = Organisation.objects.get(id=charge["organisation"]["id"])
    assert credits.solde(organisation) == 0


def test_l_identite_google_est_reprise_par_la_plateforme(
    client: Client, monkeypatch: Any
) -> None:
    """Le prénom et le nom attestés par Google doivent servir à quelque chose.

    Sans cela, la personne devrait ressaisir dans ses paramètres ce qu'elle
    vient de fournir en cliquant.
    """
    from customers.models import Customer

    _google_rend(monkeypatch, CHARGE_VALIDE)
    _poster(client, raison_sociale="Cabinet Duval", formule="pro")

    contact = Customer.objects.get(email="claire@cabinet-duval.fr")
    assert contact.first_name == "Claire"
    assert contact.last_name == "Duval"
    assert contact.company_name == "Cabinet Duval"


def test_la_raison_sociale_n_est_jamais_devinee(
    client: Client, monkeypatch: Any
) -> None:
    """Déduire « gmail » de l'adresse mettrait ce nom sur les documents livrés.

    Ces documents partent en marque blanche chez les clients de l'abonné :
    une organisation mal nommée s'y imprime.
    """
    _google_rend(monkeypatch, {**CHARGE_VALIDE, "email": "claire@gmail.com"})
    reponse = _poster(client)
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "raison_sociale_manquante"


# ── Connexion par Google ─────────────────────────────────────────────────────


def test_une_adresse_connue_ouvre_une_session(
    client: Client, monkeypatch: Any
) -> None:
    _google_rend(monkeypatch, CHARGE_VALIDE)
    _poster(client, raison_sociale="Cabinet Duval")

    seconde = _poster(client)
    assert seconde.status_code == 200
    assert seconde.json()["compte_cree"] is False

    jeton = seconde.json()["jeton"]
    moi = client.get("/api/espace/moi/", HTTP_AUTHORIZATION=f"Bearer {jeton}")
    assert moi.status_code == 200, "le jeton rendu n'ouvre pas l'espace"


def test_google_complete_les_champs_vides_mais_n_ecrase_rien(
    client: Client, monkeypatch: Any
) -> None:
    """Le test qui protège ce que la personne a corrigé elle-même.

    Quelqu'un qui rectifie son nom dans ses paramètres ne doit pas le voir
    revenir à chaque connexion : la source de son identité, c'est elle, pas
    Google.
    """
    from customers.models import Customer

    # Compte cree SANS prenom ni nom.
    _google_rend(monkeypatch, {**CHARGE_VALIDE, "given_name": "", "family_name": ""})
    _poster(client, raison_sociale="Cabinet Duval")

    contact = Customer.objects.get(email="claire@cabinet-duval.fr")
    assert contact.first_name == ""

    # Deuxieme connexion : Google atteste un prenom, le champ vide est comble.
    _google_rend(monkeypatch, CHARGE_VALIDE)
    reponse = _poster(client)
    assert "first_name" in reponse.json()["champs_completes"]
    contact.refresh_from_db()
    assert contact.first_name == "Claire"

    # La personne corrige son nom dans ses parametres.
    contact.first_name = "Claire-Marie"
    contact.save(update_fields=["first_name"])

    # Troisieme connexion : Google ne doit RIEN reecrire.
    _poster(client)
    contact.refresh_from_db()
    assert contact.first_name == "Claire-Marie", "Google a ecrase la saisie"


# ── Ce que l'interface doit savoir avant d'afficher le bouton ────────────────


def test_les_reglages_disent_si_google_est_utilisable(client: Client) -> None:
    charge = client.get("/api/public/reglages/").json()
    assert charge["google"]["actif"] is True
    assert charge["google"]["client_id"] == CLIENT_ID


def test_sans_reglage_l_interface_sait_qu_elle_ne_doit_rien_afficher(
    client: Client, settings: Any
) -> None:
    """Un bouton qui échoue faute de réglage fait douter du reste de la page."""
    settings.EVKHA_GOOGLE_CLIENT_ID = ""
    charge = client.get("/api/public/reglages/").json()
    assert charge["google"]["actif"] is False
    assert charge["google"]["client_id"] == ""
