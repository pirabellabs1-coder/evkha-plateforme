"""Ce que le client écrit prime ; ce que l'outil calcule n'est pas « hors socle ».

Business plan de test `9e38eb81` (18/11/2026), quarante constats restants. Les
classes corrigées ici :

- le seuil de rentabilité que le client donne (130 535 €) était recalculé par la
  mémoire (131 475,29 €) : deux valeurs dans le même document ;
- le résultat net que le client écrit « 1 954 € » était imprimé « 1 954,17 € » ;
- les calculs de la mémoire (évolutions, moyennes mensuelles, scénarios à −10 %)
  étaient signalés comme des chiffres inventés — vingt-huit fois ;
- un calcul sur des termes à l'euro sortait au centime à côté d'eux ;
- « un écart de 20 à 30 % » : une marge d'incertitude inventée ;
- le volume de ventes de l'annexe était lu comme le chiffre d'affaires.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from catalog.models import DeliverableType
from generation.controle_final import les_sources_en_dernier
from generation.memoire.decisions import decisions_de_l_etude
from generation.memoire.faits import faits_de_l_etude
from generation.prompts import build_system_prompt
from generation.relecture.valeurs import serie_nommee
from generation.socle.builder import reprendre_les_montants_du_client
from generation.socle.referentiel import identifiants_du_client
from generation.socle.schema import Socle
from generation.verification import controles
from generation.verification.lecture import DocumentLu, mesures_dans

BP = DeliverableType.BUSINESS_PLAN


def _donnee(
    identifiant: str, valeur: float, *, unite: str = "EUR", annee: int = 2027,
    fiabilite: str = "declaree",
) -> dict[str, Any]:
    return {
        "id": identifiant, "libelle": identifiant, "valeur": valeur, "unite": unite,
        "annee": annee, "perimetre": "entreprise", "fiabilite": fiabilite,
    }


def _socle(*supplements: dict[str, Any], seuil: str = "declaree") -> Socle:
    """Le prévisionnel du dossier : place de marché, trois exercices."""
    donnees = [
        _donnee(f"{serie}_an{rang}", valeur, annee=2026 + rang)
        for serie, valeurs in (
            ("ca_previsionnel", (136_800.0, 281_556.0, 513_280.0)),
            ("resultat_net", (1_954.0, 23_335.0, 21_625.0)),
            ("ebe", (15_500.0, 40_270.0, 37_863.0)),
        )
        for rang, valeur in enumerate(valeurs, start=1)
    ]
    donnees.append(_donnee("seuil_rentabilite", 130_535.0, fiabilite=seuil))
    donnees.append(_donnee("marge_brute_taux", 100.0, unite="%", fiabilite="scenario"))
    donnees.extend(supplements)
    return Socle.model_validate({
        "secteur": "place de marché", "zone": {"pays": "France"},
        "date_socle": "2026-11-18", "donnees": donnees, "concurrents": [],
    })


def _document(*paragraphes: str) -> DocumentLu:
    lu = DocumentLu(chemin=Path("memoire.docx"))
    lu.paragraphes = list(paragraphes)
    lu.cellules = []
    for prose in lu.paragraphes:
        lu.mesures.extend(mesures_dans(prose))
    return lu


# ── Le seuil de rentabilité du client ───────────────────────────────────────


def test_le_seuil_que_le_client_declare_n_est_pas_recalcule() -> None:
    faits = faits_de_l_etude(_socle())

    assert faits["seuil_rentabilite_an1"].valeur == pytest.approx(130_535.0)
    # (136 800 − 130 535) ÷ 136 800 : la marge de sécurité suit le MÊME seuil.
    assert faits["marge_securite_an1"].valeur == pytest.approx(4.6, abs=0.05)


def test_le_seuil_des_exercices_suivants_est_celui_du_client_quand_il_le_donne() -> None:
    faits = faits_de_l_etude(_socle(
        _donnee("seuil_rentabilite_an2", 206_744.0, annee=2028),
        _donnee("seuil_rentabilite_an3", 443_950.0, annee=2029),
    ))

    assert faits["seuil_rentabilite_an2"].valeur == pytest.approx(206_744.0)
    assert faits["seuil_rentabilite_an3"].valeur == pytest.approx(443_950.0)
    assert faits["marge_securite_an2"].valeur == pytest.approx(26.6, abs=0.05)


def test_un_seuil_que_le_socle_a_derive_reste_recalcule() -> None:
    """Contre-épreuve : seul un chiffre DÉCLARÉ prime (ÉCLORE `28a257bf`)."""
    faits = faits_de_l_etude(_socle(seuil="scenario"))

    assert faits["seuil_rentabilite_an1"].valeur == pytest.approx(134_846.0)
    # Et sans chiffre du client, les exercices suivants se calculent toujours.
    assert faits["seuil_rentabilite_an2"].formule


def test_seul_le_client_chiffre_le_seuil_d_un_exercice() -> None:
    assert {"seuil_rentabilite_an1", "seuil_rentabilite_an2", "seuil_rentabilite_an3"} <= (
        identifiants_du_client(BP)
    )
    assert "seuil_rentabilite" not in identifiants_du_client(BP)


# ── Les montants du client, sans centimes ajoutés ───────────────────────────


def test_un_montant_que_le_client_ecrit_a_l_euro_perd_ses_centimes() -> None:
    socle = _socle(_donnee("caf_an1", 12_694.17), _donnee("caf_an2", -8_086.6))

    repris = reprendre_les_montants_du_client(socle, [12_694.0, 8_087.0, 35.0])

    assert socle.donnee("caf_an1").valeur == 12_694.0  # type: ignore[union-attr]
    assert socle.donnee("caf_an2").valeur == -8_087.0  # type: ignore[union-attr]
    assert len(repris) == 2


def test_un_montant_au_centime_du_client_reste_au_centime() -> None:
    """Contre-épreuve : ÉCLORE écrit « 8 040,11 € », et c'est son chiffre."""
    socle = _socle(_donnee("caf_an1", 8_040.11), _donnee("caf_an2", 1_952.6))

    repris = reprendre_les_montants_du_client(socle, [8_040.11, 8_040.0, 1_954.0])

    assert repris == []
    assert socle.donnee("caf_an1").valeur == 8_040.11  # type: ignore[union-attr]
    # Plus d'un demi-euro d'écart : un autre chiffre, pas un arrondi.
    assert socle.donnee("caf_an2").valeur == 1_952.6  # type: ignore[union-attr]


# ── Un calcul n'a pas plus de précision que ses termes ──────────────────────


def test_un_calcul_sur_des_termes_a_l_euro_s_ecrit_a_l_euro() -> None:
    faits = faits_de_l_etude(_socle())

    assert faits["ebe_mensuel_an1"].valeur == 1_292.0  # 15 500 ÷ 12 = 1 291,67
    assert faits["resultat_net_mensuel_an1"].valeur == 163.0


def test_un_calcul_sur_des_termes_au_centime_garde_ses_centimes() -> None:
    """Contre-épreuve : le client écrit au centime, le calcul aussi."""
    faits = faits_de_l_etude(_socle(_donnee("caf_an1", 12_694.17), _donnee("caf_an2", 34_075.0)))

    assert faits["caf_ecart_an1_an2"].valeur == pytest.approx(21_380.83)


# ── Ce que la mémoire calcule n'est pas un chiffre inventé ──────────────────


def test_un_calcul_de_la_memoire_n_est_pas_hors_socle() -> None:
    socle = _socle()
    calculees = controles.valeurs_calculees_par_la_memoire(socle, str(BP))
    document = _document(
        "Notre chiffre d'affaires progresse de 82,3 % entre 2028 et 2029.",
        "L'excédent brut d'exploitation mensuel moyen atteint 1 292 € en 2027.",
        "Avec un chiffre d'affaires en recul de 10 %, il tombe à 123 120 €.",
    )

    assert controles.controler_chiffres_hors_socle(
        document, socle, valeurs_calculees=calculees,
    ) == []


def test_un_chiffre_invente_reste_signale_malgre_la_memoire() -> None:
    """Contre-épreuve : la mémoire ne blanchit pas ce qu'elle ne calcule pas."""
    socle = _socle()
    calculees = controles.valeurs_calculees_par_la_memoire(socle, str(BP))
    document = _document("Notre part de marché atteindra 47,1 % et 312 450 € de ventes.")

    details = " ".join(
        a.detail for a in controles.controler_chiffres_hors_socle(
            document, socle, valeurs_calculees=calculees,
        )
    )

    assert "47,1" in details and "312" in details


# ── La marge d'incertitude inventée ─────────────────────────────────────────


@pytest.mark.parametrize("livrable", [
    DeliverableType.BUSINESS_PLAN, DeliverableType.BUSINESS_STRATEGY,
    DeliverableType.COMPETITOR_STUDY,
])
def test_le_redacteur_ne_chiffre_pas_une_incertitude_par_une_plage(
    livrable: DeliverableType,
) -> None:
    prompt = build_system_prompt(str(livrable))

    assert "UNE INCERTITUDE NE SE CHIFFRE PAS PAR UNE PLAGE INVENTÉE" in prompt
    # La consigne ne MONTRE aucune plage : une forme interdite écrite en
    # exemple est une forme que le modèle recopie.
    assert "20 à 30" not in prompt
    assert "marge d'erreur chiffrée que personne n'a mesurée" in prompt


# ── Le volume de ventes n'est pas le chiffre d'affaires ─────────────────────


def test_un_libelle_de_volume_de_ventes_n_est_pas_le_chiffre_d_affaires() -> None:
    libelle = (
        "Volume de ventes réglé par les clients, exercice 2027 (diffère du chiffre "
        "d'affaires société, place de marché à commission)"
    )

    assert serie_nommee(libelle, "€") is None


def test_un_libelle_de_chiffre_d_affaires_reste_lu() -> None:
    """Contre-épreuve."""
    assert serie_nommee("Chiffre d'affaires HT", "€") == "ca_previsionnel"


# ── Le chapitre des sources se réécrit après les autres ─────────────────────


def test_le_chapitre_des_sources_se_reecrit_en_dernier() -> None:
    cles = {
        12: "bp.12.organisation", 21: "bp.21.sources", 3: "bp.03.porteur",
        15: "str.15.arbitrages_ressources",
    }

    # L'ordre de gravité des autres est gardé ; « arbitrages_ressources » n'est
    # pas un chapitre de sources.
    assert les_sources_en_dernier([12, 21, 3, 15], cles) == [12, 3, 15, 21]
    assert les_sources_en_dernier([3, 12], cles) == [3, 12]


# ── Un plan de financement bouclé n'est pas présenté comme troué ────────────


def _plan(investissement: float) -> Socle:
    return _socle(
        _donnee("investissement_total", investissement, annee=2026),
        _donnee("bfr", 18_000.0, annee=2026),
        _donnee("apport", 10_000.0, annee=2026),
        _donnee("emprunt", 47_700.0, annee=2026),
        _donnee("autres_ressources", 20_000.0, annee=2026),
    )


def test_un_budget_finance_a_l_euro_pres_comprend_deja_sa_tresorerie() -> None:
    """Le dossier : 77 700 € de budget total, 77 700 € de ressources, 18 000 € de
    trésorerie de départ DÉJÀ dans le budget. L'écart n'est pas −18 000 €."""
    faits = faits_de_l_etude(_plan(77_700.0))

    assert faits["besoins_totaux"].valeur == pytest.approx(77_700.0)
    assert faits["ecart_financement"].valeur == pytest.approx(0.0)
    assert "compris" in faits["besoins_totaux"].libelle


def test_un_besoin_en_fonds_de_roulement_distinct_s_ajoute_toujours() -> None:
    """Contre-épreuve : 59 700 € d'investissement et 18 000 € de BFR font 77 700 €."""
    faits = faits_de_l_etude(_plan(59_700.0))

    assert faits["besoins_totaux"].valeur == pytest.approx(77_700.0)
    assert faits["ecart_financement"].valeur == pytest.approx(0.0)
    assert "compris" not in faits["besoins_totaux"].libelle


# ── Le plafond de la micro-entreprise ne se cite pas de mémoire ─────────────


def test_un_projet_hors_micro_recoit_le_plafond_de_son_activite() -> None:
    """Le dossier : une SASU de services a écrit « 188 700 € en ventes de marchandises »."""
    socle = _socle()
    decisions = decisions_de_l_etude(
        socle,
        {"OFFRE": "Place de marché : la société se rémunère par commissions.",
         "FORME": "SASU"},
        faits_de_l_etude(socle),
    )

    (plafond,) = [d for d in decisions if d.sujet == "plafond_micro"]
    assert plafond.valeur.startswith("83 600 €")
    assert "prestations de services" in plafond.justification


def test_un_commerce_recoit_le_plafond_des_ventes() -> None:
    """Contre-épreuve : la nature décide du plafond."""
    socle = _socle()
    decisions = decisions_de_l_etude(
        socle, {"OFFRE": "Commerce de détail alimentaire."}, faits_de_l_etude(socle),
    )

    (plafond,) = [d for d in decisions if d.sujet == "plafond_micro"]
    assert plafond.valeur.startswith("203 100 €")
