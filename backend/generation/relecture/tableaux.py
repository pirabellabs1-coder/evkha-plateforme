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
    tolerance_ecrite,
    valeurs_datees,
)


def _euros(montant: float) -> str:
    return f"{montant:,.0f} €".replace(",", " ")


# ── Le compte de résultat boucle ────────────────────────────────────────────

_CHARGES = re.compile(
    r"(?i)charges|achats|cotisations|salaires|loyers|sous-traitance|frais|d[ée]penses|"
    r"r[ée]mun[ée]ration|masse salariale|imp[ôo]ts et taxes|personnel"
)
#: Ni une charge ni un produit : un sous-total (« marge brute »), une dotation,
#: un résultat, un stock ou un ratio. Un tableau d'INDICATEURS range « Résultat
#: net » ou « Trésorerie » entre le CA et l'EBE sans prétendre boucler
#: (business plan ÉCLORE, 11.3).
_PAS_UNE_LIGNE_DE_FLUX = re.compile(
    r"(?i)\bmarge\b|\btotal\b|sous-total|valeur ajout|dotation|amortissement"
    r"|r[ée]sultat|tr[ée]sorerie|capacit[ée]|\bCAF\b|seuil|\btaux\b|\bBFR\b"
    r"|fonds de roulement|point mort|effectif|nombre"
)
_PRODUIT = re.compile(r"(?i)subvention|produits?\b|reprise")


def _montant(cellule: str) -> float | None:
    lus = [n for n in nombres(cellule) if n.monetaire]
    return lus[0].valeur if lus else None


def _boucle(tableau: Tableau, section: Section) -> Constat | None:
    """CA − charges = EBE, colonne par colonne — jugé sur TOUTES les lignes entre les deux.

    Revue du 30/09/2026 : une liste fermée de mots de charges déclarait « qui ne
    boucle pas » un compte juste portant « Rémunération du dirigeant » ou
    « Impôts et taxes », et une charge écrite en négatif s'ajoutait. On compte
    désormais toute ligne entre le CA et l'EBE (sauf sous-totaux et dotations),
    en valeur absolue ; le constat ne tombe que si NI la somme des charges NI
    celle de toutes les lignes ne boucle.
    """
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
    entre = [i for i in lignes if ca < i < ebe and not _PAS_UNE_LIGNE_DE_FLUX.search(lignes[i][0])]
    produits = [i for i in entre if _PRODUIT.search(lignes[i][0])]
    depenses_lignes = [i for i in entre if i not in produits]
    charges = [i for i in depenses_lignes if _CHARGES.search(lignes[i][0])]
    if not depenses_lignes:
        return None
    for j, annee in annees:
        def lu(i: int, colonne: int = j) -> float | None:
            ligne = lignes[i]
            return _montant(ligne[colonne]) if colonne < len(ligne) else None

        chiffre, excedent = lu(ca), lu(ebe)
        tout = [lu(i) for i in entre]
        if chiffre is None or excedent is None or any(v is None for v in tout):
            continue
        depenses = [abs(v) for i in depenses_lignes if (v := lu(i)) is not None]
        entrees = [abs(v) for i in produits if (v := lu(i)) is not None]
        seules_charges = [abs(v) for i in charges if (v := lu(i)) is not None]
        attendu = chiffre + sum(entrees) - sum(depenses)
        if proche(attendu, excedent, relatif=0.01, absolu=2) or proche(
            chiffre - sum(seules_charges), excedent, relatif=0.01, absolu=2
        ):
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
    (re.compile(r"(?i)prix m[ée]dian|m[ée]diane (des|du) (prix|tarifs?)"), "le prix médian"),
)
#: Ce qui précise de QUEL panel on parle : « du panel », « des cours collectifs ».
_QUALIFICATIF = re.compile(r"(?i)^\s*(?:d[eu]s?|de la|de l['’])\s+([^:·(€\d.;]{2,50})")
#: Un qualificatif qui ne distingue rien : le panel entier.
_GENERIQUE = re.compile(r"(?i)^\s*(panel|march[ée]|concurren\w*|relev[ée]\w*)?\s*$")


def _qualificatif(texte: str, fin: int) -> str:
    m = _QUALIFICATIF.match(texte[fin:])
    mots = m.group(1).strip().lower() if m else ""
    return "" if _GENERIQUE.match(mots) else mots


def _valeur_apres(texte: str, debut: int) -> tuple[str, float] | None:
    for n in nombres(texte[debut:]):
        if n.monetaire:
            return n.ecriture, n.valeur
    return None


def _chapitre_de(numero: str) -> str:
    return numero.replace("ch. ", "").split(".")[0]


def _superlatifs(document: Document) -> list[Constat]:
    """Un même superlatif (« le prix le plus haut du panel ») n'a qu'une valeur.

    Revue du 30/09/2026 : un prix le plus bas PAR SEGMENT (cours collectifs,
    cours particuliers) n'est pas une contradiction — la règle du client du
    27/09 l'impose. Deux relevés ne se contredisent que pour le même
    qualificatif, ou quand l'un des deux ne précise rien.
    """
    vus: dict[str, list[tuple[str, str, float, str, str]]] = defaultdict(list)
    for section in document.sections:
        # La prose seule : une ligne de tableau se lit dans sa colonne de prix,
        # pas dans la liste entre parenthèses de son libellé.
        for phrase in phrases_de(section, cellules=False):
            for motif, nom in _SUPERLATIFS:
                m = motif.search(phrase)
                if m and (lu := _valeur_apres(phrase, m.end())):
                    vus[nom].append((
                        section.numero, lu[0], lu[1], phrase[:160], _qualificatif(phrase, m.end()),
                    ))
        for tableau in section.tableaux:
            colonne = next(
                (j for j, e in enumerate(tableau.entetes)
                 if re.search(r"(?i)\bprix\b|valeur|montant", e) and j > 0),
                None,
            )
            for ligne in tableau.lignes:
                for motif, nom in _SUPERLATIFS:
                    m = motif.search(ligne[0]) if ligne else None
                    if m is None:
                        continue
                    cellules = [ligne[colonne]] if colonne is not None and colonne < len(ligne) \
                        else list(ligne[1:])
                    lu = next((v for c in cellules if (v := _valeur_apres(c, 0))), None)
                    if lu:
                        vus[nom].append((
                            section.numero, lu[0], lu[1], " · ".join(ligne)[:160],
                            _qualificatif(ligne[0], m.end()),
                        ))
    constats: list[Constat] = []
    for nom, releves in vus.items():
        for numero, ecriture, valeur, passage, qualificatif in releves:
            contraires = [
                (s, e) for s, e, v, _, q in releves
                if round(v) != round(valeur) and (q == qualificatif or not q or not qualificatif)
            ]
            if not contraires:
                continue
            ailleurs = " ; ".join(f"{e} en {s}" for s, e in contraires)
            constats.append(Constat(
                "libelle_unique", numero, passage,
                f"{nom[0].upper()}{nom[1:]} n'a qu'une valeur dans un document : ici "
                f"« {ecriture} », ailleurs {ailleurs}. Garde celle du relevé retenu partout.",
                # Une reprise ne corrige que SON chapitre : grave seulement quand
                # la contradiction y est entière.
                grave=any(_chapitre_de(s) == _chapitre_de(numero) for s, _ in contraires),
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
    scenarios = [
        e for f in memoire.faits.values() if "_moins_" in f.id and (e := en_euros(f)) is not None
    ]
    for v in valeurs:
        fait = fait_de(memoire, v.serie, v.annee)
        attendu = en_euros(fait) if fait else None
        if fait is None or attendu is None:
            continue
        tolerance = max(tolerance_ecrite(v.nombre), 0.005 * abs(attendu), 1.0)
        if abs(v.nombre.valeur - attendu) <= tolerance:
            continue
        if any(abs(v.nombre.valeur - e) <= tolerance for e in scenarios):
            continue  # le scénario de sensibilité, pas le prévisionnel central
        autre = next(
            (
                s for s in _SERIES_DU_PREVISIONNEL
                if s != v.serie and (f := fait_de(memoire, s, v.annee))
                and (e := en_euros(f)) and abs(v.nombre.valeur - e) <= tolerance
            ),
            None,
        )
        autre_annee = next(
            (
                f.annee for f in memoire.faits.values()
                if f.annee != v.annee and f.id.startswith(f"{v.serie}_an")
                and (e := en_euros(f)) is not None and abs(v.nombre.valeur - e) <= tolerance
            ),
            None,
        )
        if autre:
            confusion = f" — c'est {_NOMS[autre]} {v.annee}"
        elif autre_annee:
            confusion = f" — c'est la valeur de {autre_annee}"
        else:
            confusion = ""
        constats.append(Constat(
            "libelle_unique", v.section, v.passage[:200],
            f"{_NOMS[v.serie][0].upper()}{_NOMS[v.serie][1:]} {v.annee} vaut "
            f"« {v.nombre.ecriture} » ici{confusion} ; il vaut {_euros(attendu)} "
            f"({{{{{fait.id}}}}}) partout ailleurs. Un libellé n'a qu'une valeur.",
            # Grave seulement sur un diagnostic POSITIF — une autre série, un
            # autre exercice (revue du 30/09/2026) ; sinon, un signal.
            grave=bool(autre or autre_annee),
        ))
    return constats


def controler(document: Document, reference: Reference) -> list[Constat]:
    return [
        *_comptes_de_resultat(document),
        *_superlatifs(document),
        *_series_datees(document, reference),
    ]



