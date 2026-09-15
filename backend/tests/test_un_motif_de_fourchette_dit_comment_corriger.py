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
