"""Mesure l'écart entre un chapitre produit et le modèle de référence."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .chargement import Dosage, chapitre_du_modele, dosage_attendu

#: Tolérances de la spécification.
TOLERANCE_TABLEAUX = 1
TOLERANCE_PARAGRAPHES = 1
TOLERANCE_VOLUME = 0.15

#: Une variable de gabarit laissée telle quelle : `{{client.nom}}`.
_VARIABLE = re.compile(r"\{\{[^}]*\}\}")

#: Séparateur de paragraphes dans le champ `contenu` d'une section : une ligne
#: vide. Le modèle compte les paragraphes un par un ; `Section.contenu` peut en
#: porter plusieurs.
_PARAGRAPHES = re.compile(r"\n\s*\n")


class Gravite(StrEnum):
    BLOQUANTE = "bloquante"
    AVERTISSEMENT = "avertissement"


@dataclass(frozen=True)
class Ecart:
    """Un écart au modèle. Le détail doit être trouvable dans le chapitre.

    La règle 2 est explicite là-dessus : un motif d'échec qu'on ne retrouve pas
    dans le document envoie corriger la mauvaise chose.
    """

    regle: str
    gravite: Gravite
    detail: str


@dataclass(frozen=True)
class RapportConformite:
    chapitre: int
    ecarts: list[Ecart] = field(default_factory=list)
    #: Règles réellement exécutées.
    controles_executes: list[str] = field(default_factory=list)
    #: Règles que le contrat actuel ne permet PAS d'exécuter, avec leur raison.
    #: Elles ne sont ni réussies ni échouées : elles sont absentes, et ça se dit.
    controles_impossibles: dict[str, str] = field(default_factory=dict)

    @property
    def bloquantes(self) -> list[Ecart]:
        return [e for e in self.ecarts if e.gravite is Gravite.BLOQUANTE]

    @property
    def conforme(self) -> bool:
        """Le chapitre peut-il être rendu ?

        Un rapport sans contrôle exécuté n'est PAS conforme : ne rien avoir
        vérifié n'est pas avoir vérifié sans rien trouver (règle 1).
        """
        return bool(self.controles_executes) and not self.bloquantes

    def resume(self) -> str:
        if not self.controles_executes:
            return "Aucun contrôle exécuté."
        if not self.ecarts:
            return f"{len(self.controles_executes)} contrôles, aucun écart."
        compte: dict[str, int] = {}
        for ecart in self.ecarts:
            compte[ecart.gravite] = compte.get(ecart.gravite, 0) + 1
        detail = ", ".join(f"{nombre} {gravite}" for gravite, nombre in compte.items())
        return f"{len(self.controles_executes)} contrôles, {detail}."


# ── Projection du chapitre produit dans le vocabulaire du modèle ─────────────


@dataclass(frozen=True)
class Comptes:
    paragraphes: int
    tableaux: int
    encadres: int
    graphiques: int
    sous_sections: int


def compter(payload: Any) -> Comptes:
    """Traduit un `ChapitrePayload` en comptes de blocs du modèle.

    Une `Section` vaut un titre de sous-section, un ou plusieurs paragraphes
    (séparés par une ligne vide) et au plus un tableau.
    """
    paragraphes = 0
    tableaux = 0
    for section in payload.sections:
        morceaux = [m for m in _PARAGRAPHES.split(section.contenu or "") if m.strip()]
        paragraphes += max(len(morceaux), 1)
        if getattr(section, "tableau", None) is not None:
            tableaux += 1
    return Comptes(
        paragraphes=paragraphes,
        tableaux=tableaux,
        encadres=len(payload.encadres),
        graphiques=len(payload.graphiques),
        sous_sections=len(payload.sections),
    )


def _textes(payload: Any) -> Iterable[tuple[str, str]]:
    """Tous les textes du chapitre, avec l'endroit où les trouver."""
    yield "titre", payload.titre
    yield "accroche", payload.accroche or ""
    yield "résumé", payload.resume
    for index, section in enumerate(payload.sections, start=1):
        yield f"section {index} — titre", section.titre
        yield f"section {index} — contenu", section.contenu or ""
        tableau = getattr(section, "tableau", None)
        if tableau is not None:
            for entete in tableau.entetes:
                yield f"section {index} — en-tête de tableau", entete
            for rang, ligne in enumerate(tableau.lignes, start=1):
                for cellule in ligne:
                    yield f"section {index} — tableau, ligne {rang}", cellule
    for index, encadre in enumerate(payload.encadres, start=1):
        yield f"encadré {index} — intitulé", encadre.intitule
        for ligne in encadre.lignes:
            yield f"encadré {index}", ligne
    for index, graphique in enumerate(payload.graphiques, start=1):
        yield f"graphique {index} — titre", graphique.titre


def _signes(payload: Any) -> int:
    """Volume mesuré sur la MÊME base que `signes_comparables` du modèle.

    Titres de sous-section et paragraphes, rien d'autre. Ni l'accroche, qui a sa
    propre cible, ni les encadrés, que l'extraction ne compte pas. Compter des
    choses différentes des deux côtés produirait un écart qui n'existe pas.
    """
    total = 0
    for section in payload.sections:
        total += len(section.titre or "") + len(section.contenu or "")
    return total


# ── Les contrôles ────────────────────────────────────────────────────────────


def _controler_dosage(comptes: Comptes, attendu: Dosage) -> list[Ecart]:
    ecarts: list[Ecart] = []

    if abs(comptes.tableaux - attendu.tableaux) > TOLERANCE_TABLEAUX:
        ecarts.append(Ecart(
            "dosage_tableaux", Gravite.BLOQUANTE,
            f"{comptes.tableaux} tableau(x) pour {attendu.tableaux} au modèle "
            f"(tolérance ±{TOLERANCE_TABLEAUX})",
        ))

    if abs(comptes.paragraphes - attendu.paragraphes) > TOLERANCE_PARAGRAPHES:
        ecarts.append(Ecart(
            "dosage_paragraphes", Gravite.BLOQUANTE,
            f"{comptes.paragraphes} paragraphe(s) pour {attendu.paragraphes} au "
            f"modèle (tolérance ±{TOLERANCE_PARAGRAPHES})",
        ))

    # Les encadrés portent la méthode : leur nombre est celui du modèle, sans
    # tolérance. Un encadré en moins, c'est une décision qui disparaît.
    if comptes.encadres != attendu.encadres:
        ecarts.append(Ecart(
            "dosage_encadres", Gravite.BLOQUANTE,
            f"{comptes.encadres} encadré(s) pour {attendu.encadres} au modèle",
        ))

    if comptes.sous_sections != attendu.sous_sections:
        ecarts.append(Ecart(
            "dosage_sous_sections", Gravite.AVERTISSEMENT,
            f"{comptes.sous_sections} sous-section(s) pour {attendu.sous_sections} "
            "au modèle",
        ))

    return ecarts


def _controler_graphiques(comptes: Comptes, attendu: Dosage) -> list[Ecart]:
    if comptes.graphiques >= attendu.graphiques_min:
        return []
    return [Ecart(
        "graphiques_min", Gravite.BLOQUANTE,
        f"{comptes.graphiques} graphique(s) demandé(s) pour un minimum de "
        f"{attendu.graphiques_min}",
    )]


def _controler_volume(payload: Any, attendu: Dosage) -> list[Ecart]:
    if attendu.signes <= 0:
        return []
    produit = _signes(payload)
    ecart = abs(produit - attendu.signes) / attendu.signes
    if ecart <= TOLERANCE_VOLUME:
        return []
    sens = "au-dessus" if produit > attendu.signes else "en dessous"
    return [Ecart(
        "volume", Gravite.BLOQUANTE,
        f"{produit} signes contre {attendu.signes} au modèle, "
        f"{ecart * 100:.0f} % {sens} de la tolérance de "
        f"{TOLERANCE_VOLUME * 100:.0f} %",
    )]


def _controler_data_refs(payload: Any, identifiants_socle: frozenset[str]) -> list[Ecart]:
    """Tout identifiant cité doit exister au socle.

    On ne vérifie PAS qu'un chiffre écrit en toutes lettres correspond à sa
    donnée : c'est le rôle de la vérification du lot 4, qui lit le document
    produit. Deux contrôles jugeant sur la même évidence se donneraient raison
    l'un l'autre (règle 9).
    """
    ecarts: list[Ecart] = []
    inconnus = [i for i in payload.donnees_utilisees if i not in identifiants_socle]
    if inconnus:
        ecarts.append(Ecart(
            "data_refs_inconnus", Gravite.BLOQUANTE,
            "identifiant(s) absent(s) du socle : " + ", ".join(sorted(inconnus)),
        ))
    for index, graphique in enumerate(payload.graphiques, start=1):
        hors = [i for i in graphique.donnees_ids if i not in identifiants_socle]
        if hors:
            ecarts.append(Ecart(
                "data_refs_inconnus", Gravite.BLOQUANTE,
                f"graphique {index} « {graphique.titre} » cite "
                + ", ".join(sorted(hors)) + " — absent(s) du socle",
            ))
    return ecarts


def _controler_variables(payload: Any) -> list[Ecart]:
    """Aucune variable de gabarit ne doit survivre dans le texte livré."""
    ecarts: list[Ecart] = []
    for endroit, texte in _textes(payload):
        restantes = _VARIABLE.findall(texte or "")
        if restantes:
            ecarts.append(Ecart(
                "variable_non_resolue", Gravite.BLOQUANTE,
                f"{endroit} : {', '.join(sorted(set(restantes)))}",
            ))
    return ecarts


# ── Point d'entrée ───────────────────────────────────────────────────────────

#: Contrôles que le contrat du lot 2 ne permet pas d'exécuter aujourd'hui.
#: Déclarés, jamais tus : c'est la différence entre « vérifié » et « pas de
#: nouvelle » (règle 1).
IMPOSSIBLES = {
    "sequence_des_blocs": (
        "`ChapitrePayload` porte `sections`, `encadres` et `graphiques` en trois "
        "listes séparées : il ne peut pas exprimer la position d'un graphique "
        "entre deux paragraphes. Exige une refonte du contrat du lot 2."
    ),
    "longueur_par_paragraphe": (
        "Sans ordre des blocs, aucun paragraphe ne peut être apparié à sa cible "
        "du modèle. Seul le volume total est vérifié."
    ),
}


def verifier_chapitre(
    payload: Any,
    *,
    identifiants_socle: Iterable[str],
    chemin_modele: str | None = None,
) -> RapportConformite:
    """Compare un chapitre produit au chapitre correspondant du modèle.

    Un chapitre sans modèle est BLOQUANT, pas ignoré : c'est le cas du chapitre
    00 « Fiche projet », que le moteur produit et que le modèle n'a pas.
    """
    numero = int(payload.chapitre)
    modele = chapitre_du_modele(numero, chemin=chemin_modele)
    if modele is None:
        return RapportConformite(
            chapitre=numero,
            ecarts=[Ecart(
                "modele_absent", Gravite.BLOQUANTE,
                f"aucun chapitre {numero:02d} au modèle de référence — le modèle "
                "va de 01 à 21 et n'a pas de fiche projet",
            )],
            controles_executes=["modele_present"],
            controles_impossibles=dict(IMPOSSIBLES),
        )

    attendu = dosage_attendu(modele)
    comptes = compter(payload)
    identifiants = frozenset(identifiants_socle)

    ecarts: list[Ecart] = []
    ecarts += _controler_dosage(comptes, attendu)
    ecarts += _controler_graphiques(comptes, attendu)
    ecarts += _controler_volume(payload, attendu)
    ecarts += _controler_data_refs(payload, identifiants)
    ecarts += _controler_variables(payload)

    return RapportConformite(
        chapitre=numero,
        ecarts=ecarts,
        controles_executes=[
            "modele_present", "dosage_tableaux", "dosage_paragraphes",
            "dosage_encadres", "dosage_sous_sections", "graphiques_min",
            "volume", "data_refs_inconnus", "variable_non_resolue",
        ],
        controles_impossibles=dict(IMPOSSIBLES),
    )
