"""Le jeton d'administration doit pouvoir être changé sans coupure.

## Le vrai risque d'un jeton statique

Ce n'est pas sa longueur — il fait 64 signes et la comparaison est en temps
constant. C'est qu'il est **irremplaçable en pratique** : avec une seule valeur
acceptée, tourner la clé casse tous les appelants à la seconde du déploiement.
Donc on repousse. Donc le même secret reste en place indéfiniment, et il finit
par traîner dans un historique de terminal, une capture d'écran, un fichier
d'environnement recopié.

Un secret qu'on ne peut pas changer sans coupure ne se change jamais.

## Et une fenêtre qu'on oublie de fermer est pire que rien

Elle laisse vivre exactement le secret qu'on voulait retirer, tout en donnant
l'impression qu'il l'a été. `evkha.D004` le rappelle à chaque démarrage tant
qu'elle est ouverte ; `evkha.D005` refuse la rotation qui ne tourne rien.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.core.checks import Error
from django.test import Client

from dashboard.checks import controler_garde_administration
from dashboard.middleware import jetons_acceptes

COURANT = "n" * 64
ANCIEN = "a" * 64
CHEMIN = "/api/dashboard/overview/"


@pytest.fixture
def garde(settings: Any) -> Any:
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = COURANT
    settings.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ""
    return settings


def test_sans_rotation_un_seul_jeton_ouvre(garde: Any) -> None:
    assert jetons_acceptes() == (COURANT,)


def test_pendant_la_rotation_les_deux_ouvrent(garde: Any) -> None:
    """C'est toute la raison d'être du dispositif : aucune coupure."""
    garde.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ANCIEN

    assert set(jetons_acceptes()) == {COURANT, ANCIEN}


@pytest.mark.django_db
def test_l_ancien_jeton_est_accepte_pendant_la_fenetre(garde: Any) -> None:
    """Sur la vraie route, pas seulement sur la fonction."""
    garde.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ANCIEN

    reponse = Client(HTTP_AUTHORIZATION=f"Bearer {ANCIEN}").get(CHEMIN)

    assert reponse.status_code != 401


@pytest.mark.django_db
def test_un_jeton_inconnu_reste_refuse(garde: Any) -> None:
    """Contre-épreuve : ouvrir la rotation n'ouvre pas la porte."""
    garde.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ANCIEN

    reponse = Client(HTTP_AUTHORIZATION="Bearer " + "z" * 64).get(CHEMIN)

    assert reponse.status_code == 401


@pytest.mark.django_db
def test_une_fois_la_fenetre_fermee_l_ancien_ne_passe_plus(garde: Any) -> None:
    """Le point qui compte : la rotation doit VRAIMENT retirer l'ancien."""
    garde.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ""

    reponse = Client(HTTP_AUTHORIZATION=f"Bearer {ANCIEN}").get(CHEMIN)

    assert reponse.status_code == 401


def test_la_fenetre_ouverte_se_signale(garde: Any) -> None:
    garde.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ANCIEN

    codes = {p.id for p in controler_garde_administration(None)}

    assert "evkha.D004" in codes


def test_une_fenetre_fermee_ne_dit_rien(garde: Any) -> None:
    """Un avertissement permanent cesse d'être lu."""
    codes = {p.id for p in controler_garde_administration(None)}

    assert "evkha.D004" not in codes
    assert "evkha.D005" not in codes


def test_une_rotation_qui_ne_tourne_rien_est_une_erreur(garde: Any) -> None:
    """Deux fois la même valeur : la configuration donne à croire le contraire."""
    garde.EVKHA_DASHBOARD_TOKEN_PRECEDENT = COURANT

    problemes = controler_garde_administration(None)
    fautif = [p for p in problemes if p.id == "evkha.D005"]

    assert fautif
    assert isinstance(fautif[0], Error)


def test_un_precedent_vide_n_est_pas_un_jeton(garde: Any) -> None:
    """Une chaîne d'espaces ne doit pas ouvrir une fenêtre invisible."""
    garde.EVKHA_DASHBOARD_TOKEN_PRECEDENT = "   "

    assert jetons_acceptes() == (COURANT,)
    assert "evkha.D004" not in {p.id for p in controler_garde_administration(None)}
