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

from dataclasses import dataclass
from typing import ClassVar

from catalog.models import DeliverableType
from generation.models import ChapterGeneration, GenerationJob
from generation.strategies.base import (
    ContexteSupplementaire,
    ProblemeCoherence,
)


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
        """Verifie que les 4 piliers sont poses dans le document livre.

        Un STR sans l'un des piliers est un livrable incomplet — bloque
        le gate meme si Evangeline ne peut pas relire avant delivery.
        """
        # Import lazy pour eviter le cycle strategies -> checks_evangeline
        # -> generation.models -> generation.strategies au demarrage.
        from generation.checks_evangeline import verifier_piliers_strategie  # noqa: PLC0415

        corpus_complet = "\n\n".join(corpus_par_chapitre.values())
        manquants = verifier_piliers_strategie(corpus_complet)

        return [
            ProblemeCoherence(
                categorie="pilier_manquant",
                chapitre=0,  # transversal : le pilier peut manquer partout
                detail=(
                    f"{p.intitule} absent du document. Les 4 piliers de la "
                    "strategie sont toujours poses (fiche 4 d'Evangeline) : "
                    "Positionnement & Specialisation, Structuration de "
                    "l'offre, Planning editorial, Analyse de la tarification."
                ),
            )
            for p in manquants
        ]


def get_strategy() -> STRStrategy:
    """Point d'entree utilise par `strategies.base.get_strategy`."""
    return STRStrategy()
