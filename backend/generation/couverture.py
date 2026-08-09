"""Chaque question du client a-t-elle reçu une réponse dans l'étude ?

## Le retour qui a créé ce module

Cliente, 09/08/2026 : « éviter d'avoir une étude très complète en apparence mais
qui laisse certaines questions initiales insuffisamment traitées ».

C'est un angle mort exact. Le gate vérifie la troncature, la contamination, la
cohérence chiffrée ; la conformité vérifie la forme ; la vérification du socle
vérifie les chiffres. **Personne ne relisait le brief du client pour se demander
si on lui avait répondu.** C'est la règle 9 dans sa forme la plus littérale : ce
que le contrôle ne regarde pas est exactement là où le manque vit.

## Trois statuts, et pourquoi PARTIEL existe

    OUI     — la question est traitée, avec de quoi décider.
    PARTIEL — le sujet est abordé, la réponse ne suffit pas à décider.
    NON     — la question n'est pas traitée.

Sans PARTIEL, tout deviendrait OUI : une étude de vingt-trois chapitres
« aborde » à peu près tout. C'est précisément l'illusion que la cliente décrit —
complète en apparence. Le statut qui fait le travail ici est celui du milieu.

## Ce que ce module fait, et ce qu'il ne fait PAS encore

Il MESURE et il NOMME. Chaque question insuffisamment traitée sort avec ce qui
manque, dans un incident lisible.

Il ne relance PAS encore un approfondissement automatique. Ce n'est pas un oubli
mais une décision : un approfondissement réécrit des chapitres, donc dépense, et
ce projet a appris quatre fois de suite qu'on règle mal ce qu'on n'a pas d'abord
mesuré. La première mesure sur un dossier réel dira combien de questions sont
concernées et lesquelles — et c'est elle qui doit dicter la reprise, pas une
intuition.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

_log = logging.getLogger(__name__)

OUTIL_NOM = "rendre_couverture"
OUTIL_DESCRIPTION = (
    "Enregistre, pour chaque question posée par le client, si l'étude y répond."
)

MAX_TOKENS = 3000

#: Variables du brief qui portent une DEMANDE du client, par opposition au
#: cadrage (secteur, zone, budget). Ce sont celles-là qu'on doit avoir traitées.
CHAMPS_DE_DEMANDE = ("DEMANDES_SPECIFIQUES", "ELEMENTS_A_RETENIR", "QUESTIONS")

#: En dessous, ce n'est pas une question mais un mot-clé. Une « question » de
#: dix signes ne peut pas être jugée traitée ou non.
LONGUEUR_MINIMALE = 15


class Reponse(BaseModel):
    model_config = {"extra": "forbid"}

    question: str = Field(min_length=1)
    statut: str = Field(pattern=r"^(oui|partiel|non)$")
    #: Obligatoire hors « oui » : ce qui manque, en une phrase utilisable.
    manque: str = ""


class RapportDuModele(BaseModel):
    model_config = {"extra": "forbid"}

    reponses: list[Reponse] = Field(default_factory=list)


@dataclass
class RapportCouverture:
    traitees: list[str] = field(default_factory=list)
    insuffisantes: list[tuple[str, str, str]] = field(default_factory=list)
    passe_executee: bool = False
    motif_non_executee: str = ""

    @property
    def toutes_traitees(self) -> bool:
        return self.passe_executee and not self.insuffisantes

    def as_details(self) -> dict[str, Any]:
        return {
            "type": "couverture_des_demandes",
            "traitees": len(self.traitees),
            "insuffisantes": [
                {"question": q, "statut": s, "manque": m}
                for q, s, m in self.insuffisantes
            ],
            "passe_executee": self.passe_executee,
            "motif_non_executee": self.motif_non_executee,
        }


def questions_du_brief(variables: Any) -> list[str]:
    """Les demandes du client, découpées en questions jugeables une à une.

    Le brief les écrit en vrac — une phrase, une liste à puces, trois lignes
    séparées par des points. On découpe sur la ponctuation forte et les
    retours à la ligne, puis on écarte ce qui est trop court pour être une
    question : sans cela, « RSE » sortirait comme une demande à traiter et
    serait déclaré « non couvert » à jamais (règle 2).
    """
    if not isinstance(variables, dict):
        return []
    morceaux: list[str] = []
    for champ in CHAMPS_DE_DEMANDE:
        brut = variables.get(champ)
        if isinstance(brut, str):
            morceaux.extend(re.split(r"[\n;]+|(?<=[.?!])\s+", brut))
        elif isinstance(brut, list):
            morceaux.extend(str(item) for item in brut)
    vues: set[str] = set()
    questions: list[str] = []
    for morceau in morceaux:
        question = morceau.strip(" -•\t")
        # La clé de dédoublonnage ignore la ponctuation finale et la casse : le
        # brief écrit souvent la même demande deux fois, une fois dans
        # `DEMANDES_SPECIFIQUES` et une fois dans `ELEMENTS_A_RETENIR`, à un
        # point près. Deux fois la même question, c'est un appel de plus et un
        # incident qui compte double.
        cle = question.casefold().rstrip(" .?!:;")
        if len(question) >= LONGUEUR_MINIMALE and cle not in vues:
            vues.add(cle)
            questions.append(question)
    return questions


_SYSTEME = (
    "Tu relis une étude de marché terminée et tu vérifies qu'elle répond aux "
    "questions que le client avait posées.\n"
    "\n"
    "Pour chaque question, un statut :\n"
    "- `oui` : l'étude y répond, avec de quoi DÉCIDER — un chiffre, un "
    "critère, une recommandation datée ;\n"
    "- `partiel` : le sujet est abordé, mais la réponse ne suffit pas à "
    "décider ;\n"
    "- `non` : la question n'est pas traitée.\n"
    "\n"
    "N'accorde pas `oui` parce que le sujet est mentionné. Une étude de vingt "
    "chapitres effleure à peu près tout : c'est exactement l'illusion qu'on "
    "cherche à percer. La question est « le lecteur repart-il avec sa "
    "réponse ? », pas « le mot apparaît-il ? ».\n"
    "\n"
    "Hors `oui`, `manque` dit ce qu'il faudrait ajouter, en une phrase "
    "utilisable par le rédacteur. « Insuffisant » n'aide personne.\n"
    "\n"
    f"Tu réponds exclusivement par un appel de l'outil `{OUTIL_NOM}`."
)


def controler_la_couverture(
    *,
    client: Any,
    variables: Any,
    document: str,
) -> RapportCouverture:
    """Confronte les demandes du client au document produit.

    `document` est le texte assemblé de l'étude — ce que le lecteur lira, pas le
    payload. Juger sur autre chose que ce qui part reviendrait à contrôler un
    document que personne ne recevra (règle 3).
    """
    rapport = RapportCouverture()
    questions = questions_du_brief(variables)
    if not questions:
        # Aucune demande explicite : il n'y a rien à couvrir, et le dire est
        # différent de « tout est couvert ».
        rapport.passe_executee = True
        return rapport

    if not document.strip():
        rapport.motif_non_executee = "document vide : rien à relire"
        return rapport

    liste = "\n".join(f"{n}. {q}" for n, q in enumerate(questions, 1))
    prompt = (
        f"QUESTIONS DU CLIENT :\n{liste}\n\n"
        f"ÉTUDE PRODUITE :\n{document}\n\n"
        "Rends un statut pour CHAQUE question, sans en omettre."
    )

    try:
        resultat = client.complete_structured(
            system=_SYSTEME,
            prompt=prompt,
            outil_nom=OUTIL_NOM,
            outil_description=OUTIL_DESCRIPTION,
            schema=RapportDuModele.model_json_schema(),
            max_tokens=MAX_TOKENS,
        )
        rendu = RapportDuModele.model_validate(dict(resultat.payload))
    except Exception as erreur:  # noqa: BLE001 — une panne ici ne tue pas l'étude
        _log.exception("Contrôle de couverture impossible")
        rapport.motif_non_executee = f"{type(erreur).__name__} : {erreur}"
        return rapport

    rapport.passe_executee = True
    par_question = {r.question.strip().casefold(): r for r in rendu.reponses}

    for question in questions:
        reponse = par_question.get(question.strip().casefold())
        if reponse is None:
            # Une question non EXAMINÉE n'est pas une question traitée.
            rapport.insuffisantes.append(
                (question, "non", "question non examinée par le contrôle")
            )
        elif reponse.statut == "oui":
            rapport.traitees.append(question)
        else:
            manque = reponse.manque.strip() or "la réponse ne permet pas de décider"
            rapport.insuffisantes.append((question, reponse.statut, manque))

    return rapport
