"""Un champ FILE_UPLOAD Tally se depouille en URL exploitable.

## Le defaut mesure

Aucun logo Tally ne s'affichait. Un champ fichier Tally arrive comme
``[{"url": "https://storage.tally.so/...", "mimeType": "image/png"}]``.
``_valeur_lisible`` ne le transformait pas, et ``charger_logo`` recevait
la repr Python du dict — un chemin inexistant sur disque.
"""
from __future__ import annotations

from generation.rendering import _depouiller_url_tally
from intake.services import _depouiller_fichier_tally

# ── _depouiller_fichier_tally (intake, valeur brute) ──


def test_une_liste_tally_rend_l_url() -> None:
    valeur = [{"url": "https://storage.tally.so/abc/logo.png", "mimeType": "image/png"}]
    assert _depouiller_fichier_tally(valeur) == "https://storage.tally.so/abc/logo.png"


def test_plusieurs_fichiers_rendent_une_liste() -> None:
    valeur = [
        {"url": "https://storage.tally.so/a.png", "mimeType": "image/png"},
        {"url": "https://storage.tally.so/b.jpg", "mimeType": "image/jpeg"},
    ]
    assert _depouiller_fichier_tally(valeur) == [
        "https://storage.tally.so/a.png",
        "https://storage.tally.so/b.jpg",
    ]


def test_une_liste_sans_url_reste_telle_quelle() -> None:
    valeur = [{"text": "option A"}]
    assert _depouiller_fichier_tally(valeur) == [{"text": "option A"}]


def test_une_chaine_reste_telle_quelle() -> None:
    assert _depouiller_fichier_tally("mon texte") == "mon texte"


def test_none_reste_none() -> None:
    assert _depouiller_fichier_tally(None) is None


# ── _depouiller_url_tally (rendering, valeur str d'anciens dossiers) ──


def test_un_dump_str_de_fichier_tally_rend_l_url() -> None:
    dump = "[{'url': 'https://storage.tally.so/abc/logo.png', 'mimeType': 'image/png'}]"
    assert _depouiller_url_tally(dump) == "https://storage.tally.so/abc/logo.png"


def test_une_url_directe_reste_directe() -> None:
    url = "https://example.com/logo.png"
    assert _depouiller_url_tally(url) == url


def test_un_chemin_media_reste_tel_quel() -> None:
    chemin = "/media/pieces-jointes/abc/logo.png"
    assert _depouiller_url_tally(chemin) == chemin


def test_une_chaine_vide_reste_vide() -> None:
    assert _depouiller_url_tally("") == ""


def test_un_texte_quelconque_reste_tel_quel() -> None:
    assert _depouiller_url_tally("Mon entreprise") == "Mon entreprise"
