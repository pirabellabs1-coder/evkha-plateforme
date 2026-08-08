"""Orchestration des chapitres (lot 2 de la refonte du moteur de génération).

Ce que le lot apporte, par rapport au moteur historique :

- un chapitre rend une **structure**, plus du texte libre : on sait donc
  quelles données du socle il utilise et quels graphiques il demande, sans
  analyser une chaîne de caractères ;
- un chapitre n'a le droit d'exploiter **que** des identifiants du socle
  verrouillé — c'est le contrôle qui traduit « un chapitre ne produit jamais
  un chiffre » ;
- les prompts vivent dans `prompts/<document>/chapitre_NN.md`, versionnés,
  plus dans le code ;
- l'orchestration est **générique** : le chapitrage et le nombre de tentatives
  viennent d'une entrée de configuration, jamais d'une constante ;
- chaque chapitre est une tâche Celery indépendante et idempotente, avec
  reprise exponentielle puis passage de l'étude en `intervention_requise`.

Inerte tant que `EVKHA_SOCLE_ENABLED` vaut faux : le moteur historique reste
seul en service.
"""
from __future__ import annotations

from .configuration import (
    TypeDocument,
    TypeDocumentInconnuError,
    est_declare,
    type_document,
    types_declares,
)
from .fichiers_prompts import (
    PromptIntrouvableError,
    chapitres_sans_prompt,
    charger_prompt,
    interpoler,
    rendre_prompt,
    vider_cache,
)
from .runner import (
    ChapitreInvalideError,
    construire_prompt_chapitre,
    generer_chapitre,
    payload_vers_markdown,
)
from .schema import (
    ChapitrePayload,
    Graphique,
    Section,
    TypeGraphique,
    compter_mots,
    valider_chapitre,
)
from .services import (
    SocleManquantError,
    chapitres_a_produire,
    etude_complete,
    marquer_intervention_requise,
    produire_chapitre,
    regenerer_chapitre,
    temporisation,
    variables_du_job,
)

__all__ = [
    "ChapitreInvalideError",
    "ChapitrePayload",
    "Graphique",
    "PromptIntrouvableError",
    "Section",
    "SocleManquantError",
    "TypeDocument",
    "TypeDocumentInconnuError",
    "TypeGraphique",
    "chapitres_a_produire",
    "chapitres_sans_prompt",
    "charger_prompt",
    "compter_mots",
    "construire_prompt_chapitre",
    "est_declare",
    "etude_complete",
    "generer_chapitre",
    "interpoler",
    "marquer_intervention_requise",
    "payload_vers_markdown",
    "produire_chapitre",
    "regenerer_chapitre",
    "rendre_prompt",
    "temporisation",
    "type_document",
    "types_declares",
    "valider_chapitre",
    "variables_du_job",
    "vider_cache",
]
