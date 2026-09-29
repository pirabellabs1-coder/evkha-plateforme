"""Les repères `{{identifiant}}` : le rédacteur cite un fait, le code écrit sa valeur.

## Pourquoi

Le modèle ne se trompe pas en recopiant un identifiant ; il se trompe en
recopiant — ou en refaisant — un nombre. Les figures le prouvent depuis le
10/08/2026 : elles citent des identifiants du socle, le code pose les valeurs,
et aucune figure n'a jamais porté un chiffre divergent du socle. Ce module
étend ce mécanisme à la prose et aux tableaux.

## Le format, une seule fois

La valeur s'écrit par `montant_lisible` / `nombre_francais`, les formateurs
déjà utilisés par l'annexe et les figures (règle 5) : virgule décimale, espaces
de milliers, « M€ », « 8 % ». Un montant garde au plus deux décimales, un
pourcentage une.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from generation.socle.schema import montant_lisible, nombre_francais

from .faits import Fait

#: `{{resultat_net_an3}}`, espaces tolérées. Identifiant du référentiel ou
#: dérivé : minuscules, chiffres, soulignés.
REPERE = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")


def valeur_affichee(fait: Fait) -> str:
    """La valeur d'un fait telle que le lecteur la lit."""
    if fait.unite == "%":
        return f"{nombre_francais(round(fait.valeur, 1))}\u00a0%"
    valeur = round(fait.valeur, 2)
    return montant_lisible(valeur, fait.unite)


@dataclass
class Rendu:
    """Un texte dont les repères ont été remplacés, et ce qu'il en reste."""

    texte: str
    #: Les identifiants cités et connus, dans l'ordre d'apparition.
    utilises: list[str] = field(default_factory=list)
    #: Les identifiants cités mais inconnus : laissés tels quels, pour que le
    #: contrôle du chapitre les voie et les fasse corriger.
    inconnus: list[str] = field(default_factory=list)


def remplacer_les_reperes(texte: str, faits: Mapping[str, Fait]) -> Rendu:
    """Remplace chaque `{{identifiant}}` connu par sa valeur affichée."""
    rendu = Rendu(texte="")

    def _remplacer(trouve: re.Match[str]) -> str:
        identifiant = trouve.group(1)
        fait = faits.get(identifiant)
        if fait is None:
            rendu.inconnus.append(identifiant)
            return trouve.group(0)
        rendu.utilises.append(identifiant)
        return valeur_affichee(fait)

    rendu.texte = REPERE.sub(_remplacer, texte or "")
    return rendu


def reperes_cites(texte: str) -> list[str]:
    """Les identifiants cités par un texte, sans rien remplacer."""
    return REPERE.findall(texte or "")
