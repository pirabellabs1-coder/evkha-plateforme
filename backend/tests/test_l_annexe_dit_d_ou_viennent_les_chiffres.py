"""Chaque chiffre du document dit s'il est vérifié, déclaré ou supposé.

Cliente, 08/09/2026, sur la stratégie du dossier `f7f2fad9` : « il faudrait que
chaque donnée chiffrée soit classée — vérifiée, déclarée, hypothèse — et que le
document montre le calcul plutôt que la seule conclusion ».

Le socle portait déjà cette information pour chacun de ses chiffres : fiabilité,
source, année, et pour une valeur calculée, sa formule. Rien n'en arrivait au
lecteur.

Ces tests échouent sur le code d'avant : l'annexe n'existait pas. La
contre-épreuve tient ce qui compte le plus — l'annexe est CONSTRUITE depuis le
socle, donc elle ne peut rien inventer et ne coûte rien.
"""
from __future__ import annotations

from datetime import date

import pytest

from generation.rendu_word.annexe_chiffres import blocs_annexe
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone


def _socle(*donnees: DonneeSocle) -> Socle:
    return Socle(
        secteur="assistance informatique",
        zone=Zone(pays="France"),
        date_socle=date(2026, 9, 12),
        donnees=list(donnees),
    )


def _donnee(**kwargs: object) -> DonneeSocle:
    defauts = {
        "id": "ca_actuel", "libelle": "Chiffre d'affaires actuel", "valeur": 120000.0,
        "unite": "EUR", "annee": 2026, "perimetre": Perimetre.NATIONAL,
        "fiabilite": Fiabilite.DECLAREE,
    }
    return DonneeSocle(**{**defauts, **kwargs})  # type: ignore[arg-type]


def _tableau(socle: Socle) -> list[list[str]]:
    blocs = blocs_annexe(socle, numero=21)
    return next(b["lignes"] for b in blocs if b["type"] == "tableau")


def test_un_chiffre_publie_est_dit_verifie_avec_sa_source() -> None:
    lignes = _tableau(_socle(_donnee(
        fiabilite=Fiabilite.OBSERVEE, source="Insee, 2025", valeur=96000.0, unite="MEUR",
    )))
    assert lignes[0][3] == "Vérifiée — Insee, 2025"


def test_un_chiffre_du_client_est_dit_declare() -> None:
    lignes = _tableau(_socle(_donnee(fiabilite=Fiabilite.DECLAREE)))
    assert lignes[0][3].startswith("Déclarée")
    assert "votre dossier" in lignes[0][3]


def test_une_hypothese_le_dit() -> None:
    lignes = _tableau(_socle(_donnee(fiabilite=Fiabilite.SCENARIO, id="ca_objectif_horizon")))
    assert lignes[0][3].startswith("Hypothèse")


def test_une_valeur_calculee_montre_son_calcul() -> None:
    """« Montrer le calcul plutôt que la seule conclusion ». La formule vit déjà
    dans le libellé d'une valeur calculée (`socle/calculs.py`)."""
    lignes = _tableau(_socle(_donnee(
        id="seuil_rentabilite", valeur=45000.0,
        libelle="Calculé : charges fixes ÷ taux de marge.",
        fiabilite=Fiabilite.ESTIMEE,
    )))
    assert lignes[0][3] == "Estimée — Calculé : charges fixes ÷ taux de marge"


def test_l_annexe_est_construite_depuis_le_socle_et_ne_coute_rien() -> None:
    """CONTRE-ÉPREUVE : aucun appel au modèle, et rien qui ne soit dans le socle."""
    socle = _socle(_donnee(), _donnee(id="panier_moyen", valeur=17.9, libelle="Panier moyen"))
    blocs = blocs_annexe(socle, numero=21)

    valeurs = {ligne[1] for ligne in _tableau(socle)}
    assert valeurs == {"120 000 EUR", "17,9 EUR"}
    assert blocs[0]["type"] == "bandeau"
    assert [b["type"] for b in blocs] == ["bandeau", "paragraphe", "tableau"]


def test_un_socle_vide_ne_produit_aucune_annexe() -> None:
    """Une annexe vide serait pire que pas d'annexe : elle promettrait une
    traçabilité qu'elle n'apporte pas."""
    assert blocs_annexe(_socle(), numero=21) == []


@pytest.mark.parametrize("fiabilite", list(Fiabilite))
def test_chaque_fiabilite_a_son_mot_pour_le_lecteur(fiabilite: Fiabilite) -> None:
    """Règle 4 : la classe, pas les cas — aucune fiabilité ne doit sortir nue."""
    lignes = _tableau(_socle(_donnee(
        fiabilite=fiabilite, source="Insee, 2025" if fiabilite == Fiabilite.OBSERVEE else "",
    )))
    assert lignes[0][3].split(" — ")[0] in ("Vérifiée", "Déclarée", "Estimée", "Hypothèse")
