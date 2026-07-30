"""Lecture des prompts depuis des fichiers versionnés.

Exigence du cahier des charges (§6.2) : « Les prompts sortent du code et vivent
dans des fichiers versionnés (`prompts/etude_marche/chapitre_04.md`), avec des
variables interpolées. »

Interpolation volontairement minimale : `{{ nom }}`. Ni boucle, ni condition,
ni appel — un prompt est un texte à trous, pas un programme. Une variable
inconnue est laissée telle quelle ET signalée : la remplacer silencieusement
par une chaîne vide produirait un prompt amputé sans que rien ne le dise.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from .configuration import TypeDocument, type_document

_VARIABLE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

#: Bandeau de documentation en tête de fichier. Destiné au lecteur humain, il
#: ne doit JAMAIS partir dans le prompt : il cite la syntaxe des variables, que
#: l'interpolation prendrait pour de vraies variables — et il coûterait des
#: jetons à chaque appel pour n'apprendre rien au modèle.
_BANDEAU = re.compile(r"\A\s*<!--.*?-->\s*", re.DOTALL)


class PromptIntrouvableError(FileNotFoundError):
    """Aucun fichier de prompt pour ce chapitre."""


def nom_fichier(numero: int) -> str:
    """`4` -> `chapitre_04.md`. Deux chiffres pour que l'ordre alphabétique
    coïncide avec l'ordre des chapitres dans un explorateur de fichiers."""
    return f"chapitre_{numero:02d}.md"


def chemin_prompt(code_document: str, numero: int) -> Path:
    return type_document(code_document).chemin_prompts / nom_fichier(numero)


@lru_cache(maxsize=256)
def _lire(chemin: str) -> str:
    fichier = Path(chemin)
    if not fichier.is_file():
        msg = f"Prompt introuvable : {fichier}"
        raise PromptIntrouvableError(msg)
    return fichier.read_text(encoding="utf-8")


def charger_prompt(code_document: str, numero: int, *, brut: bool = False) -> str:
    """Prompt du chapitre, bandeau de documentation retiré.

    `brut=True` rend le fichier tel quel, bandeau compris — utile aux contrôles
    et aux tests qui vérifient la provenance du fichier.
    """
    contenu = _lire(str(chemin_prompt(code_document, numero)))
    return contenu if brut else _BANDEAU.sub("", contenu)


def variables_attendues(gabarit: str) -> set[str]:
    return set(_VARIABLE.findall(gabarit))


def interpoler(gabarit: str, valeurs: Mapping[str, object]) -> tuple[str, list[str]]:
    """Remplace `{{ nom }}` par sa valeur. Retourne (texte, variables manquantes).

    Les manquantes sont RENDUES à l'appelant, jamais avalées : un prompt à trou
    doit se voir.
    """
    manquantes: list[str] = []

    def _remplacer(correspondance: re.Match[str]) -> str:
        nom = correspondance.group(1)
        if nom not in valeurs:
            manquantes.append(nom)
            return correspondance.group(0)
        return str(valeurs[nom])

    return _VARIABLE.sub(_remplacer, gabarit), manquantes


def rendre_prompt(
    code_document: str, numero: int, valeurs: Mapping[str, object]
) -> tuple[str, list[str]]:
    return interpoler(charger_prompt(code_document, numero), valeurs)


def chapitres_sans_prompt(document: TypeDocument) -> list[int]:
    """Numéros de chapitre déclarés au chapitrage mais sans fichier de prompt.

    Sert au contrôle de complétude : un chapitre sans prompt échouerait en
    plein milieu d'une génération payante. Autant le savoir avant.
    """
    manquants: list[int] = []
    for blueprint in document.chapitres():
        if not (document.chemin_prompts / nom_fichier(blueprint.number)).is_file():
            manquants.append(blueprint.number)
    return manquants


def vider_cache() -> None:
    """Oublie les prompts lus. Utile aux tests et après une modification."""
    _lire.cache_clear()
