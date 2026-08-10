"""Les quatre défauts de rendu relevés sur l'étude concurrentielle.

Signalés par la cliente le 09/08/2026, sur un document par ailleurs noté 7/10 :

  - des tableaux trop étroits, pages 10-11 ;
  - des URL longues écrites en clair dans le corps, page 40 ;
  - des renvois à un « chapitre 0 » absent du sommaire ;
  - des caractères parasites dans les mots à trait d'union (traité dans
    `test_la_typographie_est_reparee_pas_jugee.py`).

Trois d'entre eux se corrigent au RENDU ou dans le prompt, sans reprise et sans
dépense. Le quatrième — du CSV brut visible — n'a pas encore de cause établie ;
il n'est pas traité ici, et ne doit pas passer pour tel.
"""
from __future__ import annotations

import pytest

from generation.rendu_word.composants import (
    LARGEUR_UTILE_DXA,
    _largeurs,
    source_lisible,
)

# ── Tableaux trop étroits ────────────────────────────────────────────────────


def test_une_colonne_dense_recoit_plus_de_place_qu_une_colonne_breve() -> None:
    """Le défaut exact : neuf colonnes à parts strictement égales.

    Une colonne « Priorité » contenant « Haute » recevait autant de place qu'une
    colonne de recommandation de deux lignes, qui se retrouvait coupée en
    accordéon.
    """
    entetes = ["Priorité", "Recommandation"]
    lignes = [["Haute", "Renégocier les conditions d'achat avec les deux "
                        "fournisseurs principaux avant la fin du trimestre"]]

    largeurs = _largeurs(entetes, lignes, 2)

    assert largeurs[1] > largeurs[0]


def test_la_somme_des_largeurs_tient_dans_la_page() -> None:
    """Sans renormalisation, les bornes feraient déborder le tableau."""
    for colonnes in (2, 3, 5, 9):
        entetes = [f"Colonne {n}" for n in range(colonnes)]
        lignes = [[f"valeur {n}" for n in range(colonnes)]]

        total = sum(_largeurs(entetes, lignes, colonnes))

        assert total <= LARGEUR_UTILE_DXA + colonnes, colonnes


def test_aucune_colonne_ne_devient_un_filet() -> None:
    """CONTRE-ÉPREUVE : le plancher protège la colonne la plus brève.

    Sans lui, une colonne « Oui / Non » à côté d'un long commentaire tomberait
    à quelques millimètres — illisible, et pire que les parts égales d'avant.
    """
    entetes = ["Oui", "Analyse détaillée"]
    lignes = [["Oui", "x" * 400]]

    largeurs = _largeurs(entetes, lignes, 2)

    assert largeurs[0] >= LARGEUR_UTILE_DXA * 0.06


def test_un_tableau_equilibre_reste_equilibre() -> None:
    """Ce qui allait bien ne doit pas bouger."""
    entetes = ["Poste", "Année", "Total"]
    lignes = [["Loyer", "2025", "12 k€"], ["Charges", "2025", "3 k€"]]

    largeurs = _largeurs(entetes, lignes, 3)

    assert max(largeurs) / min(largeurs) < 2.0


# ── URL en clair dans le corps ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        (
            "Source : https://www.fevad.com/wp-content/uploads/2025/06/chiffres.pdf",
            "Source : fevad.com",
        ),
        ("D'après www.insee.fr/statistiques/1234", "D'après insee.fr"),
        ("Voir https://fr.wikipedia.org/wiki/Chose", "Voir wikipedia.org"),
    ],
)
def test_une_URL_devient_le_nom_de_sa_source(avant: str, apres: str) -> None:
    """« Il vaut mieux utiliser des noms de source propres. »

    Une URL de cent cinquante signes déborde de la colonne, coupe un mot en
    deux, et n'apprend rien que le nom du site ne dise mieux. Personne ne
    recopie une adresse depuis un PDF.
    """
    assert source_lisible(avant) == apres


@pytest.mark.parametrize(
    "texte",
    [
        "Fevad, 2025",
        "Insee, recensement 2025",
        "Estimation EVKHA à partir des données publiées",
        "Xerfi, étude petcare 2025",
    ],
)
def test_une_source_SANS_url_traverse_intacte(texte: str) -> None:
    """CONTRE-ÉPREUVE : on remplace l'adresse, jamais la source.

    Retirer la source entière ferait perdre l'information au nom de la mise en
    page — l'inverse de ce qui est demandé.
    """
    assert source_lisible(texte) == texte


def test_le_reste_de_la_phrase_survit_a_l_url() -> None:
    """La source garde son organisme et son année."""
    rendu = source_lisible("Fevad, 2025 — https://www.fevad.com/rapport.pdf")

    assert rendu.startswith("Fevad, 2025 —")
    assert "fevad.com" in rendu
    assert "https" not in rendu
