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

#: Valeurs d'entreprise pour la démonstration d'un business plan ou d'une
#: stratégie. En EUR et non en MdEUR : un prévisionnel de démonstration à
#: 1,0 MdEUR par ligne passerait les contrôles (tout est égal) mais rendrait
#: des figures plates et absurdes — la répétition à blanc ne montrerait rien.
#: Les trois exercices CROISSENT : c'est ce qui donne aux courbes du
#: prévisionnel une pente à dessiner.
_VALEURS_ENTREPRISE: dict[str, float] = {
    "ca_previsionnel_an1": 135_000.0,
    "ca_previsionnel_an2": 218_000.0,
    "ca_previsionnel_an3": 320_000.0,
    "resultat_net_an1": -12_000.0,
    "resultat_net_an2": 24_000.0,
    "resultat_net_an3": 61_000.0,
    "ebe_an1": 4_000.0,
    "ebe_an2": 42_000.0,
    "ebe_an3": 88_000.0,
    "caf_an1": -2_000.0,
    "caf_an2": 31_000.0,
    "caf_an3": 72_000.0,
    "tresorerie_fin_an1": 28_000.0,
    "tresorerie_fin_an2": 47_000.0,
    "tresorerie_fin_an3": 96_000.0,
    "dette_residuelle_an1": 52_000.0,
    "dette_residuelle_an2": 38_000.0,
    "dette_residuelle_an3": 23_000.0,
    "charges_fixes_an1": 78_000.0,
    "investissement_total": 100_000.0,
    "apport": 40_000.0,
    "emprunt": 60_000.0,
    "autres_ressources": 8_000.0,
    "bfr": 14_000.0,
    "seuil_rentabilite": 190_000.0,
    "remuneration_dirigeant_an1": 24_000.0,
    "masse_salariale_an1": 36_000.0,
    "ca_actuel": 96_000.0,
    "cout_acquisition_client": 85.0,
    "valeur_vie_client": 1_400.0,
    "ca_objectif_horizon": 260_000.0,
}

#: Exercice porté par un identifiant annuel : `ca_previsionnel_an2` -> 2.
_SUFFIXE_EXERCICE = re.compile(r"_an(\d{1,2})$")


_DEFAUTS_PAR_FAMILLE: dict[str, tuple[float, str]] = {
    "pourcentage": (4.5, "%"),
    "effectif": (12064.0, "unite"),
    "duree": (6.0, "mois"),
    "ratio": (3.5, "note_sur_5"),
}


def _unite_et_valeur(identifiant: str, hint_unite: str) -> tuple[float, str]:
    hint = hint_unite.strip().lower()
    if identifiant in _VALEURS_ENTREPRISE and hint.startswith("montant"):
        return _VALEURS_ENTREPRISE[identifiant], "EUR"
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
        # Un identifiant annuel porte l'annee de SON exercice : trois points a
        # la meme annee ne font pas une serie, et la repetition a blanc ne
        # dessinerait aucune courbe du previsionnel.
        exercice = _SUFFIXE_EXERCICE.search(identifiant)
        annee = (
            date.today().year + int(exercice.group(1)) - 1
            if exercice
            else date.today().year - 1
        )
        donnees.append(
            {
                "id": identifiant,
                "libelle": correspondance.group("libelle").strip(),
                "valeur": valeur,
                "unite": unite,
                "annee": annee,
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
