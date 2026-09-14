"""Une figure impossible est redessinée avec ses propres données, quand c'est juste.

Stratégie Zenitek `a678b10a` (13/09/2026) : 29 figures demandées, 6 dessinées,
23 imprimées en tableau. Les motifs dominants — « unités hétérogènes », « le
radar exige des notes » — ne sont pas des erreurs de fond : parmi les données
demandées, deux montants ou deux effectifs forment souvent une figure juste.

Ces tests échouent sur le code d'avant : `reparation_figures` n'existait pas,
et toute figure refusée devenait un tableau.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from generation.chapitres.schema import Graphique, TypeGraphique
from generation.rendu_word import assemblage, secteurs
from generation.rendu_word.reparation_figures import reparer_la_figure
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone


def _donnee(identifiant: str, libelle: str, valeur: float, unite: str) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=libelle, valeur=valeur, unite=unite, annee=2026,
        perimetre=Perimetre.NATIONAL, fiabilite=Fiabilite.DECLAREE,
    )


def _socle() -> Socle:
    return Socle(
        secteur="assistance informatique", zone=Zone(pays="France"),
        date_socle=date(2026, 9, 13),
        donnees=[
            _donnee("ca_actuel", "Chiffre d'affaires actuel", 120000, "EUR"),
            _donnee("ca_cible", "Chiffre d'affaires visé", 250000, "EUR"),
            _donnee("abonnes", "Abonnés actifs", 14, "unite"),
        ],
    )


def _rendre(graphique: Graphique) -> tuple[list[dict[str, Any]], assemblage.RapportAssemblage]:
    socle = _socle()
    rapport = assemblage.RapportAssemblage()
    blocs = assemblage._blocs_graphique(
        socle, [graphique], secteurs.profil_du_secteur(socle.secteur), rapport, "Chapitre 14",
    )
    return blocs, rapport


def test_des_unites_melangees_donnent_la_figure_de_leur_plus_grand_groupe() -> None:
    """LE cas le plus fréquent : deux montants et un effectif dans la même figure.

    Les deux montants se tracent ; l'effectif part en tableau SOUS la figure.
    """
    blocs, rapport = _rendre(Graphique(
        type_graphique=TypeGraphique.BARRES,
        titre="Chiffre d'affaires actuel, objectif et abonnés",
        donnees_ids=["ca_actuel", "abonnes", "ca_cible"],
    ))

    assert [b["type"] for b in blocs] == ["graphique", "tableau"]
    assert len(rapport.graphiques_repares) == 1
    assert rapport.graphiques_abandonnes == [] and rapport.graphiques_en_tableau == []
    assert rapport.identifiants_rendus == {"ca_actuel", "ca_cible"}
    # La réparation retire une FORME, jamais un chiffre.
    assert {ligne[0] for ligne in blocs[1]["lignes"]} == {"Abonnés actifs"}


def test_un_radar_sans_notes_devient_des_barres() -> None:
    reparee = reparer_la_figure(_socle(), "radar", ["ca_actuel", "ca_cible"])

    assert reparee is not None
    assert reparee.resolution.type_graphique == "barres"
    assert reparee.ecartes == ()


def test_un_seul_chiffre_n_est_jamais_repare() -> None:
    """CONTRE-ÉPREUVE : la réparation n'invente aucune donnée."""
    assert reparer_la_figure(_socle(), "barres", ["ca_actuel", "abonnes"]) is None


def test_une_frise_ne_devient_pas_des_barres() -> None:
    """CONTRE-ÉPREUVE : « Jalons de la feuille de route » tracé en barres de
    montants ferait mentir son titre. Une forme qui exige des dates ne se
    répare pas avec des valeurs."""
    assert reparer_la_figure(_socle(), "chronologie", ["ca_actuel", "ca_cible"]) is None


def test_une_figure_valide_n_est_pas_touchee() -> None:
    """CONTRE-ÉPREUVE : rien à réparer, rien de compté comme réparé."""
    blocs, rapport = _rendre(Graphique(
        type_graphique=TypeGraphique.BARRES,
        titre="Chiffre d'affaires actuel et visé",
        donnees_ids=["ca_actuel", "ca_cible"],
    ))

    assert [b["type"] for b in blocs] == ["graphique"]
    assert rapport.graphiques_repares == []
    assert rapport.graphiques_rendus == 1


def test_une_part_d_un_tout_n_est_jamais_redessinee_sur_une_partie() -> None:
    """LE défaut bloquant de la relecture du 13/09/2026.

    Un anneau « segment A, segment B, autres » réparé sans « autres » affichait
    57 % / 43 % et un total de 700 000 € — des chiffres absents du dossier. Les
    parts d'un tout ne se réparent qu'en barres, qui montrent les valeurs.
    """
    socle = Socle(
        secteur="assistance informatique", zone=Zone(pays="France"),
        date_socle=date(2026, 9, 13),
        donnees=[
            _donnee("seg_a", "CA segment A", 400000, "EUR"),
            _donnee("seg_b", "CA segment B", 300000, "EUR"),
            _donnee("autres", "Part des autres segments", 30, "%"),
        ],
    )
    for forme in ("anneau", "camembert", "entonnoir", "barres_empilees"):
        reparee = reparer_la_figure(socle, forme, ["seg_a", "seg_b", "autres"])
        assert reparee is not None, forme
        assert reparee.resolution.type_graphique == "barres", forme


def test_une_figure_reparee_n_est_pas_creditee_au_modele(monkeypatch: Any) -> None:
    """La mesure ne se flatte pas : une figure réparée n'a pas été « obtenue ».

    Passe par `mesurer()` lui-même — la première version de ce test recopiait
    la formule, et retirer la soustraction ne l'aurait pas fait échouer.
    """
    from types import SimpleNamespace

    from generation import mesure

    rapport = assemblage.RapportAssemblage()
    rapport.graphiques_demandes, rapport.graphiques_rendus = 3, 3
    rapport.graphiques_repares = ["a", "b"]
    monkeypatch.setattr(
        "generation.rendu_word.services.produire_docx",
        lambda job, destination: SimpleNamespace(rapport=rapport, chemin=destination),
    )
    monkeypatch.setattr(
        "generation.verification.services.verifier_livrable",
        lambda *a, **k: SimpleNamespace(anomalies=[]),
    )
    monkeypatch.setattr(mesure, "sections_du_dossier", lambda job: [])

    resultat = mesure.mesurer(SimpleNamespace(research_brief=""))  # type: ignore[arg-type]

    assert (resultat.figures_obtenues, resultat.figures_reparees) == (1, 2)


def test_une_figure_perdue_dit_pourquoi_sa_reparation_a_echoue() -> None:
    """La mesure doit dire QUELLE étape refuse : la demande, ou la réparation."""
    blocs, rapport = _rendre(Graphique(
        type_graphique=TypeGraphique.BARRES,
        titre="Chiffre d'affaires et abonnés",
        donnees_ids=["ca_actuel", "abonnes"],
    ))

    assert len(rapport.diagnostic_des_abandons) == 1
    diagnostic = rapport.diagnostic_des_abandons[0]
    assert diagnostic["donnees"] == [
        {"id": "ca_actuel", "unite": "EUR"}, {"id": "abonnes", "unite": "unite"},
    ]
    assert "aucun groupe" in str(diagnostic["reparation"])
