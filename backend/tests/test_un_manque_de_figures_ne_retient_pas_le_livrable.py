"""Le deuxième verrou de livraison, et pourquoi il ne s'ouvre qu'à moitié.

## Le défaut, mesuré

Étude de concurrence `c7c6ba96`, 17/08/2026 :

    Livrable retenu à la vérification : 14 figures dans le document, pour
    un plancher de 17 (17 à 25 attendues). Le socle n'a pas pu en
    alimenter davantage.

Dix chapitres écrits, 2,42 € payés, PDF et Word assemblés et prêts — retenus
pour trois figures manquantes. Dans le même dossier, un autre incident disait
pourtant : « Gate qualité : 6 point(s) non résolu(s), document livré quand
même ».

Le 13/08/2026 la cliente avait tranché : « l'envoi du document doit être auto
et sans aucune action de ma part ». Un verrou avait été ouvert ce jour-là. Il
y en avait deux, et personne ne l'a vu jusqu'à ce qu'elle le découvre sur son
tableau de bord.

## Pourquoi le verrou ne s'ouvre PAS entièrement

La même vérification protège deux choses qui n'ont rien à voir :

- un document **amputé** — compte de résultat vide, lignes de tableau
  perdues, prose disparue au rendu. C'est la règle 3 du dépôt, et elle a
  coûté un vrai document à la cliente : elle a reçu `<tbody></tbody>` à la
  place de son compte de résultat ;
- un document simplement **pauvre en figures**.

Le premier ne doit jamais partir : un livrable mutilé est pire que pas de
livrable. Le second doit partir : quatorze figures au lieu de dix-sept, cela
se voit et se corrige, cela ne justifie pas de retenir un document payé.

Ce fichier verrouille les deux moitiés. Sans la seconde, « débloquer la
livraison » se serait traduit par l'envoi de documents amputés — et le remède
aurait été pire que le mal.
"""
from __future__ import annotations

import pytest

from delivery.services import _seulement_un_manque_de_figures

FIGURES = [
    pytest.param(
        "14 figures dans le document, pour un plancher de 17 "
        "(17 à 25 attendues). Le socle n'a pas pu en alimenter davantage.",
        id="le-motif-exact-de-c7c6ba96",
    ),
    pytest.param(
        "9 figures dans le document, pour un plancher de 12.",
        id="la-forme-courte",
    ),
]

AMPUTATIONS = [
    pytest.param("tableau du compte de résultat vide", id="compte-de-resultat-vide"),
    pytest.param("aucun tableau dans le document", id="aucun-tableau"),
    pytest.param("document sans prose", id="sans-prose"),
    pytest.param("vérification non exécutée", id="controle-non-execute"),
    pytest.param(
        "tableau du compte de résultat vide | 14 figures dans le document, "
        "pour un plancher de 17",
        id="amputation-ET-figures-le-pire-l-emporte",
    ),
]


@pytest.mark.parametrize("motif", FIGURES)
def test_un_manque_de_figures_laisse_partir_le_document(motif: str) -> None:
    assert _seulement_un_manque_de_figures(motif), (
        f"« {motif} » ne justifie pas de retenir un livrable payé"
    )


@pytest.mark.parametrize("motif", AMPUTATIONS)
def test_un_document_ampute_reste_retenu(motif: str) -> None:
    """La moitié qui compte le plus : ouvrir trop grand serait pire.

    Le dernier cas est le plus important — quand une amputation ACCOMPAGNE un
    manque de figures, c'est l'amputation qui décide.
    """
    assert not _seulement_un_manque_de_figures(motif), (
        f"« {motif} » décrit un document mutilé : il ne part pas"
    )
