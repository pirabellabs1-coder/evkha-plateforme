"""Une cellule manquante ne doit pas tuer un chapitre.

## Le cas réel

Étude concurrentielle `5892daa5`, 09/08/2026, en production :

    Echec generation chapitre 1
    « blocs.18.tableau.tableau : La ligne 10 compte 8 cellules pour
      9 colonnes déclarées. »

Une cellule manquante sur les quatre-vingt-dix d'un tableau. Le chapitre a été
rejoué jusqu'à épuisement des tentatives, et le dossier est mort après avoir
brûlé **0,76 EUR sur un seul chapitre** — quand l'étude concurrentielle
complète de la veille avait coûté 1,27 EUR pour ses dix chapitres.

## Réparer, ou refuser ?

Le dépôt a déjà tranché cette question deux fois, dans le même sens :
`raccourcir_le_resume` ramène un résumé trop long dans sa borne, et la
typographie corrige les espaces au lieu de rejouer un appel. Le critère est
constant : **on répare quand la réparation atteint exactement le but que la
règle poursuit**.

La règle veut un tableau rectangulaire. Compléter la ligne d'une cellule vide
le rend rectangulaire. Il n'y a rien à deviner.

## Ce qui reste refusé, et pourquoi

Une ligne PLUS LONGUE que ses en-têtes. On ne sait pas laquelle des cellules est
en trop, et en choisir une détruirait de la donnée. Le refus reste le bon
comportement quand la réparation devrait deviner (règle 2) — c'est la
différence entre corriger et abîmer.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from generation.chapitres.schema import Tableau


def test_une_ligne_trop_courte_est_completee() -> None:
    """Le cas exact du dossier `5892daa5` : 8 cellules pour 9 colonnes."""
    tableau = Tableau(
        entetes=[f"C{n}" for n in range(9)],
        lignes=[["a", "b", "c", "d", "e", "f", "g", "h"]],
    )

    assert len(tableau.lignes[0]) == 9
    assert tableau.lignes[0][-1] == ""
    # Le contenu déjà présent n'est pas touché.
    assert tableau.lignes[0][:8] == ["a", "b", "c", "d", "e", "f", "g", "h"]


def test_une_ligne_vide_est_completee_entierement() -> None:
    tableau = Tableau(entetes=["Poste", "Montant"], lignes=[[]])

    assert tableau.lignes[0] == ["", ""]


def test_plusieurs_lignes_courtes_sont_toutes_completees() -> None:
    tableau = Tableau(
        entetes=["A", "B", "C"],
        lignes=[["1"], ["1", "2"], ["1", "2", "3"]],
    )

    assert [len(ligne) for ligne in tableau.lignes] == [3, 3, 3]


def test_une_ligne_TROP_LONGUE_reste_refusee() -> None:
    """LA contre-épreuve : réparer devrait ici DEVINER, donc détruire.

    Retirer une cellule au hasard ferait disparaître une donnée du document
    sans que personne ne le sache — le silence que ce dépôt combat.
    """
    with pytest.raises(ValidationError, match="ne peut pas être retirée"):
        Tableau(entetes=["A", "B"], lignes=[["1", "2", "3"]])


def test_un_tableau_deja_rectangulaire_traverse_intact() -> None:
    """Contre-épreuve : la réparation ne doit rien changer à ce qui va bien."""
    lignes = [["Loyer", "12 kEUR"], ["Charges", "3 kEUR"]]

    tableau = Tableau(
        entetes=["Poste", "Montant"], lignes=[list(ligne) for ligne in lignes]
    )

    assert tableau.lignes == lignes


def test_la_reparation_est_idempotente() -> None:
    """Revalider un tableau réparé ne doit rien ajouter de plus."""
    premier = Tableau(entetes=["A", "B", "C"], lignes=[["1"]])
    second = Tableau.model_validate(premier.model_dump())

    assert second.lignes == [["1", "", ""]]
