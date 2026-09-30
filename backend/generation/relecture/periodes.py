"""Unités et périodes des faits (classe 1).

Un fait mensuel employé là où un fait annuel est attendu, et inversement ; une
dérivation (÷ 12, × 12) refaite hors du code. Exemple : un revenu mensuel
réutilisé comme annuel puis redivisé par douze.
"""
from __future__ import annotations

from .constat import Constat, Reference
from .document import Document


def controler(document: Document, reference: Reference) -> list[Constat]:
    return []
