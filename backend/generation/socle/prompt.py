"""Construction du prompt de la passe 1 : produire le socle, rien d'autre.

Aucune rédaction n'est demandée. Le modèle ne remplit que des emplacements
déclarés dans le référentiel : c'est ce qui rend la sortie contrôlable.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date

from catalog.models import DeliverableType

from .referentiel import DefinitionDonnee, definitions_pour
from .schema import unites_hint

# Base consolidée concurrents — POINT DE CONTRÔLE du cahier des charges
# « Étude de la concurrence ». Neuf colonnes imposées, et la sélection est figée
# à 8 acteurs directs + 3 indirects.
#
# `methode_estimation` est le champ qui porte tout le chapitre 6 : sans lui, un
# acteur dont le CA n'est pas publié ne peut pas être estimé, et l'étape reste
# lettre morte. Il est donc demandé même — surtout — quand le CA est absent.
_BASE_CONCURRENTS = (
    "BASE CONSOLIDÉE CONCURRENTS (obligatoire pour cette étude).\n"
    "Renseigne `concurrents` avec EXACTEMENT 8 acteurs de type `direct` et "
    "3 de type `indirect`, soit 11. Pour chacun :\n"
    "- `nom`, `emplacement` (adresse ou ville précise), `structure` "
    "(indépendant, chaîne, franchise, groupe...), `positionnement`, `site_web` ;\n"
    "- `ca_connu` : le chiffre d'affaires PUBLIÉ avec son année "
    "(« 1,4 M€ (2024) »), ou la mention exacte « non publié ». Ne devine "
    "jamais un montant ici ;\n"
    "- `ca_source` : d'où vient ce montant. Vide si non publié ;\n"
    "- `methode_estimation` : comment ce CA POURRA être estimé si tu ne l'as "
    "pas trouvé — nombre de points de vente, volume de clients, panier moyen, "
    "fréquence d'activité, volume visible, benchmark sectoriel. Ce champ est "
    "ce qui rend l'estimation possible plus loin : ne le laisse pas vide pour "
    "un acteur sans CA publié ;\n"
    "- `fiabilite` : `haute`, `moyenne` ou `faible`, selon la qualité de la "
    "source ou de la méthode.\n"
    "Un acteur que tu ne peux pas situer et sourcer n'entre pas dans la liste : "
    "mieux vaut le remplacer par un acteur vérifiable."
)

# Règles du prévisionnel — business plan uniquement. Le pendant de
# `_BASE_CONCURRENTS` : ce que ce livrable exige de son socle et que le
# référentiel seul ne dit pas.
_PREVISIONNEL_BP = (
    "PRÉVISIONNEL FINANCIER (obligatoire pour ce business plan).\n"
    "Le prévisionnel se construit sur TROIS exercices, portés par les "
    "identifiants `_an1`, `_an2`, `_an3` du référentiel.\n"
    "- Chaque valeur du prévisionnel est un `scenario` : une hypothèse "
    "explicite, jamais une prévision observée. Les montants venus du brief "
    "(apport, emprunt, investissement) sont `declaree`.\n"
    "- Le plan de financement s'équilibre : apport + emprunt + autres "
    "ressources couvrent l'investissement total. Un découvert de départ n'est "
    "pas un montage, c'est un refus de socle.\n"
    "- Un premier exercice en perte est un scénario légitime : n'embellis pas "
    "`resultat_net_an1` pour le rendre positif.\n"
    "- Le seuil de rentabilité est un NIVEAU DE CHIFFRE D'AFFAIRES, dérivé "
    "des charges fixes et du taux de marge : déclare `derivee_de`.\n"
    "- Cohérence d'échelle : tout le prévisionnel dans la même unité "
    "monétaire. Un résultat net ne dépasse jamais le chiffre d'affaires du "
    "même exercice."
)

# Cadrage chiffré — stratégie uniquement. Presque tout vient du brief : le
# socle d'une stratégie dit ce que l'entreprise EST, pas ce que le marché vaut.
_CADRAGE_STR = (
    "CADRAGE CHIFFRÉ (stratégie d'entreprise).\n"
    "L'essentiel de ce socle vient du BRIEF : chiffre d'affaires actuel, "
    "panier moyen, marges, conversion. Fiabilité `declaree`, et rien "
    "d'inventé — une stratégie bâtie sur des chiffres supposés se retourne "
    "contre son lecteur.\n"
    "- Un projet en création n'a pas de `ca_actuel` : OMETS l'identifiant "
    "plutôt que d'y mettre zéro ou un objectif.\n"
    "- `ca_objectif_horizon` est un `scenario`, jamais une promesse, et "
    "`horizon_feuille_de_route` dit à quelle échéance il s'entend.\n"
    "- Renseigne `segments_clientele` avec les verticales du projet : nom, "
    "besoin dominant, part estimée. C'est la matière des chapitres 7 à 11."
)

_ROLE = (
    "Tu es analyste de marché. Ta seule tâche ici est de produire le SOCLE DE "
    "DONNÉES chiffrées d'une étude : les chiffres de référence sur lesquels "
    "tous les chapitres s'appuieront ensuite.\n"
    "\n"
    "Tu ne rédiges RIEN. Pas d'analyse, pas de recommandation, pas de phrase "
    "d'introduction. Tu renseignes des emplacements chiffrés.\n"
    "\n"
    "Ce socle sera verrouillé : aucun chapitre n'aura le droit de produire un "
    "chiffre de marché qui ne s'y trouve pas. Un chiffre que tu omets ici sera "
    "définitivement absent de l'étude ; un chiffre que tu inventes ici "
    "contaminera les 21 chapitres. Préfère donc omettre une donnée que la "
    "deviner."
)

_REGLES = (
    "RÈGLES ABSOLUES\n"
    "1. N'utilise QUE les identifiants du référentiel ci-dessous. Un "
    "identifiant hors liste fait rejeter tout le socle.\n"
    "2. Un identifiant = une seule valeur. Jamais de doublon.\n"
    "3. Respecte le périmètre imposé par le référentiel pour chaque "
    "identifiant. Le marché mondial et le marché continental sont deux "
    "valeurs DIFFÉRENTES : ne mets jamais la même des deux côtés.\n"
    "4. Respecte la famille d'unité imposée. Un taux de croissance s'exprime "
    "en %, jamais en milliards.\n"
    "5. `fiabilite` vaut :\n"
    "   - `observee` : chiffre publié par une source identifiée. La `source` "
    "devient alors OBLIGATOIRE (organisme + année, ex. « Insee, 2025 »).\n"
    "   - `estimee` : ordre de grandeur construit par triangulation. Explique "
    "la méthode dans `libelle`.\n"
    "   - `scenario` : hypothèse explicite, pas une prévision.\n"
    "   - `declaree` : valeur fournie par le porteur de projet dans son brief.\n"
    "6. N'invente JAMAIS de source ni d'URL. Si tu ne connais pas la source "
    "exacte, passe la donnée en `estimee` et laisse `source` vide.\n"
    "7. Une fourchette n'est pas une valeur. Si ta donnée est une fourchette, "
    "retiens la médiane dans `valeur` et indique la fourchette dans `libelle`.\n"
    "8. Emboîtement obligatoire : TAM ≥ SAM ≥ SOM, dans la même devise. Le "
    "SOM se calcule par le bas : transactions annuelles × panier moyen.\n"
    "9. `derivee_de` liste les identifiants dont un chiffre découle. Un SOM "
    "calculé à partir du panier moyen déclare `[\"panier_moyen\", "
    "\"transactions_annuelles_cible\"]`. Une donnée primaire laisse la liste vide.\n"
    "10. Toute donnée facultative que tu ne peux pas établir sérieusement doit "
    "être OMISE. Un socle court et juste vaut mieux qu'un socle complet et faux."
)


def _ligne_referentiel(item: DefinitionDonnee) -> str:
    marque = "OBLIGATOIRE" if item.obligatoire else "facultatif"
    ligne = (
        f"- `{item.identifiant}` — {item.libelle}\n"
        f"    périmètre imposé : {item.perimetre} | unité : {unites_hint(item.famille_unite)}"
        f" | {marque}"
    )
    if item.chapitres:
        ligne += f"\n    exploité par les chapitres : {', '.join(map(str, item.chapitres))}"
    if item.commentaire:
        ligne += f"\n    note : {item.commentaire}"
    return ligne


def bloc_referentiel(deliverable_type: str) -> str:
    definitions = definitions_pour(deliverable_type)
    lignes = "\n".join(_ligne_referentiel(item) for item in definitions)
    return f"RÉFÉRENTIEL DES IDENTIFIANTS ({len(definitions)} emplacements)\n{lignes}"


def construire_prompt_socle(
    *,
    deliverable_type: str,
    variables: Mapping[str, object],
    brief_recherche: str = "",
    motifs_precedents: list[str] | None = None,
) -> str:
    """Prompt utilisateur de la passe 1.

    `motifs_precedents` : en cas de nouvelle tentative, les motifs exacts du
    refus précédent. On ne redemande pas « fais mieux » — on dit ce qui a été
    refusé et pourquoi.
    """
    blocs = [
        _ROLE,
        f"DATE_DU_JOUR : {date.today().isoformat()}. Les chiffres doivent être "
        "les plus récents disponibles à cette date ; ne traite jamais une année "
        "antérieure comme l'année en cours.",
        f"BRIEF_CLIENT :\n{json.dumps(variables, ensure_ascii=False, sort_keys=True, indent=2)}",
    ]

    if brief_recherche.strip():
        blocs.append(
            "SOURCES_WEB (collectées automatiquement, à privilégier pour les "
            f"données `observee`) :\n{brief_recherche}"
        )
    else:
        blocs.append(
            "SOURCES_WEB : aucune source collectée. N'invente ni URL ni date de "
            "publication ; passe en `estimee` toute donnée que tu ne peux pas sourcer."
        )

    blocs.append(bloc_referentiel(deliverable_type))

    # Base consolidée concurrents — étude de la concurrence uniquement.
    #
    # Le référentiel EC annonce que « l'essentiel du socle EC vit dans
    # `concurrents` », et le schéma déclare bien cette liste. Mais RIEN ne la
    # demandait : ce prompt ne contenait aucune occurrence du mot concurrent.
    # La liste partait donc vide à chaque étude, et le chapitre 6 — estimation
    # des chiffres d'affaires et parts de marché — n'avait aucune matière.
    if deliverable_type == DeliverableType.COMPETITOR_STUDY:
        blocs.append(_BASE_CONCURRENTS)
    # Même mécanisme pour les deux livrables suivants : un bloc d'exigences
    # propres au métier du document, à côté du référentiel qui liste les
    # emplacements. Sans lui, la leçon de `_BASE_CONCURRENTS` se répéterait —
    # un schéma déclaré que rien ne demande part vide à chaque étude.
    elif deliverable_type == DeliverableType.BUSINESS_PLAN:
        blocs.append(_PREVISIONNEL_BP)
    elif deliverable_type == DeliverableType.BUSINESS_STRATEGY:
        blocs.append(_CADRAGE_STR)

    blocs.append(_REGLES)

    if motifs_precedents:
        motifs = "\n".join(f"- {motif}" for motif in motifs_precedents)
        blocs.append(
            "TENTATIVE PRÉCÉDENTE REFUSÉE. Corrige EXACTEMENT ces points, sans "
            f"rien changer d'autre :\n{motifs}"
        )

    blocs.append(
        "Réponds en appelant l'outil `produire_socle`. N'écris aucun texte "
        "en dehors de l'appel d'outil."
    )
    return "\n\n".join(blocs)
