"""Contrat commun aux strategies par livrable.

Interface volontairement minimale : chaque strategy ajoute uniquement ce
qui lui est SPECIFIQUE. Le socle commun reste dans les modules historiques
(`gate.py`, `checks_evangeline.py`) tant qu'ils traitent ce qui vaut pour
tous les livrables.

Regle 4 (viser la classe, pas l'exemple) : cette factorisation en modules
par livrable evite les cas particuliers eparpilles dans le socle commun.
Chaque comportement specifique vit dans SA strategy — modification locale,
propagation controlee.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from catalog.models import DeliverableType
from generation.models import ChapterGeneration, GenerationJob


@dataclass(frozen=True)
class ContexteSupplementaire:
    """Bloc de contexte a injecter dans le prompt d'un chapitre.

    Chaque strategy peut produire son propre contexte specifique — par
    exemple pour l'EM, la base chiffree consolidee produite apres les
    chapitres 1 et 2 doit reapparaitre en preambule des chapitres 3+.
    """

    intitule: str  # « BASE CHIFFREE CONSOLIDEE — reference pour tous les chapitres »
    corps: str    # contenu markdown ou texte structure
    chapitres_cibles: tuple[int, ...] = ()  # vide = tous les chapitres

    def concerne_chapitre(self, numero: int) -> bool:
        return not self.chapitres_cibles or numero in self.chapitres_cibles


@dataclass(frozen=True)
class ProblemeCoherence:
    """Un ecart mesure sur le document livre (base consolidee vs corps)."""

    categorie: str          # « arithmetique » | « chiffre_hors_base » | « source_inventee »
    chapitre: int
    detail: str
    valeur_attendue: str = ""
    valeur_trouvee: str = ""


class LivrableStrategy(Protocol):
    """Interface qu'une strategy par livrable doit exposer.

    Chaque methode est OPTIONNELLE au sens ou l'implementation par defaut
    peut renvoyer une valeur neutre. Une strategy minimale peut n'
    implementer qu'une seule methode.
    """

    deliverable_type: str

    def contexte_supplementaire(
        self, job: GenerationJob, chapter: ChapterGeneration
    ) -> ContexteSupplementaire | None:
        """Contexte specifique a injecter dans le prompt d'UN chapitre.

        Retourne None si aucun contexte n'est prevu pour ce chapitre.
        """
        ...

    def problemes_de_coherence(
        self, job: GenerationJob, corpus_par_chapitre: dict[int, str]
    ) -> list[ProblemeCoherence]:
        """Checks specifiques a executer apres generation complete.

        Executes en plus des checks du gate commun (contamination,
        verticales, coherence chiffree...). Chaque probleme retourne
        alimente le rapport gate.
        """
        ...


@dataclass(frozen=True)
class _StrategyNeutre:
    """Fallback pour un livrable qui n'a pas encore de strategy dediee.

    Ne bloque rien, n'ajoute rien : le socle commun continue d'operer
    comme avant. C'est la porte d'entree qui permet la migration
    progressive sans regression.
    """

    deliverable_type: str = "neutre"

    def contexte_supplementaire(
        self, job: GenerationJob, chapter: ChapterGeneration
    ) -> ContexteSupplementaire | None:
        return None

    def problemes_de_coherence(
        self, job: GenerationJob, corpus_par_chapitre: dict[int, str]
    ) -> list[ProblemeCoherence]:
        return []


# Registre des strategies. Import LAZY (dans get_strategy) pour eviter les
# cycles d'import : chaque strategy peut importer `checks_evangeline`, qui
# a son tour importe `models`, etc.
_STRATEGY_MODULES: dict[str, str] = {
    DeliverableType.MARKET_STUDY:     "generation.strategies.em",
    DeliverableType.COMPETITOR_STUDY: "generation.strategies.ec",
    DeliverableType.BUSINESS_PLAN:    "generation.strategies.bp",
    DeliverableType.BUSINESS_STRATEGY: "generation.strategies.str_",
}


_STRATEGY_CACHE: dict[str, LivrableStrategy] = {}


def _reset_cache() -> None:
    """Utilitaire de test : vide le cache pour re-tester une strategy
    apres modification du module. Utilise UNIQUEMENT depuis les tests."""
    _STRATEGY_CACHE.clear()


def get_strategy(deliverable_type: str) -> LivrableStrategy:
    """Retourne la strategy dediee au livrable, fallback neutre sinon.

    Le cache evite de recharger le module a chaque appel (le prompt peut
    etre reconstruit pour chaque chapitre).
    """
    from typing import cast

    if deliverable_type in _STRATEGY_CACHE:
        return _STRATEGY_CACHE[deliverable_type]

    module_path = _STRATEGY_MODULES.get(deliverable_type)
    strategy: LivrableStrategy
    if module_path is None:
        strategy = cast(LivrableStrategy, _StrategyNeutre())
    else:
        try:
            import importlib
            module = importlib.import_module(module_path)
            strategy = cast(LivrableStrategy, module.get_strategy())
        except (ImportError, AttributeError):
            # La strategy n'est pas encore migree : fallback neutre.
            strategy = cast(LivrableStrategy, _StrategyNeutre())

    _STRATEGY_CACHE[deliverable_type] = strategy
    return strategy


__all__ = [
    "ContexteSupplementaire",
    "LivrableStrategy",
    "ProblemeCoherence",
    "get_strategy",
]


# On expose `field` pour permettre aux strategies de definir des dataclasses
# avec des champs par defaut (evite un import supplementaire cote appelant).
_ = field
