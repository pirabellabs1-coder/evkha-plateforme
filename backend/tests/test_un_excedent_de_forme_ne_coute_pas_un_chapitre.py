"""Un excédent de forme se coupe ; il ne coûte jamais un chapitre.

## Le cas réel

Stratégie `0f9fb13a` (11/08/2026), cliente EVKHA. Le chapitre 0 — la fiche
projet, celle qui conditionne TOUTE la génération — est mort sur :

    blocs.14.encadre.encadre.lignes : List should have at most 6 items
    after validation, not 7

**Une ligne de trop.** Un chapitre entier, payé, correct par ailleurs, perdu
pour un excédent qui se retire en une opération.

## La règle du dépôt, appliquée pour la quatrième fois

Une ligne de tableau trop courte se complète, un résumé trop long se
raccourcit, une typographie fautive se répare. Un défaut de FORME ne doit
jamais coûter un livrable — la reprise coûte six centimes et le modèle peut
refaire la même étourderie.

Les trois plafonds de forme du contrat suivent donc la même règle : encadré à
six lignes, grille à quatre cellules, tableau à neuf colonnes (règle 4 — la
classe, pas l'exemple qu'on vient de voir).

## Ce qui reste refusé, et doit l'être

Une ligne de tableau PLUS LONGUE que ses en-têtes : on ne saurait pas
laquelle des cellules est en trop, et deviner détruirait de la donnée. Le
refus reste juste quand la réparation devrait deviner (règle 2).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from generation.chapitres.schema import BlocGrilleKpi, CelluleKpi, Encadre, Tableau


def test_un_encadre_a_sept_lignes_est_ramene_a_six() -> None:
    """Le défaut exact qui a tué le chapitre 0 de `0f9fb13a`."""
    encadre = Encadre(
        intitule="À retenir",
        lignes=[f"Ligne {n}" for n in range(1, 8)],
    )

    assert len(encadre.lignes) == 6
    assert encadre.lignes[0] == "Ligne 1"


def test_un_encadre_conforme_n_est_pas_touche() -> None:
    """CONTRE-ÉPREUVE : la réparation ne s'applique qu'à l'excédent."""
    encadre = Encadre(intitule="À retenir", lignes=["A", "B", "C"])

    assert encadre.lignes == ["A", "B", "C"]


def test_une_grille_a_cinq_cellules_est_ramenee_a_quatre() -> None:
    grille = BlocGrilleKpi(
        cellules=[
            CelluleKpi(valeur=f"{n} %", libelle=f"Repère {n}") for n in range(5)
        ]
    )

    assert len(grille.cellules) == 4


def test_un_tableau_a_dix_colonnes_est_ramene_a_neuf() -> None:
    """Les en-têtes ET les lignes sont coupés : sinon le tableau cesse d'être
    rectangulaire, et le validateur suivant refuserait ce que celui-ci sauve."""
    tableau = Tableau(
        entetes=[f"C{n}" for n in range(10)],
        lignes=[[f"v{n}" for n in range(10)], [f"w{n}" for n in range(10)]],
    )

    assert len(tableau.entetes) == 9
    assert all(len(ligne) == 9 for ligne in tableau.lignes)


def test_un_tableau_de_neuf_colonnes_passe_intact() -> None:
    """CONTRE-ÉPREUVE : neuf colonnes existent dans le document de référence."""
    tableau = Tableau(
        entetes=[f"C{n}" for n in range(9)],
        lignes=[[f"v{n}" for n in range(9)]],
    )

    assert len(tableau.entetes) == 9


def test_une_ligne_plus_longue_que_ses_entetes_reste_refusee() -> None:
    """CONTRE-ÉPREUVE : on ne devine pas quelle cellule est en trop.

    Couper au hasard détruirait de la donnée du client. Le refus est le bon
    comportement quand la réparation devrait deviner.
    """
    with pytest.raises(ValidationError, match="cellules pour"):
        Tableau(entetes=["A", "B"], lignes=[["1", "2", "3"]])


def test_une_ligne_trop_courte_est_toujours_completee() -> None:
    """Ce qui marchait avant continue : la cellule manquante se complète."""
    tableau = Tableau(entetes=["A", "B", "C"], lignes=[["1", "2"]])

    assert tableau.lignes[0] == ["1", "2", ""]
