"""Sources (classe 9).

Sources citées et listées ; une même donnée sourcée formulée de deux façons ;
un blog ou une newsletter qui porte un chiffre de marché ; les articles de
loi.
"""
from __future__ import annotations

from .constat import Constat, Reference
from .document import Document


def controler(document: Document, reference: Reference) -> list[Constat]:
    return []
