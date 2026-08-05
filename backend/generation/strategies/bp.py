"""Strategy « Business Plan » — le manuel BP.

Refonte apres retour Evangeline sur le previsionnel WAOME (21/07/2026,
applicable a tout BP) : deux defauts fiscaux/financiers qu'un banquier
detecte au premier coup d'oeil et qui detruisent la credibilite du dossier.

Cette premiere iteration verrouille deux regles :

  1. IS a 15 % applicable UNIQUEMENT sur les 42 500 premiers euros de
     benefice (Code general des impots, art. 219 I-b, taux reduit PME).
     Au-dela : 25 % (taux normal). Beaucoup de previsionnels IA ecrivent
     « IS a 15 % sur tout le benefice » — erreur classique, immediate.

  2. Remuneration dirigeante presente ET chiffree dans le previsionnel.
     Un BP sans salaire dirigeant est un dossier bancaire non serieux :
     le banquier suppose soit qu'on cache la charge, soit qu'on prevoit
     un porteur benevole (invraisemblable).

Les prochaines iterations couvriront :
  - Tresorerie cumulee reconstituable (tréso[an] ≈ tréso[an-1] + CAF -
    remboursements + variation BFR).
  - Effectif vs charges salariales (recrutement an 2 = ligne de charges
    supplémentaire).
  - Seuil de rentabilite unique (deja partiellement couvert par
    `checks_evangeline.collecter_mentions`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from catalog.models import DeliverableType
from generation.models import ChapterGeneration, GenerationJob
from generation.strategies.base import (
    ContexteSupplementaire,
    ProblemeCoherence,
)

# ══════════════════════════════════════════════════════════════════════════
# 1. IS a 15 % — tranche PME 42 500 EUR
# ══════════════════════════════════════════════════════════════════════════

# Plafond legal 2025+ (Code general des impots, art. 219 I-b). Cette
# constante est LE seuil metier — si demain le legislateur bouge, on
# corrige ici uniquement (regle 5, source unique).
_PLAFOND_IS_REDUIT_EUR = 42_500

# Motifs qui indiquent une mention d'IS a 15 %. On exige que le nombre
# « 15 » soit proche du mot « IS » ou « impot sur les societes ».
_IS_15_RE = re.compile(
    r"(?:IS|imp[oô]t\s+sur\s+les\s+soci[eé]t[eé]s|taux\s+d['’]?IS|"
    r"taux\s+r[eé]duit)"
    r"[^.\n]{0,80}?"
    r"\b15\s*%",
    re.IGNORECASE,
)

# Le contexte est LEGITIME si la phrase mentionne explicitement le plafond
# 42 500 EUR (avec espace insecable, espace fine, sans espace) OU la notion
# de tranche/premier(s) euros/plafond legal.
_TRANCHE_MENTIONNEE_RE = re.compile(
    r"42[\s\xa0]?500"
    r"|\bpremi[eè]re\s+tranche\b"
    r"|\bpremiers?\s+42"
    r"|\bplafond\s+de\s+42"
    r"|\btranche\s+r[eé]duite\b"
    r"|\btaux\s+r[eé]duit\s+PME\b"
    r"|\bart(?:icle)?\s*\.?\s*219",
    re.IGNORECASE,
)

# Contexte OPERATIONNEL du previsionnel : mots qui indiquent qu'on parle
# du calcul reel applique au projet (pas d'une reference legislative
# generique). Une mention « IS 15 % » dans un chapitre « cadre fiscal »
# purement descriptif ne doit pas declencher.
_CONTEXTE_PREVISIONNEL_RE = re.compile(
    r"\bcalcul[eé]?|\bapplique[eé]?|\bretenu[e]?|nous\s+appliquons"
    r"|\btotal\s+d['’]?IS|\bsoit\s+\d|previsionnel\s+retient",
    re.IGNORECASE,
)


def verifier_is_bracket(
    corpus_par_chapitre: dict[int, str],
) -> list[str]:
    """Chaque mention d'IS 15 % dans un contexte previsionnel doit citer
    le plafond legal de 42 500 EUR.

    Trois cas gerent la difference :
      - Mention « 15 % » sans reference legale ni contexte previsionnel :
        c'est probablement une description generique, on laisse passer.
      - Mention « 15 % » avec contexte previsionnel MAIS sans plafond :
        c'est le defaut nomme par Evangeline, signal.
      - Mention « 15 % » avec plafond 42 500 EUR cite dans les 100 chars :
        formulation correcte, on laisse passer.
    """
    problemes: list[str] = []
    for chapitre, texte in corpus_par_chapitre.items():
        for m in _IS_15_RE.finditer(texte):
            # Fenetre elargie autour du match pour chercher soit la
            # tranche, soit un contexte previsionnel.
            debut = max(0, m.start() - 60)
            fin = min(len(texte), m.end() + 100)
            fenetre = texte[debut:fin]

            if _TRANCHE_MENTIONNEE_RE.search(fenetre):
                # Formulation correcte.
                continue

            contexte_previsionnel = bool(
                _CONTEXTE_PREVISIONNEL_RE.search(fenetre)
            )
            # Si aucune mention de tranche + aucun contexte previsionnel :
            # simple description generique, on ne signale pas — mais on
            # remonte quand meme le cas « nous appliquons 15 % » sans
            # plafond, qui est le cas critique.
            if not contexte_previsionnel:
                # Cas particulier : la formulation « taux d'IS de 15 % sur
                # toute la periode » ou « taux d'IS de 15 % applique »
                # sans autre contexte reste ambigu et bancairement risque.
                # On regarde si le verbe « appliquer/retenir » ou l'adverbe
                # « toute la periode » sont pres.
                risque = re.search(
                    r"tout(?:e)?\s+(?:le|la|les)|previsionnel\s+retient",
                    fenetre, re.IGNORECASE,
                )
                if not risque:
                    continue

            problemes.append(
                f"Chapitre {chapitre} : IS a 15 % mentionne sans preciser "
                f"le plafond legal de {_PLAFOND_IS_REDUIT_EUR:_} EUR. Le "
                "taux reduit PME ne s'applique QUE sur cette premiere "
                "tranche ; au-dela, l'IS est a 25 %. Formulation correcte "
                "attendue : « 15 % sur les 42 500 premiers euros, puis "
                "25 % au-dela »."
            )
    return problemes


# ══════════════════════════════════════════════════════════════════════════
# 2. Remuneration dirigeant presente ET chiffree
# ══════════════════════════════════════════════════════════════════════════

# On cherche la mention (remuneration|salaire|traitement) + (dirigeant|
# porteur|fondateur|gerant|president|associe) OU une formulation directe
# « le porteur percevra », « le dirigeant se verse ».
_MENTION_REMUNERATION_RE = re.compile(
    r"(?:r[eé]mun[eé]ration|salaire|traitement|paie|percevoir|se\s+verse|"
    r"cotisations?\s+sociales?)"
    r"[^.\n]{0,80}?"
    r"(?:dirigeant[e]?|porteur|fondateur|fondatrice|g[eé]rant[e]?|"
    r"pr[eé]sident[e]?|associ[eé][e]?|CEO|DG)"
    r"|(?:dirigeant[e]?|porteur|fondateur|fondatrice|g[eé]rant[e]?|"
    r"pr[eé]sident[e]?)"
    r"[^.\n]{0,60}?"
    r"(?:r[eé]mun[eé]ration|salaire|per[cç]oit|per[cç]oivent|se\s+verse|"
    r"per[cç]evra|touchera|touchera[a]?)",
    re.IGNORECASE,
)

# La mention doit s'accompagner d'un chiffre (montant en EUR). Sinon, la
# formulation reste qualitative et un banquier ne peut rien en faire.
_MONTANT_PROCHE_RE = re.compile(
    r"\d[\d\s.,]{0,10}\s*(?:EUR|€|kEUR|k€|milliers|k)",
    re.IGNORECASE,
)


def verifier_remuneration_dirigeant(
    corpus_par_chapitre: dict[int, str],
) -> list[str]:
    """La remuneration dirigeante doit apparaitre au moins une fois avec
    un montant chiffre dans le corpus.

    On regarde le corpus ENTIER, pas chapitre par chapitre : le porteur
    peut ecrire son salaire dans le chapitre 7 (equipe) plutot que dans
    le chapitre 14 (previsionnel). Ce qui compte est la presence globale.
    """
    corpus_complet = "\n\n".join(corpus_par_chapitre.values())

    mentions = list(_MENTION_REMUNERATION_RE.finditer(corpus_complet))
    if not mentions:
        return [
            "Aucune mention de remuneration dirigeante dans le document. "
            "Un BP bancaire exige la remuneration de la fondatrice/du "
            "porteur, chiffree, integree aux charges du previsionnel "
            "(brut ou brut + cotisations sociales)."
        ]

    # Verifier qu'au moins UNE mention a un montant dans les 100 chars.
    for m in mentions:
        debut = max(0, m.start() - 20)
        fin = min(len(corpus_complet), m.end() + 100)
        fenetre = corpus_complet[debut:fin]
        if _MONTANT_PROCHE_RE.search(fenetre):
            return []

    return [
        "Remuneration dirigeante mentionnee mais sans montant chiffre. "
        "Un banquier attend un chiffre precis (« 2 500 EUR brut mensuel », "
        "« 30 000 EUR annuel »), pas une formulation qualitative."
    ]


# ══════════════════════════════════════════════════════════════════════════
# 3. Tresorerie cumulee reconstituable
# ══════════════════════════════════════════════════════════════════════════

# Retour Evangeline WAOME : « tresorerie fin annee 2 = 58 kEUR, fin
# annee 3 = 185 kEUR, la variation n'a pas de source identifiable ».
# Un banquier reconstitue : treso[N] = treso[N-1] + CAF - remboursements
# + variation BFR. Sans mention d'une de ces composantes dans le corpus,
# le previsionnel reste declaratif.
#
# Regle 4 : on ne fait PAS le calcul (valeurs approximees, plusieurs
# annees, formats varies). On exige juste qu'AU MOINS UNE composante
# soit citee quand une TRAJECTOIRE de tresorerie est annoncee.

# Presence du mot « tresorerie » dans le corpus — condition necessaire
# pour parler de trajectoire. Sans le mot, on ne peut pas savoir si les
# valeurs annoncees renvoient a une tresorerie ou a autre chose.
_MENTION_TRESO_MOT_RE = re.compile(r"\btr[eé]sor(?:erie)?\b", re.IGNORECASE)

# Un montant chiffre en EUR/kEUR. On compte ces montants dans une
# fenetre autour du mot « tresorerie » pour identifier les points de
# la trajectoire, qu'ils soient etiquetes « annee N » ou juste enonces
# en liste (« 12 kEUR, 58 kEUR, 185 kEUR »).
_MONTANT_EUR_RE = re.compile(
    r"\b\d[\d\s.,]{0,10}\s*(?:kEUR|k€|EUR|€|milliers)",
    re.IGNORECASE,
)

# Composantes qui permettent au lecteur de reconstituer la trajectoire.
# CAF, remboursements ou variation BFR — au moins UNE des trois.
_COMPOSANTES_RECONSTITUTION_RE = re.compile(
    r"\bCAF\b"
    r"|\bcapacite\s+d['’]?autofinancement\b"
    r"|\bremboursement[s]?\s+(?:du\s+)?(?:pr[eê]t|emprunt)\b"
    r"|\bannuit[eé]s?\s+(?:constante|de\s+pr[eê]t|d['’]emprunt)\b"
    r"|\bvariation\s+(?:du\s+)?BFR\b"
    r"|\bbesoin\s+en\s+fonds?\s+de\s+roulement\b"
    r"|\bflux\s+de\s+tr[eé]sorerie\b",
    re.IGNORECASE,
)

# Nombre minimal de mentions annuelles pour parler de « trajectoire ».
_MIN_TRAJECTOIRE = 2


def verifier_tresorerie_reconstituable(
    corpus_par_chapitre: dict[int, str],
) -> list[str]:
    """La trajectoire de tresorerie doit etre reconstituable a partir
    du corpus (au moins UNE composante mentionnee).

    Trois branches :
      - < 2 mentions de tresorerie annuelle : pas de trajectoire, silence
        (regle 4, eviter les faux positifs sur BP minimaliste).
      - Trajectoire ET au moins une composante mentionnee : silence.
      - Trajectoire ET aucune composante : signal.
    """
    corpus_complet = "\n\n".join(corpus_par_chapitre.values())

    # Cherche une fenetre autour de chaque mention de « tresorerie ».
    # Si l'une contient >= 2 montants EUR, on considere qu'une
    # trajectoire est annoncee.
    trajectoire_montants = 0
    for m in _MENTION_TRESO_MOT_RE.finditer(corpus_complet):
        debut = max(0, m.start() - 30)
        fin = min(len(corpus_complet), m.end() + 250)
        fenetre = corpus_complet[debut:fin]
        n_montants = len(_MONTANT_EUR_RE.findall(fenetre))
        if n_montants > trajectoire_montants:
            trajectoire_montants = n_montants

    if trajectoire_montants < _MIN_TRAJECTOIRE:
        return []

    if _COMPOSANTES_RECONSTITUTION_RE.search(corpus_complet):
        return []

    return [
        f"Trajectoire de tresorerie annoncee ({trajectoire_montants} valeurs "
        "chiffrees pres du mot « tresorerie ») mais aucune composante de "
        "reconstitution dans le corpus (CAF / remboursements pret / "
        "variation BFR / flux de tresorerie). Un banquier ne peut pas "
        "reconstituer treso[N] = treso[N-1] + CAF - remboursements + "
        "variation BFR. Le previsionnel reste declaratif — ajouter au "
        "moins une des composantes explicitement."
    ]


# ══════════════════════════════════════════════════════════════════════════
# 4. STRATEGY
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class BPStrategy:
    """Strategy pour le business plan."""

    deliverable_type: ClassVar[str] = DeliverableType.BUSINESS_PLAN

    def contexte_supplementaire(
        self, job: GenerationJob, chapter: ChapterGeneration
    ) -> ContexteSupplementaire | None:
        """Pas de contexte supplementaire specifique pour l'instant.

        Le BP repose deja sur `client_facts_as_context` (etat chiffre
        client verrouille) et sur le socle commun. Les prochaines
        iterations pourront injecter une checklist previsionnel
        (rappel IS bracket, cotisations sociales, tresorerie
        reconstituable) au chapitre du previsionnel.
        """
        return None

    def problemes_de_coherence(
        self, job: GenerationJob, corpus_par_chapitre: dict[int, str]
    ) -> list[ProblemeCoherence]:
        """Deux checks fiscaux/financiers a l'issue de la generation."""
        problemes: list[ProblemeCoherence] = []

        for detail in verifier_is_bracket(corpus_par_chapitre):
            # Le chapitre est cite au debut du detail.
            m = re.search(r"Chapitre (\d+)", detail)
            problemes.append(ProblemeCoherence(
                categorie="is_bracket",
                chapitre=int(m.group(1)) if m else 0,
                detail=detail,
            ))

        for detail in verifier_remuneration_dirigeant(corpus_par_chapitre):
            problemes.append(ProblemeCoherence(
                categorie="remuneration_dirigeant",
                chapitre=0,
                detail=detail,
            ))

        for detail in verifier_tresorerie_reconstituable(corpus_par_chapitre):
            problemes.append(ProblemeCoherence(
                categorie="tresorerie_non_reconstituable",
                chapitre=0,
                detail=detail,
            ))

        return problemes


def get_strategy() -> BPStrategy:
    """Point d'entree utilise par `strategies.base.get_strategy`."""
    return BPStrategy()
