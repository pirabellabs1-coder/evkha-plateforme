"""Une figure qu'on ne peut pas dessiner se redemande — elle ne disparaît plus.

Stratégie Zenitek, reprise `b098ded3` du 12/09/2026 : 31 figures demandées,
31 impossibles. Le défaut n'a été vu qu'à l'ASSEMBLAGE, c'est-à-dire une fois
les 21 chapitres écrits et payés. Les figures ont alors simplement disparu du
document, et plus rien ne pouvait les rattraper : une figure ne se répare pas
après coup, elle se redemande.

Elle est donc jugée à l'acceptation du chapitre, par le moteur qui dessine —
et le chapitre repart avec le motif exact. Demande du 12/09/2026 : « tout doit
être vérifié et validé d'abord, avant que ce soit plaqué dans le document ».

La contre-épreuve tient l'autre bord : au DERNIER essai, un chapitre juste ne
se perd pas pour une figure. Ses données partiront en tableau.
"""
from __future__ import annotations

from datetime import date

from generation.chapitres.runner import _motifs_de_figure
from generation.chapitres.schema import (
    BlocGraphique,
    ChapitrePayload,
    Graphique,
    TypeGraphique,
)
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone


def _socle() -> Socle:
    def donnee(identifiant: str, valeur: float, unite: str) -> DonneeSocle:
        return DonneeSocle(
            id=identifiant, libelle=identifiant.replace("_", " "), valeur=valeur,
            unite=unite, annee=2026, perimetre=Perimetre.NATIONAL,
            fiabilite=Fiabilite.DECLAREE,
        )

    return Socle(
        secteur="assistance informatique", zone=Zone(pays="France"),
        date_socle=date(2026, 9, 12),
        donnees=[
            donnee("ca_actuel", 120000, "EUR"),
            donnee("ca_cible", 250000, "EUR"),
            donnee("abonnes", 14, "unite"),
        ],
    )


def _payload(*identifiants: str, titre: str = "Repères économiques") -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=5, titre="Lecture économique", accroche="",
        blocs=[
            BlocGraphique(
                graphique=Graphique(
                    type_graphique=TypeGraphique.BARRES,
                    titre=titre,
                    donnees_ids=list(identifiants),
                )
            )
        ],
        donnees_utilisees=list(identifiants),
        resume="Résumé du chapitre, assez long pour tenir le contrat de forme.",
    )


def test_une_figure_aux_unites_melangees_fait_refaire_le_chapitre() -> None:
    """LE cas : un montant et un effectif dans la même figure — 14 fois sur 31."""
    motifs = _motifs_de_figure(_payload("ca_actuel", "abonnes"), _socle())

    assert len(motifs) == 1
    assert "impossible à dessiner" in motifs[0]
    # Règle 2 : le motif doit être actionnable par qui doit corriger.
    assert "unités hétérogènes" in motifs[0]
    assert "figures réalisables" in motifs[0]


def test_une_figure_realisable_ne_reproche_rien() -> None:
    """CONTRE-ÉPREUVE : le contrôle ne doit pas renvoyer un chapitre correct."""
    assert _motifs_de_figure(_payload("ca_actuel", "ca_cible"), _socle()) == []


def test_au_dernier_essai_le_chapitre_n_est_pas_perdu() -> None:
    """Un chapitre juste ne se perd pas pour une figure : ses données iront en tableau.

    C'est l'arbitrage déjà retenu ailleurs dans ce moteur — le texte du
    chapitre vaut plus que sa mise en forme.
    """
    motifs = _motifs_de_figure(
        _payload("ca_actuel", "abonnes"), _socle(), derniere_tentative=True
    )
    assert motifs == []
