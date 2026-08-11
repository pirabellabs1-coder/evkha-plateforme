"""Le proxy doit laisser passer ce que le produit promet d'accepter.

## Le défaut, signalé deux fois par la cliente

« On ne peut toujours pas joindre de fichiers dans le formulaire », puis
« il ne s'ajoutait pas pourtant il faisait 3,5 Mo ».

`frontend/nginx.conf` ne portait aucun `client_max_body_size`. Nginx applique
alors son défaut — **un mégaoctet** — et rejette la requête en 413 AVANT
qu'elle n'atteigne Django, dont les réglages autorisent pourtant 10 Mo. Le
formulaire annonçait « 10 Mo maximum » et refusait tout ce qui dépassait un
mégaoctet.

Chercher la cause côté Python ne pouvait rien donner : la requête n'y
arrivait jamais. C'est le défaut de la règle 3 appliqué à l'entrée — ce qui
se trouve DEVANT le code ne se voit pas depuis le code.

## Pourquoi ce test lit un fichier de configuration

La borne vit à deux endroits qui ne peuvent pas se lire l'un l'autre : un
`.conf` nginx et une constante Python. À défaut de source unique (règle 5),
un contrôle les tient d'accord — et casse le jour où l'une bouge sans
l'autre.
"""
from __future__ import annotations

import re
from pathlib import Path

from organisations.fichiers import TAILLE_MAX_DOCUMENT

CONF = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"


def _limite_du_proxy() -> int:
    texte = CONF.read_text(encoding="utf-8")
    trouve = re.search(r"client_max_body_size\s+(\d+)([kKmMgG]?)", texte)
    assert trouve, "nginx.conf ne fixe AUCUN client_max_body_size (défaut : 1 Mo)"
    facteur = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3}
    return int(trouve.group(1)) * facteur[trouve.group(2).lower()]


def test_le_proxy_accepte_au_moins_ce_que_le_produit_promet() -> None:
    """Un fichier de 10 Mo doit traverser, enveloppe multipart comprise."""
    assert _limite_du_proxy() >= TAILLE_MAX_DOCUMENT


def test_la_marge_couvre_l_enveloppe_multipart() -> None:
    """CONTRE-ÉPREUVE : une borne posée PILE à 10 Mo rejetterait un fichier de
    10 Mo, dont le corps multipart pèse davantage — en-têtes, séparateurs, nom
    du fichier. Le refus serait alors juste au mégaoctet près et faux pour la
    personne qui dépose.
    """
    assert _limite_du_proxy() >= TAILLE_MAX_DOCUMENT + 512 * 1024
