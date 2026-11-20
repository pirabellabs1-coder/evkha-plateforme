"""Un fichier de `/media/` est JUGÉ et SERVI sous une seule forme de chemin.

Audit du 20/11/2026. `servir_media` décidait sur le chemin brut — « commence
par un préfixe de vitrine, donc public » — puis passait ce même chemin à
`django.views.static.serve`, qui le NORMALISE avant d'ouvrir le fichier.
`formations-vitrine/../formations/<slug>/support.pdf` était donc reconnu
public, jamais confronté à sa signature, et rendait le document payant. La
vitrine de la boutique portait le même défaut depuis sa création.

Ces tests jouent `servir_media` directement, sur un dossier à part : un client
de test normaliserait l'adresse avant de l'envoyer et ne prouverait rien.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.http import Http404
from django.test import RequestFactory

from catalog.models import PREFIXE_VITRINE, PREFIXE_VITRINE_FORMATIONS
from evkha import signatures
from evkha.media import _est_canonique, servir_media

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\ntrailer\n<<>>\n%%EOF\n"


@pytest.fixture
def racine(tmp_path: Any) -> Any:
    """Un document payant, et une couverture publique à côté."""
    (tmp_path / "formations" / "methode-pop").mkdir(parents=True)
    (tmp_path / "formations" / "methode-pop" / "support.pdf").write_bytes(PDF)
    (tmp_path / "boutique" / "etude").mkdir(parents=True)
    (tmp_path / "boutique" / "etude" / "etude.pdf").write_bytes(PDF)
    for prefixe in (PREFIXE_VITRINE, PREFIXE_VITRINE_FORMATIONS):
        (tmp_path / prefixe / "x").mkdir(parents=True)
        (tmp_path / prefixe / "x" / "couverture.pdf").write_bytes(PDF)
    return tmp_path


def _servir(chemin: str, racine: Any, requete: str = "/") -> Any:
    return servir_media(RequestFactory().get(requete), chemin, document_root=racine)


@pytest.mark.parametrize(
    "detour",
    [
        f"{PREFIXE_VITRINE_FORMATIONS}/../formations/methode-pop/support.pdf",
        f"{PREFIXE_VITRINE_FORMATIONS}/x/../../formations/methode-pop/support.pdf",
        f"{PREFIXE_VITRINE}/../boutique/etude/etude.pdf",
        f"{PREFIXE_VITRINE}/./../boutique/etude/etude.pdf",
        f"{PREFIXE_VITRINE_FORMATIONS}//../formations/methode-pop/support.pdf",
        f"{PREFIXE_VITRINE_FORMATIONS}\\..\\formations\\methode-pop\\support.pdf",
        f"{PREFIXE_VITRINE_FORMATIONS}/..\\formations/methode-pop/support.pdf",
    ],
)
def test_un_detour_par_la_vitrine_ne_rend_pas_un_document_payant(
    detour: str, racine: Any
) -> None:
    with pytest.raises(Http404):
        _servir(detour, racine)


def test_un_detour_est_refuse_meme_avec_une_signature_valable(racine: Any) -> None:
    """On refuse le détour, on ne le corrige pas : nos liens n'en fabriquent pas."""
    detour = "formations/./methode-pop/support.pdf"
    jeton = signatures.signer(detour)

    with pytest.raises(Http404):
        _servir(detour, racine, f"/?{signatures.PARAMETRE}={jeton}")


def test_contre_epreuve_la_couverture_reste_servie_sans_signature(racine: Any) -> None:
    for prefixe in (PREFIXE_VITRINE, PREFIXE_VITRINE_FORMATIONS):
        servie = _servir(f"{prefixe}/x/couverture.pdf", racine)
        assert servie.status_code == 200
        assert servie.headers["Content-Disposition"] == "inline"


def test_contre_epreuve_le_document_reste_ouvrable_par_son_lien_signe(
    racine: Any,
) -> None:
    chemin = "formations/methode-pop/support.pdf"
    jeton = signatures.signer(chemin)

    servie = _servir(chemin, racine, f"/?{signatures.PARAMETRE}={jeton}")

    assert servie.status_code == 200
    assert servie.headers["Content-Disposition"] == "attachment"


def test_contre_epreuve_sans_signature_le_document_reste_ferme(racine: Any) -> None:
    with pytest.raises(Http404):
        _servir("formations/methode-pop/support.pdf", racine)


def test_le_juge_de_forme_voit_ce_qu_il_doit_voir() -> None:
    for juste in [
        "formations/methode-pop/support.pdf",
        "/boutique-vitrine/x/couverture.png",
        "livrables/2026/Étude de marché (v2).pdf",
        "a..b/c.pdf",
    ]:
        assert _est_canonique(juste), juste
    for faute in [
        "",
        "/",
        "..",
        "../secret.pdf",
        "a/../b.pdf",
        "a/./b.pdf",
        "a//b.pdf",
        "a/b.pdf/",
        "a\\b.pdf",
        "a/b\x00.pdf",
    ]:
        assert not _est_canonique(faute), repr(faute)
