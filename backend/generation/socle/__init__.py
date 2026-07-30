"""Socle de données verrouillé (lot 1 de la refonte du moteur de génération).

Le socle est produit AVANT toute rédaction, par un appel dédié dont la sortie
est contrainte par un schéma JSON et validée contre un référentiel fermé
d'identifiants. Une fois validé, il est immuable pour la durée de la
génération : les chapitres n'ont le droit que de l'exploiter.

Ce module ne modifie pas le moteur existant. Il est inerte tant que
`EVKHA_SOCLE_ENABLED` vaut faux.

Organisation
------------
- `referentiel` : liste fermée des identifiants, par type de livrable
- `schema`      : modèles Pydantic et contrôles croisés
- `prompt`      : construction du prompt de la passe 1
- `builder`     : appel au modèle, validation, nouvelle tentative sur refus
- `services`    : persistance, verrouillage, régénération explicite
- `stub`        : socle de démonstration déterministe (développement et CI)
"""
from __future__ import annotations

from .builder import (
    MAX_TENTATIVES,
    OUTIL_NOM,
    SocleGenerationError,
    produire_socle,
    schema_outil,
)
from .referentiel import (
    DefinitionDonnee,
    FamilleUnite,
    Fiabilite,
    Perimetre,
    definitions_pour,
    identifiants_obligatoires,
    identifiants_pour,
    livrable_couvert,
)
from .schema import DonneeSocle, Socle, SocleInvalideError, Zone, valider_socle
from .services import (
    etablir_socle,
    livrable_supporte,
    regenerer_socle,
    revalider_socle,
    socle_actif,
    socle_du_job,
    socle_verrouille,
)

__all__ = [
    "MAX_TENTATIVES",
    "OUTIL_NOM",
    "DefinitionDonnee",
    "DonneeSocle",
    "FamilleUnite",
    "Fiabilite",
    "Perimetre",
    "Socle",
    "SocleGenerationError",
    "SocleInvalideError",
    "Zone",
    "definitions_pour",
    "etablir_socle",
    "identifiants_obligatoires",
    "identifiants_pour",
    "livrable_couvert",
    "livrable_supporte",
    "produire_socle",
    "regenerer_socle",
    "revalider_socle",
    "schema_outil",
    "socle_actif",
    "socle_du_job",
    "socle_verrouille",
    "valider_socle",
]
