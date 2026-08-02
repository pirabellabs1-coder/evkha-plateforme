"""Le champ « logo » ne doit pas servir à sonder le réseau de la plateforme.

`charger_logo` appelait `httpx.get(url, follow_redirects=True)` sans aucune
restriction d'hôte, et cette URL vient d'un champ que l'abonné remplit
lui-même. Écrire `http://redis:6379/` faisait donc émettre la requête **par le
worker**, à l'intérieur du réseau Docker où aucun de ces ports n'est exposé
publiquement. Les erreurs et les temps de réponse suffisent à cartographier la
pile — c'est une SSRF aveugle, et l'inscription est libre et gratuite.

Le contrôle porte sur l'adresse **résolue**, jamais sur le nom écrit : sinon il
suffirait de faire pointer un domaine public vers 127.0.0.1.

Et il porte sur **chaque saut** : une URL parfaitement publique peut répondre
`302 → http://postgres:5432`, et un contrôle fait une seule fois au départ
n'aurait rien vu passer (règle 3).
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.rendu_word import logo


class _Reponse:
    """Réponse httpx minimale."""

    def __init__(self, *, contenu: bytes = b"", redirige_vers: str = "") -> None:
        self.content = contenu
        self.headers = {"location": redirige_vers} if redirige_vers else {}
        self.is_redirect = bool(redirige_vers)

    def raise_for_status(self) -> None:
        return None


# ── Ce que le champ ne doit pas atteindre ────────────────────────────────────


@pytest.mark.parametrize(
    "interne",
    [
        "http://localhost:6379/",
        "http://127.0.0.1:5432/",
        "http://redis:6379/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]:8000/",
    ],
)
def test_une_adresse_interne_n_est_jamais_jointe(
    interne: str, monkeypatch: Any
) -> None:
    """Le test qui échoue sur le code d'avant : la requête partait.

    On vise la CLASSE — toute adresse non publique — et pas une liste de noms
    interdits, qui serait fausse dès le prochain service ajouté à la pile.
    """
    appels: list[str] = []

    def _interdit(url: str, **_: Any) -> _Reponse:
        appels.append(url)
        return _Reponse(contenu=b"\\x89PNG\\r\\n\\x1a\\n")

    monkeypatch.setattr("httpx.get", _interdit)

    assert logo.charger_logo(interne) is None
    assert appels == [], f"une requete est partie vers {interne}"


def test_une_redirection_vers_l_interieur_est_arretee(monkeypatch: Any) -> None:
    """Le saut suivant est contrôlé, pas seulement le premier.

    Un contrôle appliqué une seule fois au départ laisserait passer une URL
    publique qui redirige vers la pile — et c'est le scénario qu'un attaquant
    écrirait, parce qu'il coûte une ligne de configuration sur son serveur.
    """
    joints: list[str] = []

    def _redirige(url: str, **_: Any) -> _Reponse:
        joints.append(url)
        if "exemple" in url:
            return _Reponse(redirige_vers="http://redis:6379/")
        return _Reponse(contenu=b"\\x89PNG\\r\\n\\x1a\\n")

    monkeypatch.setattr("httpx.get", _redirige)

    assert logo.charger_logo("https://exemple.fr/logo.png") is None
    assert all("redis" not in adresse for adresse in joints), (
        f"la redirection interne a ete suivie : {joints}"
    )


def test_une_boucle_de_redirections_ne_tourne_pas_sans_fin(
    monkeypatch: Any,
) -> None:
    """Contre-épreuve de robustesse : un serveur hostile boucle volontiers."""
    compte = {"n": 0}

    def _boucle(url: str, **_: Any) -> _Reponse:
        compte["n"] += 1
        return _Reponse(redirige_vers="https://exemple.fr/encore")

    monkeypatch.setattr("httpx.get", _boucle)

    assert logo.charger_logo("https://exemple.fr/logo.png") is None
    assert compte["n"] <= logo.REDIRECTIONS_MAX + 1


# ── Ce qui doit continuer à marcher ──────────────────────────────────────────


def test_un_logo_public_est_toujours_recupere(monkeypatch: Any) -> None:
    """Contre-épreuve : le correctif ne doit pas priver les abonnés de leur logo.

    Le PNG est un vrai PNG minimal : `charger_logo` valide le format, et un
    contenu quelconque serait rejeté pour la mauvaise raison — le test
    passerait alors sans rien prouver (règle 2).
    """
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    monkeypatch.setattr("httpx.get", lambda *a, **k: _Reponse(contenu=png))
    # `exemple.fr` doit resoudre vers une adresse publique pour ce test.
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )

    assert logo.charger_logo("https://exemple.fr/logo.png") == png


def test_un_nom_introuvable_est_refuse_sans_bruit(monkeypatch: Any) -> None:
    """Ne pas pouvoir juger vaut REFUS, jamais laissez-passer (règle 1)."""
    import socket

    def _echoue(*a: Any, **k: Any) -> Any:
        raise OSError("nom introuvable")

    monkeypatch.setattr(socket, "getaddrinfo", _echoue)
    appels: list[str] = []
    monkeypatch.setattr(
        "httpx.get",
        lambda url, **k: (appels.append(url), _Reponse(contenu=b"x"))[1],
    )

    assert logo.charger_logo("https://nexiste-pas.invalid/logo.png") is None
    assert appels == []


def test_un_logo_depose_dans_l_espace_ne_passe_pas_par_le_reseau(
    monkeypatch: Any,
) -> None:
    """Contre-épreuve de périmètre : le cas NORMAL n'est pas concerné.

    Depuis que le logo se téléverse, le fichier est déjà sur le disque. Le
    contrôle réseau ne doit pas s'appliquer là — il n'y a pas de requête.
    """
    def _jamais(*a: Any, **k: Any) -> Any:
        msg = "aucune requete ne doit partir pour un fichier local"
        raise AssertionError(msg)

    monkeypatch.setattr("httpx.get", _jamais)

    assert logo.charger_logo("/media/pieces-jointes/x/logo.png") is None
