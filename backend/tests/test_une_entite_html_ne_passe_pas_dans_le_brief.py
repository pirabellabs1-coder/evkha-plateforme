"""Une entité HTML d'une page n'arrive jamais dans le brief de recherche.

30/09/2026, vérification réelle de la recherche sur Claude Haiku 4.5 : un
extrait cité rendait « le prix moyen d&#x27;une coupe femme ». Le brief est
relu par tous les chapitres ; l'entité pouvait finir dans le document.
"""
from __future__ import annotations

from generation.research import _format_result
from integrations.search import SearchResult


def _resultat(titre: str, contenu: str) -> SearchResult:
    return SearchResult(
        title=titre, url="https://www.exemple.fr/a", content=contenu, score=0.0,
        published_date="",
    )


def test_les_entites_sont_decodees() -> None:
    ligne = _format_result(_resultat(
        "Tarifs coiffeur &amp; barbier", "le prix moyen d&#x27;une coupe femme est de 45&nbsp;€",
    ))
    assert "&#x27;" not in ligne and "&amp;" not in ligne and "&nbsp;" not in ligne
    assert "d'une coupe femme" in ligne
    assert "Tarifs coiffeur & barbier" in ligne


def test_un_texte_propre_reste_intact() -> None:
    """Contre-épreuve."""
    ligne = _format_result(_resultat("Marché", "Le marché pèse 6,3 milliards d'euros."))
    assert "Le marché pèse 6,3 milliards d'euros." in ligne
