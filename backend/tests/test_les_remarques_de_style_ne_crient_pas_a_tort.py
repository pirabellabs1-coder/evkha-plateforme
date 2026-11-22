"""Les remarques de style du business plan de test `9e38eb81` (18/11/2026).

Relues une par une dans le document. La plupart n'étaient pas des défauts du
texte mais des lectures fausses du contrôle — et deux d'entre elles (les zéros,
la densité) font RÉÉCRIRE des chapitres, donc payer :

- « Depot » signalé comme une faute : c'est l'épicerie « Le Petit Depot » ;
- neuf « redites », dont sept sont des constructions voulues ;
- trois zéros « inexpliqués », tous trois expliqués ;
- le seuil de rentabilité du client rangé en « hypothèse », donc recalculé ;
- un rythme de paragraphes que deux puces de la consigne contredisaient.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from catalog.models import DeliverableType
from generation.chapitres.runner import _DOSAGE_PAR_LIVRABLE
from generation.memoire.faits import faits_de_l_etude
from generation.orthographe import graphies_suspectes
from generation.relecture.constat import Reference
from generation.relecture.document import Document, Section
from generation.relecture.redaction import controler
from generation.socle.builder import declarer_le_seuil_du_client
from generation.socle.schema import Socle
from generation.verification.controles import controler_les_valeurs_nulles
from generation.verification.lecture import DocumentLu, mesures_dans

BP = DeliverableType.BUSINESS_PLAN


# ── Un nom de marque s'écrit comme la marque l'écrit ────────────────────────


def test_la_suite_d_un_nom_propre_n_est_pas_une_faute_d_accent() -> None:
    suspectes = graphies_suspectes([
        "Le Petit Depot et The French Grocer vendent en ligne à Singapour.",
        "Le dépôt de marque reste à faire. 13.9 Dépôt de marque.",
    ])

    assert "Depot" not in suspectes


def test_un_nom_commun_sans_ses_accents_reste_signale() -> None:
    """Contre-épreuve : la faute d'accent ordinaire se voit toujours."""
    suspectes = graphies_suspectes([
        "Le depot de marque reste à faire, après une etude precise.",
        "Aucun dépôt n'est fait. Notre étude est précise.",
    ])

    assert suspectes == {"depot": "dépôt", "etude": "étude", "precise": "précise"}


# ── Une construction voulue n'est pas une redite ────────────────────────────


def _redites(texte: str) -> list[str]:
    document = Document(sections=[
        Section(numero="5.1", titre="", chapitre=5, paragraphes=[texte], tableaux=[]),
    ])
    return [c.detail for c in controler(document, Reference()) if c.classe == "repetition"]


@pytest.mark.parametrize("texte", [
    # Le nom d'un indicateur.
    "La franchise reste possible tant que le chiffre d'affaires annuel ne dépasse pas "
    "le seuil, et le chiffre d'affaires visé le dépasse dès la première année.",
    # Un nom propre.
    "Les deux plateformes indirectes Tmall Global et Rakuten affichent la meilleure "
    "couverture, mais Tmall Global et JD Worldwide restent généralistes.",
    # Une corrélation.
    "Ce changement de forme ne modifie ni le régime fiscal, ni le régime de TVA, "
    "posés dans ce chapitre.",
    # Une énumération de valeurs.
    "Un budget publicitaire de 3,20 euros par commande sur l'année, qui doit "
    "descendre à 2,30 euros par commande en 2030.",
    "Une bouteille de vin de vigneron autour de 22,60 €, un champagne de vigneron "
    "autour de 39 €.",
])
def test_une_reprise_que_la_phrase_appelle_n_est_pas_signalee(texte: str) -> None:
    assert _redites(texte) == []


def test_une_vraie_redite_reste_signalee() -> None:
    """Contre-épreuve : la tournure de la cliente, et celle du document."""
    assert _redites(
        "Carine quitte son poste et passe à temps plein après avoir quitté son poste."
    )
    assert _redites(
        "Ce choix tient à la structure de notre modèle : le producteur fixe son prix, "
        "et Gourming reste le comparateur le plus proche de notre modèle."
    )


# ── Un zéro dit n'est pas une donnée manquante ──────────────────────────────


def _zeros_signales(cellule: str) -> int:
    lu = DocumentLu(chemin=Path("memoire.docx"))
    lu.cellules = [cellule]
    lu.mesures = mesures_dans(cellule, dans_un_tableau=True)
    return len(controler_les_valeurs_nulles(lu))


@pytest.mark.parametrize("cellule", [
    "Mouvement : Rémunération du président | 0 € | Choix de gestion : non rémunéré "
    "la première année",
    "Donnée : Masse salariale, exercice 2027 (0 salarié) | 0 € | 2027 | Hypothèse — "
    "posée pour raisonner, à confirmer",
])
def test_un_zero_decide_ou_annote_par_l_annexe_n_est_pas_signale(cellule: str) -> None:
    assert _zeros_signales(cellule) == 0


@pytest.mark.parametrize("cellule", [
    "Poste : Coût d'acquisition | 0 € (non chiffré) | Statut",
    "Poste : Budget publicitaire | 0 € | non renseigné par le porteur à ce stade du projet",
    "Poste : Budget publicitaire | 0 € | à confirmer",
])
def test_un_zero_qui_avoue_un_manque_reste_signale(cellule: str) -> None:
    """Contre-épreuve : « je ne sais pas » n'explique pas un zéro."""
    assert _zeros_signales(cellule) == 1


# ── Le seuil de rentabilité du client est une donnée déclarée ───────────────


def _donnee(identifiant: str, valeur: float, *, annee: int = 2027,
            fiabilite: str = "scenario", unite: str = "EUR") -> dict[str, Any]:
    return {
        "id": identifiant, "libelle": identifiant, "valeur": valeur, "unite": unite,
        "annee": annee, "perimetre": "entreprise", "fiabilite": fiabilite,
    }


def _socle(*supplements: dict[str, Any]) -> Socle:
    donnees = [
        _donnee("ca_previsionnel_an1", 136_800.0), _donnee("resultat_net_an1", 1_954.0),
        _donnee("ca_previsionnel_an2", 281_556.0, annee=2028),
        _donnee("resultat_net_an2", 23_335.0, annee=2028),
        _donnee("seuil_rentabilite", 130_535.0),
        _donnee("marge_brute_taux", 100.0, unite="%"),
        *supplements,
    ]
    return Socle.model_validate({
        "secteur": "place de marché", "zone": {"pays": "France"},
        "date_socle": "2026-11-18", "donnees": donnees, "concurrents": [],
    })


def test_un_seuil_ecrit_par_le_client_devient_declare_et_n_est_plus_recalcule() -> None:
    """Le dossier : rangé en « hypothèse », le seuil était recalculé à 134 846 €."""
    socle = _socle()
    assert faits_de_l_etude(socle)["seuil_rentabilite_an1"].valeur == pytest.approx(134_846.0)

    assert declarer_le_seuil_du_client(socle, [130_535.0, 206_744.0]) is True

    assert faits_de_l_etude(socle)["seuil_rentabilite_an1"].valeur == pytest.approx(130_535.0)


def test_un_seuil_que_le_client_n_a_pas_ecrit_reste_une_hypothese() -> None:
    """Contre-épreuve."""
    socle = _socle()

    assert declarer_le_seuil_du_client(socle, [136_800.0, 35.0]) is False
    assert faits_de_l_etude(socle)["seuil_rentabilite_an1"].valeur == pytest.approx(134_846.0)


def test_le_seuil_d_un_exercice_reserve_au_client_prime_quelle_que_soit_sa_fiabilite() -> None:
    socle = _socle(_donnee("seuil_rentabilite_an2", 206_744.0, annee=2028))

    assert faits_de_l_etude(socle)["seuil_rentabilite_an2"].valeur == pytest.approx(206_744.0)


# ── Le rythme des paragraphes du business plan ──────────────────────────────


def test_le_business_plan_mene_chaque_idee_au_bout() -> None:
    """La puce du 18/11 demandait des paragraphes d'une ou deux phrases, sur la
    foi d'une médiane qui comptait les titres de Findrax (remesurée le
    22/11/2026 : sa prose a un paragraphe médian de 69 mots)."""
    dosage = _DOSAGE_PAR_LIVRABLE[str(BP)]

    assert "deux ou trois phrases simples" in dosage
    assert "la plupart des paragraphes sont courts" not in dosage
    # L'ancienne puce, que le modèle retenait seule.
    assert "Un paragraphe peut être développé" not in dosage
