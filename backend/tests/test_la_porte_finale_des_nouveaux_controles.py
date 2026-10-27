"""Les trois contrôles du 27/10/2026, jugés sur un chapitre ORDINAIRE.

## Pourquoi ce fichier existe, en plus des tests de chaque contrôle

Le 30/09/2026, une relecture est partie au déploiement avec 43 motifs sur 43
reconnus et 4 812 tests verts — et le verdict a été NO-GO : aucune épreuve ne
passait les formes COURANTES du livrable, celles que le modèle écrit à chaque
chapitre. Les tests unitaires jugent chacun SON cas ; aucun ne demandait « et
sur un chapitre normal, qu'est-ce que ça dit ? ».

Ce fichier pose les deux moitiés de la question sur le MÊME chapitre :

1. un chapitre correct, de la forme que le modèle de référence produit, ne doit
   rien déclencher — sinon chaque dossier paierait des reprises inutiles
   (règle 2 : un contrôle qui frappe ce qui n'était pas malade est pire que le
   défaut) ;
2. le même chapitre, abîmé d'UN défaut à la fois, doit parler — sinon le
   contrôle est inerte, et un contrôle qui n'a rien à comparer est un échec,
   jamais un succès (règle 1).

Les deux moitiés ensemble, et sur la même matière : c'est la règle 9.
"""
from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest

from generation.relecture import Reference, document_du_chapitre, relire

#: Les classes ajoutées le 27/10/2026, en réponse aux points 6, 11 et 15 de la
#: cliente (étude de marché à l'export, 26/10/2026).
CLASSES_NOUVELLES = frozenset({"comptage", "orthographe", "decision"})

#: Un chapitre d'étude de marché tel que le modèle de référence en produit :
#: une accroche qui compte, un tableau de scoring, une décision de priorité, un
#: encadré de synthèse, des accents, des montants, une figure titrée.
CHAPITRE_ORDINAIRE: dict[str, Any] = {
    "chapitre": 7,
    "titre": "Priorisation des zones d'export",
    "accroche": "Quatre zones ressortent du scoring, dans un ordre que les écarts rendent net.",
    "blocs": [
        {"type": "titre_sous_section", "numero": "7.1", "intitule": "Le scoring des zones"},
        {"type": "paragraphe", "texte": (
            "Le marché français des produits transformés pèse 2,7 Md€ en 2025, et le "
            "marché export accessible 2,1 Md€. La méthode précise retenue pondère six "
            "critères : demande, solvabilité, densité, accessibilité, concurrence et "
            "réglementation. Les données de la douane couvrent 2022 à 2025."
        )},
        {"type": "tableau", "tableau": {
            "entetes": ["Zone", "Score", "Demande", "Réglementation"],
            "lignes": [
                ["Corée du Sud", "7,8/10", "Forte", "Enregistrement sanitaire"],
                ["Japon", "7,2/10", "Forte", "Étiquetage bilingue"],
                ["Taïwan", "6,4/10", "Moyenne", "Quota à l'importation"],
                ["Chine", "5,1/10", "Forte", "Agrément préalable"],
            ],
        }},
        {"type": "paragraphe", "texte": (
            "Au vu de ces écarts, la Corée du Sud est retenue comme première cible, "
            "devant le Japon et Taïwan. La Chine reste une zone de second rang : sa "
            "demande est forte, mais son agrément préalable demande dix-huit mois."
        )},
        {"type": "titre_sous_section", "numero": "7.2", "intitule": "Ce que cela implique"},
        {"type": "paragraphe", "texte": (
            "Les trois premières zones représentent 275 millions d'euros de demande "
            "adressable, soit 13 % du marché export. Deux ans suffisent à couvrir les "
            "trois, à raison d'une ouverture par semestre."
        )},
        {"type": "encadre", "encadre": {
            "intitule": "Trois décisions pour 2027",
            "lignes": [
                "Opportunité — la Corée du Sud ouvre sur 7,8/10 au scoring.",
                "Limite — l'enregistrement sanitaire coûte quatre mois.",
                "Décision — déposer le dossier coréen avant juin 2027.",
            ],
        }},
        {"type": "graphique", "graphique": {
            "type_graphique": "barres_horizontales",
            "titre": "Score de priorisation des quatre zones d'export, 2025",
            "donnees_ids": ["score_coree", "score_japon", "score_taiwan", "score_chine"],
        }},
    ],
    "resume": (
        "Le chapitre classe quatre zones d'export par un scoring à six critères et "
        "retient la Corée du Sud en première cible, devant le Japon et Taïwan."
    ),
}


def _relire(payload: dict[str, Any]) -> list[str]:
    """Les motifs des classes ajoutées le 27/10/2026, et eux seuls."""
    return [
        c.motif() for c in relire(document_du_chapitre(payload), Reference())
        if c.classe in CLASSES_NOUVELLES
    ]


def test_un_chapitre_ordinaire_ne_declenche_rien() -> None:
    """La contre-épreuve que le NO-GO du 30/09/2026 réclamait."""
    assert _relire(CHAPITRE_ORDINAIRE) == []


def _dix_decisions(payload: dict[str, Any]) -> None:
    payload["blocs"][6]["encadre"]["intitule"] = "Dix décisions pour 2027"


def _deuxieme_premiere_cible(payload: dict[str, Any]) -> None:
    payload["blocs"][5]["texte"] = (
        "En priorité, c'est le marché de la Chine qu'il faut ouvrir dès 2027."
    )


def _accent_perdu(payload: dict[str, Any]) -> None:
    payload["blocs"][5]["texte"] = (
        "La note precise que les trois zones pèsent 275 millions d'euros."
    )


def _nombre_sans_echelle(payload: dict[str, Any]) -> None:
    payload["blocs"][5]["texte"] = (
        "Les trois zones représentent 275 000 000 de euros de demande adressable."
    )


#: Un défaut à la fois, et chacun est l'un de ceux que la cliente a relevés.
DEFAUTS: dict[str, tuple[Callable[[dict[str, Any]], None], str]] = {
    "dix annoncés pour trois présentés (point 11)": (_dix_decisions, "comptage"),
    "deux premières cibles (point 6)": (_deuxieme_premiere_cible, "decision"),
    "un accent perdu (point 15)": (_accent_perdu, "orthographe"),
    "un nombre sans mot d'échelle (point 15)": (_nombre_sans_echelle, "orthographe"),
}


@pytest.mark.parametrize(("nom", "cas"), DEFAUTS.items(), ids=list(DEFAUTS))
def test_chaque_defaut_parle(nom: str, cas: tuple[Callable[[dict[str, Any]], None], str]) -> None:
    """L'autre moitié : muet sur un vrai défaut, c'est un échec (règle 1)."""
    mutation, classe = cas
    payload = copy.deepcopy(CHAPITRE_ORDINAIRE)
    mutation(payload)
    motifs = _relire(payload)
    assert motifs, f"MUET sur « {nom} »"
    assert any(m.startswith(f"[{classe}]") for m in motifs), motifs
