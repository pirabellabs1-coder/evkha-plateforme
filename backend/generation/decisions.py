"""Une décision prise dans un chapitre vaut pour tout le document.

## Le défaut, mesuré

Étude de marché à l'export, relevée par la cliente le 26/10/2026 : « le
chapitre 7 recommande la Corée, le Japon et Taïwan ; le chapitre 17 recommande
la Chine en premier ». Deux recommandations contradictoires dans un même
document, et le lecteur ne sait pas laquelle appliquer — c'est la seule chose
qu'il était venu chercher.

## Pourquoi les résumés ne suffisaient pas

Les chapitres précédents arrivent déjà au rédacteur, en résumé
(`_bloc_resumes`). Mais un résumé opérationnel raconte ce que le chapitre a
TRAITÉ ; rien n'y distingue une décision d'une observation, et rien ne dit
qu'elle est close. Le dépôt savait déjà faire ce travail pour les CHIFFRES — la
mémoire et ses repères, une valeur posée une fois et reprise à l'identique —
mais pas pour les CHOIX. C'est la même règle 5 appliquée à une autre matière :
une seule source par vérité, y compris quand la vérité est un nom de pays.

## Ce que ce module fait, et ce qu'il ne fait pas

Il EXTRAIT, de façon déterministe et sans appel au modèle, les phrases par
lesquelles un chapitre ordonne ses cibles, puis les rend au rédacteur du
chapitre suivant sous un intitulé qui dit qu'elles sont closes. Il ne juge pas
laquelle est la bonne : ce choix appartient au chapitre qui l'a pris.

Le contrôle symétrique — deux chapitres qui posent deux premières priorités
différentes — vit dans `relecture.comptages`, qui lit le document entier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

#: Ce par quoi une étude ORDONNE ses cibles. Chaque forme est un verbe de
#: décision ou un rang, jamais un simple constat : « le marché coréen croît de
#: 8 % » n'est pas une décision, « le marché coréen est retenu en premier »
#: l'est.
_DECIDE = re.compile(
    r"(?i)\b("
    r"priorit[ée]s?|prioritaires?|"
    r"recommand\w+|pr[ée]conis\w+|"
    r"retenue?s?\s+(?:comme|en|pour)|nous\s+retenons|"
    r"[àa]\s+(?:cibler|viser|aborder|attaquer|ouvrir)\s+(?:en\s+)?(?:premier|d['’]abord)|"
    r"premi[èe]re?\s+(?:cible|march[ée]|[ée]tape|zone|destination)|"
    r"cible\s+(?:primaire|principale)|"
    r"ordre\s+de\s+priorit[ée]|"
    r"par\s+ordre\s+d[ée]croissant"
    r")\b"
)

#: Un nom propre : un pays, une ville, une marque. Une décision qui ne nomme
#: rien n'en est pas une — « il faut prioriser » ne se verrouille pas.
#: Le premier mot d'une phrase est capitalisé par la ponctuation : il ne
#: compte pas.
_NOMME = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-ZÀ-Þ][\w’'-]{2,}")

#: Plafond du bloc envoyé au rédacteur. Chaque phrase coûte des jetons sur
#: CHAQUE chapitre suivant : au-delà, ce n'est plus un verrou, c'est un
#: second document. Les premières décisions prises sont les plus structurantes.
MAX_DECISIONS = 6

#: Au-delà, la phrase n'est plus une décision citable mais un paragraphe.
LONGUEUR_MAX = 320


@dataclass(frozen=True)
class Decision:
    """Une décision close, et où le lecteur la retrouve (règle 2)."""

    chapitre: int
    section: str
    phrase: str

    def ligne(self) -> str:
        return f"- chapitre {self.chapitre} ({self.section}) : « {self.phrase} »"


def decisions_du_chapitre(numero: int, payload: Any) -> list[Decision]:
    """Les décisions d'ordre que ce chapitre a prises, dans son ordre de lecture."""
    from .relecture.document import document_du_chapitre  # noqa: PLC0415
    from .relecture.valeurs import phrases_de  # noqa: PLC0415

    if not payload:
        return []
    try:
        document = document_du_chapitre(payload)
    except Exception:  # noqa: BLE001 — un payload abîmé ne tue pas un chapitre
        return []
    trouvees: list[Decision] = []
    for section in document.sections:
        for phrase in phrases_de(section):
            propre = phrase.strip()
            if len(propre) > LONGUEUR_MAX or not _DECIDE.search(propre):
                continue
            if not _NOMME.search(propre):
                continue
            trouvees.append(Decision(numero, section.numero, propre))
    return trouvees


def decisions_prises(job: Any, avant: int) -> list[Decision]:
    """Les décisions des chapitres déjà écrits, plafonnées à `MAX_DECISIONS`."""
    chapitres = (
        job.chapters.filter(chapter_number__lt=avant)
        .exclude(payload={})
        .order_by("chapter_number")
    )
    trouvees: list[Decision] = []
    for chapitre in chapitres:
        trouvees.extend(decisions_du_chapitre(chapitre.chapter_number, chapitre.payload))
        if len(trouvees) >= MAX_DECISIONS:
            break
    return trouvees[:MAX_DECISIONS]


def bloc_des_decisions(job: Any, numero: int) -> str:
    """Le bloc de consigne : ce qui est tranché ne se rejoue pas en silence."""
    try:
        prises = decisions_prises(job, numero)
    except Exception:  # noqa: BLE001 — un verrou en panne ne tue pas un chapitre
        return ""
    if not prises:
        return ""
    return (
        "DÉCISIONS DÉJÀ PRISES — elles sont closes, et le lecteur les a lues.\n"
        + "\n".join(d.ligne() for d in prises)
        + "\nSi ce chapitre doit en reprendre une, il la reprend TELLE QUELLE. "
        "S'il doit la changer, il la cite, dit en une phrase ce qui la change, "
        "et pose la nouvelle. Ce qu'il ne fait jamais : annoncer un autre ordre "
        "de priorité sans le dire — deux recommandations contradictoires dans "
        "un même document ne laissent au lecteur aucune décision à prendre."
    )
