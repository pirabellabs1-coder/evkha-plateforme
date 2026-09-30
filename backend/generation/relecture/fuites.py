"""Fuites internes et renvois de figures (classe 7).

Le vocabulaire de la chaîne dans le texte final, une phrase brute de la
mémoire collée telle quelle ; un renvoi « Figure présentée au chapitre X »
hors sujet.
"""
from __future__ import annotations

from .constat import Constat, Reference
from .document import Document


def controler(document: Document, reference: Reference) -> list[Constat]:
    return []
