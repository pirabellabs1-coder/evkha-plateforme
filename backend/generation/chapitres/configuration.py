"""Configuration déclarative des types de documents.

Exigence du cahier des charges (§6.2) : « Ajouter un type de document ne doit
demander aucune modification du moteur, seulement de nouveaux fichiers de
prompts et une entrée de configuration. »

C'est donc ici, et nulle part ailleurs, qu'un type de document se déclare.
Le moteur (`runner`, `tasks`, `services`) ne connaît que ce registre : il n'y a
aucune constante `22` ni aucun `if deliverable_type == …` dans le chemin
d'exécution.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from catalog.models import DeliverableType

from ..blueprints import ChapterBlueprint, chapters_for_deliverable

#: Racine des prompts versionnés, hors du code Python.
RACINE_PROMPTS = Path(__file__).resolve().parents[3] / "prompts"


@dataclass(frozen=True)
class TypeDocument:
    """Tout ce que le moteur doit savoir d'un type de document."""

    code: str
    libelle: str
    #: Sous-dossier de `prompts/` où vivent les fichiers de ce document.
    dossier_prompts: str
    #: Nombre de tentatives par chapitre avant de déclarer l'étude bloquée.
    tentatives_max: int = 3
    #: Bornes du résumé transmis aux chapitres suivants (§6.1 : 150 à 250 mots).
    resume_mots_min: int = 150
    resume_mots_max: int = 250

    @property
    def chemin_prompts(self) -> Path:
        return RACINE_PROMPTS / self.dossier_prompts

    def chapitres(self) -> tuple[ChapterBlueprint, ...]:
        """Chapitrage du document. Donnée de configuration, jamais une constante."""
        return chapters_for_deliverable(self.code)

    def nombre_de_chapitres(self) -> int:
        return len(self.chapitres())


_REGISTRE: dict[str, TypeDocument] = {
    DeliverableType.MARKET_STUDY: TypeDocument(
        code=DeliverableType.MARKET_STUDY,
        libelle="Étude de marché",
        dossier_prompts="etude_marche",
    ),
    DeliverableType.COMPETITOR_STUDY: TypeDocument(
        code=DeliverableType.COMPETITOR_STUDY,
        libelle="Étude de la concurrence",
        dossier_prompts="etude_concurrence",
    ),
    DeliverableType.BUSINESS_PLAN: TypeDocument(
        code=DeliverableType.BUSINESS_PLAN,
        libelle="Business plan",
        dossier_prompts="business_plan",
    ),
    DeliverableType.BUSINESS_STRATEGY: TypeDocument(
        code=DeliverableType.BUSINESS_STRATEGY,
        libelle="Stratégie business",
        dossier_prompts="strategie_business",
    ),
}


class TypeDocumentInconnuError(KeyError):
    """Le type demandé n'a pas d'entrée de configuration."""


def type_document(code: str) -> TypeDocument:
    try:
        return _REGISTRE[code]
    except KeyError as erreur:
        msg = (
            f"Aucune entrée de configuration pour « {code} ». "
            f"Types déclarés : {', '.join(sorted(_REGISTRE))}."
        )
        raise TypeDocumentInconnuError(msg) from erreur


def types_declares() -> tuple[TypeDocument, ...]:
    return tuple(_REGISTRE.values())


def est_declare(code: str) -> bool:
    return code in _REGISTRE
