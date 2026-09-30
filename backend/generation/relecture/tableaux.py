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
    r"(?i)charges|achats?|cotisations|salaires|loyers?|sous-traitance|frais|d[ée]penses|"
    r"r[ée]mun[ée]ration|masse salariale|imp[ôo]ts et taxes|personnel|"
    r"co[ûu]ts?\b|consommations?|fournitures|mati[èe]res|marchandises"
)
#: La nature d'une ligne se lit sur son NOM EN TÊTE — jamais sur un mot pris
#: n'importe où. Trois passages de la porte finale (30/09/2026) l'ont montré :
#: chercher « produits », « aides » ou « recettes » dans tout le libellé fait de
#: « Achats de produits », « Salaires des aides à domicile » ou « Achats
#: d'ingrédients pour les recettes » des recettes ; chercher « taux » ou
#: « effectif » exclut « Cotisations sociales (taux de 47 %) ».
#:
#: Une recette : « Produits » seul ou catégorisé (financiers, exceptionnels…),
#: « Autres produits », subvention, reprise, dons, aides, recettes, crédit
#: d'impôt, transfert de charges, production stockée, cotisations des adhérents.
#: « Produits d'entretien » est un achat.
_RECETTE_EN_TETE = re.compile(
    r"(?i)^(?:autres?\s+produits?\b|produits?(?:\s*$|\s+(?:financiers|exceptionnels|divers"
    r"|annexes|des\s+activit|d.exploitation|de\s+gestion))"
    r"|subventions?\b|reprises?\b|dons?\b|aides?(?![\w-])|recettes?\b"
    r"|cr[ée]dits?\s+d.imp[ôo]ts?\b|transferts?\s+de\s+charges|production\s+(?:stock|immobilis)"
    r"|cotisations?\s+des\s+(?:adh[ée]rents|membres))"
)
#: Ni une charge ni une recette : un sous-total (« Marge brute »), un ratio, un
#: résultat, un stock de fin d'exercice, un autre chiffre d'affaires ou sa
#: ventilation (« Ventes de marchandises », « Prestations de services » sous le
#: CA). Un tableau d'INDICATEURS range « Résultat net » ou « Trésorerie » entre
#: le CA et l'EBE sans prétendre boucler (business plan ÉCLORE, 11.3).
_NON_FLUX_EN_TETE = re.compile(
    r"(?i)^(?:marges?\b|taux\b|r[ée]sultats?\b|seuils?\b|point\s+mort|capacit[ée]|CAF\b"
    r"|tr[ée]sorerie|valeur\s+ajout|BFR\b|besoin\s+en\s+fonds|fonds\s+de\s+roulement"
    r"|nombre|effectifs?\b|panier|prix\b(?!\s+d.achat)|chiffres?\s+d.affaires|CA\b"
    r"|ventes?\b|prestations?\b|dotations?\b|amortissements?\b|exc[ée]dent|EBE\b)"
)
#: Ailleurs dans le libellé, ces mots-là seulement disent encore « pas un flux » :
#: « Impôt sur le résultat », « Variation de trésorerie ».
_PAS_UNE_LIGNE_DE_FLUX = re.compile(
    r"(?i)r[ée]sultat|tr[ée]sorerie|capacit[ée] d.autofinancement|valeur ajout|dotation"
    r"|amortissement"
)
#: Un libellé générique qui peut coiffer le détail (« Charges d'exploitation »
#: sous ses lignes) : un sous-total implicite, s'il vaut la somme des autres.
_CHARGES_GENERIQUES = re.compile(
    r"(?i)^charges(?:\s+d.exploitation|\s+de\s+fonctionnement|\s+courantes)?\s*$"
)
_TOTAL = re.compile(r"(?i)\btota(?:l|ux|les?)\b|sous-total")
#: « dont rémunération du dirigeant » détaille la ligne d'au-dessus : la compter
#: la retrancherait deux fois.
_DETAIL = re.compile(r"(?i)^\W*dont\b")
#: Une variation de stock est une charge SIGNÉE, dont le signe écrit varie
#: selon les usages : les deux lectures sont admises.
_STOCK = re.compile(r"(?i)variation (?:des |de |du )?stocks?")
#: « — », « – », une cellule vide ou « 0 » : zéro, écrit à la façon d'un compte
#: de résultat. Il ne coupe pas le contrôle de l'exercice (porte finale du
#: 30/09/2026 : un seul « — » sur une ligne de subvention faisait tout sauter).
_ZERO = re.compile(r"^[\s—–-]*$|^\s*0(?:[,.]0+)?\s*€?\s*$")
#: Le chiffre d'affaires de l'ENTREPRISE, qui coiffe sa ventilation.
_CA_GENERIQUE = re.compile(
    r"(?i)^\W*chiffres?\s+d.affaires(?:\s+(?:HT|hors\s+taxes?|net|total|global|annuel))*\s*$"
)


def _montant(cellule: str) -> float | None:
    lus = [n for n in nombres(cellule) if n.monetaire]
    return lus[0].valeur if lus else None


def _tete(libelle: str) -> str:
    """Le libellé sans sa parenthèse ni ce qui précède le premier mot."""
    return re.sub(r"^[\W\d_]+", "", re.sub(r"\([^)]*\)", " ", libelle)).strip()


def _nature(libelle: str) -> str | None:
    """« charge », « autre », « generique », « produit », « stock », « total » — ou None.

    None : pas une ligne de flux. « autre » : un libellé inconnu (« Assurance »,
    « Honoraires »), compté comme une dépense.
    """
    if _DETAIL.search(libelle):
        return None
    tete = _tete(libelle)
    if _TOTAL.search(tete):
        return "total" if _CHARGES.search(tete) else None
    if _STOCK.search(tete):
        return "stock"
    if _RECETTE_EN_TETE.search(tete):
        return "produit"
    if _NON_FLUX_EN_TETE.search(tete):
        return None
    if _CHARGES_GENERIQUES.search(tete):
        return "generique"
    if _CHARGES.search(tete):
        return "charge"
    if _PAS_UNE_LIGNE_DE_FLUX.search(tete):
        return None
    return "autre"


def _boucle(tableau: Tableau, section: Section) -> Constat | None:
    """CA + produits − charges = EBE, colonne par colonne.

    Revue du 30/09/2026 : une liste fermée de mots de charges déclarait « qui ne
    boucle pas » un compte juste portant « Rémunération du dirigeant » ou
    « Impôts et taxes ». Chaque ligne a donc une NATURE, lue sur son nom en tête
    (`_nature`), et les montants se lisent en valeur absolue.

    Le constat ne tombe que si aucune lecture HONNÊTE ne boucle — et une lecture
    n'est honnête que si elle ne peut pas blanchir un compte faux (porte finale,
    NO-GO sur `63be6a3` et `1d526db`) :
    - le détail des lignes, toujours ;
    - un libellé générique (« Charges d'exploitation ») n'est un sous-total que
      s'il vaut la somme des autres lignes ;
    - les seules charges nommées, seulement à côté d'un libellé inconnu ;
    - un total de charges, seulement quand il n'y a AUCUN détail ;
    - la somme d'un CA ventilé, seulement si aucune ligne de CA générique ne le
      coiffe.
    Un montant illisible (« 40 % », « 25 000 » sans unité) sur une ligne de flux
    coupe le contrôle de l'exercice, comme avant : on ne juge pas sans lire.
    """
    annees = [
        (j, m.group(0)) for j, e in enumerate(tableau.entetes)
        if (m := re.search(r"\b20[2-6]\d\b", e))
    ]
    if not annees:
        return None
    lignes = {i: ligne for i, ligne in enumerate(tableau.lignes) if ligne}
    series = {i: serie_nommee(ligne[0], "€") for i, ligne in lignes.items()}
    ebe = next((i for i, s in series.items() if s == "ebe"), None)
    if ebe is None:
        return None
    lignes_ca = [i for i, s in series.items() if s == "ca_previsionnel" and i < ebe]
    if not lignes_ca:
        return None
    ca_total = next((i for i in lignes_ca if _TOTAL.search(lignes[i][0])), None)
    ca_coiffe = _CA_GENERIQUE.search(lignes[lignes_ca[0]][0]) is not None
    natures = {
        i: n for i in lignes
        if lignes_ca[0] < i < ebe and i not in lignes_ca and (n := _nature(lignes[i][0]))
    }
    if not natures or all(n == "produit" for n in natures.values()):
        return None
    for j, annee in annees:
        def lu(i: int, colonne: int = j, flux: bool = True) -> float | None:
            ligne = lignes[i]
            cellule = ligne[colonne] if colonne < len(ligne) else ""
            if flux and _ZERO.match(cellule):
                return 0.0
            return _montant(cellule)

        excedent = lu(ebe, flux=False)
        ventiles = [lu(i, flux=False) for i in lignes_ca]
        valeurs = {i: lu(i) for i in natures}
        if excedent is None or any(v is None for v in (*ventiles, *valeurs.values())):
            continue  # un montant illisible : l'exercice ne se juge pas
        montants = {i: v for i, v in valeurs.items() if v is not None}
        chiffres_lus = [c for c in ventiles if c is not None]
        if ca_total is not None:
            chiffres = [chiffres_lus[lignes_ca.index(ca_total)]]
        elif len(chiffres_lus) > 1 and not ca_coiffe:
            chiffres = [chiffres_lus[0], sum(chiffres_lus)]
        else:
            chiffres = [chiffres_lus[0]]

        # Un libellé générique qui vaut la somme des autres lignes : un sous-total.
        precis = {i: abs(v) for i, v in montants.items() if natures[i] in ("charge", "autre")}
        sous_totaux = {
            i for i, v in montants.items() if natures[i] == "generique"
            and precis and proche(abs(v), sum(precis.values()), relatif=0.01, absolu=2)
        }
        comptees = {i: v for i, v in montants.items() if i not in sous_totaux}

        def somme(*genres: str, lues: dict[int, float] = comptees) -> float:
            return sum(abs(v) for i, v in lues.items() if natures[i] in genres)

        produits = somme("produit")
        stock = sum(v for i, v in comptees.items() if natures[i] == "stock")
        a_du_detail = any(
            natures[i] in ("charge", "autre", "generique", "stock") for i in comptees
        )
        retraits = [somme("charge", "autre", "generique")]
        if any(natures[i] == "autre" for i in comptees):
            retraits.append(somme("charge", "generique"))
        if not a_du_detail:
            retraits += [abs(v) for i, v in comptees.items() if natures[i] == "total"]
        if any(
            proche(chiffre + produits - retrait - signe * stock, excedent,
                   relatif=0.01, absolu=2)
            for chiffre in chiffres for retrait in retraits for signe in (1, -1)
        ):
            continue
        chiffre = chiffres[0]
        if a_du_detail:
            detail = " ".join([
                _euros(chiffre),
                *(f"{'+' if natures[i] == 'produit' else '−'} {_euros(abs(v))}"
                  for i, v in comptees.items() if natures[i] != "total" and v),
            ])
            attendu = chiffre + produits - somme("charge", "autre", "generique", "stock")
        else:
            # Seul un total de charges : l'opération se lit sur lui.
            total = next(abs(v) for i, v in comptees.items() if natures[i] == "total")
            ajout = f" + {_euros(produits)}" if produits else ""
            detail = f"{_euros(chiffre)}{ajout} − {_euros(total)}"
            attendu = chiffre + produits - total
        return Constat(
            "tableau", section.numero,
            f"{tableau.lignes[ca_total if ca_total is not None else lignes_ca[0]][0]} "
            f"{_euros(chiffre)} · {tableau.lignes[ebe][0]} {_euros(excedent)}",
            f"Le compte de résultat ne boucle pas en {annee} : {detail} = "
            f"{_euros(attendu)}, mais l'EBE affiché est {_euros(excedent)}. Il manque des "
            "lignes de charges (charges externes, cotisations…) ou un montant est faux : "
            "reprends-les depuis la mémoire, ou ne montre pas de compte de résultat "
            "incomplet.",
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



