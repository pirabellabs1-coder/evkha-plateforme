"""Lire des adresses e-mail : une saisie, ou un texte entier (liste, export).

Une SEULE lecture pour le formulaire public et pour l'ajout par la gérante
(règle 5). La relecture du 26/11/2026 a montré ce que coûte une expression
qui CHERCHE des adresses dans un texte : `élise@exemple.fr` y devenait
`lise@exemple.fr` — une adresse valide, que personne n'a donnée, abonnée sans
confirmation. On DÉCOUPE donc le texte sur ses séparateurs, et chaque morceau
qui porte un `@` est jugé ENTIER : il est une adresse, ou il est rejeté et
montré tel quel. Jamais une sous-chaîne.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

#: Ce qui sépare deux valeurs dans une liste, un CSV, un copier-coller.
_SEPARATEURS = re.compile(r"[\s,;<>\"'()\[\]|]+")

#: Une ligne d'export qui dit que la personne est PARTIE (désinscrite,
#: rebond, opposition) : elle n'est jamais lue comme une adresse à abonner.
#: Les exports de contacts — Systeme.io compris — listent tout le monde,
#: quel que soit son statut.
MARQUEURS_DE_RETRAIT = re.compile(
    r"unsubscrib|d[ée]sinscri|d[ée]sabonn|bounce|rebond|opt[\s_-]?out|"
    r"supprim|blacklist|liste noire|complain|plainte",
    re.IGNORECASE,
)


def adresse_normalisee(brut: object) -> str | None:
    """L'adresse saisie, nettoyée et en minuscules, ou `None` si elle n'en est
    pas une. Minuscules : `Marie@Exemple.fr` et `marie@exemple.fr` sont la
    même personne, et la contrainte d'unicité doit le savoir."""
    if not isinstance(brut, str):
        return None
    adresse = brut.strip().lower()
    if not adresse or len(adresse) > 254:
        return None
    try:
        validate_email(adresse)
    except ValidationError:
        return None
    return adresse


@dataclass
class Lecture:
    valides: list[str] = field(default_factory=list)
    invalides: list[str] = field(default_factory=list)
    #: Lignes portant une adresse ET une marque de retrait : écartées.
    lignes_ecartees: int = 0


def lire_les_adresses(texte: str) -> Lecture:
    """Les adresses d'un texte, ligne par ligne, sans doublon, dans l'ordre."""
    lecture = Lecture()
    vues: dict[str, None] = {}
    for ligne in texte.splitlines():
        morceaux = [m.strip(".:") for m in _SEPARATEURS.split(ligne) if "@" in m]
        if not morceaux:
            continue
        reste = " ".join(m for m in _SEPARATEURS.split(ligne) if "@" not in m)
        if MARQUEURS_DE_RETRAIT.search(reste):
            lecture.lignes_ecartees += 1
            continue
        for morceau in morceaux:
            adresse = adresse_normalisee(morceau)
            if adresse is None:
                lecture.invalides.append(morceau)
            else:
                vues.setdefault(adresse, None)
    lecture.valides = list(vues)
    return lecture


def empreinte(adresse: str) -> str:
    """L'empreinte d'une adresse effacée (`Opposition`) : de quoi reconnaître
    la personne si sa ligne revient dans un import, sans garder l'adresse."""
    return hashlib.sha256(f"evkha-opposition:{adresse}".encode()).hexdigest()
