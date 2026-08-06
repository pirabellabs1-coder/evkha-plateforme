"""Un dossier d'images ne doit pas faire disparaitre une page du site.

Mesure du 05/08/2026, en cherchant simplement le lien a mettre dans le menu du
tunnel de vente :

    https://app2.evkha.fr/partenaires    -> HTTP 403
    https://app2.evkha.fr/inscription    -> HTTP 200
    https://app2.evkha.fr/Partenaires    -> HTTP 200   <-- la casse trahit

`/partenaires` est la SEULE page publique de l'application — le routeur le dit
lui-meme : « aucune garde : elle s'adresse a des visiteurs sans compte […] le
menu du site vitrine pointe dessus ». Elle etait injoignable.

## La cause

Vite copie `frontend/public/` tel quel a la racine du site. Les deux photos de
la page vivent dans `public/partenaires/`, donc le site deploye porte un vrai
REPERTOIRE `/partenaires`. La directive `try_files $uri $uri/ /index.html`
essayait ce repertoire, n'y trouvait aucun index, et nginx repondait 403 —
l'autoindex etant desactive, a raison.

## Pourquoi retirer `$uri/` plutot que renommer le dossier

Renommer n'aurait regle que ce cas. Demain, un dossier `credits/` ou
`livrables/` masquerait la route du meme nom, et le defaut reviendrait sous une
autre forme (regle 4). Sans `$uri/`, un repertoire ne satisfait plus le premier
test et la route tombe sur `index.html`, comme toutes les autres. Les fichiers
restent servis par `$uri`.

Ce test lit le FICHIER de configuration : c'est lui qui part en production, et
c'est la seule chose verifiable sans deployer.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
NGINX = RACINE / "frontend" / "nginx.conf"
PUBLIC = RACINE / "frontend" / "public"


def _try_files() -> str:
    contenu = NGINX.read_text(encoding="utf-8")
    trouve = re.search(r"try_files([^;]*);", contenu)
    assert trouve is not None, "aucune directive try_files dans nginx.conf"
    return " ".join(trouve.group(1).split())


def test_le_repli_spa_n_essaie_pas_les_repertoires() -> None:
    """`$uri/` fait repondre 403 des qu'un dossier porte le nom d'une route."""
    directive = _try_files()

    assert "$uri/" not in directive, directive
    assert "$uri" in directive and "/index.html" in directive, directive


def test_les_fichiers_statiques_restent_servis() -> None:
    """Contre-epreuve : on n'a pas casse le service des images.

    `/partenaires/reunion.jpg` est un FICHIER : `$uri` le trouve.
    """
    assert _try_files().split()[0] == "$uri"


@pytest.mark.parametrize(
    "dossier", [d.name for d in PUBLIC.iterdir() if d.is_dir()] or ["partenaires"]
)
def test_un_dossier_statique_porte_le_nom_d_une_route_et_c_est_permis(
    dossier: str,
) -> None:
    """La collision EXISTE et doit rester sans effet.

    Ce test ne demande pas de renommer quoi que ce soit : il constate que le
    depot porte bien le cas qui a produit le 403, et que la configuration le
    supporte desormais. Le jour ou quelqu'un remet `$uri/`, le test precedent
    echoue — celui-ci documente pourquoi.
    """
    assert (PUBLIC / dossier).is_dir()
    assert "$uri/" not in _try_files()
