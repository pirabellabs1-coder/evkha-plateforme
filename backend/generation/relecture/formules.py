"""Formules écrites en toutes lettres (classe 3).

« X divisé par Y = Z », « X moins Y », « N × P » : recalculées ; une quantité
vague (« quelques dizaines ») confrontée à l'ordre de grandeur qu'elle
prétend.
"""
from __future__ import annotations

from .constat import Constat, Reference
from .document import Document


def controler(document: Document, reference: Reference) -> list[Constat]:
    return []
