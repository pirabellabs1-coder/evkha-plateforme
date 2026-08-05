"""Strategy « Business Strategy » — le manuel STR.

Consigne d'Evangeline (fiche 4, question 1) : pour une strategie
business, les 4 piliers sont TOUJOURS traites, dans le meme ordre,
avec leur objectif verbatim. La strategy STR se charge de verifier que
le document rendu les contient bien tous les quatre.

Regle 4 (viser la classe, pas l'exemple) : la regle « un STR pose ses
4 piliers » est structurelle, pas dependante d'un projet. Elle vit
donc dans la strategy STR — pas dans le socle commun, pas eparpillee.

Regle 5 (source unique) : la liste des piliers reste declaree dans
`checks_evangeline.PILIERS_STRATEGIE` parce que `prompts.py` s'en sert
aussi pour construire la consigne de generation. La strategy delegue
simplement a `verifier_piliers_strategie` — un seul endroit ou changer
un intitule si Evangeline modifie la fiche 4.
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
# Structure interne obligatoire de chaque chapitre
# ══════════════════════════════════════════════════════════════════════════
#
# Le cahier des charges « Strategies business » impose la meme ossature a TOUS
# ses chapitres : une introduction, des sous-parties nommees, un bloc de lecture
# strategique — « prendre du recul, produire une analyse directionnelle,
# identifier les consequences futures, relier les constats aux decisions » — et
# une synthese fermant sur une transition.
#
# Rien ne le verifiait. Le seul controle STR portait sur quatre chaines
# litterales cherchees dans le document entier : un chapitre pouvait sortir en
# un bloc de prose sans structure ni recul, le gate rendait `passed`.
#
# On ne verifie ici que le MECANIQUE. « L'analyse est-elle strategique ? » ne se
# controle pas par une expression reguliere, et pretendre le contraire
# produirait un motif faux — pire qu'un controle absent (regle 2).

#: Intitules admis pour le bloc de recul. La liste est ouverte a dessein : le
#: document impose la fonction, pas le titre, et le livrable est en marque
#: blanche — aucun intitule de marque ne doit y apparaitre.
_MARQUEURS_RECUL = (
    "a retenir",
    "à retenir",
    "lecture strategique",
    "lecture stratégique",
    "verdict",
)

_SOUS_TITRE_RE = re.compile(r"^#{2,4}\s+\S", re.MULTILINE)

#: Un chapitre du document porte au minimum quatre sous-parties ; on exige deux
#: sous-titres pour ne pas transformer une variation de mise en forme en echec.
_MIN_SOUS_TITRES = 2

#: Un chapitre plus court que cela n'est pas un chapitre : le signaler comme un
#: defaut de structure serait un motif faux. `_check_chapitres_avortes` du gate
#: traite deja la troncature, avec la cible de mots du blueprint.
_LONGUEUR_MINIMALE_JUGEABLE = 400


def verifier_structure_des_chapitres(
    corpus_par_chapitre: dict[int, str],
) -> list[ProblemeCoherence]:
    """Chaque chapitre redige porte ses sous-parties et son bloc de recul."""
    problemes: list[ProblemeCoherence] = []

    for numero, corps in sorted(corpus_par_chapitre.items()):
        texte = (corps or "").strip()
        if len(texte) < _LONGUEUR_MINIMALE_JUGEABLE:
            continue  # troncature : c'est l'affaire du gate, pas de la structure

        if len(_SOUS_TITRE_RE.findall(texte)) < _MIN_SOUS_TITRES:
            problemes.append(ProblemeCoherence(
                categorie="structure_chapitre",
                chapitre=numero,
                detail=(
                    f"Chapitre {numero} : moins de {_MIN_SOUS_TITRES} sous-titres. "
                    "Le cahier des charges impose a chaque chapitre une structure "
                    "interne en sous-parties nommees ; un chapitre en bloc de "
                    "prose n'est pas exploitable par un lecteur qui cherche."
                ),
            ))

        minuscules = texte.lower()
        if not any(marqueur in minuscules for marqueur in _MARQUEURS_RECUL):
            problemes.append(ProblemeCoherence(
                categorie="lecture_strategique_absente",
                chapitre=numero,
                detail=(
                    f"Chapitre {numero} : aucun bloc de recul. Le document en "
                    "impose un a chaque chapitre — prendre du recul, produire "
                    "une analyse directionnelle, identifier les consequences "
                    "futures, relier les constats aux decisions. C'est ce qui "
                    "separe une strategie d'un compte rendu."
                ),
            ))

    return problemes


@dataclass(frozen=True)
class STRStrategy:
    """Strategy pour la strategie business."""

    deliverable_type: ClassVar[str] = DeliverableType.BUSINESS_STRATEGY

    def contexte_supplementaire(
        self, job: GenerationJob, chapter: ChapterGeneration
    ) -> ContexteSupplementaire | None:
        """Pas de contexte supplementaire specifique pour l'instant.

        La consigne des 4 piliers est deja injectee dans le prompt via
        `prompts.py` (qui lit PILIERS_STRATEGIE). Le socle commun
        (client_facts_as_context) fournit le reste. Les prochaines
        iterations pourront ajouter une checklist de coherence
        pilier-par-pilier au moment du rendu de chaque chapitre.
        """
        return None

    def problemes_de_coherence(
        self, job: GenerationJob, corpus_par_chapitre: dict[int, str]
    ) -> list[ProblemeCoherence]:
        """Piliers transversaux, puis structure interne de chaque chapitre."""
        # Import lazy pour eviter le cycle strategies -> checks_evangeline
        # -> generation.models -> generation.strategies au demarrage.
        from generation.checks_evangeline import verifier_piliers_strategie  # noqa: PLC0415

        corpus_complet = "\n\n".join(corpus_par_chapitre.values())

        problemes: list[ProblemeCoherence] = [
            ProblemeCoherence(
                categorie="pilier_manquant",
                chapitre=0,  # transversal : le pilier peut manquer partout
                detail=(
                    f"{p.intitule} absent du document. Quatre axes structurants "
                    "sont toujours poses : positionnement et differenciation, "
                    "structuration de l'offre, visibilite et acquisition, "
                    "rentabilite et modele economique."
                ),
            )
            for p in verifier_piliers_strategie(corpus_complet)
        ]

        problemes.extend(verifier_structure_des_chapitres(corpus_par_chapitre))
        return problemes


def get_strategy() -> STRStrategy:
    """Point d'entree utilise par `strategies.base.get_strategy`."""
    return STRStrategy()
