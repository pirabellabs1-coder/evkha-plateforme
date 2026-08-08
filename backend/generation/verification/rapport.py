"""Rapport de contrôle du livrable (lot 4).

Trois niveaux, et la frontière entre eux compte autant que les contrôles
eux-mêmes.

- **Bloquante** : le document ne doit pas partir. Réservé à ce qui se juge sans
  ambiguïté — un chapitre absent, un tableau vide, une hiérarchie de marché
  inversée. Y mettre un contrôle incertain reviendrait à bloquer des livrables
  corrects, et la barrière finirait débrayée.
- **Avertissement** : quelque chose mérite un œil humain, sans certitude.
- **Information** : mesuré, tracé, sans jugement.

Un contrôle qui n'a rien à comparer produit une anomalie **bloquante**, jamais
un silence : c'est la première règle du dépôt, née d'une barrière qui rendait
`passed: True` sur des documents truffés d'incohérences.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Gravite(StrEnum):
    BLOQUANTE = "bloquante"
    AVERTISSEMENT = "avertissement"
    INFORMATION = "information"


@dataclass(frozen=True)
class Anomalie:
    """Un constat, formulé pour être retrouvé dans le document par un lecteur."""

    controle: str
    gravite: Gravite
    detail: str
    chapitre: int | None = None
    extrait: str = ""
    """Fragment exact du document. Sans lui, un motif n'est pas vérifiable."""

    def en_dict(self) -> dict[str, Any]:
        return {
            "controle": self.controle,
            "gravite": str(self.gravite),
            "detail": self.detail,
            "chapitre": self.chapitre,
            "extrait": self.extrait,
        }


@dataclass
class RapportControle:
    """Résultat de la passe. `mesures` sert au suivi, pas au jugement."""

    anomalies: list[Anomalie] = field(default_factory=list)
    mesures: dict[str, Any] = field(default_factory=dict)
    controles_executes: list[str] = field(default_factory=list)

    def ajouter(self, *anomalies: Anomalie) -> None:
        self.anomalies.extend(anomalies)

    def par_gravite(self, gravite: Gravite) -> list[Anomalie]:
        return [a for a in self.anomalies if a.gravite is gravite]

    @property
    def bloquantes(self) -> list[Anomalie]:
        return self.par_gravite(Gravite.BLOQUANTE)

    @property
    def livrable(self) -> bool:
        """Le document peut-il partir au client ?"""
        return not self.bloquantes

    def resume(self) -> str:
        if not self.anomalies:
            return f"{len(self.controles_executes)} contrôles, aucune anomalie."
        compte = {
            gravite: len(self.par_gravite(gravite))
            for gravite in Gravite
            if self.par_gravite(gravite)
        }
        detail = ", ".join(f"{nombre} {gravite}" for gravite, nombre in compte.items())
        return f"{len(self.controles_executes)} contrôles, {detail}."

    def en_dict(self) -> dict[str, Any]:
        return {
            "livrable": self.livrable,
            "controles": list(self.controles_executes),
            "mesures": dict(self.mesures),
            "anomalies": [anomalie.en_dict() for anomalie in self.anomalies],
        }
