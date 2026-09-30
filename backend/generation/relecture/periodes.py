"""Unités et périodes des faits (classe 1).

Un fait mensuel employé là où un fait annuel est attendu, et inversement ; une
dérivation (÷ 12, × 12) refaite hors du code.

Business plan ÉCLORE `28a257bf` (30/09/2026) : la « moyenne mensuelle » de la
CAF (55 €, 721 €, 1 986 €) est présentée comme un revenu ANNUEL, puis
redivisée par douze pour donner un revenu « mensuel » de 4,58 €, 60,08 € et
165,5 € — dans cinq sections. Aucun de ces nombres n'est dans la mémoire :
chacun est un fait annuel divisé deux fois par douze, ou divisé une fois et
présenté comme annuel.

Seuls les flux DÉCLARÉS de l'exercice servent de base, et seulement là où le
texte parle de revenu ou de période : un prix de 94 € peut tomber, par
hasard, sur un chiffre calculé divisé par 144 — ce n'est pas une période.
"""
from __future__ import annotations

import re
from collections.abc import Iterator

from ..memoire.faits import Fait
from .constat import Constat, Reference
from .document import Document, Section
from .valeurs import Nombre, en_euros, extrait, nombres, phrases, proche, valeurs_des_faits

_ANNUEL = re.compile(r"(?i)\bannuel|\bpar an\b|sur l.ann[ée]e|/ ?an\b")
_MENSUEL = re.compile(r"(?i)\bmensuel|\bpar mois\b|/ ?mois\b")
#: Là où une confusion de période est possible : un revenu, une rémunération.
_REVENU = re.compile(r"(?i)revenu|r[ée]mun[ée]ration|salaire|pr[ée]l[èe]vement")
#: Un prix n'est jamais une période divisée : « ateliers à 100 € » (revue du
#: 30/09/2026 — une rémunération de 14 400 €/an tombe sur 100 € ÷ 144).
#: Un prix unitaire s'écrit « 20 ateliers à 100 € » ou « à 100 € l'atelier » —
#: jamais « le revenu ressort à 100 € », qui est un montant, pas un prix.
_PRIX = re.compile(
    r"(?i)\bprix\b|\btarif|s[ée]ance|abonnement|par personne|par participant|panier"
    # « 12 ateliers à 110 € » : un compte de choses, puis leur prix — pas
    # « de 12 000 à 14 000 € », où le mot entre les deux est un nombre.
    r"|\d\s+[^\W\d_]+(?:\s+[^\W\d_]+)?\s+à\s+\d"
    # « à 110 € l'atelier », pas « à 110 € la première année ».
    r"|\bà\s+\d[\d\s\u00a0\u202f,]*€\s*(?:(?:l['’]|la |le )"
    r"(?!premi|derni|deuxi|second|troisi|ann[ée]e|mois|semaine|p[ée]riode|fin\b|d[ée]but)"
    r"|pi[èe]ce|unit)"
)


def _flux_declares(faits: list[Fait]) -> list[tuple[Fait, float]]:
    return [
        (f, v) for f in faits
        if f.periode == "an" and f.origine != "calculee" and (v := en_euros(f)) and v > 0
    ]


def _nom(fait: Fait) -> str:
    nom = fait.libelle.split(",")[0].split(" —")[0].strip() or fait.id
    return f"{nom} {fait.annee}" if fait.annee and str(fait.annee) not in nom else nom


def _le_plus_proche(
    valeur: float, candidats: list[tuple[Fait, float]], diviseur: float, relatif: float,
) -> Fait | None:
    ecarts = [
        (abs(valeur - v / diviseur) / (v / diviseur), f) for f, v in candidats
        if proche(valeur, v / diviseur, relatif=relatif, absolu=0.02)
    ]
    return min(ecarts, key=lambda e: e[0])[1] if ecarts else None


def _textes(section: Section) -> Iterator[tuple[str, str]]:
    """(texte, contexte) : la phrase, ou la cellule avec son en-tête et sa ligne."""
    for paragraphe in section.paragraphes:
        for phrase in phrases(paragraphe):
            yield phrase, phrase
    for tableau in section.tableaux:
        lignes = list(tableau.lignes) or [tableau.entetes]
        for ligne in lignes:
            for j, cellule in enumerate(ligne):
                entete = tableau.entetes[j] if j < len(tableau.entetes) and tableau.lignes else ""
                yield cellule, f"{entete} {ligne[0]} {cellule}"


def _redivise(
    n: Nombre, texte: str, contexte: str, flux: list[tuple[Fait, float]], connus: list[float],
    section: str,
) -> Constat | None:
    # Un revenu ET une période mensuelle, sans prix : la seule lecture où
    # « fait annuel ÷ 144 » n'est pas une coïncidence.
    if not n.monetaire or n.valeur <= 0:
        return None
    if not (_REVENU.search(contexte) and _MENSUEL.search(contexte)) or _PRIX.search(contexte):
        return None
    if any(proche(n.valeur, v, relatif=0.005) for v in connus):
        return None
    fait = _le_plus_proche(n.valeur, flux, 144, 0.01)
    if fait is None:
        return None
    return Constat(
        "periode", section, extrait(texte, n.debut, n.fin),
        f"« {n.ecriture} » est {_nom(fait)} divisé DEUX fois par douze : un montant déjà "
        f"mensuel a été redivisé. Cite le repère mensuel ou annuel voulu (l'exercice : "
        f"{{{{{fait.id}}}}}) ; toute conversion se fait en code, une seule fois.",
    )


def controler(document: Document, reference: Reference) -> list[Constat]:
    memoire = reference.memoire
    if memoire is None:
        return []
    faits = list(memoire.faits.values())
    flux = _flux_declares(faits)
    connus = valeurs_des_faits(faits)
    constats: list[Constat] = []
    for section in document.sections:
        for texte, contexte in _textes(section):
            for n in nombres(texte):
                redivise = _redivise(n, texte, contexte, flux, connus, section.numero)
                if redivise is not None:
                    constats.append(redivise)
        # Un montant mensuel sous un libellé annuel, et inversement.
        for tableau in section.tableaux:
            for ligne in tableau.lignes:
                for j, cellule in enumerate(ligne[1:], start=1):
                    entete = tableau.entetes[j] if j < len(tableau.entetes) else ""
                    contexte = f"{ligne[0]} {entete}"
                    annuel = bool(_ANNUEL.search(contexte)) and not _MENSUEL.search(contexte)
                    mensuel = bool(_MENSUEL.search(contexte)) and not _ANNUEL.search(contexte)
                    if not (annuel or mensuel) or not _REVENU.search(contexte):
                        continue
                    for n in nombres(cellule):
                        if not n.monetaire or n.valeur <= 0:
                            continue
                        if annuel and not any(proche(n.valeur, v) for _, v in flux):
                            fait = _le_plus_proche(n.valeur, flux, 12, 0.01)
                            if fait is not None:
                                constats.append(Constat(
                                    "periode", section.numero, f"{contexte.strip()} · {cellule}",
                                    f"« {n.ecriture} » est présenté comme annuel, mais c'est "
                                    f"{_nom(fait)} divisé par douze — un montant MENSUEL. Le "
                                    f"montant annuel de l'exercice est {{{{{fait.id}}}}}.",
                                ))
                        if mensuel and not any(proche(n.valeur, v / 12) for _, v in flux):
                            fait = _le_plus_proche(n.valeur, flux, 1, 0.005)
                            if fait is not None:
                                constats.append(Constat(
                                    "periode", section.numero, f"{contexte.strip()} · {cellule}",
                                    f"« {n.ecriture} » est présenté comme mensuel, mais c'est "
                                    f"{_nom(fait)} — un montant ANNUEL. Cite le repère mensuel "
                                    "calculé par la mémoire, ou écris « par an ».",
                                ))
    return constats
