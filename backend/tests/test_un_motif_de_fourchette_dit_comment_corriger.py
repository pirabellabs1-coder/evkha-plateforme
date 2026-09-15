"""Un motif de fourchette dit COMMENT corriger, et la forme parle le langage du moteur.

## Le défaut mesuré

Génération de preuve `7567ca2f` (15/09/2026). Le brief donne un coût variable
par livrable — étude de marché 7 €, business plan 6 €, stratégie 6 €, étude de
la concurrence 4 € — et un tarif par offre — 149 €, 149 €, 185 €, 195 €. Le
document écrivait « 4 à 7 € » et « 149-195 € ». Deux passes de relecture n'ont
pas convergé : le motif demandait « un chiffre unique », que personne n'avait
décidé. Quand les deux bornes sont des valeurs que le client donne séparément,
le motif dit désormais d'écrire chaque valeur avec sa variante.

Et la consigne de forme parlait du « champ `contenu` d'une section » — l'ancien
format de chapitre. Les blocs `paragraphe` n'étaient bornés par rien :
paragraphe médian de 37 à 41 mots aux chapitres 2, 17 et 19, pour un plafond de
25.
"""
from __future__ import annotations

from generation.gate import _motif_de_fourchette


def test_des_valeurs_donnees_separement_font_ecrire_chaque_variante() -> None:
    motif = _motif_de_fourchette("4 à 7 €", "4", "7", {7.0, 6.0, 4.0, 149.0})
    assert motif.startswith("Fourchette detectee : « 4 à 7 € ».")
    assert "chaque valeur avec ce qu'elle désigne" in motif


def test_une_plage_inventee_garde_le_motif_du_chiffre_unique() -> None:
    """CONTRE-ÉPREUVE : une borne que le client n'a pas donnée."""
    motif = _motif_de_fourchette("15 à 2 500 €", "15", "2 500", {15.0, 149.0})
    assert "chiffre unique" in motif
    assert "chaque valeur" not in motif


def test_la_forme_borne_les_blocs_paragraphe_au_seuil_du_controle() -> None:
    from generation.chapitres.runner import _bloc_forme
    from generation.verification.controles import seuils_de_densite

    for livrable in ("business_plan", "competitor_study", "business_strategy"):
        forme = _bloc_forme(livrable)
        assert "champ `contenu` d'une section" not in forme
        plafond = seuils_de_densite(livrable).mediane_paragraphe_max
        assert f"Un bloc `paragraphe` tient en {plafond} mots au plus" in forme


def test_un_catalogue_court_se_dit_sans_toucher_a_l_objectif() -> None:
    """`cd639627` : quatre figures possibles, vingt-deux demandées, huit inventées."""
    from datetime import date
    from unittest.mock import MagicMock, patch

    from generation.chapitres.runner import _bloc_visuels
    from generation.socle.referentiel import Fiabilite, Perimetre
    from generation.socle.schema import DonneeSocle, Socle, Zone

    socle = Socle(
        secteur="legaltech", zone=Zone(pays="France"), date_socle=date(2026, 9, 15),
        donnees=[DonneeSocle(
            id="ca_objectif_an1", libelle="CA", valeur=51030, unite="EUR", annee=2026,
            perimetre=Perimetre.ENTREPRISE, fiabilite=Fiabilite.DECLAREE,
        )],
    )
    job = MagicMock()
    with patch("generation.chapitres.runner.formes_deja_employees", return_value=[]), \
            patch("generation.rendu_word.catalogue_figures.figures_possibles",
                  return_value=[object()] * 4):
        bloc = _bloc_visuels(socle, job, 6)
    assert "CE SOCLE NE PERMET QUE 4 FIGURE(S)" in bloc
    with patch("generation.chapitres.runner.formes_deja_employees", return_value=[]), \
            patch("generation.rendu_word.catalogue_figures.figures_possibles",
                  return_value=[object()] * 24):
        assert "CE SOCLE NE PERMET QUE" not in _bloc_visuels(socle, job, 6)
