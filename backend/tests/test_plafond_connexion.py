"""Un mot de passe ne doit pas pouvoir être essayé indéfiniment.

`/api/espace/connexion/` n'avait **aucun plafond de tentatives**. L'inscription
publique en avait un depuis le début ; la porte qui intéresse réellement un
attaquant, elle, était grande ouverte. Un dictionnaire de mots de passe
courants s'y déroulait aussi vite que le réseau le permettait.

Le second défaut est plus sournois : le plafond de l'inscription reposait sur
l'entrée **la plus à gauche** de `X-Forwarded-For`, c'est-à-dire sur une valeur
que l'appelant écrit lui-même. Un en-tête différent à chaque requête donnait
une clé neuve à chaque requête. Le compteur existait, s'affichait dans le code,
et ne comptait rien (règle 1).

Les tests qui comptent ici sont ceux qui échouent sur le code d'avant, et les
contre-épreuves qui vérifient qu'on n'a pas fermé la porte aux abonnés.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client

from organisations import limitation

pytestmark = pytest.mark.django_db

EMAIL = "claire@cabinet-duval.fr"
MOT_DE_PASSE = "un-mot-de-passe-solide-42"
URL = "/api/espace/connexion/"


@pytest.fixture(autouse=True)
def _decor(settings: Any) -> None:
    # Les tests parlent d'adresses : on fixe la topologie au lieu de la subir.
    settings.EVKHA_PROXIES_DE_CONFIANCE = 1
    cache.clear()


@pytest.fixture
def compte() -> None:
    """Un compte réel, ouvert par le chemin que la plateforme utilise."""
    from organisations import inscription

    inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email=EMAIL,
        mot_de_passe=MOT_DE_PASSE,
        activer_abonnement=False,
    )


def _tenter(
    client: Client, *, mot_de_passe: str, adresse: str = "203.0.113.7", email: str = EMAIL
) -> Any:
    """Une tentative de connexion, vue depuis `adresse`.

    L'adresse est placée en dernière position de `X-Forwarded-For`, là où un
    relais de confiance l'écrirait. Ce qui précède est ce qu'un appelant peut
    raconter.
    """
    return client.post(
        URL,
        data=json.dumps({"email": email, "mot_de_passe": mot_de_passe}),
        content_type="application/json",
        HTTP_X_FORWARDED_FOR=f"10.0.0.1, {adresse}",
    )


# ── Le plafond existe ────────────────────────────────────────────────────────


def test_les_tentatives_finissent_par_etre_refusees(
    client: Client, compte: None
) -> None:
    """Le test qui échoue sur le code d'avant : il n'y avait aucune limite."""
    for _ in range(limitation_maximum()):
        assert _tenter(client, mot_de_passe="faux").status_code == 401

    barre = _tenter(client, mot_de_passe="faux")
    assert barre.status_code == 429, "le mot de passe reste essayable sans fin"
    assert barre.json()["code"] == "trop_de_tentatives"


def test_le_refus_ne_dit_pas_si_le_compte_existe(client: Client) -> None:
    """Sinon le plafond devient un moyen d'énumérer les abonnés.

    Aucun compte n'est créé dans ce test : les réponses doivent être les mêmes
    que pour une adresse connue.
    """
    for _ in range(limitation_maximum()):
        assert _tenter(client, mot_de_passe="faux").status_code == 401

    barre = _tenter(client, mot_de_passe="faux")
    assert barre.status_code == 429
    assert "existe" not in barre.json()["error"].lower()


def test_le_balayage_de_plusieurs_comptes_est_arrete(client: Client) -> None:
    """Un mot de passe courant essayé sur beaucoup d'adresses différentes.

    Le plafond par compte ne voit rien — chaque compte n'est essayé qu'une
    fois. C'est le plafond par adresse qui doit répondre.
    """
    from organisations.vues_espace import CONNEXIONS_PAR_ADRESSE

    for numero in range(CONNEXIONS_PAR_ADRESSE.maximum):
        reponse = _tenter(
            client, mot_de_passe="Bonjour2024", email=f"cible{numero}@exemple.fr"
        )
        assert reponse.status_code == 401

    suivante = _tenter(client, mot_de_passe="Bonjour2024", email="cible-suivante@exemple.fr")
    assert suivante.status_code == 429


# ── Le plafond ne se contourne pas ───────────────────────────────────────────


def test_un_en_tete_falsifie_ne_donne_pas_un_compteur_neuf(
    client: Client, compte: None
) -> None:
    """Le test qui échoue sur le code d'avant.

    L'adresse était lue à gauche de `X-Forwarded-For`. En changeant cette
    partie — que le client écrit — on obtenait une clé différente à chaque
    tentative, et le plafond n'était jamais atteint.
    """
    for numero in range(limitation_maximum()):
        reponse = client.post(
            URL,
            data=json.dumps({"email": EMAIL, "mot_de_passe": "faux"}),
            content_type="application/json",
            # La partie de gauche change à chaque coup : c'est exactement ce
            # qu'un attaquant écrirait. La dernière entrée, elle, est celle que
            # le relais de confiance appose, et elle ne bouge pas.
            HTTP_X_FORWARDED_FOR=f"192.0.2.{numero}, 203.0.113.7",
        )
        assert reponse.status_code == 401

    barre = client.post(
        URL,
        data=json.dumps({"email": EMAIL, "mot_de_passe": "faux"}),
        content_type="application/json",
        HTTP_X_FORWARDED_FOR="192.0.2.250, 203.0.113.7",
    )
    assert barre.status_code == 429, "l'en-tete falsifie a remis le compteur a zero"


# ── Le plafond ne doit pas devenir une arme ──────────────────────────────────


def test_un_tiers_ne_peut_pas_bloquer_le_compte_de_quelqu_un_d_autre(
    client: Client, compte: None
) -> None:
    """La contre-épreuve qui a dicté la conception.

    Un plafond posé sur le seul e-mail permettrait à n'importe qui de fermer
    l'accès d'un abonné en se trompant exprès : la protection deviendrait
    l'attaque. Le compteur est donc lié au couple compte + adresse.
    """
    for _ in range(limitation_maximum() + 2):
        _tenter(client, mot_de_passe="faux", adresse="198.51.100.66")

    # La personne légitime, depuis chez elle, entre normalement.
    depuis_chez_elle = _tenter(
        client, mot_de_passe=MOT_DE_PASSE, adresse="203.0.113.7"
    )
    assert depuis_chez_elle.status_code == 200, "un tiers a bloque le titulaire"


def test_une_connexion_reussie_efface_le_compteur(
    client: Client, compte: None
) -> None:
    """Chercher son mot de passe, le trouver, revenir : rien ne doit rester.

    Sans cet oubli, les hésitations de la veille compteraient encore le
    lendemain, et l'abonné se verrait refuser une connexion parfaitement
    légitime.
    """
    for _ in range(limitation_maximum() - 1):
        _tenter(client, mot_de_passe="faux")

    assert _tenter(client, mot_de_passe=MOT_DE_PASSE).status_code == 200

    # Le quota est reparti de zéro : on peut de nouveau se tromper.
    assert _tenter(client, mot_de_passe="faux").status_code == 401


def test_se_tromper_une_fois_ne_bloque_rien(client: Client, compte: None) -> None:
    """Contre-épreuve élémentaire : le cas courant reste fluide."""
    assert _tenter(client, mot_de_passe="faux").status_code == 401
    assert _tenter(client, mot_de_passe=MOT_DE_PASSE).status_code == 200


# ── La lecture de l'adresse ──────────────────────────────────────────────────


def _fausse_requete(**meta: str) -> Any:
    from django.test import RequestFactory

    requete = RequestFactory().get("/")
    requete.META.update(meta)
    return requete


def test_sans_relais_l_en_tete_est_ignore(settings: Any) -> None:
    """Joint directement, `X-Forwarded-For` n'est qu'une déclaration."""
    settings.EVKHA_PROXIES_DE_CONFIANCE = 0
    requete = _fausse_requete(
        HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="203.0.113.9"
    )
    assert limitation.adresse_client(requete) == "203.0.113.9"


def test_avec_un_relais_la_derniere_entree_fait_foi(settings: Any) -> None:
    settings.EVKHA_PROXIES_DE_CONFIANCE = 1
    requete = _fausse_requete(
        HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.9", REMOTE_ADDR="10.0.0.1"
    )
    assert limitation.adresse_client(requete) == "203.0.113.9"


def test_avec_deux_relais_on_remonte_d_un_cran(settings: Any) -> None:
    settings.EVKHA_PROXIES_DE_CONFIANCE = 2
    requete = _fausse_requete(
        HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.9, 10.0.0.2", REMOTE_ADDR="10.0.0.1"
    )
    assert limitation.adresse_client(requete) == "203.0.113.9"


def test_un_en_tete_trop_court_retombe_sur_remote_addr(settings: Any) -> None:
    """La topologie annoncée ne correspond pas : on ne devine pas (règle 1)."""
    settings.EVKHA_PROXIES_DE_CONFIANCE = 2
    requete = _fausse_requete(
        HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="203.0.113.9"
    )
    assert limitation.adresse_client(requete) == "203.0.113.9"


# ── Le compteur lui-même ─────────────────────────────────────────────────────


def test_le_compteur_expire() -> None:
    """Une fenêtre écoulée doit rouvrir, sinon le blocage serait définitif."""
    plafond = limitation.Plafond("essai", maximum=1, fenetre_s=900)
    limitation.enregistrer(plafond, "quelqu-un")
    assert limitation.depasse(plafond, "quelqu-un")

    limitation.oublier(plafond, "quelqu-un")
    assert not limitation.depasse(plafond, "quelqu-un")


def test_deux_plafonds_ne_se_melangent_pas() -> None:
    """Même identifiant, compteurs distincts."""
    un = limitation.Plafond("un", maximum=1, fenetre_s=900)
    autre = limitation.Plafond("autre", maximum=1, fenetre_s=900)
    limitation.enregistrer(un, "203.0.113.7")
    assert limitation.depasse(un, "203.0.113.7")
    assert not limitation.depasse(autre, "203.0.113.7")


def limitation_maximum() -> int:
    from organisations.vues_espace import CONNEXIONS_PAR_COMPTE

    return CONNEXIONS_PAR_COMPTE.maximum
