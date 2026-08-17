"""Deux tableaux JUSTES qu'un contrôle a déclarés faux, et pourquoi.

## Les deux motifs, relevés sur le business plan 73dde3ab du 17/08/2026

    Colonne « Montant » : le tableau annonce un total de 180 000,
    mais ses lignes font 405 000.

    Colonne « Montant retenu (exercice 1) » : le tableau annonce un
    total de 3,00, mais ses lignes font 70 000.

Les deux tableaux étaient corrects. Aucun des deux ne portait de ligne de
total. `totaux_faux` reconnaissait un total au SEUL MOT, où qu'il se trouve :

- « **Investissement total** (aménagement, matériel, droit au bail) | 180 000 € »
  ouvrait un plan de financement, et les cinq lignes suivantes — BFR, besoin
  global, apport, emprunt, autres ressources — ont été additionnées contre
  lui : 405 000 ;
- « **Effectif total** exercice 1 (dirigeant compris) | 3 personnes » fermait
  un tableau de masse salariale : trois personnes comparées à 70 000 euros.

## Les deux discriminants, et pourquoi il en fallait deux

**La position.** Un total est en bas. « Investissement total » était la
PREMIÈRE ligne — ce n'est pas une somme, c'est un poste dont le nom contient
le mot. Les lignes partielles (« dont », « soit », « sous-total ») ne comptent
pas dans cette position : un tableau qui détaille son total après l'avoir posé
reste lisible.

**L'unité.** La position ne suffisait pas : « Effectif total » était bel et
bien la dernière ligne. Ce qui la disqualifie, c'est que trois *personnes* ne
sont pas la somme de montants en *euros*. Deux grandeurs qui ne se comparent
pas ne s'additionnent pas — on s'abstient plutôt que d'accuser.

## Ce que ce fichier verrouille

Les deux moitiés. Le contrôle doit se taire sur ces deux tableaux-là, et
continuer de MORDRE sur un vrai total faux — sinon le correctif n'aurait fait
que désarmer le contrôle, ce qui est la manière la plus discrète de le casser
(règle 1 : un contrôle qui n'a plus rien à comparer n'est pas un succès).
"""
from __future__ import annotations

from generation.arithmetique import totaux_faux

# ── Les deux tableaux réels, recopiés du document livré ──────────────────────

PLAN_DE_FINANCEMENT = """
| Poste | Montant |
| --- | --- |
| Investissement total (aménagement, matériel, droit au bail) | 180 000 € |
| Besoin en fonds de roulement | 15 000 € |
| Besoin de financement global (investissement + BFR) | 195 000 € |
| Apport personnel | 45 000 € |
| Emprunt bancaire sollicité | 120 000 € |
| Autres ressources | 30 000 € |
"""

MASSE_SALARIALE = """
| Poste | Montant retenu (exercice 1) |
| --- | --- |
| Rémunération brute du dirigeant | 20 000 euros |
| Reste de la masse salariale (deux autres postes) | 50 000 euros |
| Effectif total exercice 1 (dirigeant compris) | 3 personnes |
"""


def test_un_poste_nomme_total_en_tete_n_est_pas_la_somme_des_suivants() -> None:
    assert totaux_faux(PLAN_DE_FINANCEMENT) == [], (
        "le plan de financement est juste : « Investissement total » est un "
        "poste, pas le total du tableau"
    )


def test_un_effectif_ne_totalise_pas_des_euros() -> None:
    assert totaux_faux(MASSE_SALARIALE) == [], (
        "trois personnes ne sont pas la somme de 20 000 et 50 000 euros"
    )


# ── La contre-épreuve : le contrôle doit toujours mordre ─────────────────────

TOTAL_FAUX = """
| Poste | Montant |
| --- | --- |
| Aménagement | 90 000 € |
| Matériel | 60 000 € |
| Droit au bail | 30 000 € |
| Total | 200 000 € |
"""

TOTAL_JUSTE = """
| Poste | Montant |
| --- | --- |
| Aménagement | 90 000 € |
| Matériel | 60 000 € |
| Droit au bail | 30 000 € |
| Total | 180 000 € |
"""

TOTAL_PUIS_SON_DETAIL = """
| Poste | Montant |
| --- | --- |
| Aménagement | 90 000 € |
| Matériel | 60 000 € |
| Total | 200 000 € |
| dont matériel de cuisson | 40 000 € |
"""


def test_un_vrai_total_faux_est_toujours_trouve() -> None:
    fautes = totaux_faux(TOTAL_FAUX)
    assert len(fautes) == 1, "90 000 + 60 000 + 30 000 = 180 000, pas 200 000"
    assert "Montant" in fautes[0].colonne


def test_un_vrai_total_juste_traverse_le_controle() -> None:
    assert totaux_faux(TOTAL_JUSTE) == []


def test_le_detail_apres_le_total_ne_deplace_pas_la_derniere_ligne() -> None:
    """« dont … » ne prend pas la place du total qu'il explique."""
    assert len(totaux_faux(TOTAL_PUIS_SON_DETAIL)) == 1
