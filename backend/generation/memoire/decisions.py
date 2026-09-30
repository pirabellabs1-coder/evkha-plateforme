"""Le registre des décisions : ce que chaque chapitre tient, sans jamais le contredire.

## Le défaut, mesuré

29/09/2026, business plan ÉCLORE. Le brief disait en une phrase « 2029 : à temps
plein, après avoir quitté son poste ». Le document a écrit « courant 2029 »,
« fin 2029 », « en 2029 », selon le chapitre ; il a annoncé « 13 acteurs
analysés » (l'étude jointe de la cliente) quand notre base en comptait 11 ; il
a présenté la TVA « par choix » au-dessus du seuil de franchise. Aucun
chapitre ne recevait de décisions : seulement le brief brut et les résumés
des chapitres précédents, que chacun reformulait à sa manière.

## Trois sources, par ordre de force

1. **Les règles** (`regles.py`) : régime de TVA et sortie du régime micro,
   calculés depuis le chiffre d'affaires de chaque exercice. Elles ne se
   discutent pas.
2. **Le socle** : le nombre de concurrents analysés est celui de la base.
3. **Le brief, mot pour mot** : les phrases du client qui fixent une date ou un
   statut sont GARDÉES telles quelles dans la mémoire. On ne les résume pas :
   c'est la reformulation qui a produit cinq dates pour un même départ.

## Tenir la décision, pas recopier la phrase (30/09/2026)

Business plan ÉCLORE `28a257bf` : la consigne « phrase du client (EQUIPE), à
reprendre telle quelle » a été suivie à la lettre. La phrase de calendrier du
brief s'imprimait SEULE, avec son intitulé « AAAA : » de prise de notes, en
12.1 et dans une cellule en 19.4 ; « phrase du client » s'imprimait
dans une cellule en 11.4. La cliente : « toute phrase brute de la mémoire
collée telle quelle » est une fuite.

Ce qui doit rester identique, c'est la DÉCISION : l'année et sa précision, le
statut, le compte. La phrase, elle, s'écrit avec les mots du document. La
justification ne porte donc plus ni la clé du brief, ni l'ordre de recopier, ni
une étiquette qu'on ne voudrait pas lire imprimée ; la consigne vit dans
l'en-tête de la liste (`etude.bloc_pour_le_redacteur`). La relecture signale ce
qui passerait encore (`relecture.fuites`).
"""
from __future__ import annotations

import re
from collections.abc import Mapping

from generation.socle.schema import Socle

from .faits import Fait
from .regles import Decision, Nature, depasse_le_plafond_micro, regime_de_tva

#: Ce qui fait d'une phrase du brief une décision de calendrier ou de statut.
_SUJETS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("statut", re.compile(
        r"(?i)\b(micro-?entreprise|auto-?entrepreneur|EURL|SASU|SARL|SAS|EI|"
        r"entreprise individuelle|trajectoire juridique|passage en société|statut)\b"
    )),
    ("calendrier", re.compile(
        r"(?i)\b(quitt\w+ (son|mon) (poste|emploi)|départ|temps plein|lancement|"
        r"immatricul\w+|création|ouverture|démarr\w+|premier(e)? (atelier|session|vente))\b"
    )),
)
_ANNEE = re.compile(r"\b(20[2-4]\d)\b")
_PHRASES = re.compile(r"(?<=[.;!?])\s+|\n+")

#: Au-delà, le registre cesse d'être lu : quelques phrases décisives valent
#: mieux qu'un second brief.
MAX_PHRASES_DU_BRIEF = 8

#: La justification d'une décision du brief, telle que le rédacteur la lit.
#: Courte, sans clé de variable ni consigne de recopie : si elle est recopiée,
#: elle se lit encore comme du français (voir la docstring du module).
JUSTIFICATION_DU_BRIEF = "choix déjà arrêté pour le projet"


def nature_de_l_activite(variables: Mapping[str, object]) -> Nature:
    """Services ou ventes, au sens des seuils fiscaux. Services par défaut.

    Le brief d'ÉCLORE le dit : « Il s'agit d'une prestation de services
    commerciale, relevant du régime BIC ». Une activité de vente de
    marchandises a d'autres seuils — les confondre fausse la TVA.
    """
    texte = " ".join(str(v) for v in variables.values() if v).lower()
    ventes = re.search(r"vente de marchandises|négoce|commerce de détail|revente", texte)
    services = re.search(r"prestations? de services?", texte)
    if ventes and not services:
        return Nature.VENTES
    return Nature.SERVICES


def _phrases_decisives(variables: Mapping[str, object]) -> list[Decision]:
    decisions: list[Decision] = []
    vues: set[str] = set()
    for valeur in variables.values():
        if not isinstance(valeur, str) or not valeur.strip():
            continue
        for phrase in _PHRASES.split(re.sub(r"[ \t]+", " ", valeur)):
            phrase = phrase.strip(" -•\t")
            if len(phrase) < 12 or len(phrase) > 320 or not _ANNEE.search(phrase):
                continue
            for sujet, motif in _SUJETS:
                if motif.search(phrase) and phrase.lower() not in vues:
                    vues.add(phrase.lower())
                    annee = _ANNEE.search(phrase)
                    decisions.append(Decision(
                        sujet, phrase, int(annee.group(1)) if annee else None,
                        JUSTIFICATION_DU_BRIEF, source="brief",
                    ))
                    break
            if len(decisions) >= MAX_PHRASES_DU_BRIEF:
                return decisions
    return decisions


def decisions_de_l_etude(
    socle: Socle, variables: Mapping[str, object], faits: Mapping[str, Fait],
) -> list[Decision]:
    """Le registre, dans l'ordre de force : règles, socle, phrases du brief."""
    decisions: list[Decision] = []
    nature = nature_de_l_activite(variables)
    texte_brief = " ".join(str(v) for v in variables.values() if v).lower()
    en_micro = bool(re.search(r"micro-?entreprise|auto-?entrepreneur", texte_brief))

    for rang in (1, 2, 3, 4, 5):
        ca = faits.get(f"ca_previsionnel_an{rang}")
        if ca is None or ca.annee is None:
            continue
        # La franchise d'une année dépend AUSSI de l'année précédente
        # (art. 293 B CGI, revue du 30/09/2026).
        precedent = faits.get(f"ca_previsionnel_an{rang - 1}")
        tva = regime_de_tva(
            ca.valeur, ca.annee, nature,
            ca_precedent=precedent.valeur if precedent is not None else None,
        )
        if tva is not None:
            decisions.append(tva)
        if en_micro:
            sortie = depasse_le_plafond_micro(ca.valeur, ca.annee, nature)
            if sortie is not None:
                decisions.append(sortie)

    directs = sum(1 for a in socle.concurrents if a.type == "direct")
    indirects = sum(1 for a in socle.concurrents if a.type == "indirect")
    if directs or indirects:
        decisions.append(Decision(
            "concurrents", f"{directs + indirects} concurrents analysés "
            f"({directs} directs, {indirects} indirects)", None,
            "compte de la base de référence ; un autre compte trouvé dans un document "
            "du client s'attribue au client, jamais à l'étude", source="socle",
        ))

    decisions.extend(_phrases_decisives(variables))
    return decisions
