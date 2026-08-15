"""Quand le document POSE une opération, le code la refait.

## Le défaut, mesuré sur un business plan livré

13/08/2026, relevé par la cliente : « le document écrit 50 000 milliers de
cibles, puis interprète cela comme 50 000 000, et calcule
102 / 50 000 000 = 0,000204 % ». Douze fois dans le même document.

Le premier défaut — l'unité — est réparé à la source. Restait le second,
plus profond : **personne ne refaisait la division**. Le rédacteur pose une
opération, écrit son résultat, et rien ne vérifie que le résultat découle des
termes. Sa demande, mot pour mot : « vérifier automatiquement tous les calculs
simples : pourcentages, ratios, taux de conversion, marges, évolutions, parts
de marché, additions, moyennes et projections ».

## Ce que ce module vérifie, et pourquoi seulement cela

Il ne relit que les opérations **explicites** : celles où le texte donne les
DEUX termes ET le résultat. « 102 sur 50 000, soit 0,2 % » se vérifie ; « la
part de marché atteint 0,2 % » ne se vérifie pas — il n'y a rien à recouper,
et l'inventer serait pire que de s'abstenir.

C'est la limite honnête de l'exercice, et elle est assumée : un contrôle qui
devinerait les termes manquants produirait des motifs faux, et ce projet a
mesuré ce que coûte un contrôle qui crie faux — des réécritures payantes sur
des défauts inexistants.

## La tolérance

Un pour cent en relatif. Un document arrondit ses pourcentages — « 0,204 % »
s'écrit « 0,2 % » — et exiger l'égalité exacte produirait du bruit sur chaque
phrase correcte. Au-delà, ce n'est plus un arrondi : c'est une autre opération.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

#: Écart relatif toléré entre le résultat écrit et le résultat recalculé.
TOLERANCE = 0.01

#: Un nombre français : « 50 000 », « 1 250,5 », « 0,204 ».
#: Les espaces fines et insécables comptent comme séparateurs de milliers.
_NOMBRE = r"\d[\d    ]*(?:[.,]\d+)?"


def _valeur(texte: str) -> float | None:
    """« 50 000 » → 50000.0. None si ce n'est pas un nombre lisible."""
    nu = re.sub(r"[    ]", "", texte).replace(",", ".")
    try:
        return float(nu)
    except ValueError:
        return None


#: « 102 sur 50 000, soit 0,2 % » — la forme qui a produit le défaut.
#:
#: `sur` et `/` sont les deux écritures d'une même division. Le résultat suit,
#: introduit par « soit », « = » ou « c'est-à-dire ».
_POURCENTAGE = re.compile(
    rf"(?P<num>{_NOMBRE})\s*(?:sur|/)\s*(?P<den>{_NOMBRE})\s*"
    rf"(?:,\s*)?(?:soit|=|c'est-à-dire|c'est à dire)\s*"
    rf"(?P<res>{_NOMBRE})\s*%",
    re.IGNORECASE,
)

#: « 12 % de 50 000, soit 6 000 » — le pourcentage appliqué.
_PART_DE = re.compile(
    rf"(?P<taux>{_NOMBRE})\s*%\s*(?:de|des|du)\s*(?P<base>{_NOMBRE})\s*"
    rf"(?:,\s*)?(?:soit|=|c'est-à-dire|c'est à dire)\s*"
    rf"(?P<res>{_NOMBRE})",
    re.IGNORECASE,
)

#: « de 40 000 à 50 000, soit une hausse de 25 % » — l'évolution.
_EVOLUTION = re.compile(
    rf"de\s*(?P<avant>{_NOMBRE})\s*(?:€|euros?|k€|M€)?\s*à\s*"
    rf"(?P<apres>{_NOMBRE})\s*(?:€|euros?|k€|M€)?\s*"
    rf"[^.]{{0,40}}?(?:soit|=)\s*(?:une?\s+)?"
    rf"(?:hausse|baisse|progression|croissance|recul|évolution)\s*"
    rf"(?:de\s*)?(?P<res>{_NOMBRE})\s*%",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CalculFaux:
    """Une opération dont le résultat écrit ne découle pas de ses termes."""

    extrait: str
    ecrit: float
    calcule: float
    nature: str

    def __str__(self) -> str:
        return (
            f"{self.nature} : le document écrit « {self.extrait.strip()} », "
            f"mais le calcul donne {self.calcule:,.4g} et non "
            f"{self.ecrit:,.4g}. Un lecteur qui refait l'opération le verra ; "
            "corrige le résultat, ou les termes s'ils sont faux."
        )


def _decimales(texte: str) -> int:
    """Combien de décimales le document a écrites. « 0,2 » → 1, « 6 000 » → 0."""
    partie = re.split(r"[.,]", texte.strip())
    return len(partie[1]) if len(partie) > 1 else 0


def _ecart_trop_grand(ecrit: float, calcule: float, precision: int) -> bool:
    """Faux au-delà de l'ARRONDI QUE LE DOCUMENT A CHOISI.

    Un document qui écrit « 0,2 % » pour 0,204 % ne se trompe pas : il arrondit
    au dixième, et c'est ce qu'un lecteur attend. Comparer en écart relatif
    déclencherait ici — 2 % d'écart — et produirait un motif sur une phrase
    juste. Ce projet a mesuré ce que coûte un contrôle qui crie faux.

    On arrondit donc le résultat CALCULÉ à la précision que le rédacteur a
    retenue, et on compare à ce niveau-là. Reste une tolérance relative pour
    les grands nombres, où le dernier chiffre écrit n'est déjà plus significatif.
    """
    if round(calcule, precision) == round(ecrit, precision):
        return False
    reference = max(abs(calcule), abs(ecrit))
    if reference == 0:
        return False
    return abs(ecrit - calcule) / reference > TOLERANCE


def verifier(texte: str) -> list[CalculFaux]:
    """Toutes les opérations explicites du texte dont le résultat est faux.

    L'ordre des motifs suit celui du texte : un lecteur qui corrige remonte le
    document une seule fois.
    """
    fautes: list[CalculFaux] = []

    for m in _POURCENTAGE.finditer(texte):
        num, den, res = (_valeur(m.group(n)) for n in ("num", "den", "res"))
        if None in (num, den, res) or not den:
            continue
        calcule = num / den * 100.0  # type: ignore[operator]
        if _ecart_trop_grand(res, calcule, _decimales(m.group("res"))):  # type: ignore[arg-type]
            fautes.append(CalculFaux(
                extrait=m.group(0), ecrit=res, calcule=calcule,  # type: ignore[arg-type]
                nature="Pourcentage",
            ))

    for m in _PART_DE.finditer(texte):
        taux, base, res = (_valeur(m.group(n)) for n in ("taux", "base", "res"))
        if None in (taux, base, res):
            continue
        calcule = base * taux / 100.0  # type: ignore[operator]
        if _ecart_trop_grand(res, calcule, _decimales(m.group("res"))):  # type: ignore[arg-type]
            fautes.append(CalculFaux(
                extrait=m.group(0), ecrit=res, calcule=calcule,  # type: ignore[arg-type]
                nature="Part d'un total",
            ))

    for m in _EVOLUTION.finditer(texte):
        avant, apres, res = (_valeur(m.group(n)) for n in ("avant", "apres", "res"))
        if None in (avant, apres, res) or not avant:
            continue
        calcule = abs(apres - avant) / avant * 100.0  # type: ignore[operator]
        if _ecart_trop_grand(res, calcule, _decimales(m.group("res"))):  # type: ignore[arg-type]
            fautes.append(CalculFaux(
                extrait=m.group(0), ecrit=res, calcule=calcule,  # type: ignore[arg-type]
                nature="Évolution",
            ))

    return fautes
