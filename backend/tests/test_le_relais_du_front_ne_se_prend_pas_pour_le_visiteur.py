"""Deux visiteurs restent deux visiteurs, par les deux chemins de la production.

Audit du 19/11/2026. L'espace client appelle `/api/` en chemin RELATIF
(`VITE_API_URL` n'est pas posé) : ses requêtes passent par Traefik, puis par le
nginx du front, puis arrivent à Django. Ce nginx écrivait

    X-Forwarded-For: $proxy_add_x_forwarded_for

c'est-à-dire ce que Traefik avait écrit, PLUS sa propre vue de l'appelant —
l'adresse de Traefik. Django lit la dernière entrée de l'en-tête
(`EVKHA_PROXIES_DE_CONFIANCE=1`) : il prenait Traefik pour le visiteur, donc
tous les visiteurs pour un seul. Cinq inscriptions par heure, cinq
réinitialisations, trente connexions par quart d'heure — pour la plateforme
entière.

Aucun test ne pouvait le voir : `test_plafond_connexion` écrit lui-même
l'en-tête que Django reçoit. Celui-ci le fabrique comme la production le
fabrique, à partir de la ligne réellement écrite dans `frontend/nginx.conf`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.test import RequestFactory, override_settings

from organisations import limitation

CONF = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"

#: L'adresse du conteneur Traefik, telle que le nginx du front la voit.
TRAEFIK = "10.0.1.4"


def _directive() -> str:
    """La valeur que le nginx du front donne à `X-Forwarded-For`."""
    lignes = [
        ligne.split("#", 1)[0].strip()
        for ligne in CONF.read_text(encoding="utf-8").splitlines()
    ]
    trouvees = [
        m.group(1)
        for ligne in lignes
        if (m := re.match(r"proxy_set_header\s+X-Forwarded-For\s+(.+?);$", ligne))
    ]
    assert len(trouvees) == 1, f"une directive X-Forwarded-For attendue, {len(trouvees)} lues"
    return trouvees[0]


def _ecrit_par_nginx(directive: str, *, recu: str, appelant: str) -> str:
    """Ce que nginx envoie à Django, selon les variables de la directive.

    Les trois variables que nginx sait mettre dans cet en-tête. Une directive
    qui en emploierait une autre fait échouer le test plutôt que de le laisser
    juger sur une supposition (règle 1).
    """
    valeurs = {
        "$proxy_add_x_forwarded_for": f"{recu}, {appelant}" if recu else appelant,
        "$http_x_forwarded_for": recu,
        "$remote_addr": appelant,
    }
    assert directive in valeurs, f"directive inconnue de ce test : {directive!r}"
    return valeurs[directive]


def _vue_par_django(visiteur: str, *, par_le_front: bool) -> str:
    """L'adresse que les plafonds retiennent pour `visiteur`."""
    # Traefik n'a pas de relais de confiance devant lui : il écrit l'adresse
    # qu'il voit, quoi que le visiteur ait prétendu.
    de_traefik = visiteur
    if par_le_front:
        entete = _ecrit_par_nginx(_directive(), recu=de_traefik, appelant=TRAEFIK)
        remote = "10.0.1.9"  # le conteneur nginx
    else:
        entete = de_traefik
        remote = TRAEFIK
    requete = RequestFactory().get(
        "/api/public/formules/", REMOTE_ADDR=remote, HTTP_X_FORWARDED_FOR=entete,
    )
    return limitation.adresse_client(requete)


@pytest.mark.parametrize("par_le_front", [True, False], ids=["app2", "api2"])
@override_settings(EVKHA_PROXIES_DE_CONFIANCE=1)
def test_chaque_visiteur_garde_son_adresse(par_le_front: bool) -> None:
    """Échoue sur le code d'avant par le chemin `app2` : les deux valaient Traefik."""
    assert _vue_par_django("203.0.113.7", par_le_front=par_le_front) == "203.0.113.7"
    assert _vue_par_django("198.51.100.23", par_le_front=par_le_front) == "198.51.100.23"


@override_settings(EVKHA_PROXIES_DE_CONFIANCE=1)
def test_l_adresse_d_un_relais_n_est_jamais_celle_d_un_visiteur() -> None:
    """La propriété, dite autrement : le plafond ne se pose pas sur Traefik."""
    assert _vue_par_django("203.0.113.7", par_le_front=True) != TRAEFIK


def test_le_reglage_par_defaut_est_celui_que_la_configuration_suppose() -> None:
    """La ligne de nginx et ce défaut se répondent : en changer un seul remet le
    défaut en place. Le serveur ne pose pas la variable (lu dans Coolify le
    19/11/2026), c'est donc ce défaut qui tourne."""
    from django.conf import settings

    assert settings.EVKHA_PROXIES_DE_CONFIANCE == 1
