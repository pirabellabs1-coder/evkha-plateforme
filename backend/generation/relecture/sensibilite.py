"""Analyse de sensibilité (classe 11) — la DÉTECTION.

Un business plan porte un scénario à −10 % et à −20 % de chiffre d'affaires,
calculé en code depuis la mémoire ; une phrase qui dit ne pas pouvoir le faire
est interdite. Le calcul et la consigne vivent ailleurs : ce module dit
seulement ce qui manque.

## Le défaut, mesuré

Business plan ÉCLORE `28a257bf` (30/09/2026) : une section de sensibilité
titrée sur une baisse de 10 % du chiffre d'affaires, aucun scénario à −20 %,
pas un montant pour −10 %, et à la place une phrase qui renonce : le compte
de résultat recalculé n'est « pas fourni », le construire « exigerait » des
hypothèses que le client n'a « pas arbitrées ». Un banquier lit : l'étude n'a
pas fait son travail.

## Ce qui est regardé

- Sur un chapitre seul comme sur le document : la phrase de renoncement —
  une négation qui porte sur le CALCUL (« ne fournit pas de compte de
  résultat recalculé », « n'est pas chiffré ») ou un conditionnel d'obstacle
  (« exigerait », « faute de »), dans une phrase qui parle de sensibilité ou
  d'une baisse de chiffre d'affaires. « Le scénario à −20 % ne permet pas de
  couvrir les charges fixes » est une conclusion, pas un renoncement : la
  négation n'y porte pas sur le calcul.
- Sur le document ENTIER : un scénario à −10 % ET un à −20 %, CHIFFRÉS (un
  montant dans la phrase, la ligne ou le tableau du scénario). Annoncer
  « −10 % » dans un titre sans un seul montant n'est pas un scénario.

Réservé au business plan (`Reference.livrable`).
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from .constat import Constat, Reference
from .document import Document, Section, Tableau

CLASSE = "sensibilite"

#: Les deux scénarios exigés (cliente, 30/09/2026).
BAISSES_EXIGEES = (10, 20)

#: Une baisse de N % : « −10 % », « baisse de 20 % », « inférieur de 10 % »,
#: « 20 % de moins ».
_BAISSE = re.compile(
    r"(?i)(?:(?<![\w%])[-−–]\s?(\d{1,2})\s?%"
    r"|\b(?:baisse|recul|diminution|repli|chute|perte|contraction)\s+(?:de\s+|d['’])?"
    r"(?:[\w'’]+\s+){0,5}?(\d{1,2})\s?%"
    r"|\binf[ée]rieure?s?\s+de\s+(\d{1,2})\s?%"
    r"|\b(\d{1,2})\s?%\s+(?:de\s+)?(?:moins|en\s+moins))"
)
_CHIFFRE_D_AFFAIRES = re.compile(r"(?i)chiffres?\s+d['’]\s?affaires|\bCA\b|\bventes\b")
_SENSIBILITE = re.compile(r"(?i)sensibilit|sc[ée]nario|stress|d[ée]grad")

#: « chiffrer », « chiffré », « chiffrage » — pas « chiffre d'affaires ».
_CHIFFRER = r"chiffr(?!es?\s+d['’]\s?affaires)\w*"
#: Ce que le renoncement refuse de produire : le calcul, ou son livrable.
_OBJETS = (
    rf"(?:(?:re)?calcul\w*|constru\w*|{_CHIFFRER}|[ée]tabli\w*|mod[ée]lis\w*|simul\w*"
    r"|ventil\w*|redistribu\w*|compte\s+de\s+r[ée]sultat|colonne|tableau|sc[ée]nario"
    r"|sensibilit[ée]|projection)"
)
#: Entre la négation et son objet, rien que des mots-outils : « ne fournit pas
#: DE compte de résultat », « n'a pas ÉTÉ chiffré ». « n'est pas négatif dans
#: le scénario » ne porte pas sur le calcul — un adjectif s'intercale.
_OUTILS = (
    r"(?:de|d['’]|du|la|le|les|l['’]|un|une|des|ce|cette|ces|être|été|encore|en"
    r"|son|sa|ses|leur|leurs)"
)
_NEGATION_DU_CALCUL = re.compile(
    rf"(?i)\b(?:ne\s+|n['’]\s*)(?:[\w'’]+\s+){{0,2}}?(?:pas|aucun|aucune|jamais|plus)\s+"
    rf"(?:{_OUTILS}\s*)*{_OBJETS}"
)
#: L'obstacle invoqué : un conditionnel qui renvoie le calcul à plus tard…
_OBSTACLE = re.compile(
    r"(?i)\b(?:exigerait|n[ée]cessiterait|supposerait|imposerait|demanderait)\b"
    r"|\bfaute\s+d|\bimpossible\b|\bpas\s+(?:été\s+)?arbitr|\bnon\s+arbitr"
)
#: … quand il porte sur le calcul (« rendrait impossible le remboursement »
#: est une conclusion).
_CALCUL = re.compile(
    rf"(?i)\b(?:re)?calcul|\bconstrui|\b{_CHIFFRER}|\bmod[ée]lis|\bsimul|\bventil|\bredistribu"
    r"|\bcompte\s+de\s+r[ée]sultat|\bcolonne"
)


def _montant_re() -> re.Pattern[str]:
    from core.numbers import MONEY  # noqa: PLC0415 — règle 5

    return re.compile(MONEY, re.IGNORECASE)


def _phrases(paragraphe: str) -> list[str]:
    from .sources import phrases  # noqa: PLC0415

    return phrases(paragraphe)


def _baisses(texte: str) -> set[int]:
    return {int(next(g for g in m.groups() if g)) for m in _BAISSE.finditer(texte)}


def renonce_au_calcul(phrase: str, *, titre: str = "") -> bool:
    """Cette phrase dit-elle que la sensibilité ne peut pas être calculée ?

    `titre` : celui de la section — dans une section « Sensibilité », une
    phrase n'a pas besoin de le redire pour en parler.
    """
    if not (_SENSIBILITE.search(phrase) or _baisses(phrase) or _SENSIBILITE.search(titre)):
        return False
    if _NEGATION_DU_CALCUL.search(phrase):
        return True
    return bool(_OBSTACLE.search(phrase) and _CALCUL.search(phrase))


# ── Le renoncement ──────────────────────────────────────────────────────────


def _renoncements(document: Document) -> list[Constat]:
    constats: list[Constat] = []
    for section in document.sections:
        for paragraphe in section.paragraphes:
            for phrase in _phrases(paragraphe):
                if not renonce_au_calcul(phrase, titre=section.titre):
                    continue
                constats.append(Constat(
                    CLASSE, section.numero, _court(phrase),
                    "Phrase interdite : le business plan ne dit jamais qu'il ne peut pas "
                    "calculer sa sensibilité. Le scénario à −10 % et à −20 % de chiffre "
                    "d'affaires se calcule depuis la mémoire de l'étude (charges fixes "
                    "inchangées, charges variables au taux de marge) : écrire le résultat, "
                    "pas l'impossibilité.",
                ))
    return constats


def _court(texte: str, plafond: int = 200) -> str:
    texte = " ".join(texte.split())
    if len(texte) <= plafond:
        return texte
    tete = texte[:plafond]
    return tete[: tete.rfind(" ")] if " " in tete else tete


# ── Les deux scénarios ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Passage:
    section: Section
    texte: str
    #: Le tableau entier, quand le passage en est une ligne ou l'en-tête : un
    #: scénario en colonne porte ses montants dans les lignes.
    tableau: Tableau | None = None


def _passages(document: Document) -> Iterator[_Passage]:
    for section in document.sections:
        for paragraphe in section.paragraphes:
            for phrase in _phrases(paragraphe):
                yield _Passage(section, phrase)
        for tableau in section.tableaux:
            for ligne in (tableau.entetes, *tableau.lignes):
                yield _Passage(section, " | ".join(ligne), tableau)


def _scenarios_chiffres(document: Document) -> set[int]:
    """Les baisses exigées pour lesquelles le document écrit un scénario CHIFFRÉ."""
    montant = _montant_re()
    trouves: set[int] = set()
    for passage in _passages(document):
        baisses = _baisses(passage.texte) & set(BAISSES_EXIGEES)
        if not baisses or renonce_au_calcul(passage.texte):
            continue
        cadre = f"{passage.section.titre} {passage.texte}"
        if passage.tableau is not None:
            cadre += " " + " ".join(passage.tableau.entetes)
        if not _CHIFFRE_D_AFFAIRES.search(cadre):
            continue
        chiffre = passage.texte if passage.tableau is None else " ".join(
            " ".join(ligne) for ligne in passage.tableau.lignes
        )
        if montant.search(chiffre):
            trouves |= baisses
    return trouves


def _section_de_sensibilite(document: Document) -> Section | None:
    """Où le lecteur cherche la sensibilité : la section qui la titre, sinon le
    chapitre du prévisionnel."""
    for section in document.sections:
        if _SENSIBILITE.search(section.titre):
            return section
    for section in document.sections:
        if section.numero.startswith("ch.") and re.search(r"(?i)pr[ée]visionnel", section.titre):
            return section
    return None


def _scenarios_manquants(document: Document) -> list[Constat]:
    manquants = [b for b in BAISSES_EXIGEES if b not in _scenarios_chiffres(document)]
    if not manquants:
        return []
    section = _section_de_sensibilite(document) or (
        document.sections[-1] if document.sections else None
    )
    if section is None:
        return []
    ecrit = " ".join([*(s.titre for s in document.sections), document.texte()])
    annonces = sorted(b for b in _baisses(ecrit) & set(BAISSES_EXIGEES) if b in manquants)
    precision = (
        f" ({', '.join(f'−{b} %' for b in annonces)} annoncé sans un seul montant)"
        if annonces else ""
    )
    return [Constat(
        CLASSE, section.numero, section.titre or section.numero,
        f"Scénario(s) de sensibilité manquant(s) : {', '.join(f'−{b} %' for b in manquants)} "
        f"de chiffre d'affaires{precision}. Un business plan présente le compte de résultat à "
        "−10 % ET à −20 % de chiffre d'affaires, chiffré depuis la mémoire de l'étude : "
        "chiffre d'affaires, charges, résultat net pour chaque exercice.",
    )]


# ── Le contrôle ─────────────────────────────────────────────────────────────


def controler(document: Document, reference: Reference) -> list[Constat]:
    from catalog.models import DeliverableType  # noqa: PLC0415

    if reference.livrable != DeliverableType.BUSINESS_PLAN:
        return []
    constats = _renoncements(document)
    if reference.document_entier:
        constats += _scenarios_manquants(document)
    return constats
