"""Lecture du modèle de référence. Une seule source, lue une seule fois."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

#: `references/` est à la racine du dépôt, comme `prompts/` et `gabarits/`.
#: Le Dockerfile doit le copier dans l'image — `test_image_dependances.py` le
#: vérifie, après que l'absence de `prompts/` a fait échouer la première
#: génération réelle sur le serveur.
RACINE = Path(__file__).resolve().parents[3]
CHEMIN_MODELE = RACINE / "references" / "modele_etude_marche.json"


class ModeleIntrouvableError(RuntimeError):
    """Le modèle de référence est absent ou illisible.

    Volontairement une erreur, jamais un repli silencieux : sans modèle, il n'y
    a rien à comparer, et un contrôle qui n'a rien à comparer est un échec
    (règle 1).
    """


@lru_cache(maxsize=1)
def charger_modele(chemin: str | None = None) -> dict[str, Any]:
    """Modèle complet. Mis en cache : il ne change pas en cours d'exécution."""
    fichier = Path(chemin) if chemin else CHEMIN_MODELE
    if not fichier.is_file():
        msg = (
            f"Modèle de référence introuvable : {fichier}. Aucun chapitre ne "
            "peut être validé sans lui."
        )
        raise ModeleIntrouvableError(msg)
    try:
        modele = json.loads(fichier.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erreur:
        msg = f"Modèle de référence illisible ({fichier}) : {erreur}"
        raise ModeleIntrouvableError(msg) from erreur
    return _lire_chaque_tableau(modele)


#: Longueur du paragraphe de lecture posé après chaque tableau : deux ou trois
#: phrases, une cinquantaine de mots — sous les soixante qui font un paragraphe
#: « long » au contrôle de densité.
LECTURE_DE_TABLEAU_SIGNES = 300

#: Ce que la cellule porte, et ce qu'elle laisse au paragraphe.
CELLULES_COURTES = (
    "Cellules COURTES : une donnée, un mot-clé ou un verdict de douze mots au "
    "plus. L'explication ne va pas dans la cellule : elle va dans le paragraphe "
    "de lecture qui suit le tableau."
)


def _lire_chaque_tableau(modele: dict[str, Any]) -> dict[str, Any]:
    """Après chaque tableau du modèle, un paragraphe qui le LIT.

    ## Le retour de la cliente, et la mesure qui le fonde

    Le 29/10/2026, sur les deux études de marché de la boutique : « il y avait
    beaucoup de tableaux, mais pas beaucoup de textes. Du coup, ça fait un
    empilement de tableaux, mais c'est bien aussi qu'il y ait des paragraphes
    écrits. Mais ça, je vous l'avais dit l'autre fois. » Son cahier des charges
    de l'étude de marché le dit aussi : « Les paragraphes doivent être
    rédigés », « des paragraphes développés ».

    Mesuré au même extracteur le 31/10/2026 : Joalie, le document validé qui
    sert de modèle, porte 61,6 % de ses mots en tableaux ; l'étude IA de test
    `e30fce14`, 61,7 %. Le moteur ne s'écartait pas du modèle, il le
    reproduisait — et le validateur de conformité plafonnait la prose au
    volume de Joalie (paragraphes ±1, volume ±15 %). Une consigne « écris plus »
    aurait été refusée par ce validateur.

    L'écart se lisait ailleurs : 18 % de nos cellules font douze mots ou plus
    et portent 52 % des mots de tableau (6 % et 25 % chez Joalie). L'analyse
    vivait dans les cellules.

    ## Ce qui change, et pourquoi ici

    Chaque tableau qui n'est pas déjà suivi d'un paragraphe en reçoit un, et
    chaque tableau demande des cellules courtes. C'est fait AU CHARGEMENT, la
    seule source que lisent à la fois le plan envoyé au modèle et le
    validateur qui le juge (règle 5) : demander une forme et en contrôler une
    autre ne converge jamais. Le fichier mesuré reste intact.
    """
    for chapitre in modele.get("chapitres", []):
        blocs = chapitre.get("blocs") or []
        ajustes: list[dict[str, Any]] = []
        for rang, bloc in enumerate(blocs):
            if bloc.get("type") != "tableau":
                ajustes.append(bloc)
                continue
            consigne = str(bloc.get("consigne", "")).strip()
            ajustes.append({
                **bloc,
                "consigne": f"{consigne}\n   → {CELLULES_COURTES}" if consigne
                else CELLULES_COURTES,
            })
            suivant = blocs[rang + 1] if rang + 1 < len(blocs) else {}
            if suivant.get("type") != "paragraphe":
                ajustes.append({
                    "type": "paragraphe",
                    "longueur_cible_signes": LECTURE_DE_TABLEAU_SIGNES,
                    "consigne": (
                        "Lecture du tableau qui précède : ce qu'il montre, et "
                        "ce que cela implique pour le projet. Deux ou trois "
                        "phrases rédigées — jamais une redite des cellules."
                    ),
                })
        chapitre["blocs"] = ajustes
    return modele


#: Livrables décrits par un modèle de forme, et le `type_document` que leur
#: fichier doit déclarer.
#:
#: **Une table, et non plus une constante scalaire.** Le jour où un second
#: modèle arrive, il se pose ici : une ligne de données, aucun code à changer.
#: Tant qu'elle n'a qu'une entrée, elle se comporte exactement comme la
#: constante qu'elle remplace.
#:
#: ## Ce qu'il faut pour y ajouter le business plan, et pourquoi ce n'est pas
#: ## un travail de code
#:
#: Le modèle de l'étude de marché n'a pas été écrit : il a été MESURÉ sur
#: `references/joalie_2026.docx`, une étude réelle livrée à la cliente, via
#: `references/structurer.py` puis `references/modeliser.py`. Longueurs de
#: paragraphes, en-têtes et hauteurs de tableaux, séquence des blocs : tout
#: vient du document.
#:
#: Le dériver d'un business plan que NOUS avons produit n'apprendrait rien —
#: il encoderait ce que le moteur fait déjà et le déclarerait conforme. Une
#: boucle qui valide contre sa propre mesure se donne raison toute seule
#: (règle 9). Il faut donc un business plan validé par la cliente, écrit
#: hors de cette chaîne, et refaire le passage `structurer` → `modeliser` avec
#: des constantes propres au BP (`GRAPHIQUES_MIN`, `VISUEL_ATTENDU`,
#: `VOLUME_PAGES` sont spécifiques à l'étude de marché).
#:
#: En attendant, un livrable non décrit reçoit `_bloc_forme(code)` — une forme
#: PROPRE à son type, et non plus la même consigne pour tout le monde.
MODELES_PAR_LIVRABLE: dict[str, str] = {
    "market_study": "etude_de_marche",
}


def modele_couvre(code_livrable: str, *, chemin: str | None = None) -> bool:
    """Le modèle décrit-il ce type de livrable ?

    Vérifie les DEUX côtés : le code du livrable demandé et le `type_document`
    déclaré dans le fichier. Si le jour où un second modèle arrive le fichier
    change de type sans que ce code bouge, la consigne ne partira pas quand
    même — elle s'éteindra.
    """
    attendu = MODELES_PAR_LIVRABLE.get(code_livrable)
    if attendu is None:
        return False
    return charger_modele(chemin).get("type_document") == attendu


def chapitre_du_modele(numero: int, *, chemin: str | None = None) -> dict[str, Any] | None:
    """Chapitre du modèle, ou None s'il n'existe pas.

    Le modèle numérote « CHAPITRE 01 » à « CHAPITRE 21 ». Il n'a **pas** de
    chapitre 00 : la fiche projet du moteur actuel n'y correspond à rien, et
    c'est un écart connu à traiter séparément.
    """
    reference = f"CHAPITRE {numero:02d}"
    for chapitre in charger_modele(chemin).get("chapitres", []):
        if chapitre.get("numero") == reference:
            return chapitre  # type: ignore[no-any-return]
    return None


@dataclass(frozen=True)
class Dosage:
    """Comptes attendus pour un chapitre, tirés de ses blocs."""

    paragraphes: int
    tableaux: int
    encadres: int
    grilles_kpi: int
    sous_sections: int
    graphiques_min: int
    #: Volume attendu, en signes, calculé sur la MÊME base que la mesure du
    #: chapitre produit : titres de sous-section et paragraphes, rien d'autre.
    #: Voir `signes_comparables`.
    signes: int


def signes_comparables(chapitre_modele: dict[str, Any]) -> int:
    """Volume attendu, sur la base de ce qu'un chapitre produit peut porter.

    `statistiques_reference.signes` ne convient PAS comme cible : il additionne
    tous les blocs de type paragraphe de l'extraction, ce qui inclut les
    **lignes de source** sous les graphiques — 125 signes rien qu'au chapitre 01.
    Or ces lignes sont écrites par le rendu, pas par le modèle de langage : les
    exiger du chapitre reviendrait à lui reprocher de ne pas produire ce qu'on
    ne lui demande pas.

    Sont donc comptés, et de chaque côté à l'identique : les titres de
    sous-section et les paragraphes. Ni l'accroche — qui a sa propre cible —,
    ni les encadrés, que l'extraction ne compte pas non plus.

    Mesurer une chose d'un côté et une autre de l'autre, c'est le défaut de la
    règle 2 : un écart affiché qui n'existe pas.
    """
    total = 0
    for bloc in chapitre_modele.get("blocs", []):
        type_bloc = bloc.get("type")
        if type_bloc == "paragraphe":
            total += int(bloc.get("longueur_cible_signes", 0))
        elif type_bloc == "titre_sous_section":
            # « 1.1 » + espace + intitulé, comme dans le document d'origine.
            total += len(str(bloc.get("numero", ""))) + 1 + len(
                str(bloc.get("intitule_reference", ""))
            )
    return total


def dosage_attendu(chapitre_modele: dict[str, Any]) -> Dosage:
    """Compte les blocs du modèle par type.

    Les `ligne_source` ne sont pas comptées : elles sont produites par le rendu
    sous un graphique, pas demandées au modèle de langage.
    """
    blocs = chapitre_modele.get("blocs", [])
    compte = {type_bloc: 0 for type_bloc in
              ("paragraphe", "tableau", "encadre", "grille_kpi", "titre_sous_section")}
    for bloc in blocs:
        type_bloc = bloc.get("type")
        if type_bloc in compte:
            compte[type_bloc] += 1

    return Dosage(
        paragraphes=compte["paragraphe"],
        tableaux=compte["tableau"],
        encadres=compte["encadre"],
        grilles_kpi=compte["grille_kpi"],
        sous_sections=compte["titre_sous_section"],
        graphiques_min=int(chapitre_modele.get("graphiques_min", 0)),
        signes=signes_comparables(chapitre_modele),
    )
