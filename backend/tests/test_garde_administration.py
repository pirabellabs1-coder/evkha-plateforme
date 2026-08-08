"""L'administration ne doit pas pouvoir s'ouvrir par accident.

Deux défauts constatés le 31/07/2026 sur l'instance en ligne :

1. `EVKHA_DASHBOARD_AUTH_DISABLED=true` était posé sur le serveur public — à
   côté d'un jeton parfaitement valide de 64 signes. Le tableau de bord était
   consultable par quiconque connaissait l'adresse.
2. Le jeton était accepté en paramètre d'URL. Une URL finit dans les journaux
   du serveur, l'historique du navigateur, l'en-tête `Referer` et les captures
   d'écran.

Le correctif ne vise pas ces deux instances mais leur CLASSE : le contournement
ne peut plus ouvrir la production, et le jeton ne voyage plus que dans un
en-tête.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

JETON = "b" * 64
UNE_ROUTE = "/api/dashboard/jobs/"


# ── Le contournement ne peut pas ouvrir la production ────────────────────────


def test_le_contournement_est_ignore_quand_debug_est_faux(
    client: Client, settings: Any
) -> None:
    """Le test qui échoue sur le code d'avant.

    Avant, ce drapeau ouvrait le tableau de bord quel que soit `DEBUG` — et
    c'est exactement la configuration qui tournait en ligne.
    """
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = True
    settings.EVKHA_DASHBOARD_TOKEN = JETON

    assert client.get(UNE_ROUTE).status_code == 401, (
        "le contournement a ouvert la production"
    )


def test_le_contournement_fonctionne_toujours_en_developpement(
    client: Client, settings: Any
) -> None:
    """Contre-épreuve : le correctif ne doit pas casser ce qui est légitime.

    Sans elle, on aurait supprimé un outil de développement utile en croyant
    corriger une faille.
    """
    settings.DEBUG = True
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = True
    settings.EVKHA_DASHBOARD_TOKEN = ""

    assert client.get(UNE_ROUTE).status_code != 401


# ── Le jeton ne voyage que dans l'en-tête ────────────────────────────────────


def test_le_jeton_en_parametre_d_url_est_refuse(
    client: Client, settings: Any
) -> None:
    """Une URL se journalise, se partage et s'affiche. Pas un jeton d'admin."""
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON

    assert client.get(f"{UNE_ROUTE}?token={JETON}").status_code == 401


def test_le_jeton_dans_l_entete_est_accepte(client: Client, settings: Any) -> None:
    """Contre-épreuve : le chemin légitime doit continuer à passer."""
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON

    reponse = client.get(UNE_ROUTE, HTTP_AUTHORIZATION=f"Bearer {JETON}")
    assert reponse.status_code != 401, reponse.content


def test_un_mauvais_jeton_est_refuse(client: Client, settings: Any) -> None:
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON

    mauvais = client.get(UNE_ROUTE, HTTP_AUTHORIZATION="Bearer " + "c" * 64)
    assert mauvais.status_code == 401


def test_sans_jeton_configure_tout_est_refuse(
    client: Client, settings: Any
) -> None:
    """Règle 1 : ne rien avoir à comparer est un refus, jamais un laissez-passer."""
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = ""

    assert client.get(UNE_ROUTE).status_code == 401
    assert client.get(
        UNE_ROUTE, HTTP_AUTHORIZATION="Bearer " + "c" * 64
    ).status_code == 401


# ── L'espace client n'est pas concerné ───────────────────────────────────────


def test_la_garde_ne_touche_pas_l_espace_client(
    client: Client, settings: Any
) -> None:
    """Contre-épreuve de périmètre.

    L'espace client a sa propre authentification, nominative. Si cette garde
    l'attrapait, elle laisserait passer tout le monde dès que le jeton
    d'administration serait présent — ou bloquerait tous les abonnés.
    """
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON

    # Refus par l'authentification de l'ESPACE, pas par celle du tableau de bord.
    reponse = client.get("/api/espace/moi/")
    assert reponse.status_code == 401
    assert reponse.json()["code"] == "unauthorized"

    # Et le jeton d'administration n'y donne AUCUN droit.
    avec = client.get("/api/espace/moi/", HTTP_AUTHORIZATION=f"Bearer {JETON}")
    assert avec.status_code == 401


# ── Le contrôle de démarrage ─────────────────────────────────────────────────


def test_le_controle_signale_le_contournement_en_production(settings: Any) -> None:
    """Le middleware protège en silence ; le contrôle, lui, le dit."""
    from dashboard.checks import controler_garde_administration

    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = True
    settings.EVKHA_DASHBOARD_TOKEN = JETON

    codes = [p.id for p in controler_garde_administration(None)]
    assert "evkha.D001" in codes


def test_le_controle_signale_l_absence_de_jeton(settings: Any) -> None:
    from dashboard.checks import controler_garde_administration

    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = ""

    codes = [p.id for p in controler_garde_administration(None)]
    assert "evkha.D002" in codes


def test_le_controle_signale_un_jeton_trop_court(settings: Any) -> None:
    from dashboard.checks import controler_garde_administration

    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = "trop-court"

    codes = [p.id for p in controler_garde_administration(None)]
    assert "evkha.D003" in codes


def test_une_configuration_saine_ne_signale_rien(settings: Any) -> None:
    """Contre-épreuve : le contrôle ne doit pas crier sur ce qui va bien."""
    from dashboard.checks import controler_garde_administration

    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON

    assert controler_garde_administration(None) == []
