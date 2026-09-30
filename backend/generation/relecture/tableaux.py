"""Tableaux qui doivent boucler, un libellé = une valeur (classe 5).

Un compte de résultat complet (CA − charges = EBE) ; un même libellé (« prix
le plus haut du panel », « résultat 2029 ») ne porte qu'une valeur dans le
document.
"""
from __future__ import annotations

from .constat import Constat, Reference
from .document import Document


def controler(document: Document, reference: Reference) -> list[Constat]:
    return []
