"""Une adresse plausible inventée passait le gate : personne ne vérifiait qu'elle mène quelque part.

Audit du 26/09/2026. `_URL_BIDON_RE` ne connaît que les gabarits (example.com,
source.fr) ; « https://www.observatoire-des-services-premium.fr/etude-2025 »
passait. Comparer chaque domaine au brief de recherche aurait été FAUX par
construction : la charte ordonne de remonter au PRODUCTEUR de la donnée, dont
le domaine n'est jamais dans le brief quand la recherche n'a rapporté que la
presse. On ne juge donc que ce qui se prouve : un domaine que rien ne nous a
donné ET qui n'existe pas (aucune résolution DNS) est un lien mort. Une panne
DNS n'accuse personne (règle 2).
"""
from __future__ import annotations

import socket
from typing import Any

import pytest

from generation.checks_post_rendu import (
    _hote,
    detecter_domaines_inexistants,
    hotes_cites,
    resoudre_dns,
)
from generation.correction import _CHECK_LABELS, _is_regenerable
from generation.rendering import RenderedSection


def _section(numero: int, corps: str) -> RenderedSection:
    return RenderedSection(number=numero, title=f"Chapitre {numero}", kind="chapitre", body=corps)


# ── Lire un domaine ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("adresse", "hote"),
    [
        pytest.param(
            "https://www.Insee.fr/fr/statistiques/8727786?x=1", "insee.fr", id="url-complete",
        ),
        pytest.param("http://data.gouv.fr:8080/", "data.gouv.fr", id="port-et-sous-domaine"),
        pytest.param("gold.fr/vente-or", "gold.fr", id="domaine-nu"),
        pytest.param("WWW.XERFI.COM", "xerfi.com", id="majuscules"),
    ],
)
def test_l_hote_est_normalise(adresse: str, hote: str) -> None:
    assert _hote(adresse) == hote


def test_les_deux_formes_d_adresse_sont_lues() -> None:
    cites = hotes_cites(
        "Voir https://www.insee.fr/fr/statistiques/1 et gold.fr/vente-or (Insee, 2025)."
    )
    assert set(cites) == {"insee.fr", "gold.fr"}


# ── Juger ────────────────────────────────────────────────────────────────────

RESOLUTIONS = {
    "insee.fr": True,
    "observatoire-bidon.fr": False,
    "portail-inconnu-mais-reel.fr": True,
    "dns-en-panne.fr": None,
}


def _faux_dns(hote: str) -> bool | None:
    return RESOLUTIONS.get(hote, False)


def test_un_domaine_inconnu_et_inexistant_est_signale() -> None:
    (trouve,) = detecter_domaines_inexistants(
        [_section(9, "Source : https://www.observatoire-bidon.fr/etude-2025")],
        hotes_admis=frozenset({"insee.fr"}),
        resoudre=_faux_dns,
    )
    assert trouve.hote == "observatoire-bidon.fr"
    assert trouve.chapitre == 9
    assert "n'existe pas" in str(trouve)


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("Source : https://www.insee.fr/fr/statistiques/1", id="admis"),
        pytest.param("Source : https://data.insee.fr/serie/2", id="sous-domaine-admis"),
        pytest.param(
            "Source : https://portail-inconnu-mais-reel.fr/rapport", id="inconnu-mais-existant",
        ),
        pytest.param(
            "Source : https://dns-en-panne.fr/rapport", id="dns-indisponible-n-accuse-pas",
        ),
        pytest.param(
            "Article L221-18 du code de la consommation.", id="reference-juridique-sans-adresse",
        ),
    ],
)
def test_ce_qui_ne_se_prouve_pas_n_est_pas_signale(texte: str) -> None:
    assert detecter_domaines_inexistants(
        [_section(9, texte)], hotes_admis=frozenset({"insee.fr"}), resoudre=_faux_dns,
    ) == []


def test_chaque_domaine_n_est_interroge_qu_une_fois() -> None:
    appels: list[str] = []

    def _compteur(hote: str) -> bool | None:
        appels.append(hote)
        return False

    detecter_domaines_inexistants(
        [_section(3, "https://a-bidon.fr/x et https://a-bidon.fr/y"), _section(4, "a-bidon.fr/z")],
        hotes_admis=frozenset(), resoudre=_compteur,
    )
    assert appels == ["a-bidon.fr"]


# ── Le DNS réel, classé ──────────────────────────────────────────────────────


def test_seul_un_nom_inconnu_vaut_inexistant(monkeypatch: pytest.MonkeyPatch) -> None:
    def _inconnu(*_: Any, **__: Any) -> Any:
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    def _resolveur_en_panne(*_: Any, **__: Any) -> Any:
        raise socket.gaierror(getattr(socket, "EAI_AGAIN", 11002), "Temporary failure")

    monkeypatch.setattr(socket, "getaddrinfo", _inconnu)
    assert resoudre_dns("n-importe-quoi.fr") is False
    monkeypatch.setattr(socket, "getaddrinfo", _resolveur_en_panne)
    assert resoudre_dns("n-importe-quoi.fr") is None
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_, **__: [("ok",)])
    assert resoudre_dns("insee.fr") is True


def test_la_boucle_de_correction_sait_le_reparer() -> None:
    assert _is_regenerable("domaine_inexistant")
    assert "domaine_inexistant" in _CHECK_LABELS
