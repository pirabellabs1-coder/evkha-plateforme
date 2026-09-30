"""Mise en page (classe 10).

## Les défauts, mesurés

Business plan ÉCLORE `28a257bf` (30/09/2026), relu par la cliente :

- l'annexe des chiffres : une définition coupée par « … » au milieu de sa
  phrase. La coupe venait de NOTRE rendu (`rendu_word.texte.libelle_court`,
  plafond de 110 signes) ;
- une page qui ne porte que la légende « Données du socle vérifié » d'une
  figure repoussée seule en fin de chapitre ; une page blanche entre deux
  chapitres ; une autre à quatre lignes ;
- plus de sept cents espaces ORDINAIRES entre un nombre et « € » ou « % »,
  sur les quatre cinquièmes des pages : le nombre et son unité se séparent en
  fin de ligne. `socle.schema.montant_lisible` écrivait lui-même cette
  espace ;
- dans un même tableau, des montants à l'euro à côté d'un montant au
  centime, et un montant à une décimale parmi des centimes.

## Ce que chaque contrôle regarde

1. Une cellule qui finit par « … » et qui porte une phrase (au moins cinq
   mots). « Accélérer si… / Ralentir si… », en-têtes voulus, en ont deux.
2. Les montants d'un même tableau, cellule de VALEUR par cellule de valeur
   (un montant, pas une phrase qui en cite plusieurs), unité par unité : un
   seul nombre de décimales.
3. Sur le document ENTIER (le texte des pages n'existe qu'après rendu) : les
   pages de moins de dix lignes utiles — en-tête et pied courants retirés —,
   couverture et quatrième exceptées ; et les espaces sécables avant « € » et
   « % », réunis en UN constat : c'est le rendu qui les pose, pas un chapitre.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from .constat import Constat, Reference
from .document import Document, _lignes_d_en_tete

CLASSE = "mise_en_page"

#: « Aucune page de moins de 10 lignes utiles » (cliente, 30/09/2026).
LIGNES_UTILES_MIN = 10

#: En deçà, « … » est une amorce voulue (« Accélérer si… »), pas une coupe.
MOTS_MIN_CELLULE_COUPEE = 5

#: Une cellule de valeur : un montant, éventuellement suivi d'une courte
#: précision (« 182 € TTC (donnée du projet) »). Au-delà, c'est une phrase.
MOTS_MAX_CELLULE_DE_VALEUR = 6

_COUPE = re.compile(r"(?:…|\.\.\.)\s*$")
_ETC = re.compile(r"(?i)\betc\.?\s*(?:…|\.\.\.)?\s*$")


def _fin(texte: str, mots: int = 10) -> str:
    """Les derniers mots d'une cellule, tels qu'écrits : là où la coupe se voit."""
    decoupe = texte.split()
    return " ".join(decoupe[-mots:])


# ── 1. Cellules coupées ─────────────────────────────────────────────────────


def _cellules_coupees(document: Document, reference: Reference) -> list[Constat]:
    constats: list[Constat] = []
    for section in document.sections:
        for tableau in section.tableaux:
            for ligne in (tableau.entetes, *tableau.lignes):
                for cellule in ligne:
                    texte = " ".join(cellule.split())
                    if not _COUPE.search(texte) or _ETC.search(texte):
                        continue
                    if len(texte.split()) < MOTS_MIN_CELLULE_COUPEE:
                        continue
                    constats.append(Constat(
                        CLASSE, section.numero, _fin(texte),
                        "Cellule de tableau coupée par « … » : le lecteur n'en lit pas la fin. "
                        "Aucune ligne de tableau ne se tronque — écrire la cellule en entier "
                        "(elle passe à la ligne), ou la reformuler plus courte, sans points de "
                        "suspension.",
                        # Sur un chapitre, c'est le texte du rédacteur : le réécrire
                        # répare. Sur le document rendu, la coupe peut venir du rendu.
                        grave=not reference.document_entier,
                    ))
    return constats


# ── 2. Un arrondi par tableau ───────────────────────────────────────────────


def _montant_re() -> re.Pattern[str]:
    from core.numbers import MONEY_CAPTURED  # noqa: PLC0415 — règle 5

    return re.compile(MONEY_CAPTURED, re.IGNORECASE)


#: Les écritures d'une même unité (`core.numbers.CURRENCY_ALTERNATION`),
#: ramenées à une clé : « euros », « EUR » et « € » s'arrondissent ensemble.
_UNITES = {
    "€": "€", "euro": "€", "euros": "€", "eur": "€",
    "k€": "k€", "keur": "k€", "m€": "M€", "md€": "Md€", "mds€": "Md€",
}


def _decimales(nombre: str) -> int:
    trouve = re.search(r",(\d+)$", nombre.strip())
    return len(trouve.group(1)) if trouve else 0


def _cellule_de_valeur(cellule: str, montant: re.Match[str]) -> bool:
    avant = cellule[: montant.start()].strip(" (+-−–")
    return not avant and len(cellule.split()) <= MOTS_MAX_CELLULE_DE_VALEUR


def _arrondis_heterogenes(document: Document) -> list[Constat]:
    motif = _montant_re()
    constats: list[Constat] = []
    for section in document.sections:
        for tableau in section.tableaux:
            if not tableau.lignes:
                # Un encadré (« VERDICT | Opportunité — … ») n'est pas un tableau
                # de chiffres : il n'a pas de lignes de données.
                continue
            par_unite: dict[str, list[tuple[int, str]]] = defaultdict(list)
            for ligne in tableau.lignes:
                for cellule in ligne:
                    texte = " ".join(cellule.split())
                    premier = motif.search(texte)
                    if premier is None or not _cellule_de_valeur(texte, premier):
                        continue
                    for montant in motif.finditer(texte):
                        unite = _UNITES.get(montant.group(2).lower())
                        if unite:
                            decimales = _decimales(montant.group(1))
                            par_unite[unite].append((decimales, montant.group(0)))
            for valeurs in par_unite.values():
                compte = Counter(d for d, _ in valeurs)
                if len(compte) < 2:
                    continue
                rare = min(compte, key=lambda d: (compte[d], -d))
                ecarts = list(dict.fromkeys(v for d, v in valeurs if d == rare))
                autres = list(dict.fromkeys(v for d, v in valeurs if d != rare))[:3]
                constats.append(Constat(
                    CLASSE, section.numero, ecarts[0],
                    f"Dans le même tableau, « {' », « '.join(ecarts[:3])} » "
                    f"({_arrondi(rare)}) à côté de « {' », « '.join(autres)} » "
                    f"({', '.join(_arrondi(d) for d in sorted(compte) if d != rare)}) : tous "
                    "les montants d'un tableau portent le même arrondi — tous à l'euro, ou "
                    "tous au centime.",
                    grave=False,
                ))
    return constats


def _arrondi(decimales: int) -> str:
    return {0: "à l'unité", 1: "à une décimale", 2: "au centime"}.get(
        decimales, f"à {decimales} décimales"
    )


# ── 3. Pages presque vides ──────────────────────────────────────────────────

_NUMERO_DE_PAGE = re.compile(r"^\W*\d{1,4}\W*$")


def _pages_presque_vides(document: Document) -> list[Constat]:
    pages = [page.splitlines() for page in document.pages]
    en_tetes = _lignes_d_en_tete(pages)
    derniere = len(pages)
    constats: list[Constat] = []
    for numero, lignes in enumerate(pages, start=1):
        if numero in (1, derniere):
            # Couverture et quatrième de couverture : peu de lignes, c'est leur
            # dessin.
            continue
        utiles = [
            ligne.strip() for ligne in lignes
            if ligne.strip() and re.search(r"\w", ligne)
            and re.sub(r"\d+", "#", ligne.strip()) not in en_tetes
            and not _NUMERO_DE_PAGE.match(ligne)
        ]
        if len(utiles) >= LIGNES_UTILES_MIN:
            continue
        constats.append(Constat(
            CLASSE, f"p. {numero}",
            " ".join(utiles)[:120] if utiles else "(page blanche)",
            f"Page {numero} : {len(utiles)} ligne(s) utile(s), en-tête et pied de page retirés "
            f"— moins de {LIGNES_UTILES_MIN}. Une figure, une fin de chapitre ou un saut de "
            "page laisse la page presque vide ; hors couverture et quatrième de couverture, "
            "aucune page n'en porte si peu.",
            grave=False,
        ))
    return constats


# ── 4. Espaces sécables avant « € » et « % » ────────────────────────────────

#: Un chiffre, une espace ORDINAIRE ou un saut de ligne, puis le symbole. Toute
#: autre espace (insécable, fine insécable) tient le nombre et son unité.
_SECABLE = re.compile(r"\d(?P<espace>[ \n]+)(?P<unite>%|(?:Mds|Md|M|k)?€)(?![^\W\d_])")


def _espaces_secables(document: Document) -> list[Constat]:
    occurrences: list[tuple[int, str]] = []
    for numero, page in enumerate(document.pages, start=1):
        for trouve in _SECABLE.finditer(page):
            debut = max(0, trouve.start() - 24)
            # Le passage commence à un début de mot : le lecteur le cherche tel quel.
            while 0 < debut < trouve.start() and page[debut - 1].isalnum():
                debut += 1
            contexte = " ".join(page[debut : trouve.end()].split())
            occurrences.append((numero, contexte))
    if not occurrences:
        return []
    pages = list(dict.fromkeys(n for n, _ in occurrences))
    liste = ", ".join(map(str, pages[:12])) + (", …" if len(pages) > 12 else "")
    premiere, contexte = occurrences[0]
    return [Constat(
        CLASSE, f"p. {premiere}", contexte,
        f"{len(occurrences)} espace(s) ordinaire(s) entre un nombre et « € » ou « % », sur "
        f"{len(pages)} page(s) (p. {liste}) : le nombre et son unité se séparent en fin de "
        "ligne. Une espace insécable avant « € » et « % », partout — c'est le rendu qui la "
        "pose (`montant_lisible`, typographie du chapitre).",
        grave=False,
    )]


# ── Le contrôle ─────────────────────────────────────────────────────────────


def controler(document: Document, reference: Reference) -> list[Constat]:
    constats = [*_cellules_coupees(document, reference), *_arrondis_heterogenes(document)]
    if reference.document_entier and document.pages:
        constats += _pages_presque_vides(document)
        constats += _espaces_secables(document)
    return constats
