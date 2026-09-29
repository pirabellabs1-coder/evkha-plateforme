"""Le questionnaire, première source de la mémoire : ce qui a été répondu, et ce qui sert.

## Pourquoi

29/09/2026 : les réponses du client étaient données en JSON brut à chaque
chapitre, sans que personne sache lesquelles servaient. Une réponse vide ne
posait aucune hypothèse : le rédacteur comblait seul, sans le dire. Et une
réponse jamais exploitée — le client a répondu, l'étude n'en dit rien — ne se
voyait nulle part.

## Ce que ce module fait

- `etat_des_reponses` : chaque question du formulaire du type d'étude,
  renseignée ou vide ;
- `hypotheses_pour_les_vides` : une réponse obligatoire vide devient une
  HYPOTHÈSE PRUDENTE nommée, jamais un arrêt de l'étude (engagement du
  29/09/2026) ;
- `questions_utilisees` : les questions dont la réponse se retrouve dans un
  texte — par ses nombres, ou par ses mots distinctifs. C'est une mesure, pas
  une preuve : elle sert au rapport interne à désigner les réponses que
  l'étude a probablement laissées de côté.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

from .regles import Decision

#: Mots trop courants pour signer une réponse.
_VIDES = frozenset(
    "avec dans pour sans sous entre leurs notre votre cette cettes elles aussi comme "
    "mais plus moins tres très tout toute tous toutes être avoir fait faire sont sera "
    "seront etre chaque ainsi alors donc apres après avant depuis pendant selon".split()
)
_MOT = re.compile(r"[a-zà-ÿ]{7,}", re.IGNORECASE)
_NOMBRE = re.compile(r"\d[\d \u00a0\u202f]{2,}(?:,\d+)?")

#: Une réponse est jugée utilisée si ce nombre de ses mots distinctifs
#: apparaissent dans le texte (ou un de ses nombres).
MOTS_DISTINCTIFS = 8
SEUIL_D_UTILISATION = 3


@dataclass(frozen=True)
class Reponse:
    code: str
    libelle: str
    obligatoire: bool
    renseignee: bool


def _plat(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in texte if not unicodedata.combining(c))


def etat_des_reponses(
    variables: Mapping[str, object], deliverable_type: str
) -> list[Reponse]:
    """Chaque question du formulaire de ce type d'étude, renseignée ou non."""
    from organisations.formulaires import formulaire  # noqa: PLC0415

    formulaire_du_type = formulaire(deliverable_type)
    if formulaire_du_type is None:
        return []
    reponses = []
    for champ in formulaire_du_type.champs:
        valeur = variables.get(champ.identifiant)
        renseignee = isinstance(valeur, str) and len(valeur.strip()) >= 2
        reponses.append(Reponse(champ.identifiant, champ.libelle, champ.obligatoire, renseignee))
    return reponses


def hypotheses_pour_les_vides(reponses: list[Reponse]) -> list[Decision]:
    """Une réponse obligatoire vide : une hypothèse prudente, nommée, jamais un arrêt."""
    return [
        Decision(
            "hypothese", f"Réponse absente à « {r.libelle} »", None,
            "toute valeur utilisée à sa place est une HYPOTHÈSE PRUDENTE : la nommer comme "
            "telle dans le chapitre, et elle figure dans l'annexe des chiffres",
            source="brief",
        )
        for r in reponses if r.obligatoire and not r.renseignee
    ]


def _signature(reponse: str) -> tuple[set[str], set[str]]:
    """Les nombres et les mots distinctifs d'une réponse."""
    nombres = {re.sub(r"[ \u00a0\u202f]", "", n) for n in _NOMBRE.findall(reponse)}
    mots = [_plat(m) for m in _MOT.findall(reponse)]
    distinctifs = []
    for mot in mots:
        if mot not in _VIDES and mot not in distinctifs:
            distinctifs.append(mot)
    return {n for n in nombres if len(n) >= 3}, set(distinctifs[:MOTS_DISTINCTIFS])


def questions_utilisees(variables: Mapping[str, object], texte: str) -> list[str]:
    """Les questions dont la réponse se retrouve dans `texte`."""
    plat = _plat(texte)
    compact = re.sub(r"[ \u00a0\u202f]", "", texte)
    utilisees = []
    for code, valeur in variables.items():
        if not isinstance(valeur, str) or len(valeur.strip()) < 2:
            continue
        nombres, mots = _signature(valeur)
        if any(n in compact for n in nombres):
            utilisees.append(code)
            continue
        if mots and sum(1 for m in mots if m in plat) >= min(SEUIL_D_UTILISATION, len(mots)):
            utilisees.append(code)
    return utilisees
