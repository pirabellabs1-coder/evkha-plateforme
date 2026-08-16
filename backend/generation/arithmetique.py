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


# ── Une même donnée, une seule source ────────────────────────────────────────

#: « 1,4 M€ (Insee, 2025) » ou « 1,4 M€ — source : Xerfi 2026 ».
#:
#: Le montant PUIS sa source, dans la parenthèse ou après un tiret. C'est la
#: forme que produisent les tableaux et les notes de figure.
_MONTANT_SOURCE = re.compile(
    rf"(?P<montant>{_NOMBRE})\s*(?P<unite>M€|Md€|k€|€|%)\s*"
    rf"(?:\(|—\s*source\s*:\s*|-\s*source\s*:\s*)"
    rf"(?P<source>[^)\n.;]{{3,60}})",
    re.IGNORECASE,
)

#: Ce qui n'est pas une source mais une précision : « (2025) », « (estimation) ».
_PAS_UNE_SOURCE = re.compile(
    r"^\s*(?:\d{4}|estimation|estimé\w*|prévision\w*|hypothèse|projection)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceDivergente:
    """Un même montant attribué à deux sources différentes."""

    montant: str
    sources: tuple[str, ...]

    def __str__(self) -> str:
        liste = " ; ".join(f"« {s} »" for s in self.sources)
        return (
            f"Le montant {self.montant} est attribué à {len(self.sources)} "
            f"sources différentes dans le document : {liste}. Un lecteur qui "
            "vérifie ira à la première et n'y trouvera pas le chiffre. Une "
            "donnée a UNE origine : garde celle qui la porte réellement."
        )


def sources_divergentes(textes: list[str]) -> list[SourceDivergente]:
    """Les montants que le document attribue à plusieurs sources.

    ## Le défaut visé

    Demande de la cliente, 13/08/2026 : « tester les cohérences interchapitres
    toujours niveau chiffres ET sources ». La cohérence des CHIFFRES était
    contrôlée depuis longtemps ; celle des SOURCES ne l'était pas.

    Une même donnée créditée à l'Insee au chapitre 3 et à Xerfi au chapitre 12
    est un défaut plus grave qu'il n'y paraît : le lecteur qui vérifie ira à la
    première, n'y trouvera pas le chiffre, et cessera de croire le reste.

    ## Ce qui n'est pas jugé

    Les parenthèses qui portent une ANNÉE ou une nature — « (2025) »,
    « (estimation) » — ne sont pas des sources. Les compter ferait crier sur
    un montant daté deux fois, ce qui est normal et souhaitable.
    """
    par_montant: dict[str, list[str]] = {}
    for texte in textes:
        for m in _MONTANT_SOURCE.finditer(texte):
            source = " ".join(m.group("source").split()).strip(" ,;")
            if not source or _PAS_UNE_SOURCE.match(source):
                continue
            cle = f"{re.sub(r'[    ]', '', m.group('montant'))} {m.group('unite')}"
            connues = par_montant.setdefault(cle, [])
            if source.casefold() not in {s.casefold() for s in connues}:
                connues.append(source)

    return [
        SourceDivergente(montant=montant, sources=tuple(sources))
        for montant, sources in par_montant.items()
        if len(sources) > 1
    ]


# ── Les tableaux qui annoncent un total ──────────────────────────────────────

#: Une ligne de tableau markdown : « | a | b | c | ».
_LIGNE_TABLEAU = re.compile(r"^\s*\|(?P<cellules>.+)\|\s*$")

#: Une ligne de séparation : « |---|---|ce ».
_SEPARATEUR = re.compile(r"^\s*\|[\s:|-]+\|\s*$")

#: L'intitulé qui ANNONCE une somme. C'est le seul cas vérifiable sans deviner.
_INTITULE_TOTAL = re.compile(r"\btotal\b|\bcumul\b|\bensemble\b", re.IGNORECASE)

#: Un intitulé qui porte DÉJÀ une somme partielle : l'additionner double-compte.
_INTITULE_PARTIEL = re.compile(r"sous[- ]total|\bdont\b|\bsoit\b", re.IGNORECASE)


@dataclass(frozen=True)
class TotalFaux:
    """Une colonne dont le total annoncé ne fait pas la somme de ses lignes."""

    colonne: str
    annonce: float
    somme: float

    def __str__(self) -> str:
        return (
            f"Colonne « {self.colonne} » : le tableau annonce un total de "
            f"{self.annonce:,.2f}, mais ses lignes font {self.somme:,.2f}. "
            "Un lecteur qui additionne la colonne verra l'écart ; corrige le "
            "total, ou la ligne qui manque."
        )


def _cellules(ligne: str) -> list[str]:
    trouve = _LIGNE_TABLEAU.match(ligne)
    return [c.strip() for c in trouve.group("cellules").split("|")] if trouve else []


def totaux_faux(texte: str) -> list[TotalFaux]:
    """Les totaux annoncés qu'un tableau ne vérifie pas.

    ## Ce que ce contrôle vérifie, et pourquoi si peu

    Demande de la cliente, 13/08/2026 : vérifier « les additions » des
    tableaux. Un tableau ne dit PAS lequel de ses nombres est une somme — il
    faudrait le comprendre. Ce contrôle ne juge donc que le cas où le document
    l'ANNONCE lui-même : une ligne intitulée « Total », « Cumul »,
    « Ensemble ».

    Deviner qu'une ligne est un total parce qu'elle est la dernière ferait
    crier sur tous les tableaux qui n'en portent pas — et ce projet a mesuré ce
    que coûte un contrôle qui se trompe : des réécritures payantes sur des
    défauts inexistants.

    ## Les deux pièges évités

    Les lignes qui portent déjà une somme partielle — « sous-total », « dont »,
    « soit » — sont exclues des termes : les additionner double-compterait et
    produirait un motif sur un tableau juste.

    Une colonne dont une seule cellule n'est pas un nombre est ignorée
    entièrement : elle mélange du texte et des chiffres, et sa somme n'a pas de
    sens.
    """
    fautes: list[TotalFaux] = []
    lignes = texte.split("\n")
    debut = 0

    while debut < len(lignes):
        if not _cellules(lignes[debut]):
            debut += 1
            continue
        fin = debut
        while fin < len(lignes) and (_cellules(lignes[fin]) or _SEPARATEUR.match(lignes[fin])):
            fin += 1

        table = [
            _cellules(ligne) for ligne in lignes[debut:fin]
            if _cellules(ligne) and not _SEPARATEUR.match(ligne)
        ]
        debut = fin
        if len(table) < 3:
            continue

        entetes, corps = table[0], table[1:]
        totaux = [r for r in corps if r and _INTITULE_TOTAL.search(r[0])]
        termes = [
            r for r in corps
            if r and not _INTITULE_TOTAL.search(r[0]) and not _INTITULE_PARTIEL.search(r[0])
        ]
        if len(totaux) != 1 or not termes:
            continue
        total = totaux[0]

        for colonne in range(1, min(len(entetes), len(total))):
            annonce = _valeur(re.sub(r"[^\d,.\s ]", "", total[colonne]))
            if annonce is None:
                continue
            valeurs = [
                _valeur(re.sub(r"[^\d,.\s ]", "", r[colonne]))
                for r in termes if colonne < len(r)
            ]
            if not valeurs or any(v is None for v in valeurs):
                continue
            somme = sum(v for v in valeurs if v is not None)
            if _ecart_trop_grand(annonce, somme, _decimales(total[colonne])):
                fautes.append(TotalFaux(
                    colonne=entetes[colonne] or f"colonne {colonne}",
                    annonce=annonce, somme=somme,
                ))

    return fautes
