"""Définitions contre calculs, faits par année (classes 2 et 4).

Un indicateur défini d'une façon et calculé d'une autre (le revenu d'une
micro-entreprise calculé sur la CAF) ; un fait daté réutilisé pour une autre
année (le seuil de rentabilité d'un exercice appliqué aux suivants).
"""
from __future__ import annotations

from .constat import Constat, Reference
from .document import Document


def controler(document: Document, reference: Reference) -> list[Constat]:
    return []
