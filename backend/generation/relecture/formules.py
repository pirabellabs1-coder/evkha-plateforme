"""Formules écrites en toutes lettres (classe 3).

Toute phrase qui calcule — « X divisé par Y = Z », « X moins Y », « N × P » —
est recalculée ; une quantité vague (« quelques dizaines ») est confrontée à
l'ordre de grandeur qu'elle prétend décrire.

Business plan ÉCLORE `28a257bf` (30/09/2026) :
- « charges fixes de 4 785 € et une marge de 100 % : le seuil se fixe à
  24 802 € » (9.3, 16.4) — 4 785 ÷ 100 % = 4 785, pas 24 802 ;
- « 200 femmes […] rapporté au panier moyen de 141 € […] situe l'ambition de
  la troisième année » (6.4) — 28 200 €, pas 97 060 € ;
- « quelques dizaines de participantes » pour 97 060 € (5.5) — à 141 € de
  panier, il en faut près de 700.
"""
from __future__ import annotations

import re

from .constat import Constat, Reference
from .document import Document, Section
from .valeurs import (
    Nombre,
    annee_d_un_ordinal,
    en_euros,
    est_une_annee,
    fait_de,
    faits_de_la_serie,
    nombres,
    phrases_de,
    proche,
    valeurs_datees,
)


def _entier(nombre: float) -> str:
    return f"{nombre:,.0f}".replace(",", " ")


def _euros(montant: float) -> str:
    return f"{_entier(montant)} €"


# ── Le seuil de rentabilité, recalculé depuis sa propre formule ─────────────

_ROLES = (
    ("seuil", re.compile(r"(?i)seuil de rentabilit")),
    ("charges", re.compile(r"(?i)charges fixes")),
    # Le taux de marge sur coûts variables — jamais la marge de SÉCURITÉ, nette
    # ou d'EBE, qui sont d'autres grandeurs (revue du 30/09/2026).
    ("taux", re.compile(
        r"(?i)taux de marge|marge sur co[ûu]ts variables|marge brute|"
        r"\bmarge\b(?!\s+(?:de\s+s[ée]curit|nette|d.EBE|d.exploitation))"
    )),
)
#: Des charges fixes MENSUELLES ne se divisent pas comme des annuelles.
_MENSUELLES = re.compile(r"(?i)^\s*(?:€\s*)?(?:par mois|/ ?mois|mensuel)")


def _roles(phrase: str) -> dict[str, Nombre]:
    """Chaque nombre prend le rôle du dernier mot-clé qui le précède."""
    reperes = sorted(
        (m.start(), role) for role, motif in _ROLES for m in motif.finditer(phrase)
    )
    trouves: dict[str, Nombre] = {}
    for n in nombres(phrase):
        if est_une_annee(n) or n.unite is None:
            continue
        avant = [role for debut, role in reperes if debut < n.debut]
        if not avant:
            continue
        role = avant[-1]
        attendu = "%" if role == "taux" else "€"
        if (n.unite == "%") != (attendu == "%"):
            continue
        trouves.setdefault(role, n)
    return trouves


def _charges_fixes_du_document(document: Document) -> dict[int, float]:
    return {
        v.annee: v.nombre.valeur for v in valeurs_datees(document)
        if v.serie == "charges_fixes" and v.nombre.monetaire
    }


def _seuils(document: Document, reference: Reference) -> list[Constat]:
    charges_du_document = _charges_fixes_du_document(document)
    constats: list[Constat] = []
    for section in document.sections:
        textes = [*phrases_de(section), *(
            " · ".join(ligne) for tableau in section.tableaux for ligne in tableau.lignes
        )]
        for phrase in textes:
            if not re.search(r"(?i)seuil de rentabilit", phrase):
                continue
            if not re.search(r"(?i)charges fixes", phrase):
                continue  # la phrase ne pose pas la formule
            roles = _roles(phrase)
            seuil, taux = roles.get("seuil"), roles.get("taux")
            if seuil is None or taux is None or taux.valeur <= 0:
                continue
            charges = roles.get("charges")
            if charges is not None and _MENSUELLES.match(phrase[charges.fin:]):
                continue
            annees = [int(a) for a in re.findall(r"\b(20[2-6]\d)\b", phrase)]
            montant_charges = charges.valeur if charges else (
                charges_du_document.get(annees[0]) if annees else None
            )
            if montant_charges is None:
                continue
            attendu = montant_charges / (taux.valeur / 100)
            if proche(seuil.valeur, attendu, relatif=0.02, absolu=2):
                continue
            constats.append(Constat(
                "formule", section.numero, phrase[:220],
                f"Formule fausse : charges fixes ÷ taux de marge = {_euros(montant_charges)} "
                f"÷ {taux.ecriture} = {_euros(attendu)}, pas {seuil.ecriture}. Les charges "
                "fixes citées ne sont pas celles qui donnent ce seuil. Cite le seuil calculé "
                "pour l'exercice par la mémoire, sans le recalculer, ou les charges fixes "
                "complètes.",
            ))
    return constats


# ── Les opérations écrites : A ÷ B = C, A × B = C, A − B = C ────────────────

_OPERATEUR = re.compile(
    r"^\s*(÷|/|×|x|\*|−|-|\+|divis[ée]e?s? par|multipli[ée]e?s? par|moins|plus)\s*$",
    re.IGNORECASE,
)
_EGAL = re.compile(r"^\s*(=|soit|donne|font)\s*$", re.IGNORECASE)


def _valeur_operande(n: Nombre) -> float:
    return n.valeur / 100 if n.pourcentage else n.valeur


def _operations(document: Document) -> list[Constat]:
    constats: list[Constat] = []
    for section in document.sections:
        for phrase in phrases_de(section):
            lus = [n for n in nombres(phrase) if not est_une_annee(n)]
            for a, b, c in zip(lus, lus[1:], lus[2:], strict=False):
                operateur = _OPERATEUR.match(phrase[a.fin: b.debut])
                if not operateur or not _EGAL.match(phrase[b.fin: c.debut]):
                    continue
                signe = operateur.group(1).lower()
                x, y = _valeur_operande(a), _valeur_operande(b)
                baisse_ou_hausse = signe in ("−", "-", "moins", "+", "plus")
                if b.pourcentage and not a.pourcentage and baisse_ou_hausse:
                    # « 80 000 € − 10 % » : une baisse de 10 %, pas une soustraction.
                    calcul = x * (1 - y) if signe in ("−", "-", "moins") else x * (1 + y)
                elif signe in ("÷", "/") or signe.startswith("divis"):
                    if y == 0:
                        continue
                    calcul = x / y
                elif signe in ("×", "x", "*") or signe.startswith("multipli"):
                    calcul = x * y
                elif signe in ("−", "-", "moins"):
                    calcul = x - y
                else:
                    calcul = x + y
                attendu = _valeur_operande(c)
                absolu = 0.001 if c.pourcentage else 0.51
                if proche(calcul, attendu, relatif=0.01, absolu=absolu):
                    continue
                constats.append(Constat(
                    "formule", section.numero, phrase[a.debut: c.fin],
                    f"Calcul faux : {a.ecriture} {signe} {b.ecriture} ne donne pas "
                    f"{c.ecriture}. Cite le repère de la mémoire qui porte ce résultat, "
                    "ou retire l'opération.",
                ))
    return constats


# ── Un effectif × un panier, confronté à l'objectif qu'il prétend porter ────

_PERSONNES = (
    r"(femmes|participantes?|participants|clientes?|clients|personnes|inscrit\w*|"
    r"adh[ée]rent\w*)"
)
_EFFECTIF = re.compile(rf"(?i)\b(\d[\d  ]*)\s+{_PERSONNES}\b")
_OBJECTIF = re.compile(r"(?i)ambition|objectif|vis[ée]|atteindre|chiffre d.affaires")
#: Une fréquence d'achat rend le produit « effectif × panier » faux par nature.
_FREQUENCE = re.compile(r"(?i)par an\b|par mois|\bfois\b|s[ée]ances|abonnement|visites")
#: Les quantités vagues et l'intervalle qu'elles promettent.
_VAGUE = {
    re.compile(rf"(?i)\bune poign[ée]e (de |d.){_PERSONNES}"): (2, 15, "une poignée"),
    re.compile(rf"(?i)\b(quelques|des) dizaines (de |d.){_PERSONNES}"):
        (20, 99, "quelques dizaines"),
    re.compile(rf"(?i)\b(quelques|des) centaines (de |d.){_PERSONNES}"):
        (200, 999, "quelques centaines"),
    re.compile(rf"(?i)\b(quelques|des) milliers (de |d.){_PERSONNES}"):
        (2_000, 9_999, "quelques milliers"),
}


def _premiere_annee(reference: Reference) -> int | None:
    annees = [f.annee for f in faits_de_la_serie(reference.memoire, "ca_previsionnel") if f.annee]
    return min(annees) if annees else None


def _chiffre_d_affaires(reference: Reference, annee: int | None) -> float | None:
    if annee is None:
        return None
    fait = fait_de(reference.memoire, "ca_previsionnel", annee)
    return en_euros(fait) if fait else None


def _panier(reference: Reference, section: Section) -> float | None:
    memoire = reference.memoire
    if memoire is not None and "panier_moyen" in memoire.faits:
        return en_euros(memoire.faits["panier_moyen"])
    for phrase in phrases_de(section):
        m = re.search(r"(?i)panier moyen[^.€]{0,60}?(\d[\d  ,]*)\s?€", phrase)
        if m:
            return float(m.group(1).replace(" ", "").replace(" ", "").replace(",", "."))
    return None


def _annee_visee(phrase: str, reference: Reference) -> int | None:
    annees = [int(a) for a in re.findall(r"\b(20[2-6]\d)\b", phrase)]
    return annees[-1] if annees else annee_d_un_ordinal(phrase, _premiere_annee(reference))


def _ordres_de_grandeur(document: Document, reference: Reference) -> list[Constat]:
    constats: list[Constat] = []
    for section in document.sections:
        precedente = ""
        for phrase in phrases_de(section):
            panier = _panier(reference, section)
            if panier and _OBJECTIF.search(phrase):
                # « N personnes […] au panier de P € […] l'objectif de l'année A ».
                effectif = _EFFECTIF.search(phrase)
                annee = _annee_visee(phrase, reference)
                objectif = _chiffre_d_affaires(reference, annee)
                if (
                    effectif and objectif and re.search(r"(?i)panier|prix moyen", phrase)
                    and not _FREQUENCE.search(phrase)
                ):
                    n = float(re.sub(r"\D", "", effectif.group(1)))
                    produit = n * panier
                    deja_ecrit = any(
                        n_.monetaire and proche(n_.valeur, produit, relatif=0.02)
                        for n_ in nombres(phrase)
                    )
                    if n >= 2 and not deja_ecrit and not 0.7 <= produit / objectif <= 1.3:
                        constats.append(Constat(
                            "formule", section.numero, phrase[:220],
                            f"Ordre de grandeur faux : {_entier(n)} × {_euros(panier)} = "
                            f"{_euros(produit)}, pas l'objectif de {annee} "
                            f"({_euros(objectif)}) ; il faudrait environ "
                            f"{_entier(objectif / panier)} personnes. Écris l'ordre de "
                            "grandeur juste, ou retire le rapprochement.",
                            # Un achat par personne et par an est une hypothèse que la
                            # mémoire ne fait pas : un signal, jamais une reprise.
                            grave=False,
                        ))
            for motif, (bas, haut, mots) in _VAGUE.items():
                if not motif.search(phrase) or not panier:
                    continue
                contexte = f"{precedente} {phrase}"
                annee = _annee_visee(contexte, reference)
                objectif = _chiffre_d_affaires(reference, annee)
                if objectif is None:
                    montants = [
                        n.valeur for n in nombres(contexte)
                        if n.monetaire and re.search(r"(?i)chiffre d.affaires", contexte)
                    ]
                    objectif = max(montants) if montants else None
                if objectif is None:
                    continue
                besoin = objectif / panier
                if bas <= besoin <= haut:
                    continue
                constats.append(Constat(
                    "formule", section.numero, phrase[:220],
                    f"« {mots} » ne décrit pas l'ordre de grandeur : {_euros(objectif)} au "
                    f"panier de {_euros(panier)} demandent environ {_entier(besoin)} "
                    "personnes. Écris le nombre calculé, ou retire la quantité.",
                    grave=False,  # même hypothèse d'un achat par personne : un signal
                ))
            precedente = phrase
    return constats


def controler(document: Document, reference: Reference) -> list[Constat]:
    return [
        *_seuils(document, reference),
        *_operations(document),
        *_ordres_de_grandeur(document, reference),
    ]
