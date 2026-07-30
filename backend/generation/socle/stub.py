"""Socle de démonstration déterministe, pour le développement et la CI.

Ne produit QUE des identifiants effectivement listés dans le prompt reçu :
le bouchon ne peut donc pas, par construction, fabriquer un socle hors
référentiel et masquer une régression du validateur.
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

_BRIEF = re.compile(r"^BRIEF_CLIENT :\n(\{.*?\n\})", re.MULTILINE | re.DOTALL)


def _brief_client(prompt: str) -> dict[str, str]:
    """Variables du brief, relues dans le prompt.

    Le bouchon ne devine rien : il ne restitue que ce qu'on lui a donné, au
    même titre que les identifiants du référentiel. Un brief illisible rend un
    dictionnaire vide et les valeurs de repli s'appliquent.
    """
    trouve = _BRIEF.search(prompt)
    if trouve is None:
        return {}
    try:
        charge: Any = json.loads(trouve.group(1))
    except json.JSONDecodeError:
        return {}
    if not isinstance(charge, dict):
        return {}
    return {str(cle): str(valeur) for cle, valeur in charge.items() if valeur}

_LIGNE_ID = re.compile(
    r"^- `(?P<id>[a-z0-9_]+)` — (?P<libelle>.+)\n"
    r"\s+périmètre imposé : (?P<perimetre>\w+) \| unité : (?P<unite>[^|]+)\|",
    re.MULTILINE,
)

#: Valeurs de démonstration. Choisies pour respecter les contrôles croisés :
#: monde > continent, et TAM ≥ SAM ≥ SOM une fois ramenés en unités de base.
_VALEURS: dict[str, float] = {
    "marche_mondial_taille": 381.5,
    "marche_mondial_projection": 578.5,
    "segment_premium_mondial_taille": 32.0,
    "marche_continental_taille": 37.3,
    "marche_continental_projection": 57.0,
    "production_continentale": 4.4,
    "marche_national_taille": 5.92,
    "production_nationale": 6.16,
    "marche_regional_taille": 1.2,
    "tam": 4.0,
    "sam": 0.25,
    "som": 0.0003,
    "panier_moyen": 4000.0,
}

_DEFAUTS_PAR_FAMILLE: dict[str, tuple[float, str]] = {
    "pourcentage": (4.5, "%"),
    "effectif": (12064.0, "unite"),
    "duree": (6.0, "mois"),
    "ratio": (3.5, "note_sur_5"),
}


def _unite_et_valeur(identifiant: str, hint_unite: str) -> tuple[float, str]:
    hint = hint_unite.strip().lower()
    if hint.startswith("montant"):
        return _VALEURS.get(identifiant, 1.0), "MdEUR"
    for famille, (valeur, unite) in _DEFAUTS_PAR_FAMILLE.items():
        if famille in hint or unite in hint:
            return _VALEURS.get(identifiant, valeur), unite
    return _VALEURS.get(identifiant, 1.0), "unite"


def socle_de_demonstration(prompt: str) -> dict[str, object]:
    """Construit un socle valide à partir du référentiel présent dans le prompt."""
    donnees: list[dict[str, object]] = []
    for correspondance in _LIGNE_ID.finditer(prompt):
        identifiant = correspondance.group("id")
        valeur, unite = _unite_et_valeur(identifiant, correspondance.group("unite"))
        donnees.append(
            {
                "id": identifiant,
                "libelle": correspondance.group("libelle").strip(),
                "valeur": valeur,
                "unite": unite,
                "annee": date.today().year - 1,
                "perimetre": correspondance.group("perimetre"),
                "source": "Jeu de démonstration",
                "fiabilite": "observee",
                "derivee_de": [],
            }
        )

    brief = _brief_client(prompt)
    return {
        # Lus dans le BRIEF_CLIENT du prompt, et non écrits en dur. Le bouchon
        # renvoyait « secteur de démonstration » quelle que soit la demande :
        # le secteur ne descendait donc jamais jusqu'aux chapitres, qui s'en
        # servent pour choisir leurs graphiques. Deux aperçus produits pour des
        # métiers opposés sortaient rigoureusement identiques — même taille,
        # mêmes figures — et ne pouvaient rien montrer de l'adaptation.
        "secteur": brief.get("SECTEUR") or "secteur de démonstration",
        "zone": {
            "pays": brief.get("PAYS") or "France",
            "region": brief.get("REGION") or "",
            "ville": brief.get("ZONE") or brief.get("VILLE") or "",
        },
        "date_socle": date.today().isoformat(),
        "donnees": donnees,
        "segments_clientele": [
            {
                "nom": "Segment principal",
                "description": "Clientèle cœur de cible du projet.",
                "besoin_dominant": "Qualité et accompagnement",
                "part_estimee": 60.0,
            }
        ],
        "concurrents": [
            {"nom": "Acteur A", "type": "direct", "positionnement": "généraliste", "source": ""},
            {"nom": "Acteur B", "type": "indirect", "positionnement": "spécialiste", "source": ""},
        ],
        # QUATRE tendances DATÉES. `_frise` refuse en dessous de deux horizons :
        # « une frise sans date n'est pas une frise ». Avec une seule tendance,
        # la chronologie ne sortait jamais.
        "tendances": [
            {
                "intitule": "Montée de la demande premium",
                "horizon": "2026",
                "description": "Tendance de démonstration.",
                "source": "",
            },
            {
                "intitule": "Structuration des canaux en ligne",
                "horizon": "2027",
                "description": "Tendance de démonstration.",
                "source": "",
            },
            {
                "intitule": "Exigence de traçabilité et de preuve",
                "horizon": "2028",
                "description": "Tendance de démonstration.",
                "source": "",
            },
            {
                "intitule": "Consolidation des acteurs de la zone",
                "horizon": "2030",
                "description": "Tendance de démonstration.",
                "source": "",
            },
        ],
        # QUATRE risques notés, et non un seul. `_matrice` et `_chaleur`
        # exigent au moins deux risques portant probabilité ET impact : avec
        # un seul, la matrice de positionnement et la carte de chaleur étaient
        # refusées à chaque chapitre. L'aperçu ne sortait que six types de
        # graphiques sur quatorze, et donnait à croire que le rendu les
        # perdait — alors qu'il n'avait rien à tracer.
        "risques": [
            {
                "intitule": "Notoriété insuffisante",
                "probabilite": 3,
                "impact": 4,
                "description": "Risque de démonstration.",
            },
            {
                "intitule": "Dépendance à un canal d'acquisition",
                "probabilite": 4,
                "impact": 3,
                "description": "Risque de démonstration.",
            },
            {
                "intitule": "Pression sur la marge unitaire",
                "probabilite": 3,
                "impact": 5,
                "description": "Risque de démonstration.",
            },
            {
                "intitule": "Évolution réglementaire du secteur",
                "probabilite": 2,
                "impact": 4,
                "description": "Risque de démonstration.",
            },
        ],
    }
