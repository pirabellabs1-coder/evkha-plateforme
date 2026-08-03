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

#: « Visuel pertinent » du manuel EVKHA « Cheminement et profondeur d'une étude
#: de marché » (pp. 11-31), chapitre par chapitre, verbatim.
#:
#: Ce que le modèle apporte ici, c'est l'INTENTION — quoi montrer — et rien
#: d'autre. Il portait naguère un `TYPES_GRAPHIQUES` de sept noms dont quatre —
#: `barres_verticales`, `courbe`, `pyramide`, `jauge` — que
#: `chapitres.schema.TypeGraphique` refuse. Le prompt annonçait donc une liste
#: « imposée » qui faisait échouer la validation plus d'une fois sur deux, et le
#: catalogue correct quelques lignes plus bas. Il ne restait que trois types
#: employables pour tout un document : les figures ne pouvaient pas varier.
#:
#: La liste des types appartient au moteur qui dessine
#: (`rendu_word.graphiques.RENDU_PAR_TYPE`), une seule fois — règle 5.
VISUEL_ATTENDU: dict[str, str] = {
    "CHAPITRE 01": "Courbe historique et projection ; monde versus continent pertinent.",
    "CHAPITRE 02": "Graphique national/local et schéma TAM/SAM/SOM.",
    "CHAPITRE 03": "Carte ou matrice de segmentation, limitée aux axes utiles.",
    "CHAPITRE 04": "Encadré comparatif ou balance avantages/contraintes.",
    "CHAPITRE 05": "Matrice impact/horizon des défis et opportunités.",
    "CHAPITRE 06": "Parcours de conformité ou tableau obligations/actions.",
    "CHAPITRE 07": "Frise 2026-2027 ou radar de tendances.",
    "CHAPITRE 08": "Frise ou tableau de scénarios à 2030.",
    "CHAPITRE 09": "Tuiles chiffrées ou tableau synthétique lisible.",
    "CHAPITRE 10": "Parcours de décision ou matrice attentes/freins/leviers.",
    "CHAPITRE 11": "Deux fiches persona sobres et comparables.",
    "CHAPITRE 12": "Registre des risques synthétique.",
    "CHAPITRE 13": "Matrice probabilité/impact haute résolution.",
    "CHAPITRE 14": "Scorecard de viabilité avec justification, jamais un score décoratif.",
    "CHAPITRE 15": "Planche de graphiques cohérente avec la charte.",
    "CHAPITRE 16": "Matrice besoins/couverture ou équilibre offre-demande.",
    "CHAPITRE 17": "Carte si données géographiques fiables ; sinon tableau de scoring.",
    "CHAPITRE 18": "Matrice SWOT 2 × 2 lisible.",
    "CHAPITRE 19": "Feuille de route 90 jours / 12 mois / 24 mois.",
    "CHAPITRE 20": "Encadré final « Potentiel / Conditions / Vigilances ».",
    "CHAPITRE 21": "Aucun visuel obligatoire ; mise en page bibliographique claire.",
}

#: « Volume indicatif dans l'étude client » du manuel, en pages.
#:
#: Indicatif et NON additif : les planchers cumulés font 63 pages, les plafonds
#: 85 — cinq de plus que la limite de 80 que le manuel se donne lui-même, annexe
#: non comprise. On recopie ses chiffres sans les corriger ; c'est sa décision,
#: pas la nôtre. Le test `test_le_plancher_des_volumes_produit_deja_une_etude_
#: conforme` verrouille la seule propriété dont la génération dépend : au
#: plancher, l'étude est déjà conforme.
VOLUME_PAGES: dict[str, tuple[int, int]] = {
    "CHAPITRE 01": (4, 5), "CHAPITRE 02": (5, 6), "CHAPITRE 03": (3, 4),
    "CHAPITRE 04": (2, 3), "CHAPITRE 05": (3, 4), "CHAPITRE 06": (3, 4),
    "CHAPITRE 07": (2, 3), "CHAPITRE 08": (3, 4), "CHAPITRE 09": (2, 3),
    "CHAPITRE 10": (4, 5), "CHAPITRE 11": (2, 3), "CHAPITRE 12": (4, 5),
    "CHAPITRE 13": (2, 3), "CHAPITRE 14": (3, 4), "CHAPITRE 15": (3, 4),
    "CHAPITRE 16": (3, 4), "CHAPITRE 17": (3, 4), "CHAPITRE 18": (3, 4),
    "CHAPITRE 19": (4, 5), "CHAPITRE 20": (2, 3), "CHAPITRE 21": (3, 5),
}

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


#: Nom de la plateforme, tel qu'il apparaît dans le document de référence.
#: Celui-ci a été produit PAR la plateforme POUR sa propre cliente : il signe
#: donc son travail. Les documents que le moteur produit, eux, partent en
#: **marque blanche** — l'abonné les remet à SON client. Le nom de la
#: plateforme sur l'un d'eux signerait le travail d'un tiers au nom d'un autre.
#:
#: Mesuré : « LECTURE EVKHA » étiquetait quinze encadrés du modèle et « 21.1
#: Méthode EVKHA appliquée » un titre de sous-section. Le document livré portait
#: la mention seize fois.
MARQUE_PLATEFORME = re.compile(r"\s*\bEVKHA\b\s*", re.IGNORECASE)


def _neutraliser(texte: str) -> str:
    """Retire le nom de la plateforme d'un libellé destiné au document.

    Appliqué à TOUT libellé recopié de la référence, pas aux seuls encadrés :
    un correctif qui énumère les cas est incomplet (règle 4). Ce qui garantit
    l'absence, ce n'est pas cette fonction mais le contrôle qui balaie le
    modèle entier — voir `test_marque_blanche_document.py`.
    """
    return " ".join(MARQUE_PLATEFORME.sub(" ", texte).split()).strip()


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
                    "intitule_reference": _neutraliser(trouve.group(2)),
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
            "entetes": [_neutraliser(str(e)) for e in bloc.get("entetes", [])],
            "nb_lignes_cible": bloc.get("nb_lignes", 0),
            "nb_colonnes": bloc.get("nb_colonnes", 0),
            "consigne": CONSIGNE_TABLEAU,
        }

    if type_bloc == "encadre":
        return {
            "type": "encadre",
            "etiquette": _neutraliser(bloc.get("etiquette", "")),
            "longueur_cible_signes": len(bloc.get("texte", "")),
            "consigne": CONSIGNE_ENCADRE,
        }

    if type_bloc == "graphique":
        return {
            "type": "graphique",
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


def _placer_graphiques_supplementaires(
    blocs: list[dict[str, Any]], minimum: int
) -> list[dict[str, Any]]:
    """Ajoute les emplacements de graphique que `GRAPHIQUES_MIN` réclame.

    Le supplément demandé — quatorze visuels contre huit dans l'original —
    portait sur le COMPTE, pas sur la séquence. Cinq chapitres exigeaient donc
    un graphique sans qu'aucun bloc ne lui donne de place : le modèle demandait
    une chose qu'il ne permettait pas de placer, et un chapitre respectant sa
    séquence était refusé pour graphique manquant.

    L'emplacement retenu est APRÈS le premier paragraphe. C'est là que le
    document de référence place les siens quand il en a un : le lecteur pose le
    cadre, puis voit la figure. Un choix explicite, pas un défaut.
    """
    presents = sum(1 for b in blocs if b["type"] == "graphique")
    manquants = minimum - presents
    if manquants <= 0:
        return blocs

    modele = list(blocs)
    for _ in range(manquants):
        gabarit = {
            "type": "graphique",
            "obligatoire": True,
            "ajoute_par_le_modele": True,
            "spec": {
                "titre": "à définir selon la niche",
                "data_refs": ["ids du socle"],
                "largeur_px": 2000,
                "dpi": 200,
            },
        }
        position = next(
            (i + 1 for i, b in enumerate(modele) if b["type"] == "paragraphe"),
            len(modele),
        )
        modele.insert(position, gabarit)
    return modele


def construire(reference: dict[str, Any]) -> dict[str, Any]:
    chapitres = []
    for chapitre in reference["chapitres"]:
        numero = chapitre["numero"]
        if numero not in GRAPHIQUES_MIN:
            msg = f"{numero} n’a pas de graphiques_min déclaré."
            raise ValueError(msg)
        blocs, saut = _blocs(chapitre["blocs"])
        blocs = _placer_graphiques_supplementaires(blocs, GRAPHIQUES_MIN[numero])
        if numero not in VISUEL_ATTENDU or numero not in VOLUME_PAGES:
            # Bruyant, jamais un repli (règle 1) : un chapitre sans intention
            # visuelle ni épaisseur reprendrait la figure du profil sectoriel,
            # la même que ses voisins — exactement le défaut qu'on corrige.
            msg = f"{numero} n’a ni visuel attendu ni volume déclaré."
            raise ValueError(msg)
        chapitres.append({
            "numero": numero,
            "titre_reference": _neutraliser(chapitre["titre"]),
            "titre_consigne": (
                "Conserver le titre tel quel ; seuls les chapitres 1, 2 et 17 "
                "précisent la zone de la niche."
            ),
            "volume_pages": list(VOLUME_PAGES[numero]),
            "visuel_attendu": VISUEL_ATTENDU[numero],
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
