"""CORS de l'API, appelée depuis un front hébergé ailleurs (Vercel).

Le front et l'API ne vivent plus sur le même domaine. Sans en-têtes CORS, le
navigateur bloque chaque appel — c'est le premier point qui casse à la mise en
ligne, et il ne se voit dans aucun test qui appelle Django en direct.

Ces tests portent donc sur ce que le NAVIGATEUR verra, pas sur ce que Django
sait faire : la présence et la valeur de `Access-Control-Allow-Origin`.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from tests.conftest import JETON_ADMIN

ORIGINE_AUTORISEE = "https://app.evkha.fr"
ORIGINE_INCONNUE = "https://site-malveillant.example"
CHEMIN = "/api/dashboard/summary/"


@pytest.fixture
def api(settings: Any) -> Client:
    settings.CORS_ALLOWED_ORIGINS = [ORIGINE_AUTORISEE]
    settings.CORS_ALLOWED_ORIGIN_REGEXES = []
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = True
    return Client(HTTP_AUTHORIZATION=f"Bearer {JETON_ADMIN}")


def test_une_origine_autorisee_recoit_l_en_tete_cors(api: Client) -> None:
    reponse = api.get(CHEMIN, HTTP_ORIGIN=ORIGINE_AUTORISEE)
    assert reponse["Access-Control-Allow-Origin"] == ORIGINE_AUTORISEE


def test_une_origine_inconnue_ne_recoit_aucun_en_tete_cors(api: Client) -> None:
    """Contre-épreuve : sans cet en-tête, le navigateur refuse la réponse."""
    reponse = api.get(CHEMIN, HTTP_ORIGIN=ORIGINE_INCONNUE)
    assert "Access-Control-Allow-Origin" not in reponse


def test_la_requete_preflight_est_traitee(api: Client) -> None:
    """Le préflight doit répondre AVANT l'authentification et le routage.

    C'est ce qui impose la place du middleware CORS en haut de la pile : une
    requête `OPTIONS` ne porte pas de jeton, et un middleware d'authentification
    placé avant lui la rejetterait en 401 — le navigateur conclurait au blocage
    sans jamais émettre la vraie requête.
    """
    reponse = api.options(
        CHEMIN,
        HTTP_ORIGIN=ORIGINE_AUTORISEE,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
    )
    assert reponse.status_code == 200
    assert reponse["Access-Control-Allow-Origin"] == ORIGINE_AUTORISEE
    assert "authorization" in reponse["Access-Control-Allow-Headers"].lower()


def test_le_preflight_passe_meme_sans_jeton(settings: Any) -> None:
    """Avec l'authentification ACTIVE, le préflight doit quand même aboutir."""
    settings.CORS_ALLOWED_ORIGINS = [ORIGINE_AUTORISEE]
    settings.CORS_ALLOWED_ORIGIN_REGEXES = []
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    reponse = Client(HTTP_AUTHORIZATION=f"Bearer {JETON_ADMIN}").options(
        CHEMIN,
        HTTP_ORIGIN=ORIGINE_AUTORISEE,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
    )
    assert reponse.status_code == 200


def test_les_identifiants_ne_sont_jamais_autorises() -> None:
    """L'authentification passe par un jeton, jamais par un cookie.

    Autoriser les identifiants ferait envoyer le cookie de session vers un
    autre domaine sans qu'aucun code ne le demande, et rouvrirait la porte au
    CSRF que l'en-tête `Authorization` referme.
    """
    from django.conf import settings as reglages

    assert reglages.CORS_ALLOW_CREDENTIALS is False


def test_les_previsualisations_vercel_sont_fermees_par_defaut() -> None:
    """Un motif `*.vercel.app` autoriserait n'importe quel site hébergé là-bas.

    Il existe pour le développement, il doit rester fermé en production. Ce
    test échoue si quelqu'un l'active dans les réglages par défaut.
    """
    from django.conf import settings as reglages

    assert not getattr(reglages, "CORS_ALLOWED_ORIGIN_REGEXES", [])


def test_le_cors_ne_couvre_que_l_api(api: Client) -> None:
    """L'interface d'administration Django n'a rien à exposer à un autre domaine."""
    reponse = api.get("/healthz/", HTTP_ORIGIN=ORIGINE_AUTORISEE)
    assert "Access-Control-Allow-Origin" not in reponse
