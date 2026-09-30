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

from ..memoire.faits import BAISSES_DE_SENSIBILITE
from .constat import Constat, Reference
from .document import Document, Section, Tableau
from .valeurs import BAISSE

CLASSE = "sensibilite"

#: Les deux scénarios exigés (cliente, 30/09/2026).
#: Une seule liste : celle que la mémoire calcule (`faits_de_sensibilite`).
BAISSES_EXIGEES = BAISSES_DE_SENSIBILITE

#: Une baisse de N % — une seule définition, partagée avec la lecture des
#: valeurs datées, qui ne doit pas juger un scénario comme le prévisionnel.
_BAISSE = BAISSE
_CHIFFRE_D_AFFAIRES = re.compile(r"(?i)chiffres?\s+d['’]\s?affaires|\bCA\b|\bventes\b")
#: « stress-test », pas « gestion du stress » (revue du 30/09/2026).
_SENSIBILITE = re.compile(r"(?i)sensibilit|sc[ée]nario|stress[- ]test|d[ée]grad")

#: Le VERBE du calcul : « calculer », « chiffré », « modéliser »… « chiffre »,
#: nom commun, n'en est pas un ; « construire » non plus (« ne peut plus
#: construire sa deuxième salle » est une conclusion).
_VERBES = (
    r"(?:(?:re)?calcul(?:er|é|ée|és|ées|able)|chiffr(?:er|é|ée|és|ées|age|able)"
    r"|mod[ée]lis\w+|simul(?:er|é|ée|és|ées)|ventil\w+|redistribu\w+)\b"
)
#: Le LIVRABLE du calcul, qu'un renoncement dit ne pas fournir.
_LIVRABLES = (
    r"(?:compte\s+de\s+r[ée]sultat|colonne|tableau|sc[ée]nario|projection|simulation"
    r"|calcul)\b"
)
_NEGATION = r"\b(?:ne\s+|n['’]\s*)(?:[\w'’]+\s+){0,2}?"
#: La négation porte sur le calcul quand il la suit sans rien d'autre que des
#: mots-outils : « n'a pas ÉTÉ chiffré », « ne permet pas DE calculer » ; et
#: sur le livrable quand il est INDÉFINI : « ne fournit pas DE compte de
#: résultat », « ne présente AUCUN scénario ». « N'est pas LE scénario central »
#: est une conclusion (revue du 30/09/2026).
_NEGATION_DU_CALCUL = re.compile(
    rf"(?i){_NEGATION}(?:pas|jamais|plus)\s+"
    rf"(?:(?:de|d['’]|être|été|encore|le|la|les|l['’])\s*)*{_VERBES}"
    rf"|{_NEGATION}(?:(?:pas|jamais|plus)\s+(?:de\s+|d['’])|aucun\s+|aucune\s+){_LIVRABLES}"
)
#: L'obstacle invoqué, quand il porte sur le calcul : « exigerait de
#: redistribuer », « impossible de chiffrer », « faute de données », des
#: « hypothèses non arbitrées ». « Nécessiterait un apport » est une conclusion.
_OBSTACLE_AU_CALCUL = re.compile(
    rf"(?i)\b(?:exigerait|n[ée]cessiterait|supposerait|imposerait|demanderait)\s+"
    rf"(?:de\s+|d['’])?(?:[\w'’]+\s+){{0,2}}?(?:{_VERBES}|hypoth[èe]ses?\b)"
    rf"|\bimpossible\s+(?:de\s+|d['’]){_VERBES}"
    r"|\bfaute\s+(?:de\s+|d['’])(?:donn[ée]es|hypoth[èe]ses|chiffres|informations)\b"
    r"|\bhypoth[èe]ses?\b[^.;]{0,60}?\b(?:non|pas)\s+(?:encore\s+)?arbitr"
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
    # Une phrase qui donne un montant a calculé quelque chose : son
    # conditionnel est celui du scénario (« nécessiterait un apport de… »).
    return bool(_OBSTACLE_AU_CALCUL.search(phrase)) and not _montant_re().search(phrase)


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
