"""Définitions contre calculs (classe 2), faits par année (classe 4).

Business plan ÉCLORE `28a257bf` (30/09/2026) :
- 16.3 définit le revenu de la dirigeante comme le chiffre d'affaires diminué
  des charges décaissées et des cotisations — puis le calcule avec la CAF
  divisée par douze ;
- le seuil de rentabilité de 2027 est appliqué à 2028 et 2029 (17.3), et les
  marges de sécurité de 2028 et 2029 sont calculées sur lui (9.3, 15.6, 15.7,
  21.6).
Un indicateur se calcule selon sa définition ; un fait daté ne sert qu'à son
exercice.
"""
from __future__ import annotations

import re

from .constat import Constat, Reference
from .document import Document
from .valeurs import en_euros, fait_de, faits_de_la_serie, phrases_de, valeurs_datees

#: Les calculs qu'une définition interdit : (ce qui est calculé, la base
#: interdite, le signe d'un calcul fait sur cette base, ce qui l'excuse,
#: ce qu'il faut écrire à la place).
_DEFINITIONS_FAUSSES: tuple[
    tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str], re.Pattern[str], str], ...
] = (
    (
        re.compile(r"(?i)\brevenu"),
        re.compile(r"(?i)capacit[ée] d.autofinancement|\bCAF\b"),
        re.compile(r"(?i)divis|÷|/ ?12|\bdouze\b|\bpart de\b|\bdonne\b|× ?12|="),
        # « il n'est ni le chiffre d'affaires, ni la CAF » : une définition juste.
        re.compile(r"(?i)\b(ni|pas|non)\b[^.;]{0,25}(la |sa )?(CAF|capacit)"),
        "le revenu n'est pas la CAF : en micro-entreprise, c'est le chiffre d'affaires "
        "diminué des charges réellement décaissées et des cotisations sociales. Cite le "
        "repère du résultat voulu, ou retire le calcul.",
    ),
    (
        re.compile(r"(?i)r[ée]sultat net"),
        re.compile(r"(?i)(exc[ée]dent brut|\bEBE\b).{0,80}dotations"),
        re.compile(r"(?i)\bdiminu|\bmoins\b|\bretranch|−|\bdonne\b|="),
        re.compile(
            r"(?i)imp[ôo]t|\bIS\b|charges financi|int[ée]r[êe]ts|cotisations|exceptionnel|"
            r"\b(ni|pas|non)\b[^.;]{0,25}r[ée]sultat net"
        ),
        "l'EBE diminué des dotations est le résultat d'EXPLOITATION ; le résultat net "
        "retire encore les charges financières, les cotisations ou l'impôt. Cite le repère "
        "du résultat net ({{resultat_net_anN}}).",
    ),
)


def _definitions(document: Document) -> list[Constat]:
    constats: list[Constat] = []
    for section in document.sections:
        for phrase in phrases_de(section):
            for calcule, base, calcul, excuse, consigne in _DEFINITIONS_FAUSSES:
                if not (calcule.search(phrase) and base.search(phrase)):
                    continue
                if not calcul.search(phrase) or excuse.search(phrase):
                    continue
                constats.append(Constat(
                    "definition", section.numero, phrase[:220],
                    f"Calcul contraire à la définition : {consigne}",
                ))
    return constats


#: Les séries calculées PAR EXERCICE par la mémoire : un chiffre d'un
#: exercice n'y vaut jamais pour un autre.
_SERIES_PAR_EXERCICE = {
    "seuil_rentabilite": "le seuil de rentabilité",
    "marge_securite": "la marge de sécurité",
}


def _faits_par_annee(document: Document, reference: Reference) -> list[Constat]:
    memoire = reference.memoire
    constats: list[Constat] = []
    for valeur in valeurs_datees(document):
        nom = _SERIES_PAR_EXERCICE.get(valeur.serie)
        if nom is None:
            continue
        fait = fait_de(memoire, valeur.serie, valeur.annee)
        if fait is None:
            continue
        attendu = en_euros(fait) if not valeur.nombre.pourcentage else fait.valeur
        if attendu is None:
            continue
        tolerance = 0.15 if valeur.nombre.pourcentage else attendu * 0.005 + 1
        if abs(valeur.nombre.valeur - attendu) <= tolerance:
            continue
        autre = next(
            (
                f for f in faits_de_la_serie(memoire, valeur.serie)
                if f.annee != valeur.annee and abs(
                    valeur.nombre.valeur
                    - ((en_euros(f) or 0.0) if not valeur.nombre.pourcentage else f.valeur)
                ) <= tolerance
            ),
            None,
        )
        origine = (
            f"c'est celui de {autre.annee}, qui ne vaut que pour son exercice"
            if autre is not None else
            f"il n'a pas été calculé sur l'exercice {valeur.annee}"
        )
        constats.append(Constat(
            "fait_par_annee", valeur.section, valeur.passage[:220],
            f"{nom[0].upper()}{nom[1:]} {valeur.annee} écrit « {valeur.nombre.ecriture} » : "
            f"{origine}. La mémoire le calcule exercice par exercice : cite "
            f"{{{{{fait.id}}}}}.",
        ))
    return constats


def controler(document: Document, reference: Reference) -> list[Constat]:
    return [*_definitions(document), *_faits_par_annee(document, reference)]
