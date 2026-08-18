"""Un chapitre manquant se dit dans le sommaire.

Business plan `256e63d8`, 17/08/2026. Le dossier s'arrete a 21 chapitres sur
22 : le plafond de depense est atteint avant le dernier. Le sommaire livre a la
cliente ecrit alors :

    | 01 | Résumé exécutif |
    | 03 | Genèse du projet |

Le chapitre 02 ne manque pas : il n'existe pas. Aucune ligne, aucune mention,
nulle part. La cliente : « il manque le chapitre 02 dans le sommaire, c'est le
premier defaut de forme evident » — et elle a du deviner la cause elle-meme.

Le depot avait deja tranche ce principe pour la generation : un dossier qui
coince « livre le reste avec un trou nomme ». Le rendu n'avait jamais appris la
seconde moitie de la phrase.
"""
from __future__ import annotations

from generation.rendu_word.depuis_json import (
    MENTION_CHAPITRE_ABSENT,
    entrees_du_sommaire,
)


def test_le_chapitre_absent_apparait_dans_le_sommaire() -> None:
    """Le cas reel : le sommaire saute de 01 a 03.

    Echoue sur le code d'avant : le sommaire listait les chapitres PRODUITS,
    donc un chapitre non ecrit disparaissait sans laisser de trace.
    """
    entrees = entrees_du_sommaire([
        {"numero": 1, "titre": "Résumé exécutif"},
        {"numero": 3, "titre": "Genèse du projet"},
        {"numero": 4, "titre": "Présentation de l'activité"},
    ])
    numeros = [numero for numero, _titre, _page in entrees]
    assert numeros == ["01", "02", "03", "04"]
    assert entrees[1][1] == MENTION_CHAPITRE_ABSENT


def test_un_document_complet_est_inchange() -> None:
    """Contre-epreuve : aucune ligne inventee sur un dossier sain."""
    chapitres = [{"numero": n, "titre": f"Chapitre {n}"} for n in range(1, 23)]
    entrees = entrees_du_sommaire(chapitres)
    assert len(entrees) == 22
    assert all(MENTION_CHAPITRE_ABSENT != titre for _n, titre, _p in entrees)


def test_le_sommaire_commence_au_premier_chapitre_present() -> None:
    """Contre-epreuve : la fiche projet (chapitre 0) est ecartee en amont.

    Demarrer l'intervalle a zero reclamerait un chapitre que `pour_le_client`
    vient justement de retirer — le controle contredirait le rendu (regle 3).
    """
    entrees = entrees_du_sommaire([
        {"numero": 1, "titre": "Résumé exécutif"},
        {"numero": 2, "titre": "Genèse"},
    ])
    assert [n for n, _t, _p in entrees] == ["01", "02"]


def test_un_sommaire_vide_reste_vide() -> None:
    """Contre-epreuve : rien a annoncer sur un document sans chapitre."""
    assert entrees_du_sommaire([]) == []
