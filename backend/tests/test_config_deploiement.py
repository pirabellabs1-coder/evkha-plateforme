"""Aucun domaine écrit en dur dans les fichiers de déploiement.

Ce défaut a frappé **deux fois** sur ce projet, sous deux formes différentes :

- `docker-compose.prod.yml` inscrivait `app.evkha.fr` dans ses étiquettes
  Traefik. Un second déploiement réclamait le même domaine au proxy, et la
  production tombait ;
- `frontend/nginx.conf` forçait `Host: app.evkha.fr` en relayant vers Django.
  Avec `USE_X_FORWARDED_HOST=True`, Django rejetait tout autre domaine par un
  `DisallowedHost`. L'espace client se chargeait — nginx sert la page sans
  consulter Django — et **tous** ses appels d'API répondaient 400. Mesuré le
  30 juillet 2026 sur `app2.evkha.fr`.

Corriger la seconde instance après la première, c'est ce que la règle 4
proscrit. Ce test vise la classe : un fichier de déploiement ne nomme aucun
domaine public, il les reçoit par variable.

Il liste ce qui est **autorisé** plutôt que ce qui est interdit. Une liste
d'interdits est toujours en retard d'un cas ; une liste d'autorisés force à
justifier chaque ajout.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]

#: Fichiers dont le contenu part tel quel sur le serveur.
FICHIERS_DEPLOIEMENT: tuple[str, ...] = (
    "docker-compose.prod.yml",
    "frontend/nginx.conf",
    "frontend/Dockerfile",
    "backend/Dockerfile",
)

#: Extensions publiques. C'est une liste, et la règle 4 s'en méfie à juste
#: titre — mais celle-ci porte sur un espace de noms **externe et borné**, pas
#: sur les cas d'un défaut. La première rédaction cherchait « un point suivi de
#: deux lettres », et prenait `traefik.http.routers` ou `evkha.wsgi` pour des
#: domaines : un contrôle qui compare à une donnée mal extraite est pire
#: qu'absent (règle 2).
_EXTENSIONS = (
    "fr", "com", "net", "org", "io", "eu", "dev", "app", "co", "cloud",
    "tech", "site", "online", "info", "biz", "me", "sh", "ai", "xyz",
)

#: Un nom d'hôte pleinement qualifié, se terminant par une extension publique.
_FQDN = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:" + "|".join(_EXTENSIONS) + r")\b",
    re.I,
)

#: Hôtes d'infrastructure légitimes. Ce ne sont pas des domaines applicatifs :
#: ils désignent d'où viennent les images et les paquets, jamais où le service
#: est publié. Tout ajout ici doit se justifier.
HOTES_AUTORISES: frozenset[str] = frozenset(
    {
        # Registres d'images et miroirs de paquets.
        "ghcr.io",
        "docker.io",
        "deb.debian.org",
        "security.debian.org",
        "dl-cdn.alpinelinux.org",
        "registry.npmjs.org",
    }
)


def _lignes_utiles(contenu: str) -> list[tuple[int, str]]:
    """Retire les commentaires : un domaine cité pour l'expliquer n'en est pas un.

    Sans ce dépouillage, le commentaire qui documente le défaut déclencherait
    le test qui le verrouille — la mesure porterait sur son propre balisage
    (corollaire de la règle 9).
    """
    utiles: list[tuple[int, str]] = []
    for numero, ligne in enumerate(contenu.splitlines(), start=1):
        sans_commentaire = ligne.split("#", 1)[0]
        if sans_commentaire.strip():
            utiles.append((numero, sans_commentaire))
    return utiles


def domaines_en_dur(contenu: str) -> list[tuple[int, str]]:
    """Domaines publics inscrits en dur, hors commentaires et hors autorisés."""
    trouves: list[tuple[int, str]] = []
    for numero, ligne in _lignes_utiles(contenu):
        for brut in _FQDN.findall(ligne):
            hote = brut.lower()
            if hote in HOTES_AUTORISES:
                continue
            # `${API_DOMAIN}` et compagnie ne sont pas des domaines : ce sont
            # précisément le correctif attendu.
            trouves.append((numero, hote))
    return trouves


@pytest.mark.parametrize("chemin_relatif", FICHIERS_DEPLOIEMENT)
def test_aucun_domaine_public_en_dur(chemin_relatif: str) -> None:
    fichier = RACINE / chemin_relatif
    assert fichier.is_file(), f"{chemin_relatif} introuvable"

    trouves = domaines_en_dur(fichier.read_text(encoding="utf-8"))

    assert not trouves, (
        f"{chemin_relatif} nomme un domaine en dur : "
        + ", ".join(f"ligne {n} → {h}" for n, h in trouves)
        + ". Un domaine public doit venir d'une variable d'environnement, "
        "sinon un second déploiement entre en collision avec le premier."
    )


def test_le_detecteur_voit_le_defaut_reel_de_nginx() -> None:
    """Contre-épreuve : le détecteur attrape bien le code d'AVANT.

    Sans ceci, le test précédent pourrait passer parce qu'il ne cherche rien.
    """
    avant = """
    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host app.evkha.fr;
    }
    """
    assert domaines_en_dur(avant) == [(4, "app.evkha.fr")]


def test_le_detecteur_voit_le_defaut_reel_des_etiquettes_traefik() -> None:
    """Contre-épreuve : il aurait aussi attrapé la première instance."""
    avant = '- "traefik.http.routers.evkha-api-https.rule=Host(`app.evkha.fr`)"'
    assert [h for _, h in domaines_en_dur(avant)] == ["app.evkha.fr"]


def test_le_detecteur_ne_bloque_pas_ce_qui_est_correct() -> None:
    """Contre-épreuve inverse : le correctif ne doit pas être signalé.

    Un contrôle qui refuse aussi la bonne réponse est inutilisable — il sera
    désactivé au premier faux positif.
    """
    apres = """
    proxy_set_header Host $host;
    - "traefik.http.routers.${STACK_NAME:-evkha}-api-https.rule=Host(`${API_DOMAIN}`)"
    image: postgres:16-alpine
    # Ici on cite app.evkha.fr pour expliquer le defaut : c'est un commentaire.
    """
    assert domaines_en_dur(apres) == []
