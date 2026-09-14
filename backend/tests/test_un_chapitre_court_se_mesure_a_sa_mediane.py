"""Le motif d'un chapitre trop court dit la référence qui l'a jugé.

## Le défaut mesuré

Étude de concurrence `5892daa5`, corpus du 15/09/2026 :

    Chapitre 3 (Approfondissement stratégique) : 644 mots pour un plafond de
    671 (soit 96%). Contenu indigent — le chapitre a ete declare fini alors
    qu'il n'a pas ete produit.

671 n'est pas un plafond : c'est le PLANCHER, 40 % de la médiane des chapitres
du document. Un lecteur lisait « 96 % du plafond » et « non produit » sur un
chapitre de 644 mots — deux affirmations fausses dans un seul motif, qui ne
pouvait ni se vérifier ni se corriger (règle 2).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from generation.gate import _check_chapitres_avortes
from generation.rendering import RenderedSection


def _section(numero: int, mots: int) -> RenderedSection:
    return RenderedSection(
        number=numero, title=f"Chapitre {numero}", kind="chapter",
        body=" ".join(["analyse"] * mots),
    )


def _motifs(longueurs: dict[int, int]) -> list[str]:
    job: Any = SimpleNamespace(deliverable_type="competitor_study")
    sections = tuple(_section(n, mots) for n, mots in longueurs.items())
    return [f.detail for f in _check_chapitres_avortes(job, sections)]


def test_le_motif_nomme_le_plancher_et_la_mediane() -> None:
    motifs = _motifs({1: 1500, 2: 1500, 3: 500, 4: 1500, 5: 1500, 6: 1500, 7: 1500})

    assert len(motifs) == 1
    assert "plafond" not in motifs[0]
    assert "non produit" not in motifs[0] and "n'a pas ete produit" not in motifs[0]
    assert "500 mots, sous le plancher de 600" in motifs[0]
    assert "40 % de la médiane des chapitres de ce document (1500 mots)" in motifs[0]


def test_un_chapitre_au_niveau_de_ses_voisins_ne_produit_aucun_motif() -> None:
    """CONTRE-ÉPREUVE : la reformulation ne change pas ce qui est jugé."""
    assert _motifs({1: 1500, 2: 1500, 3: 700, 4: 1500, 5: 1500, 6: 1500, 7: 1500}) == []
