"""Construction du prompt de la passe 1 : produire le socle, rien d'autre.

Aucune rédaction n'est demandée. Le modèle ne remplit que des emplacements
déclarés dans le référentiel : c'est ce qui rend la sortie contrôlable.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date

from .referentiel import DefinitionDonnee, definitions_pour
from .schema import unites_hint

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
