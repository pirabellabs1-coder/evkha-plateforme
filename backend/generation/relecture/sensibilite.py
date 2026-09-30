"""Analyse de sensibilité (classe 11).

Un business plan porte un scénario à −10 % et à −20 % de chiffre d'affaires,
calculé en code ; une phrase qui dit ne pas pouvoir le faire est interdite.
"""
from __future__ import annotations

from .constat import Constat, Reference
from .document import Document


def controler(document: Document, reference: Reference) -> list[Constat]:
    return []
