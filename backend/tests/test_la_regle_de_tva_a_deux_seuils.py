"""La règle de TVA a deux seuils ; la mémoire montre la période ; la relecture lit l'accroche.

Business plan ÉCLORE `28a257bf` (30/09/2026) :
- « la TVA s'applique dès que le chiffre d'affaires dépasse le seuil de
  franchise (37 500 €) » : la justification de la mémoire ne nommait que ce
  seuil. Règle exacte : bascule en cours d'année au-delà du seuil MAJORÉ ;
  entre les deux seuils, la franchise vaut encore l'année même ;
- un montant mensuel réemployé comme annuel : le rédacteur ne voyait pas la
  période des faits ;
- « Trois univers, huit formats » était dans l'accroche du chapitre, que la
  relecture avant rendu ne lisait pas.
Chiffres fictifs.
"""
from __future__ import annotations

from generation.memoire.etude import MemoireEtude
from generation.memoire.faits import Fait
from generation.memoire.regles import Nature, regime_de_tva
from generation.relecture import document_du_chapitre


def test_au_dela_du_seuil_majore_la_tva_s_applique_des_le_depassement() -> None:
    decision = regime_de_tva(60_000.0, 2028, Nature.SERVICES)
    assert decision is not None and decision.valeur == "TVA obligatoire"
    assert "seuil majoré (41 250 €)" in decision.justification
    assert "dès le jour du dépassement" in decision.justification


def test_entre_les_deux_seuils_la_franchise_vaut_encore_l_annee_meme() -> None:
    decision = regime_de_tva(39_000.0, 2028, Nature.SERVICES)
    assert decision is not None
    assert "obligatoire" not in decision.valeur.lower()
    assert "1er janvier" in decision.justification


def test_sous_le_seuil_la_franchise_reste() -> None:
    """Contre-épreuve."""
    decision = regime_de_tva(20_000.0, 2028, Nature.SERVICES)
    assert decision is not None and decision.valeur == "franchise en base"


def test_la_memoire_montre_la_periode_de_chaque_fait() -> None:
    faits = {
        "resultat_net_an1": Fait(id="resultat_net_an1", valeur=12_000.0, unite="EUR",
                                 libelle="Résultat net", origine="declaree", periode="an"),
        "resultat_net_mensuel_an1": Fait(
            id="resultat_net_mensuel_an1", valeur=1_000.0, unite="EUR",
            libelle="Résultat net mensuel", origine="calculee", periode="mois",
        ),
        "apport": Fait(id="apport", valeur=5_000.0, unite="EUR", libelle="Apport",
                       origine="declaree"),
    }
    bloc = MemoireEtude(faits=faits).bloc_pour_le_redacteur()
    assert "{{resultat_net_an1}} : 12" in bloc and " par an — Résultat net" in bloc
    assert " par mois — Résultat net mensuel" in bloc
    assert "{{apport}}" in bloc and "par an — Apport" not in bloc


def test_la_relecture_lit_l_accroche_du_chapitre() -> None:
    document = document_du_chapitre({
        "chapitre": 8, "titre": "Offre", "accroche": "Trois univers, huit formats.",
        "blocs": [{"type": "paragraphe", "texte": "Le détail suit."}],
    })
    assert "Trois univers, huit formats." in document.sections[0].paragraphes
