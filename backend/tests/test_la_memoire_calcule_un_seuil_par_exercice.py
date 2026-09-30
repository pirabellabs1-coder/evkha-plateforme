"""La mémoire calcule un seuil de rentabilité PAR EXERCICE, et l'analyse de sensibilité.

Business plan ÉCLORE `28a257bf` (30/09/2026) : la marge de sécurité de chaque
exercice était calculée par la mémoire sur le seuil unique du socle — celui
du premier exercice —, et quatre sections reprenaient des marges fausses. Le
même document écrivait qu'on ne pouvait pas construire de scénario de baisse
du chiffre d'affaires. Et la « CAF mensuelle » de la mémoire a été lue comme
le revenu mensuel de la dirigeante, puis redivisée par douze.

Chiffres fictifs.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.memoire.etude import MemoireEtude
from generation.memoire.faits import faits_de_l_etude
from generation.socle.schema import Socle


def _socle(avec_taux: bool = True) -> Socle:
    donnees: list[dict[str, Any]] = [
        {"id": f"{serie}_an{rang}", "libelle": f"{serie} {rang}", "valeur": valeur,
         "unite": "EUR", "annee": 2026 + rang, "perimetre": "entreprise",
         "fiabilite": "declaree"}
        for serie, valeurs in (
            ("ca_previsionnel", (20_000.0, 40_000.0, 80_000.0)),
            ("resultat_net", (100.0, 6_000.0, 20_000.0)),
            ("caf", (400.0, 6_300.0, 20_300.0)),
        )
        for rang, valeur in enumerate(valeurs, start=1)
    ]
    donnees.append({
        "id": "seuil_rentabilite", "libelle": "Seuil", "valeur": 19_900.0, "unite": "EUR",
        "annee": 2027, "perimetre": "entreprise", "fiabilite": "declaree",
    })
    if avec_taux:
        donnees.append({
            "id": "marge_brute_taux", "libelle": "Taux de marge", "valeur": 100.0,
            "unite": "%", "annee": 2027, "perimetre": "entreprise", "fiabilite": "scenario",
        })
    return Socle.model_validate({
        "secteur": "loisirs", "zone": {"pays": "France"}, "date_socle": "2026-09-01",
        "donnees": donnees, "concurrents": [],
    })


def test_chaque_exercice_a_son_seuil() -> None:
    faits = faits_de_l_etude(_socle())
    assert faits["seuil_rentabilite_an1"].valeur == pytest.approx(19_900.0)
    assert faits["seuil_rentabilite_an2"].valeur == pytest.approx(34_000.0)
    assert faits["seuil_rentabilite_an3"].valeur == pytest.approx(60_000.0)


def test_la_marge_de_securite_se_calcule_sur_le_seuil_de_son_exercice() -> None:
    """Et non sur celui du premier exercice : 50,2 % au lieu de 15 %, c'était le défaut."""
    faits = faits_de_l_etude(_socle())
    assert faits["marge_securite_an1"].valeur == pytest.approx(0.5)
    assert faits["marge_securite_an2"].valeur == pytest.approx(15.0)
    assert faits["marge_securite_an3"].valeur == pytest.approx(25.0)


def test_sans_taux_de_marge_seule_l_annee_du_seuil_a_sa_marge() -> None:
    """Contre-épreuve : sans quoi calculer le seuil des autres exercices, on ne l'invente pas."""
    faits = faits_de_l_etude(_socle(avec_taux=False))
    assert faits["marge_securite_an1"].valeur == pytest.approx(0.5)
    assert "marge_securite_an2" not in faits
    assert "seuil_rentabilite_an2" not in faits


def test_la_caf_n_a_pas_de_moyenne_mensuelle_et_chaque_fait_porte_sa_periode() -> None:
    faits = faits_de_l_etude(_socle())
    assert "caf_mensuel_an1" not in faits
    assert faits["resultat_net_mensuel_an1"].periode == "mois"
    assert faits["resultat_net_an1"].periode == "an"
    assert faits["marge_securite_an1"].periode == ""


def test_un_business_plan_porte_son_analyse_de_sensibilite() -> None:
    memoire = MemoireEtude.construire(_socle(), {}, "business_plan")
    assert memoire.faits["ca_moins_20_pc_an3"].valeur == pytest.approx(64_000.0)
    assert memoire.faits["resultat_net_moins_10_pc_an3"].valeur == pytest.approx(12_000.0)
    assert memoire.faits["resultat_net_moins_20_pc_an3"].valeur == pytest.approx(4_000.0)


def test_une_etude_de_marche_n_en_porte_pas() -> None:
    """Contre-épreuve : la sensibilité est une pièce du business plan."""
    memoire = MemoireEtude.construire(_socle(), {}, "market_study")
    assert not [i for i in memoire.faits if "_moins_" in i]


def _socle_a_60_pc(charges_fixes_an2: float | None = None) -> Socle:
    """Un taux de marge de 60 % : un taux de 100 % masque les erreurs de ×/÷ taux."""
    donnees: list[dict[str, Any]] = [
        {"id": f"{serie}_an{rang}", "libelle": f"{serie} {rang}", "valeur": valeur,
         "unite": "EUR", "annee": 2026 + rang, "perimetre": "entreprise",
         "fiabilite": "declaree"}
        for serie, valeurs in (
            ("ca_previsionnel", (20_000.0, 40_000.0)),
            ("resultat_net", (100.0, 6_000.0)),
        )
        for rang, valeur in enumerate(valeurs, start=1)
    ]
    donnees.append({
        "id": "marge_brute_taux", "libelle": "Taux de marge", "valeur": 60.0,
        "unite": "%", "annee": 2027, "perimetre": "entreprise", "fiabilite": "scenario",
    })
    if charges_fixes_an2 is not None:
        donnees.append({
            "id": "charges_fixes_an2", "libelle": "Charges fixes 2", "valeur": charges_fixes_an2,
            "unite": "EUR", "annee": 2028, "perimetre": "entreprise", "fiabilite": "declaree",
        })
    return Socle.model_validate({
        "secteur": "loisirs", "zone": {"pays": "France"}, "date_socle": "2026-09-01",
        "donnees": donnees, "concurrents": [],
    })


def test_a_60_pc_le_seuil_et_la_sensibilite_divisent_et_multiplient_par_le_taux() -> None:
    """CA 40 000 €, résultat 6 000 €, marge 60 % : charges fixes 18 000 €, seuil 30 000 €.

    À −10 %, la marge perdue est 4 000 € × 60 % = 2 400 € : le résultat passe à
    3 600 € — pas à 2 000 € (baisse du CA entière) ni à 6 000 € − 4 000 ÷ 0,6.
    """
    memoire = MemoireEtude.construire(_socle_a_60_pc(), {}, "business_plan")
    assert memoire.faits["seuil_rentabilite_an2"].valeur == pytest.approx(30_000.0)
    assert memoire.faits["marge_securite_an2"].valeur == pytest.approx(25.0)
    assert memoire.faits["resultat_net_moins_10_pc_an2"].valeur == pytest.approx(3_600.0)
    assert memoire.faits["resultat_net_moins_20_pc_an2"].valeur == pytest.approx(1_200.0)


def test_les_charges_fixes_declarees_font_le_seuil() -> None:
    """Le socle déclare 21 000 € de charges fixes : seuil 35 000 €, pas les 30 000 € reconstitués.

    Le résultat net a pu supporter l'impôt ou des intérêts : le seuil reconstitué
    depuis lui n'est qu'un repli, qui dit son hypothèse.
    """
    faits = faits_de_l_etude(_socle_a_60_pc(charges_fixes_an2=21_000.0))
    assert faits["seuil_rentabilite_an2"].valeur == pytest.approx(35_000.0)
    assert faits["seuil_rentabilite_an2"].formule == "charges_fixes_an2 ÷ marge_brute_taux"
    assert faits["marge_securite_an2"].valeur == pytest.approx(12.5)


def test_le_seuil_reconstitue_dit_son_hypothese() -> None:
    faits = faits_de_l_etude(_socle_a_60_pc())
    assert "sans impôt" in faits["seuil_rentabilite_an2"].formule
