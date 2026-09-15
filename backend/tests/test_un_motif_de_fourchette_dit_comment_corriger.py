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

import pytest

from generation.gate import _motif_de_fourchette

CLIENT = {
    (7.0, "eur"), (6.0, "eur"), (4.0, "eur"), (149.0, "eur"), (60.0, "eur"), (75.0, "eur"),
    (7000.0, "eur"), (4000.0, "eur"),
}


def test_des_valeurs_donnees_separement_font_ecrire_chaque_variante() -> None:
    motif = _motif_de_fourchette("4 à 7 €", "4", "7", "€", CLIENT)
    assert motif.startswith("Fourchette detectee : « 4 à 7 € ».")
    assert "chaque valeur avec ce qu'elle désigne" in motif


def test_une_plage_inventee_garde_le_motif_du_chiffre_unique() -> None:
    """CONTRE-ÉPREUVE : une borne que le client n'a pas donnée."""
    motif = _motif_de_fourchette(
        "15 à 2 500 €", "15", "2 500", "€", {(15.0, "eur"), (149.0, "eur")}
    )
    assert "chiffre unique" in motif
    assert "chaque valeur" not in motif


def test_des_euros_du_client_ne_sont_pas_des_pourcentages_du_document() -> None:
    """`7567ca2f` : « 60 à 75 % » de charges sociales, 60 € et 75 € au client."""
    motif = _motif_de_fourchette("60 à 75 %", "60", "75", "%", CLIENT)
    assert "SÉPARÉMENT" not in motif
    assert "chiffre unique" in motif
    assert "SÉPARÉMENT" in _motif_de_fourchette("60 à 75 €", "60", "75", "euros", CLIENT)


def test_les_multiples_se_comparent_en_unites_de_base() -> None:
    assert "SÉPARÉMENT" in _motif_de_fourchette("4 à 7 k€", "4", "7", "k€", CLIENT)
    assert "SÉPARÉMENT" in _motif_de_fourchette("4 à 7 kEUR", "4", "7", "kEUR", CLIENT)


def test_les_valeurs_du_client_portent_leur_unite(monkeypatch: pytest.MonkeyPatch) -> None:
    """L'extraction elle-même, sur un brief et un document doublés."""
    from generation import documents_client, gate
    from generation.verification import services

    brief = "Charges : 60 € et 75 €\nObjectif 2026\n12 %"
    document = "Budget 1,5 k€ ; 30 abonnés"
    monkeypatch.setattr(gate, "_brief_free_text", lambda job, avec="": "coût 7 € HT, 6 €, 4 €")
    monkeypatch.setattr(services, "_brief_complet", lambda job: brief)
    monkeypatch.setattr(documents_client, "texte_des_documents", lambda job: document)
    valeurs = services.valeurs_du_client(object())  # type: ignore[arg-type]
    assert {(7.0, "eur"), (6.0, "eur"), (60.0, "eur"), (75.0, "eur"), (1500.0, "eur")} <= valeurs
    assert (12.0, "%") in valeurs and (202612.0, "%") not in valeurs
    assert (60.0, "%") not in valeurs
    assert not any(v == 30.0 for v, _ in valeurs)


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
