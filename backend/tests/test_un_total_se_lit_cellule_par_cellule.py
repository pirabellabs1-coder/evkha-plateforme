"""Un total se vérifie sur des GRANDEURS, pas sur les chiffres d'une phrase.

## Les motifs, relevés sur le corpus du 14/09/2026

    Colonne « Écart » : le tableau annonce un total de 0.00,
    mais ses lignes font 30,000.00.                        (73dde3ab)

    Colonne « Méthode d'évaluation » : le tableau annonce un total de
    12,001,000.00, mais ses lignes font 6,032.00.          (8bda1173)

`totaux_faux` lisait une cellule en retirant tout ce qui n'était ni chiffre
ni séparateur. Le SIGNE partait avec les lettres — « +15 000 € » et
« −15 000 € » faisaient 30 000 contre un écart nul annoncé, juste. Une cellule
de PROSE devenait un nombre : « Comparaison avec les ventes 2025 » valait 2025.
Et une cellule à deux nombres collait leurs chiffres en un seul.

Une cellule n'est désormais une grandeur que si elle porte UN nombre, et son
signe s'il est seul devant lui ; une colonne ne s'additionne que si toutes ses
cellules ont la même unité — ce que des phrases n'ont jamais. La contre-épreuve :
un vrai total faux, signé ou non, à unité composée ou non, reste accusé.
"""
from __future__ import annotations

from generation.arithmetique import _valeur_de_cellule, totaux_faux

ECARTS = """
| Poste | Prévu | Écart |
| --- | --- | --- |
| Ventes | 120 000 € | +15 000 € |
| Charges | 90 000 € | −15 000 € |
| Total | 210 000 € | 0 € |
"""

METHODES = """
| Poste | Méthode d'évaluation |
| --- | --- |
| Stock | Coût d'achat constaté sur les factures 2025 |
| Matériel | Valeur nette comptable au 31/12/2025 |
| Total | Somme des postes 1 à 12 000 |
"""


def test_le_signe_d_une_cellule_est_lu() -> None:
    assert _valeur_de_cellule("+15 000 €") == 15000
    assert _valeur_de_cellule("−15 000 €") == -15000
    assert _valeur_de_cellule("- 3 200") == -3200
    assert _valeur_de_cellule("**45 000 € HT**") == 45000


def test_une_phrase_ou_deux_nombres_ne_font_pas_une_grandeur() -> None:
    assert _valeur_de_cellule("mois 1 à 6") is None
    assert _valeur_de_cellule("Non chiffré") is None


def test_un_ecart_nul_n_est_pas_un_total_faux() -> None:
    assert totaux_faux(ECARTS) == []


def test_une_colonne_de_methodes_ne_s_additionne_pas() -> None:
    assert totaux_faux(METHODES) == []


def test_un_vrai_total_faux_reste_accuse() -> None:
    """Contre-épreuve : le correctif ne désarme pas le contrôle."""
    faux = ECARTS.replace("| 0 € |", "| 30 000 € |")
    fautes = totaux_faux(faux)
    assert [f.colonne for f in fautes] == ["Écart"]
    assert fautes[0].somme == 0

    montants = """
| Poste | Montant |
| --- | --- |
| Loyer | 12 000 € |
| Salaires | 48 000 € |
| Total | 70 000 € |
"""
    assert [f.colonne for f in totaux_faux(montants)] == ["Montant"]


def test_un_tiret_de_separation_n_est_pas_un_signe() -> None:
    assert _valeur_de_cellule("Charges – 5 000 €") == 5000
    assert _valeur_de_cellule("1 200 € HT par mois") == 1200


def test_une_colonne_a_unite_composee_reste_verifiee() -> None:
    """CONTRE-ÉPREUVE : « € HT par mois » est une unité, pas de la prose."""
    tableau = """
| Poste | Coût mensuel |
| --- | --- |
| Loyer | 1 200 € HT par mois |
| Salaires | 4 000 € HT par mois |
| Total | 9 000 € HT par mois |
"""
    assert [f.colonne for f in totaux_faux(tableau)] == ["Coût mensuel"]


def test_des_lignes_signees_sous_un_total_nu_se_comparent() -> None:
    """CONTRE-ÉPREUVE : le signe n'est pas une autre unité que l'euro."""
    tableau = """
| Poste | Écart |
| --- | --- |
| Ventes | +15 000 € |
| Services | +5 000 € |
| Total | 30 000 € |
"""
    fautes = totaux_faux(tableau)
    assert [f.somme for f in fautes] == [20000]


DUREES = """
| Ligne de sécurisation | Montant | Durée couverte |
| --- | --- | --- |
| Avance charges fixes | 1 200 € | 6 mois |
| Provision coûts variables | 1 000 € | 6 mois |
| Avance rémunération et cotisations | 8 000 € | 6 mois |
| Total du besoin en fonds de roulement | 10 200 € | 6 mois |
"""


def test_une_duree_commune_n_est_pas_une_somme() -> None:
    """Business plans `9f8f144a`, `256e63d8` : trois réserves pour la même période."""
    assert totaux_faux(DUREES) == []


def test_un_montant_faux_reste_accuse_a_cote_d_une_duree_commune() -> None:
    """CONTRE-ÉPREUVE : la colonne des montants se vérifie toujours."""
    fautes = totaux_faux(DUREES.replace("| 10 200 € |", "| 12 200 € |"))
    assert [f.colonne for f in fautes] == ["Montant"]
