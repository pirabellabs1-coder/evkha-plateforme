"""Strategies par type de livrable — le « manuel » de chaque generation.

Chaque type de livrable (EM, EC, BP, STR) a sa propre logique metier :
- consignes prompt specifiques,
- concepts financiers surveilles,
- checks post-generation,
- contexte supplementaire a injecter (base chiffree consolidee, faits
  verrouilles, tableau de reference, ...).

Refonte demandee par Tobias (retour Evangeline WAOME v1, 21/07/2026) : le
socle commun bricole des specificites eparpillees dans plusieurs fichiers
(`prompts.py`, `coherence.py`, `checks_evangeline.py`, `gate.py`). C'est
opaque et cree des angles morts (16 % de 3,6 Md€ = 576 M€, pas 2,1 Md€ —
aucun check arithmetique). Ici chaque livrable est un module autonome.

Architecture progressive : on n'a PAS deplace tout le code d'un coup. Cette
premiere iteration expose le pattern (`get_strategy`) et l'utilise pour la
premiere piece manquante : la base chiffree consolidee EM. Les prochaines
sessions migreront le reste (concepts, prompts, checks) depuis les fichiers
existants vers les modules par livrable.
"""
from __future__ import annotations

from .base import LivrableStrategy, get_strategy

__all__ = ["LivrableStrategy", "get_strategy"]
