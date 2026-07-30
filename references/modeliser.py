#!/usr/bin/env python3
"""Dérive le MODÈLE variabilisé depuis l'extraction du document de référence.

    python references/modeliser.py \
        references/document_reference_v2.json \
        references/modele_etude_marche.json

Le modèle n'est pas écrit à la main : il est **calculé** à partir de
`joalie_2026.docx`. Recopier un contrat de 1 400 lignes exposerait à une faute
de frappe que rien ne détecterait — aucun test ne compare le modèle à
lui-même. Ici, le modèle et la référence ne peuvent pas diverger : l'un est
produit par l'autre.

Deux choses seulement ne se déduisent pas de la référence, et sont donc
déclarées explicitement ci-dessous :

- `GRAPHIQUES_MIN` — la cliente demande 14 visuels là où l'original en portait
  8. Le supplément est réparti sur les chapitres qui le justifient ;
- `VARIABLES_GLOBALES` — les emplacements à substituer par la fiche client.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

#: Nombre minimal de graphiques par chapitre. L'original en portait 8 ; la
#: cliente en a demandé davantage une fois la densité de texte réglée. Le
#: supplément va aux chapitres où une figure apporte une lecture que le tableau
#: ne donne pas : dynamique de marché (05, 07), repères chiffrés (09),
#: comportements (10), viabilité (14) et tableau de bord (15).
GRAPHIQUES_MIN: dict[str, int] = {
    "CHAPITRE 01": 1, "CHAPITRE 02": 2, "CHAPITRE 03": 0, "CHAPITRE 04": 0,
    "CHAPITRE 05": 1, "CHAPITRE 06": 0, "CHAPITRE 07": 1, "CHAPITRE 08": 1,
    "CHAPITRE 09": 1, "CHAPITRE 10": 1, "CHAPITRE 11": 0, "CHAPITRE 12": 0,
    "CHAPITRE 13": 1, "CHAPITRE 14": 1, "CHAPITRE 15": 2, "CHAPITRE 16": 1,
    "CHAPITRE 17": 1, "CHAPITRE 18": 0, "CHAPITRE 19": 0, "CHAPITRE 20": 0,
    "CHAPITRE 21": 0,
}

TYPES_GRAPHIQUES = [
    "barres_verticales", "barres_horizontales", "courbe", "camembert",
    "pyramide", "matrice_positionnement", "jauge",
]

VARIABLES_GLOBALES = {
    "client.nom": "Nom du client final (remplace partout où le modèle disait Joalie)",
    "client.logo": "Fichier logo fourni sur la fiche client — page de garde et quatrième de couverture",
    "client.baseline": "Phrase de signature du client, quatrième de couverture",
    "client.couleur_principale": "Hex — remplace le prune 3A132C partout",
    "client.couleur_secondaire": "Hex — remplace l’or B98B4E dans les graphiques",
    "niche.libelle": "Secteur du client",
    "zone.pays": "Pays de l’étude",
    "zone.region": "Région",
    "zone.ville": "Ville",
    "date.mois_annee": "Mois et année de production",
    "socle": "Données de référence verrouillées — SEULE origine autorisée des chiffres",
}

REGLES = {
    "chiffres": "Toute valeur chiffrée provient du socle et porte un data_ref. Aucune exception.",
    "structure": (
        "La séquence de blocs de chaque chapitre est obligatoire. Tolérance : ±1 tableau "
        "et ±1 paragraphe par chapitre. Aucun bloc d’un type absent du chapitre ne peut "
        "être ajouté."
    ),
    "graphiques": (
        "Nombre minimal par chapitre défini par graphiques_min. Un graphique de plus est "
        "permis si le socle le justifie ; jamais un de moins. Palette : couleur "
        "principale, couleur secondaire, crème F1EEDB, rose D8C7CF. Fond FDFBF6, sans "
        "grille verticale, 2000 px, 200 dpi."
    ),
    "casse": (
        "Titres de chapitre en casse normale dans les données ; la mise en capitales est "
        "du ressort du rendu."
    ),
    "typographie": (
        "Apostrophes typographiques (’), espaces insécables avant : ; ! ? et dans les "
        "nombres."
    ),
    "longueurs": (
        "longueur_cible_signes = ±20 %. Le volume total du chapitre doit rester dans "
        "±15 % de la référence."
    ),
}

_NUMERO_SOUS_SECTION = re.compile(r"^(\d+\.\d+)\s+(.*)$")
_DEBUT_SOURCE = re.compile(r"^\s*sources?\s*[:—-]", re.IGNORECASE)

CONSIGNE_PARAGRAPHE = "Rédiger à partir du socle uniquement. Aucun chiffre hors socle."
CONSIGNE_TABLEAU = (
    "Conserver les en-têtes tels quels si génériques, sinon adapter à la niche. "
    "Toute valeur chiffrée provient du socle (data_refs)."
)
CONSIGNE_ENCADRE = (
    "Étiquette fixe. Le texte est une lecture stratégique propre à la niche."
)
CONSIGNE_SOUS_SECTION = (
    "Adapter l'intitulé à la niche en gardant le même angle d'analyse."
)
CONSIGNE_SOURCE = (
    "Citer la ou les sources réelles des chiffres du bloc précédent, format identique."
)
CONSIGNE_KPI = (
    "Trois indicateurs clés du chapitre, valeurs issues du socle (data_refs)."
)


def _variabiliser(bloc: dict[str, Any], precedent: dict[str, Any] | None) -> dict[str, Any] | None:
    """Transforme UN bloc de la référence en emplacement du modèle."""
    type_bloc = bloc["type"]

    if type_bloc == "saut_de_page":
        return None  # porté par `saut_de_page_final` du chapitre

    if type_bloc == "paragraphe":
        texte = bloc.get("texte", "")
        # Un Heading2 numéroté « 1.1 Intitulé » devient un titre de sous-section.
        if bloc.get("style") == "Heading2":
            trouve = _NUMERO_SOUS_SECTION.match(texte.strip())
            if trouve:
                return {
                    "type": "titre_sous_section",
                    "numero": trouve.group(1),
                    "intitule_reference": trouve.group(2).strip(),
                    "consigne": CONSIGNE_SOUS_SECTION,
                }
        # La ligne qui suit un graphique et commence par « Source » est sa
        # légende, pas un paragraphe de corps.
        if precedent is not None and precedent["type"] == "graphique" and _DEBUT_SOURCE.match(texte):
            return {"type": "ligne_source", "consigne": CONSIGNE_SOURCE}
        return {
            "type": "paragraphe",
            "longueur_cible_signes": bloc.get("signes", 0),
            "gras": bool(bloc.get("gras", False)),
            "consigne": CONSIGNE_PARAGRAPHE,
        }

    if type_bloc == "tableau":
        return {
            "type": "tableau",
            "entetes": bloc.get("entetes", []),
            "nb_lignes_cible": bloc.get("nb_lignes", 0),
            "nb_colonnes": bloc.get("nb_colonnes", 0),
            "consigne": CONSIGNE_TABLEAU,
        }

    if type_bloc == "encadre":
        return {
            "type": "encadre",
            "etiquette": bloc.get("etiquette", ""),
            "longueur_cible_signes": len(bloc.get("texte", "")),
            "consigne": CONSIGNE_ENCADRE,
        }

    if type_bloc == "graphique":
        return {
            "type": "graphique",
            "types_autorises": TYPES_GRAPHIQUES,
            "obligatoire": True,
            "spec": {
                "titre": "à définir selon la niche",
                "data_refs": ["ids du socle"],
                "largeur_px": 2000,
                "dpi": 200,
            },
        }

    if type_bloc == "grille_kpi":
        return {
            "type": "grille_kpi",
            "cellules": len(bloc.get("cellules", [])),
            "structure_cellule": ["valeur", "libelle", "source"],
            "consigne": CONSIGNE_KPI,
        }

    msg = f"Type de bloc inconnu : {type_bloc!r}. Le modèle serait incomplet."
    raise ValueError(msg)


def _blocs(blocs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    modele: list[dict[str, Any]] = []
    precedent: dict[str, Any] | None = None
    saut_final = False
    for bloc in blocs:
        if bloc["type"] == "saut_de_page":
            saut_final = True
        variabilise = _variabiliser(bloc, precedent)
        if variabilise is not None:
            modele.append(variabilise)
        precedent = bloc
    return modele, saut_final


def construire(reference: dict[str, Any]) -> dict[str, Any]:
    chapitres = []
    for chapitre in reference["chapitres"]:
        numero = chapitre["numero"]
        if numero not in GRAPHIQUES_MIN:
            msg = f"{numero} n’a pas de graphiques_min déclaré."
            raise ValueError(msg)
        blocs, saut = _blocs(chapitre["blocs"])
        chapitres.append({
            "numero": numero,
            "titre_reference": chapitre["titre"],
            "titre_consigne": (
                "Conserver le titre tel quel ; seuls les chapitres 1, 2 et 17 "
                "précisent la zone de la niche."
            ),
            "accroche": {
                "longueur_cible_signes": len(chapitre.get("accroche", "")),
                "consigne": "Une phrase de positionnement du chapitre pour cette niche.",
            },
            "graphiques_min": GRAPHIQUES_MIN[numero],
            "statistiques_reference": chapitre["statistiques"],
            "blocs": blocs,
            "saut_de_page_final": saut,
        })

    sections = {}
    for nom in ("page_de_garde", "synthese_executive", "mode_emploi"):
        blocs, _ = _blocs(reference.get(nom, []))
        sections[nom] = blocs

    return {
        "nom": "modele_etude_marche_v1",
        "type_document": "etude_de_marche",
        "statut": "MODELE DE REFERENCE — structure obligatoire, contenu variable",
        "derive_de": "references/document_reference_v2.json",
        "variables_globales": VARIABLES_GLOBALES,
        "gabarit": {
            "en_tete": "{{client.nom}}  /  ÉTUDE DE MARCHÉ {{date.annee}}",
            "pied_de_page": "{{agence.nom}}  ·  Document confidentiel  ·  {{numero_page}}",
            "note": (
                "En marque blanche, le pied de page porte le nom de l’abonné, jamais "
                "celui de la plateforme."
            ),
        },
        "page_de_garde": sections["page_de_garde"],
        "synthese_executive": {
            "titre": "Synthèse exécutive",
            "blocs": sections["synthese_executive"],
        },
        "sommaire": {
            "type": "tableau",
            "entetes": ["Chap.", "Intitulé", "Chap.", "Intitulé"],
            "consigne": (
                "Généré automatiquement depuis la liste des chapitres, sur deux colonnes "
                "appariées. Jamais rédigé par le modèle de langage."
            ),
        },
        "mode_emploi": {
            "titre": "Mode d’emploi de l’étude",
            "blocs": sections["mode_emploi"],
        },
        "regles_generation": REGLES,
        "chapitres": chapitres,
        "quatrieme_de_couverture": [
            {"type": "fond", "couleur": "{{client.couleur_principale}}", "pleine_page": True},
            {"type": "logo", "source": "{{client.logo}}"},
            {"type": "nom", "texte": "{{client.nom}}"},
            {"type": "baseline", "texte": "{{client.baseline}}"},
            {"type": "mention", "texte": "ÉTUDE DE MARCHÉ APPROFONDIE · {{date.annee}}"},
        ],
    }


def main(chemin_reference: str, chemin_sortie: str) -> int:
    reference = json.loads(Path(chemin_reference).read_text(encoding="utf-8"))
    modele = construire(reference)
    Path(chemin_sortie).write_text(
        json.dumps(modele, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total_min = sum(c["graphiques_min"] for c in modele["chapitres"])
    total_reference = sum(
        c["statistiques_reference"]["graphiques"] for c in modele["chapitres"]
    )
    print(f"{chemin_sortie} :")
    print(f"  chapitres            {len(modele['chapitres'])}")
    print(f"  blocs modelises      {sum(len(c['blocs']) for c in modele['chapitres'])}")
    print(f"  graphiques_min total {total_min}  (référence : {total_reference})")
    for nom in ("page_de_garde", "synthese_executive", "mode_emploi"):
        section = modele[nom]
        blocs = section if isinstance(section, list) else section["blocs"]
        print(f"  {nom:20} {len(blocs)} blocs")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
