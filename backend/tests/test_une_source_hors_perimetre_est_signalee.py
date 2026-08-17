"""Une source d'un autre périmètre doit se signaler AVANT d'entrer dans le socle.

## Le retour, et il est économique autant que qualitatif

Cliente, 09/08/2026 : « l'IA ne doit pas chercher des infos qui ne
correspondent pas, c'est grave et une perte de temps — surtout quand il y aura
plus d'utilisateurs. »

La chaîne lui donnait raison. La requête ciblait bien « e-commerce animalier
**France** », mais **rien ne vérifiait que le résultat parlait de la France**.
Sur le dossier réel `451f955b`, une source sur le marché **mondial** des « pet
products » est entrée dans le brief, le socle l'a exploitée, l'appel a été payé,
puis la vérification l'a déclassée :

    « La source porte sur le marché mondial des pet products […] pas
      spécifiquement l'e-commerce animalier France. »

Trois dépenses pour une source qu'il fallait signaler au départ. À dix
utilisateurs, dix fois ce gaspillage.

## Pourquoi on MARQUE et non on JETTE

Un filtre qui supprime se trompe dans les deux sens : une page de la Fevad sur
le marché français n'écrit pas forcément « France », et un article mondial peut
porter le seul chiffre disponible. Supprimer ferait disparaître des sources
utiles sans que personne ne le sache — le silence que ce dépôt combat (règle 1).

Marquer donne l'information **au moment où la décision se prend**. C'est la
même leçon que la nature des identifiants du socle entre crochets, et que les
règles de figures enfin transmises au bon moteur : une aide sert là où l'on
choisit, pas dans un document que personne ne lit.
"""
from __future__ import annotations

import pytest

from generation.research import _format_result, _perimetre_apparent
from integrations.search import SearchResult


def _resultat(titre: str, contenu: str = "") -> SearchResult:
    return SearchResult(
        title=titre,
        url="https://exemple.fr/page",
        content=contenu or titre,
        score=0.9,
        published_date="2026-01-15",
    )


# ── Ce qui doit être signalé ─────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("titre", "portee"),
    [
        ("Global pet products market size 2025-2034", "monde entier"),
        ("Le marché mondial des produits pour animaux", "monde entier"),
        ("Worldwide e-commerce trends for pet supplies", "monde entier"),
        ("Le marché européen de l'alimentation animale", "Europe"),
        ("International pet care market outlook", "plusieurs pays"),
    ],
)
def test_une_source_d_un_perimetre_plus_large_est_signalee(
    titre: str, portee: str
) -> None:
    """Le cas exact du dossier `451f955b`, et ses variantes."""
    assert _perimetre_apparent(_resultat(titre), "France") == portee


def test_le_marqueur_dit_quoi_faire_et_pas_seulement_ce_qui_ne_va_pas() -> None:
    """Un motif qui ne dit pas quoi faire ne fait rien corriger (règle 2)."""
    rendu = _format_result(
        _resultat("Global pet products market size 2025-2034"), "France"
    )

    assert "PÉRIMÈTRE APPARENT" in rendu
    assert "monde entier" in rendu
    assert "France" in rendu
    assert "`estimee`" in rendu


# ── LA contre-épreuve : ne pas signaler ce qui va bien ───────────────────────

@pytest.mark.parametrize(
    "titre",
    [
        "Le marché français de l'e-commerce animalier en 2026",
        "Fevad — bilan du e-commerce en France",
        "Marché mondial des pet products, et la France en particulier",
        "Insee — établissements du commerce de détail",
        "Les dépenses des ménages pour leurs animaux",
    ],
)
def test_une_source_du_bon_perimetre_n_est_pas_signalee(titre: str) -> None:
    """Signaler à tort ferait écarter des sources justes.

    Le troisième cas compte le plus : un article qui dit « mondial » ET
    « France » traite bien du pays étudié. Ne regarder que le mot « mondial »
    l'aurait condamné — la règle 2, un remède qui frappe ce qui n'était pas
    malade.
    """
    assert _perimetre_apparent(_resultat(titre), "France") == ""


def test_sans_pays_declare_on_ne_signale_rien() -> None:
    """Pas de périmètre de référence : rien à quoi comparer, donc aucun verdict.

    On ne prétend pas avoir jugé (règle 1) — et on n'invente pas un défaut.
    """
    assert _perimetre_apparent(_resultat("Global market report"), "") == ""


def test_une_source_saine_est_rendue_telle_quelle() -> None:
    """Le format existant ne doit pas bouger pour les sources du bon périmètre."""
    rendu = _format_result(
        _resultat("Fevad — le e-commerce en France en 2026"), "France"
    )

    assert "PÉRIMÈTRE APPARENT" not in rendu
    assert rendu.startswith("- Fevad")


def test_le_pays_est_reconnu_quelle_que_soit_la_casse() -> None:
    assert _perimetre_apparent(_resultat("Le marché MONDIAL, focus france"), "France") == ""
