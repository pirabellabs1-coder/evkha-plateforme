"""Socle de démonstration déterministe, pour le développement et la CI.

Ne produit QUE des identifiants effectivement listés dans le prompt reçu :
le bouchon ne peut donc pas, par construction, fabriquer un socle hors
référentiel et masquer une régression du validateur.
"""
from __future__ import annotations

import re
from datetime import date

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
                "source": "Bouchon EVKHA, jeu de démonstration",
                "fiabilite": "observee",
                "derivee_de": [],
            }
        )

    return {
        "secteur": "secteur de démonstration",
        "zone": {"pays": "France", "region": "Île-de-France", "ville": "Paris"},
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
        "tendances": [
            {
                "intitule": "Montée de la demande premium",
                "horizon": "2026-2030",
                "description": "Tendance de démonstration.",
                "source": "",
            }
        ],
        "risques": [
            {
                "intitule": "Notoriété insuffisante",
                "probabilite": 3,
                "impact": 4,
                "description": "Risque de démonstration.",
            }
        ],
    }
