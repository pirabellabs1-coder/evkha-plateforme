"""Entrer dans son espace, et pouvoir en reprendre la clé — sans écrire à personne.

Deux moitiés du même trou, toutes deux vérifiées avant correction.

**1. Un collaborateur invité ne pouvait JAMAIS se connecter.** `inviter` créait
un `Customer` et un `MembreOrganisation` en déclarant « le compte de connexion
sera créé à la première connexion, une fois le mot de passe défini » — alors
qu'aucune route ne permettait de définir ce mot de passe et qu'aucun courriel
ne partait. Les trois portes restantes étaient fermées : la connexion exige un
compte, l'inscription publique répond « cette adresse a déjà un compte »
(message faux), et Google tombe sur le même refus. L'écran, lui, affirmait
« EVKHA lui transmettra ses identifiants de connexion ».

**2. Personne ne pouvait réinitialiser son mot de passe.** `set_password`
n'apparaissait qu'une fois dans tout le dépôt, à la création du compte. Un
abonné dont le mot de passe fuit ne pouvait rien faire pendant les quatorze
jours de validité de ses jetons.

Les tests qui comptent ici ne sont pas « ça marche ». Ce sont ceux qui
verrouillent ce qu'un lien ne doit PAS permettre.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from organisations import identifiants, inscription
from tests.aides_abonnement import abonner

pytestmark = pytest.mark.django_db

EMAIL = "claire@cabinet-duval.fr"
MOT_DE_PASSE = "un-mot-de-passe-solide-42"
NOUVEAU = "un-autre-mot-de-passe-98"


@pytest.fixture
def compte() -> Any:
    from organisations.models import CompteClient

    ouverture = inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email=EMAIL,
        mot_de_passe=MOT_DE_PASSE,
        activer_abonnement=False,
    )
    # L'espace est fermé à qui n'a rien payé : sans abonnement, l'invitation
    # d'un collaborateur répondrait 402. Aucun crédit versé, solde à zéro.
    abonner(ouverture.organisation)
    return CompteClient.objects.select_related("user", "customer").get(
        user__username__iexact=EMAIL
    )


def _poster(client: Any, chemin: str, **charge: Any) -> Any:
    return client.post(
        chemin, data=json.dumps(charge), content_type="application/json"
    )


def _parametres(lien: str) -> dict[str, str]:
    from urllib.parse import parse_qs, urlparse

    requete = parse_qs(urlparse(lien).query)
    return {cle: valeurs[0] for cle, valeurs in requete.items()}


# ── Ce qu'un lien ne doit PAS permettre ──────────────────────────────────────


def test_un_lien_deja_utilise_ne_vaut_plus(client: Any, compte: Any) -> None:
    """La propriété qui a dicté le choix du générateur de jetons.

    Le jeton de Django intègre le condensat du mot de passe dans sa signature :
    dès que le mot de passe change, il cesse de valider. Un lien intercepté
    dans une boîte, ou resté dans un historique, ne rouvre donc rien.
    """
    parametres = _parametres(identifiants.lien_pour(compte))

    premier = _poster(
        client, "/api/public/mot-de-passe/definir/",
        mot_de_passe=NOUVEAU, **parametres,
    )
    assert premier.status_code == 200, premier.content

    second = _poster(
        client, "/api/public/mot-de-passe/definir/",
        mot_de_passe="encore-un-autre-mot-77", **parametres,
    )
    assert second.status_code == 400, "le lien a resservi"
    assert second.json()["code"] == "lien_invalide"


def test_un_jeton_bricole_est_refuse(client: Any, compte: Any) -> None:
    """Sans signature valable, changer l'identifiant prendrait le compte voisin."""
    parametres = _parametres(identifiants.lien_pour(compte))
    parametres["jeton"] = "aaaaaa-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    reponse = _poster(
        client, "/api/public/mot-de-passe/definir/",
        mot_de_passe=NOUVEAU, **parametres,
    )
    assert reponse.status_code == 400


def test_un_identifiant_illisible_ne_casse_rien(client: Any) -> None:
    """Une entrée absurde doit refuser proprement, jamais rendre une 500."""
    reponse = _poster(
        client, "/api/public/mot-de-passe/definir/",
        id="pas-du-base64", jeton="x", mot_de_passe=NOUVEAU,
    )
    assert reponse.status_code == 400


def test_un_mot_de_passe_faible_est_refuse(client: Any, compte: Any) -> None:
    """Les MÊMES validateurs que l'inscription (règle 5).

    Deux avis sur ce qu'est un mot de passe acceptable finiraient par se
    contredire, et c'est la porte la plus permissive qui gagnerait.
    """
    parametres = _parametres(identifiants.lien_pour(compte))
    reponse = _poster(
        client, "/api/public/mot-de-passe/definir/",
        mot_de_passe="1234", **parametres,
    )
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "mot_de_passe_faible"


# ── L'oubli ne renseigne personne ────────────────────────────────────────────


def test_la_reponse_est_la_meme_pour_une_adresse_inconnue(
    client: Any, compte: Any
) -> None:
    """Sinon ce formulaire devient un annuaire.

    On y saisirait des adresses jusqu'à trouver lesquelles ont un compte,
    c'est-à-dire qui travaille avec la plateforme.
    """
    connue = _poster(client, "/api/public/mot-de-passe/oublie/", email=EMAIL)
    inconnue = _poster(
        client, "/api/public/mot-de-passe/oublie/", email="personne@nulle-part.fr"
    )

    assert connue.status_code == inconnue.status_code == 200
    assert connue.json() == inconnue.json()


def test_les_demandes_sont_plafonnees(client: Any, compte: Any) -> None:
    """Sans plafond, on inonde la boîte de quelqu'un dont on connaît l'adresse."""
    from organisations.vues_publiques import REINITIALISATIONS_PAR_HEURE

    for _ in range(REINITIALISATIONS_PAR_HEURE.maximum):
        assert _poster(
            client, "/api/public/mot-de-passe/oublie/", email=EMAIL
        ).status_code == 200

    barre = _poster(client, "/api/public/mot-de-passe/oublie/", email=EMAIL)
    assert barre.status_code == 429


# ── Le parcours complet de l'invité ──────────────────────────────────────────


def test_un_invite_peut_entrer_dans_son_espace(client: Any, compte: Any) -> None:
    """Le test qui échoue sur le code d'avant, de bout en bout.

    Avant : compte inexistant, aucun courriel, aucune route pour définir un mot
    de passe. L'invité n'avait strictement aucun moyen d'entrer.
    """
    from customers.models import Customer
    from organisations.models import CompteClient, MembreOrganisation

    jeton_invitant, _ = _session(EMAIL, MOT_DE_PASSE)
    invitation = client.post(
        "/api/espace/equipe/inviter/",
        data=json.dumps({"email": "thomas@cabinet-duval.fr", "role": "membre"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {jeton_invitant}",
    )
    assert invitation.status_code == 201, invitation.content
    assert invitation.json()["invitation_envoyee"] is True

    invite = Customer.objects.get(email="thomas@cabinet-duval.fr")
    assert MembreOrganisation.objects.filter(customer=invite).exists()

    compte_invite = CompteClient.objects.select_related("user").get(customer=invite)
    parametres = _parametres(identifiants.lien_pour(compte_invite))

    active = _poster(
        client, "/api/public/mot-de-passe/definir/",
        mot_de_passe="mot-de-passe-de-thomas-42", **parametres,
    )
    assert active.status_code == 200, active.content

    # Le jeton rendu doit REELLEMENT ouvrir l'espace : renvoyer une chaine sans
    # session serait un succes de facade (regle 7).
    moi = client.get(
        "/api/espace/moi/",
        HTTP_AUTHORIZATION=f"Bearer {active.json()['jeton']}",
    )
    assert moi.status_code == 200, moi.content
    assert moi.json()["organisation"]["raison_sociale"] == "Cabinet Duval"


def test_un_envoi_qui_echoue_ne_perd_pas_l_invitation(
    client: Any, compte: Any, monkeypatch: Any
) -> None:
    """Contre-épreuve : une panne de messagerie ne doit pas annuler le geste.

    Le rattachement reste valide et le lien est rendu à l'écran, pour que
    l'invitant puisse le recopier au lieu de croire qu'il n'a rien fait.
    """
    monkeypatch.setattr(
        "organisations.courriels._envoyer", lambda **_: False
    )
    jeton_invitant, _ = _session(EMAIL, MOT_DE_PASSE)

    reponse = client.post(
        "/api/espace/equipe/inviter/",
        data=json.dumps({"email": "sophie@cabinet-duval.fr", "role": "membre"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {jeton_invitant}",
    )

    assert reponse.status_code == 201
    charge = reponse.json()
    assert charge["invitation_envoyee"] is False
    assert charge["lien_activation"], "l'invitant n'a aucun recours"


# ── Changer son mot de passe depuis l'espace ─────────────────────────────────


def _session(email: str, mot_de_passe: str) -> tuple[str, Any]:
    from organisations import authentification

    return authentification.ouvrir_session(email, mot_de_passe)


def test_changer_son_mot_de_passe_ferme_les_autres_sessions(
    client: Any, compte: Any
) -> None:
    """Le seul recours de quelqu'un dont le jeton a fuité.

    Sans la révocation, l'intrus resterait connecté quatorze jours de plus et
    le changement de mot de passe aurait l'air d'agir sans rien changer.
    """
    jeton_intrus, _ = _session(EMAIL, MOT_DE_PASSE)
    jeton_titulaire, _ = _session(EMAIL, MOT_DE_PASSE)

    assert client.get(
        "/api/espace/moi/", HTTP_AUTHORIZATION=f"Bearer {jeton_intrus}"
    ).status_code == 200

    reponse = client.post(
        "/api/espace/mot-de-passe/",
        data=json.dumps({
            "mot_de_passe_actuel": MOT_DE_PASSE,
            "nouveau_mot_de_passe": NOUVEAU,
        }),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {jeton_titulaire}",
    )
    assert reponse.status_code == 200, reponse.content

    assert client.get(
        "/api/espace/moi/", HTTP_AUTHORIZATION=f"Bearer {jeton_intrus}"
    ).status_code == 401, "l'intrus est toujours connecte"

    # Le titulaire, lui, repart avec un jeton neuf : il ne doit pas etre
    # ejecte de l'ecran ou il se trouve.
    assert client.get(
        "/api/espace/moi/",
        HTTP_AUTHORIZATION=f"Bearer {reponse.json()['jeton']}",
    ).status_code == 200


def test_le_mot_de_passe_actuel_est_exige(client: Any, compte: Any) -> None:
    """Sinon un jeton volé suffirait à verrouiller le titulaire dehors.

    C'est la situation même dont on cherche à sortir : exiger le mot de passe
    actuel est ce qui distingue le titulaire de l'intrus.
    """
    jeton, _ = _session(EMAIL, MOT_DE_PASSE)

    reponse = client.post(
        "/api/espace/mot-de-passe/",
        data=json.dumps({
            "mot_de_passe_actuel": "ce-n-est-pas-le-bon",
            "nouveau_mot_de_passe": NOUVEAU,
        }),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {jeton}",
    )

    assert reponse.status_code == 403
    assert reponse.json()["code"] == "mot_de_passe_actuel"
    # Contre-épreuve : l'ancien mot de passe fonctionne toujours.
    assert _session(EMAIL, MOT_DE_PASSE)[0]
