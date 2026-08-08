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
        return json.loads(fichier.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except json.JSONDecodeError as erreur:
        msg = f"Modèle de référence illisible ({fichier}) : {erreur}"
        raise ModeleIntrouvableError(msg) from erreur


#: Le modèle ne décrit QU'UN type de document. Soumettre un business plan à la
#: forme de l'étude de marché lui imposerait un plan qui n'est pas le sien —
#: et le validateur de conformité le refuserait pour un défaut qu'on aurait
#: nous-mêmes provoqué.
TYPE_LIVRABLE_MODELE = "market_study"


def modele_couvre(code_livrable: str, *, chemin: str | None = None) -> bool:
    """Le modèle décrit-il ce type de livrable ?

    Vérifie les DEUX côtés : le code du livrable demandé et le `type_document`
    déclaré dans le fichier. Si le jour où un second modèle arrive le fichier
    change de type sans que ce code bouge, la consigne ne partira pas quand
    même — elle s'éteindra.
    """
    if code_livrable != TYPE_LIVRABLE_MODELE:
        return False
    return charger_modele(chemin).get("type_document") == "etude_de_marche"


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
