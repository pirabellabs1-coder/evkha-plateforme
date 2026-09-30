"""Relecture du texte final : ce que le lecteur lit, contrôlé en code.

30/09/2026 — business plan ÉCLORE `28a257bf` : nette amélioration, mais onze
classes d'erreurs passaient encore (unités et périodes, définitions contre
calculs, formules en toutes lettres, faits par année, tableaux qui ne bouclent
pas, comptages, fuites internes, graphiques, sources, mise en page, analyse de
sensibilité). Chaque classe a son contrôle, déterministe, sans appel au
modèle.

Deux usages, un seul jeu de contrôles :
- avant rendu, sur chaque chapitre (`document_du_chapitre`) : un constat GRAVE
  fait reprendre le chapitre avec son motif — c'est la correction ; au
  dernier essai, le chapitre est gardé (l'étude ne s'arrête jamais) ;
- après rendu, sur le PDF (`document_du_pdf`) : ce qui reste est consigné au
  dossier et signalé en interne, jamais bloquant pour le client.
"""
from __future__ import annotations

from .constat import Constat, Reference, relire
from .document import Document, Section, Tableau, document_du_chapitre, document_du_pdf

__all__ = [
    "Constat",
    "Document",
    "Reference",
    "Section",
    "Tableau",
    "document_du_chapitre",
    "document_du_pdf",
    "relire",
]
