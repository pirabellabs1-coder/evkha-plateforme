"""Référentiel fermé des identifiants de données du socle.

Pourquoi une liste fermée
-------------------------
Le moteur actuel dérive la clé d'un fait du libellé rencontré dans la prose
(`coherence._normalize_key`). Deux formulations du même indicateur produisent
donc deux faits distincts, qui ne peuvent alors plus se contredire — donc ne
sont jamais détectés comme incohérents. C'est la faille centrale relevée en 7.3
de la cartographie.

Une liste fermée supprime cette classe de défaut : un chiffre porte un
identifiant choisi dans un ensemble connu à l'avance, ou il n'entre pas dans le
socle. Deux chapitres qui parlent de la taille du marché national désignent
forcément `marche_national_taille`, et une divergence devient mécaniquement
détectable.

Provenance
----------
Les identifiants de l'étude de marché sont dérivés du livrable de référence
« Etude_de_marche_Joalie_EVKHA_2026_v4.docx » (21 chapitres), seul document
validé par la cliente dont nous disposions. Ils sont volontairement
**sectoriellement neutres** : `marche_national_taille` vaut pour la joaillerie
comme pour la restauration.

Ce référentiel est une proposition à amender avec la cliente. Le modifier est
sans risque tant qu'aucun socle n'a été produit ; après, voir
`socle/services.py` (la régénération invalide les chapitres).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from catalog.models import DeliverableType


class Perimetre(StrEnum):
    """Échelle géographique d'une donnée.

    `ENTREPRISE` couvre les données propres au porteur de projet (panier
    moyen observé, nombre de références en catalogue) : ce ne sont pas des
    données de marché, mais elles doivent être verrouillées au même titre.
    """

    MONDE = "monde"
    CONTINENT = "continent"
    NATIONAL = "national"
    REGIONAL = "regional"
    ENTREPRISE = "entreprise"


class Fiabilite(StrEnum):
    """Statut d'une donnée, repris de la convention du livrable de référence.

    Le document Joalie affiche cette distinction au lecteur dans son
    « mode d'emploi de l'étude » ; elle doit donc exister dans le socle pour
    pouvoir être rendue.
    """

    OBSERVEE = "observee"        # chiffre publié par une source identifiée
    ESTIMEE = "estimee"          # fourchette construite par triangulation
    SCENARIO = "scenario"        # hypothèse explicite, pas une prévision
    DECLAREE = "declaree"        # fournie par le client dans son brief


class FamilleUnite(StrEnum):
    """Nature de l'unité attendue, contrôlée à la validation.

    Empêche qu'un taux de croissance arrive en milliards d'euros — défaut
    réellement observé sur le pipeline actuel (confusion mondial/continental).
    """

    MONETAIRE = "monetaire"      # EUR, MEUR, MdEUR, USD, MdUSD…
    POURCENTAGE = "pourcentage"  # %
    EFFECTIF = "effectif"        # nombre d'entreprises, d'emplois, d'habitants
    DUREE = "duree"              # mois, années
    RATIO = "ratio"              # sans unité


@dataclass(frozen=True)
class DefinitionDonnee:
    """Un emplacement du socle : ce que le modèle a le droit de renseigner."""

    identifiant: str
    libelle: str
    perimetre: Perimetre
    famille_unite: FamilleUnite
    #: Un socle sans cette donnée est refusé. Réservé aux chiffres qui
    #: structurent l'étude entière ; tout le reste est facultatif.
    obligatoire: bool = False
    #: Chapitres du livrable qui exploitent cette donnée. Purement
    #: documentaire : sert à instruire le prompt et à tracer la couverture.
    chapitres: tuple[int, ...] = field(default_factory=tuple)
    commentaire: str = ""


# ── Étude de marché ──────────────────────────────────────────────────────────
# Dérivé des chapitres 1, 2, 9, 10, 14, 16 et 17 du livrable Joalie.

_EM: tuple[DefinitionDonnee, ...] = (
    # Chapitre 1 — marché mondial et continent pertinent
    DefinitionDonnee(
        "marche_mondial_taille", "Taille du marché mondial",
        Perimetre.MONDE, FamilleUnite.MONETAIRE, obligatoire=True,
        chapitres=(1, 8, 9),
        commentaire="Périmètre large du secteur. Ne sert jamais à calculer le marché accessible.",
    ),
    DefinitionDonnee(
        "marche_mondial_croissance", "Croissance annuelle du marché mondial",
        Perimetre.MONDE, FamilleUnite.POURCENTAGE, obligatoire=True,
        chapitres=(1, 8),
    ),
    DefinitionDonnee(
        "marche_mondial_projection", "Taille projetée du marché mondial à l'horizon",
        Perimetre.MONDE, FamilleUnite.MONETAIRE, chapitres=(1, 8),
    ),
    DefinitionDonnee(
        "segment_premium_mondial_taille", "Taille mondiale du segment premium visé",
        Perimetre.MONDE, FamilleUnite.MONETAIRE, chapitres=(1, 9),
        commentaire="Sous-ensemble du marché mondial réellement proche du projet.",
    ),
    DefinitionDonnee(
        "segment_premium_mondial_croissance", "Croissance du segment premium mondial",
        Perimetre.MONDE, FamilleUnite.POURCENTAGE, chapitres=(1, 9),
    ),
    # Chapitre 1 — continent
    DefinitionDonnee(
        "marche_continental_taille", "Taille du marché sur le continent pertinent",
        Perimetre.CONTINENT, FamilleUnite.MONETAIRE, obligatoire=True,
        chapitres=(1, 9),
        commentaire="JAMAIS égal au marché mondial. Distinction imposée par le prompt actuel.",
    ),
    DefinitionDonnee(
        "marche_continental_croissance", "Croissance du marché continental",
        Perimetre.CONTINENT, FamilleUnite.POURCENTAGE, chapitres=(1,),
    ),
    DefinitionDonnee(
        "marche_continental_projection", "Taille projetée du marché continental",
        Perimetre.CONTINENT, FamilleUnite.MONETAIRE, chapitres=(1, 8),
    ),
    DefinitionDonnee(
        "production_continentale", "Production du secteur sur le continent",
        Perimetre.CONTINENT, FamilleUnite.MONETAIRE, chapitres=(1,),
    ),
    # Chapitre 2 — national
    DefinitionDonnee(
        "marche_national_taille", "Taille du marché national",
        Perimetre.NATIONAL, FamilleUnite.MONETAIRE, obligatoire=True,
        chapitres=(2, 9, 14, 16),
    ),
    DefinitionDonnee(
        "marche_national_croissance", "Croissance annuelle du marché national",
        Perimetre.NATIONAL, FamilleUnite.POURCENTAGE, obligatoire=True,
        chapitres=(2, 8, 9),
    ),
    DefinitionDonnee(
        "production_nationale", "Production nationale du secteur",
        Perimetre.NATIONAL, FamilleUnite.MONETAIRE, chapitres=(2, 9),
    ),
    DefinitionDonnee(
        "production_nationale_croissance", "Croissance de la production nationale",
        Perimetre.NATIONAL, FamilleUnite.POURCENTAGE, chapitres=(2, 9),
    ),
    DefinitionDonnee(
        "emplois_secteur_national", "Emplois du secteur au niveau national",
        Perimetre.NATIONAL, FamilleUnite.EFFECTIF, chapitres=(2, 4),
    ),
    DefinitionDonnee(
        "nb_entreprises_national", "Nombre d'entreprises du secteur",
        Perimetre.NATIONAL, FamilleUnite.EFFECTIF, chapitres=(2, 16),
    ),
    # Chapitre 2 — régional / local
    DefinitionDonnee(
        "marche_regional_taille", "Taille du marché sur la zone du projet",
        Perimetre.REGIONAL, FamilleUnite.MONETAIRE, chapitres=(2, 17),
    ),
    DefinitionDonnee(
        "population_zone", "Population de la zone de chalandise",
        Perimetre.REGIONAL, FamilleUnite.EFFECTIF, chapitres=(2, 10, 17),
    ),
    DefinitionDonnee(
        "frequentation_zone", "Fréquentation annuelle de la zone",
        Perimetre.REGIONAL, FamilleUnite.EFFECTIF, chapitres=(2, 17),
        commentaire="Touristes, visiteurs, passage : dépend du secteur.",
    ),
    # Chapitre 2 — marché accessible. Le trio doit être cohérent : TAM ≥ SAM ≥ SOM.
    DefinitionDonnee(
        "tam", "Marché total théorique (TAM)",
        Perimetre.NATIONAL, FamilleUnite.MONETAIRE, obligatoire=True, chapitres=(2, 14),
    ),
    DefinitionDonnee(
        "sam", "Marché adressable (SAM)",
        Perimetre.NATIONAL, FamilleUnite.MONETAIRE, obligatoire=True, chapitres=(2, 14),
    ),
    DefinitionDonnee(
        "som", "Marché atteignable par le projet (SOM)",
        Perimetre.ENTREPRISE, FamilleUnite.MONETAIRE, obligatoire=True, chapitres=(2, 14),
        commentaire="Calcul ascendant : transactions × panier moyen. "
                    "Rythme ANNUEL, jamais un cumul.",
    ),
    # Chapitre 10 / 14 — comportements et économie unitaire
    DefinitionDonnee(
        "panier_moyen", "Panier moyen constaté ou visé",
        Perimetre.ENTREPRISE, FamilleUnite.MONETAIRE, chapitres=(10, 14, 16),
    ),
    DefinitionDonnee(
        "frequence_achat", "Fréquence d'achat de la clientèle cible",
        Perimetre.ENTREPRISE, FamilleUnite.DUREE, chapitres=(10,),
    ),
    DefinitionDonnee(
        "cycle_decision", "Durée du cycle de décision d'achat",
        Perimetre.ENTREPRISE, FamilleUnite.DUREE, chapitres=(10,),
    ),
    DefinitionDonnee(
        "transactions_annuelles_cible", "Nombre de transactions annuelles visé",
        Perimetre.ENTREPRISE, FamilleUnite.EFFECTIF, chapitres=(14,),
    ),
    DefinitionDonnee(
        "taux_conversion_cible", "Taux de conversion visé",
        Perimetre.ENTREPRISE, FamilleUnite.POURCENTAGE, chapitres=(14, 15),
    ),
    DefinitionDonnee(
        "part_reachat_cible", "Part du chiffre issue du réachat ou de la recommandation",
        Perimetre.ENTREPRISE, FamilleUnite.POURCENTAGE, chapitres=(14, 15),
    ),
    # Chapitre 5 / 13 — contexte et risques chiffrés
    DefinitionDonnee(
        "evolution_couts_intrants", "Évolution du coût des intrants ou matières",
        Perimetre.NATIONAL, FamilleUnite.POURCENTAGE, chapitres=(5, 13),
    ),
    DefinitionDonnee(
        "taille_clientele_cible", "Taille de la clientèle cible",
        Perimetre.NATIONAL, FamilleUnite.EFFECTIF, chapitres=(3, 10),
    ),
)


# ── Étude de la concurrence ──────────────────────────────────────────────────
# Volontairement minimal : l'essentiel du socle EC vit dans `concurrents`,
# pas dans les données chiffrées.

_EC: tuple[DefinitionDonnee, ...] = (
    DefinitionDonnee(
        "marche_national_taille", "Taille du marché national",
        Perimetre.NATIONAL, FamilleUnite.MONETAIRE, obligatoire=True, chapitres=(1, 6),
    ),
    DefinitionDonnee(
        "marche_regional_taille", "Taille du marché sur la zone du projet",
        Perimetre.REGIONAL, FamilleUnite.MONETAIRE, chapitres=(1, 6),
    ),
    DefinitionDonnee(
        "nb_concurrents_directs", "Nombre de concurrents directs retenus",
        Perimetre.REGIONAL, FamilleUnite.EFFECTIF, obligatoire=True, chapitres=(1, 2, 3),
    ),
    DefinitionDonnee(
        "nb_concurrents_indirects", "Nombre de concurrents indirects retenus",
        Perimetre.REGIONAL, FamilleUnite.EFFECTIF, obligatoire=True, chapitres=(1, 2, 3),
    ),
    DefinitionDonnee(
        "panier_moyen", "Panier moyen du marché",
        Perimetre.REGIONAL, FamilleUnite.MONETAIRE, chapitres=(6,),
    ),
)


_PAR_LIVRABLE: dict[str, tuple[DefinitionDonnee, ...]] = {
    DeliverableType.MARKET_STUDY: _EM,
    DeliverableType.COMPETITOR_STUDY: _EC,
}


def definitions_pour(deliverable_type: str) -> tuple[DefinitionDonnee, ...]:
    """Référentiel du livrable, ou tuple vide s'il n'est pas encore couvert.

    Le business plan et la stratégie ne sont pas couverts par le lot 1 : ils
    continuent de tourner sur l'ancien moteur, drapeau `EVKHA_SOCLE_ENABLED`
    ou pas.
    """
    return _PAR_LIVRABLE.get(deliverable_type, ())


def identifiants_pour(deliverable_type: str) -> frozenset[str]:
    return frozenset(d.identifiant for d in definitions_pour(deliverable_type))


def identifiants_obligatoires(deliverable_type: str) -> frozenset[str]:
    return frozenset(d.identifiant for d in definitions_pour(deliverable_type) if d.obligatoire)


def definition(deliverable_type: str, identifiant: str) -> DefinitionDonnee | None:
    for item in definitions_pour(deliverable_type):
        if item.identifiant == identifiant:
            return item
    return None


def livrable_couvert(deliverable_type: str) -> bool:
    return bool(definitions_pour(deliverable_type))
