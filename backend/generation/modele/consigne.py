"""Le modèle de référence, traduit en consigne pour le modèle de langage.

Jusqu'ici, la consigne de forme était **la même pour les vingt-et-un
chapitres** : « chaque section porte un tableau de 3 à 5 colonnes, un encadré au
moins par chapitre ». Elle décrivait une moyenne. Or le modèle validé par la
cliente ne décrit pas une moyenne, il décrit vingt-et-une formes différentes :
le chapitre 09 aligne quatre grilles de chiffres et n'a aucun paragraphe, le 19
enchaîne treize tableaux, le 03 ouvre sur une matrice.

Le contrat ordonné (`chapitres.schema`) sait désormais *exprimer* cette suite.
Ce module la *demande* : il rend le plan du chapitre — bloc par bloc, dans
l'ordre, avec la consigne et la longueur cible de chacun — puis le chapitre
équivalent du document de référence, en exemple.

Deux principes, tirés des règles du dépôt.

1. **Une seule source** (règle 5). Le plan n'est pas retranscrit à la main : il
   est lu dans `references/modele_etude_marche.json`, le même fichier que le
   validateur de conformité utilise pour juger. Demander une forme et en
   contrôler une autre est la manière la plus sûre de ne jamais converger.

2. **Aucune troncature muette** (règle 1). L'exemple de référence est long — le
   chapitre 19 dépasse dix mille signes. Il est abrégé pour tenir dans la
   consigne, mais l'abrègement est **écrit dans le texte** : le modèle de
   langage doit savoir qu'il lit un extrait, sinon il calque la longueur de
   l'extrait au lieu de celle du modèle.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .chargement import RACINE, ModeleIntrouvableError, chapitre_du_modele

#: Extraction du document validé par la cliente. Sert d'exemple, jamais de
#: contrainte : c'est le modèle dérivé qui fait foi.
CHEMIN_REFERENCE = RACINE / "references" / "document_reference_v2.json"

#: Budget de l'exemple, en signes. Le chapitre 19 de la référence en fait plus
#: de dix mille : l'inclure entier ferait de l'exemple les trois quarts de la
#: consigne, et le coût du chapitre suivrait.
EXEMPLE_SIGNES_MAX = 3_500

#: Au-delà, une cellule de tableau de l'exemple est abrégée. Les cellules de
#: méthode de la référence font jusqu'à 600 signes ; trois d'entre elles
#: mangeraient le budget entier.
CELLULE_SIGNES_MAX = 180


@lru_cache(maxsize=1)
def charger_reference(chemin: str | None = None) -> dict[str, Any]:
    """Extraction du document de référence, mise en cache."""
    fichier = Path(chemin) if chemin else CHEMIN_REFERENCE
    if not fichier.is_file():
        msg = (
            f"Document de référence introuvable : {fichier}. Les chapitres "
            "peuvent être rédigés sans exemple, mais pas sans le savoir."
        )
        raise ModeleIntrouvableError(msg)
    try:
        return json.loads(fichier.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except json.JSONDecodeError as erreur:
        msg = f"Document de référence illisible ({fichier}) : {erreur}"
        raise ModeleIntrouvableError(msg) from erreur


def chapitre_de_reference(
    numero: int, *, chemin: str | None = None
) -> dict[str, Any] | None:
    """Chapitre du document de référence, ou None."""
    attendu = f"CHAPITRE {numero:02d}"
    for chapitre in charger_reference(chemin).get("chapitres", []):
        if chapitre.get("numero") == attendu:
            return chapitre  # type: ignore[no-any-return]
    return None


def _abreger(texte: str, maximum: int) -> str:
    """Coupe sur une frontière de mot, et le DIT."""
    texte = " ".join(str(texte).split())
    if len(texte) <= maximum:
        return texte
    coupe = texte.rfind(" ", 0, maximum)
    return (texte[:coupe] if coupe > 0 else texte[:maximum]) + " […]"


def _ligne_de_plan(rang: int, bloc: dict[str, Any]) -> str:
    """Un bloc du modèle, rendu en une ligne de consigne."""
    type_bloc = str(bloc.get("type", ""))
    consigne = str(bloc.get("consigne", "")).strip()

    if type_bloc == "titre_sous_section":
        tete = (
            f"`titre_sous_section` — numéro {bloc.get('numero', '')}, "
            f"intitulé de référence « {bloc.get('intitule_reference', '')} »"
        )
    elif type_bloc == "paragraphe":
        tete = (
            f"`paragraphe` — environ "
            f"{int(bloc.get('longueur_cible_signes', 0))} signes"
        )
    elif type_bloc == "tableau":
        entetes = [str(e) for e in (bloc.get("entetes") or [])]
        tete = (
            f"`tableau` — {int(bloc.get('nb_lignes_cible', 0))} lignes, "
            f"en-têtes de référence : {' | '.join(entetes)}"
        )
    elif type_bloc == "encadre":
        tete = (
            f"`encadre` — étiquette « {bloc.get('etiquette', '')} », environ "
            f"{int(bloc.get('longueur_cible_signes', 0))} signes"
        )
    elif type_bloc == "grille_kpi":
        tete = (
            f"`grille_kpi` — {int(bloc.get('cellules', 3))} cellules "
            "(valeur, libellé, source)"
        )
    elif type_bloc == "graphique":
        # PAS de liste de types ici, et c'est délibéré (règle 5). Le modèle
        # portait la sienne — `barres_verticales`, `courbe`, `pyramide`,
        # `jauge` — dont AUCUN de ces quatre n'existe dans
        # `chapitres.schema.TypeGraphique`. Le même prompt annonçait donc une
        # liste « imposée » qui faisait échouer la validation plus d'une fois
        # sur deux, et une liste « disponible » correcte quelques lignes plus
        # bas. Le modèle de langage suivait la première : il ne restait que
        # `barres_horizontales`, `camembert` et `matrice_positionnement` pour
        # tout un document — d'où des figures qui ne varient jamais.
        #
        # Les types appartiennent au moteur qui dessine, une seule fois, dans
        # le bloc VISUELS du prompt.
        tete = "`graphique` — type à choisir dans le catalogue VISUELS ci-dessous"
    else:
        # `ligne_source` et compagnie : produits par le rendu, pas par le
        # modèle de langage. On ne les demande pas, mais on ne les efface pas
        # non plus du plan sans le dire.
        return f"{rang}. (bloc `{type_bloc}` : produit au rendu, ne pas rédiger)"

    return f"{rang}. {tete}" + (f"\n   → {consigne}" if consigne else "")


def plan_du_chapitre(numero: int, *, chemin: str | None = None) -> str:
    """Suite ordonnée des blocs attendus pour ce chapitre.

    C'est la pièce que la consigne générique ne pouvait pas porter : une forme
    propre au chapitre, et non la moyenne des vingt-et-un.
    """
    modele = chapitre_du_modele(numero, chemin=chemin)
    if modele is None:
        return ""

    lignes = [
        _ligne_de_plan(rang, bloc)
        for rang, bloc in enumerate(modele.get("blocs", []), start=1)
    ]
    accroche = modele.get("accroche") or {}
    graphiques_min = int(modele.get("graphiques_min", 0))

    entete = [
        f"PLAN IMPOSÉ DU CHAPITRE {numero:02d} — c'est la structure du document "
        "validé par la cliente, mesurée sur lui, pas une préférence de style.",
        "Produis les blocs DANS CET ORDRE et dans ces proportions. Le champ "
        "`blocs` de ta réponse doit suivre cette suite.",
        f"Titre : {modele.get('titre_consigne', '')}",
        f"Accroche : environ {int(accroche.get('longueur_cible_signes', 0))} "
        f"signes. {accroche.get('consigne', '')}",
    ]

    # Le manuel donne, chapitre par chapitre, une épaisseur ET une intention
    # visuelle — « Courbe historique et projection » au chapitre 1, « Scorecard
    # de viabilité » au 14. C'est ce que le catalogue de types ne peut pas
    # dire : il sait dessiner, il ne sait pas QUOI montrer ici.
    pages = modele.get("volume_pages") or []
    if len(pages) == 2:
        entete.append(
            f"Épaisseur attendue : {pages[0]} à {pages[1]} pages de l'étude "
            "finale, remplies d'analyse utile — jamais par de la redite."
        )
    visuel = str(modele.get("visuel_attendu", "")).strip()
    if visuel:
        entete.append(f"Visuel attendu par le manuel : {visuel}")

    pied = (
        f"\nAu moins {graphiques_min} graphique"
        f"{'s' if graphiques_min > 1 else ''} dans ce chapitre."
        if graphiques_min
        else ""
    )
    return "\n".join(entete) + "\n\n" + "\n".join(lignes) + pied


def _bloc_en_exemple(bloc: dict[str, Any]) -> str:
    """Un bloc de la référence, rendu lisible pour un exemple."""
    type_bloc = str(bloc.get("type", ""))

    if type_bloc == "paragraphe":
        texte = str(bloc.get("texte", "")).strip()
        if not texte:
            return ""
        # L'extraction rend les titres de sous-section comme des paragraphes
        # de style Heading2. Les afficher comme du corps de texte donnerait à
        # croire que le modèle écrit « 1.1 Deux périmètres » en pleine prose.
        if str(bloc.get("style", "")).startswith("Heading"):
            return f"[titre_sous_section] {texte}"
        return f"[paragraphe] {texte}"

    if type_bloc == "tableau":
        entetes = [str(e) for e in (bloc.get("entetes") or [])]
        lignes = [
            " | ".join(_abreger(cellule, CELLULE_SIGNES_MAX) for cellule in ligne)
            for ligne in (bloc.get("lignes") or [])
        ]
        return "[tableau] " + " | ".join(entetes) + "\n  " + "\n  ".join(lignes)

    if type_bloc == "encadre":
        return (
            f"[encadre · {bloc.get('etiquette', '')}] "
            + str(bloc.get("texte", "")).strip()
        )

    if type_bloc == "grille_kpi":
        cellules = [
            " / ".join(str(c.get("contenu", "")).splitlines())
            for c in (bloc.get("cellules") or [])
        ]
        return "[grille_kpi] " + " ‖ ".join(cellules)

    # Graphiques et sauts de page : rien de rédactionnel à montrer.
    return ""


def exemple_de_reference(
    numero: int, *, chemin: str | None = None, budget: int = EXEMPLE_SIGNES_MAX
) -> str:
    """Le chapitre équivalent du document validé, en exemple de rédaction.

    Montre le NIVEAU attendu — densité des cellules, ton des encadrés, forme
    des libellés de chiffres —, jamais le contenu : la niche est différente, et
    reprendre un chiffre de la joaillerie dans une étude sur l'automobile
    serait un chiffre hors socle.
    """
    reference = chapitre_de_reference(numero, chemin=chemin)
    if reference is None:
        return ""

    morceaux: list[str] = []
    total = 0
    tronque = False
    for bloc in reference.get("blocs", []):
        rendu = _bloc_en_exemple(bloc)
        if not rendu:
            continue
        if total + len(rendu) > budget:
            tronque = True
            break
        morceaux.append(rendu)
        total += len(rendu)

    if not morceaux:
        return ""

    entete = (
        f"EXEMPLE — chapitre {numero:02d} du document de référence, rédigé sur "
        "une AUTRE niche (joaillerie). Il montre le niveau de densité et le ton "
        "attendus.\n"
        "N'en reprends AUCUN chiffre, AUCUNE source, AUCUN nom : ils "
        "appartiennent à une autre étude. Tes valeurs viennent du socle, et de "
        "lui seul."
    )
    pied = (
        "\n\n[extrait abrégé pour tenir dans la consigne — le chapitre de "
        "référence est plus long ; c'est le PLAN IMPOSÉ qui fixe la longueur, "
        "pas cet extrait]"
        if tronque
        else ""
    )
    return entete + "\n\n" + "\n".join(morceaux) + pied
