"""Une requête trop lourde est refusée sur son annonce, pas après lecture.

Audit du 19/11/2026. Le nginx du front coupe à 12 Mo, mais il ne garde que
`app2.evkha.fr` : par `api2.evkha.fr`, l'API recevait n'importe quel poids. Un
fichier était écrit en entier sur le disque, puis relu en entier en mémoire par
la vue de dépôt, qui constatait seulement ALORS qu'il dépassait 10 Mo.

Ces tests échouent sur le code d'avant : la requête atteignait la vue.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory

from evkha.corps import CorpsBorne
from organisations.fichiers import TAILLE_MAX_DOCUMENT

CONF = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"


def _passer(annonce: Any) -> tuple[HttpResponse, list[HttpRequest]]:
    """Fait traverser la garde à une requête qui ANNONCE `annonce` octets."""
    lues: list[HttpRequest] = []

    def vue(requete: HttpRequest) -> HttpResponse:
        lues.append(requete)
        return HttpResponse("lu")

    requete = RequestFactory().post(
        "/api/espace/pieces-jointes/", data=b"x", content_type="application/octet-stream",
    )
    requete.META["CONTENT_LENGTH"] = annonce
    return CorpsBorne(vue)(requete), lues


def test_un_envoi_de_deux_gigaoctets_n_atteint_aucune_vue() -> None:
    reponse, lues = _passer(str(2 * 1024**3))

    assert reponse.status_code == 413
    assert lues == []


def test_le_refus_dit_la_borne_a_la_personne() -> None:
    reponse, _ = _passer(str(settings.EVKHA_TAILLE_MAX_REQUETE + 1))

    assert reponse.status_code == 413
    assert b"12 Mo" in reponse.content


def test_un_fichier_de_dix_megaoctets_traverse() -> None:
    """Contre-épreuve : ce que le produit promet passe, enveloppe comprise."""
    reponse, lues = _passer(str(TAILLE_MAX_DOCUMENT + 512 * 1024))

    assert reponse.status_code == 200
    assert len(lues) == 1


@pytest.mark.parametrize("annonce", ["", None, "pas-un-nombre"])
def test_une_annonce_illisible_ne_bloque_pas(annonce: Any) -> None:
    """Contre-épreuve : un GET n'annonce rien, et ce n'est pas un refus."""
    reponse, lues = _passer(annonce)

    assert reponse.status_code == 200
    assert len(lues) == 1


def test_la_garde_est_branchee_avant_tout_ce_qui_lit_le_corps() -> None:
    """Un intergiciel écrit et jamais branché ne garde rien (règle 8)."""
    pile = list(settings.MIDDLEWARE)

    assert "evkha.corps.CorpsBorne" in pile
    assert pile.index("evkha.corps.CorpsBorne") < pile.index(
        "django.middleware.csrf.CsrfViewMiddleware"
    )
    assert pile.index("corsheaders.middleware.CorsMiddleware") < pile.index(
        "evkha.corps.CorpsBorne"
    ), "le refus doit porter les en-têtes CORS, sinon le navigateur n'en lit pas le motif"


@pytest.mark.django_db
def test_la_garde_repond_sur_une_vraie_route() -> None:
    reponse = Client().post(
        "/api/espace/pieces-jointes/",
        data=b"x",
        content_type="application/octet-stream",
        CONTENT_LENGTH=str(50 * 1024 * 1024),
    )

    assert reponse.status_code == 413
    assert reponse.json()["code"] == "requete_trop_lourde"


def test_les_deux_chemins_acceptent_le_meme_poids() -> None:
    """`app2` (nginx) et `api2` (cette garde) : une seule borne, deux écritures.

    Le fichier nginx n'est pas du Python et ne peut pas importer la constante ;
    à défaut d'une source unique, ce test les tient d'accord (règle 5).
    """
    trouve = re.search(
        r"client_max_body_size\s+(\d+)([kKmMgG]?)", CONF.read_text(encoding="utf-8")
    )
    assert trouve is not None
    facteur = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3}
    du_proxy = int(trouve.group(1)) * facteur[trouve.group(2).lower()]

    assert du_proxy == settings.EVKHA_TAILLE_MAX_REQUETE
