"""Comptages, dénombrements et décisions contradictoires (classe 6).

« N sur M », « N formats », « N familles » vérifiés contre la mémoire ou le
tableau voisin ; une même décision (date, seuil, statut) écrite de deux
façons.
"""
from __future__ import annotations

from .constat import Constat, Reference
from .document import Document


def controler(document: Document, reference: Reference) -> list[Constat]:
    return []
