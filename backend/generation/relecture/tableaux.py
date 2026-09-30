"""Tableaux qui doivent boucler, un libellé = une valeur (classe 5).

Business plan ÉCLORE `28a257bf` (30/09/2026) :
- le compte de résultat de 16.2 montre 24 852 € de chiffre d'affaires, 4 785 €
  de charges et 782 € d'EBE : 24 852 − 4 785 ≠ 782, il manque des lignes ;
- « résultat 2029 » vaut 23 836 € en 4.3 (c'est la CAF) et 23 224 € en 8.1 ;
- « prix le plus haut du panel » vaut 3 890 € en 5.3 et 2 790 € en 7.4.
Un compte de résultat se lit ligne à ligne : il boucle, ou il ne se montre
pas. Un même libellé ne porte qu'une valeur dans tout le document.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .constat import Constat, Reference
from .document import Document, Section, Tableau
from .valeurs import (
    en_euros,
    fait_de,
    nombres,
    phrases_de,
    proche,
    serie_nommee,
    valeurs_datees,
)


def _euros(montant: float) -> str:
    return f"{montant:,.0f} €".replace(",", " ")


# ── Le compte de résultat boucle ────────────────────────────────────────────

_CHARGES = re.compile(
    r"(?i)charges|achats|cotisations|salaires|loyers|sous-traitance|frais|d[ée]penses"
)


def _montant(cellule: str) -> float | None:
    lus = [n for n in nombres(cellule) if n.monetaire]
    return lus[0].valeur if lus else None


def _boucle(tableau: Tableau, section: Section) -> Constat | None:
    annees = [
        (j, m.group(0)) for j, e in enumerate(tableau.entetes)
        if (m := re.search(r"\b20[2-6]\d\b", e))
    ]
    if not annees:
        return None
    lignes = {i: ligne for i, ligne in enumerate(tableau.lignes) if ligne}
    series = {i: serie_nommee(ligne[0], "€") for i, ligne in lignes.items()}
    ca = next((i for i, s in series.items() if s == "ca_previsionnel"), None)
    ebe = next((i for i, s in series.items() if s == "ebe"), None)
    if ca is None or ebe is None or ebe < ca:
        return None
    charges = [
        i for i, ligne in lignes.items()
        if ca < i < ebe and _CHARGES.search(ligne[0])
        and not re.search(r"(?i)dotation", ligne[0])
    ]
    if not charges:
        return None
    for j, annee in annees:
        cellules = [lignes[i][j] if j < len(lignes[i]) else "" for i in (ca, ebe, *charges)]
        valeurs = [_montant(c) for c in cellules]
        if any(v is None for v in valeurs):
            continue
        chiffre, excedent, *depenses = (v for v in valeurs if v is not None)
        attendu = chiffre - sum(depenses)
        if proche(attendu, excedent, relatif=0.01, absolu=2):
            continue
        detail = " − ".join(_euros(v) for v in (chiffre, *depenses))
        return Constat(
            "tableau", section.numero,
            f"{tableau.lignes[ca][0]} {_euros(chiffre)} · {tableau.lignes[ebe][0]} "
            f"{_euros(excedent)}",
            f"Le compte de résultat ne boucle pas en {annee} : {detail} = "
            f"{_euros(attendu)}, mais l'EBE affiché est {_euros(excedent)}. Il manque des "
            "lignes de charges (charges externes, cotisations…) : ajoute-les depuis la "
            "mémoire, ou ne montre pas de compte de résultat incomplet.",
        )
    return None


def _comptes_de_resultat(document: Document) -> list[Constat]:
    constats: list[Constat] = []
    for section in document.sections:
        for tableau in section.tableaux:
            constat = _boucle(tableau, section)
            if constat is not None:
                constats.append(constat)
    return constats


# ── Un libellé, une valeur ──────────────────────────────────────────────────

_SUPERLATIFS = (
    (re.compile(r"(?i)prix (le plus (haut|[ée]lev[ée])|maximum|maximal)"), "le prix le plus haut"),
    (re.compile(r"(?i)prix (le plus bas|minimum|minimal)"), "le prix le plus bas"),
    (re.compile(r"(?i)prix m[ée]dian|m[ée]diane"), "le prix médian"),
)


def _valeur_apres(texte: str, debut: int) -> tuple[str, float] | None:
    for n in nombres(texte[debut:]):
        if n.monetaire:
            return n.ecriture, n.valeur
    return None


def _superlatifs(document: Document) -> list[Constat]:
    vus: dict[str, list[tuple[str, str, float, str]]] = defaultdict(list)
    for section in document.sections:
        # La prose seule : une ligne de tableau se lit dans sa colonne de prix,
        # pas dans la liste entre parenthèses de son libellé.
        for phrase in phrases_de(section, cellules=False):
            for motif, nom in _SUPERLATIFS:
                m = motif.search(phrase)
                if m and (lu := _valeur_apres(phrase, m.end())):
                    vus[nom].append((section.numero, lu[0], lu[1], phrase[:160]))
        for tableau in section.tableaux:
            colonne = next(
                (j for j, e in enumerate(tableau.entetes)
                 if re.search(r"(?i)\bprix\b|valeur|montant", e) and j > 0),
                None,
            )
            for ligne in tableau.lignes:
                for motif, nom in _SUPERLATIFS:
                    if not ligne or not motif.search(ligne[0]):
                        continue
                    cellules = [ligne[colonne]] if colonne is not None and colonne < len(ligne) \
                        else list(ligne[1:])
                    lu = next((v for c in cellules if (v := _valeur_apres(c, 0))), None)
                    if lu:
                        vus[nom].append((section.numero, lu[0], lu[1], " · ".join(ligne)[:160]))
    constats: list[Constat] = []
    for nom, releves in vus.items():
        distinctes = {round(v) for _, _, v, _ in releves}
        if len(distinctes) < 2:
            continue
        for section, ecriture, valeur, passage in releves:
            ailleurs = " ; ".join(
                f"{e} en {s}" for s, e, v, _ in releves if round(v) != round(valeur)
            )
            constats.append(Constat(
                "libelle_unique", section, passage,
                f"{nom[0].upper()}{nom[1:]} n'a qu'une valeur dans un document : ici "
                f"« {ecriture} », ailleurs {ailleurs}. Garde celle du relevé retenu partout.",
            ))
    return constats


#: Les séries du prévisionnel qu'un libellé daté doit citer à l'identique.
_SERIES_DU_PREVISIONNEL = ("ca_previsionnel", "resultat_net", "caf", "ebe")
_NOMS = {
    "ca_previsionnel": "le chiffre d'affaires", "resultat_net": "le résultat net",
    "caf": "la CAF", "ebe": "l'EBE",
}


def _series_datees(document: Document, reference: Reference) -> list[Constat]:
    memoire = reference.memoire
    constats: list[Constat] = []
    valeurs = [
        v for v in valeurs_datees(document)
        if v.serie in _SERIES_DU_PREVISIONNEL and v.nombre.monetaire
    ]
    if memoire is None:
        # Sans mémoire, la valeur majoritaire du document fait référence.
        par_cle: dict[tuple[str, int], list[float]] = defaultdict(list)
        for v in valeurs:
            par_cle[(v.serie, v.annee)].append(v.nombre.valeur)
        for v in valeurs:
            releves = par_cle[(v.serie, v.annee)]
            majoritaire = max(set(releves), key=releves.count)
            if releves.count(majoritaire) > 1 and not proche(v.nombre.valeur, majoritaire):
                constats.append(Constat(
                    "libelle_unique", v.section, v.passage[:200],
                    f"{_NOMS[v.serie][0].upper()}{_NOMS[v.serie][1:]} {v.annee} vaut "
                    f"« {v.nombre.ecriture} » ici et {_euros(majoritaire)} ailleurs : un "
                    "libellé n'a qu'une valeur.",
                ))
        return constats
    for v in valeurs:
        fait = fait_de(memoire, v.serie, v.annee)
        attendu = en_euros(fait) if fait else None
        if fait is None or attendu is None:
            continue
        if proche(v.nombre.valeur, attendu, relatif=0.005, absolu=1):
            continue
        autre = next(
            (
                s for s in _SERIES_DU_PREVISIONNEL
                if s != v.serie and (f := fait_de(memoire, s, v.annee))
                and (e := en_euros(f)) and proche(v.nombre.valeur, e, relatif=0.005, absolu=1)
            ),
            None,
        )
        confusion = f" — c'est {_NOMS[autre]} {v.annee}" if autre else ""
        constats.append(Constat(
            "libelle_unique", v.section, v.passage[:200],
            f"{_NOMS[v.serie][0].upper()}{_NOMS[v.serie][1:]} {v.annee} vaut "
            f"« {v.nombre.ecriture} » ici{confusion} ; il vaut {_euros(attendu)} "
            f"({{{{{fait.id}}}}}) partout ailleurs. Un libellé n'a qu'une valeur.",
        ))
    return constats


def controler(document: Document, reference: Reference) -> list[Constat]:
    return [
        *_comptes_de_resultat(document),
        *_superlatifs(document),
        *_series_datees(document, reference),
    ]



