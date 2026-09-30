"""Contre-épreuves de la relecture : un texte JUSTE ne fait reprendre aucun chapitre.

Revue de code du 30/09/2026 : chaque constat grave déclenche une réécriture
PAYÉE du chapitre, sur tous les dossiers. Les contrôles des onze classes
(business plan ÉCLORE `28a257bf`) signalaient pourtant des phrases correctes —
le tableau de sensibilité que la consigne 16 exige, le compte de résultat d'une
société à l'IS, un arrondi, un prix par segment. Chaque cas ci-dessous est un
faux positif relevé par la revue ; la plupart échouent sur le code d'avant.

Chiffres et textes FICTIFS. Taux de marge de 60 % : à 100 %, multiplier ou
diviser par le taux donne le même nombre, et une erreur de formule passerait.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.memoire.decisions import decisions_de_l_etude
from generation.memoire.etude import MemoireEtude
from generation.memoire.faits import faits_de_l_etude
from generation.memoire.regles import Nature, regime_de_tva
from generation.relecture import Reference, Section, Tableau, document_du_chapitre, relire
from generation.relecture.coherence import controler as coherence
from generation.relecture.comptages import controler as comptages
from generation.relecture.document import Document
from generation.relecture.formules import controler as formules
from generation.relecture.periodes import controler as periodes
from generation.relecture.tableaux import controler as tableaux
from generation.socle.schema import Socle

pytestmark = pytest.mark.django_db

#: CA, résultat net, EBE, CAF, rémunération du dirigeant — exercices 2027 à 2029.
SERIES: dict[str, tuple[float, float, float]] = {
    "ca_previsionnel": (20_000.0, 40_000.0, 80_000.0),
    "resultat_net": (100.0, 6_000.0, 15_000.0),
    "ebe": (500.0, 6_500.0, 25_000.0),
    "caf": (400.0, 6_300.0, 17_000.0),
    "remuneration_dirigeant": (15_840.0, 15_840.0, 15_840.0),
}


def _socle(series: dict[str, tuple[float, ...]] | None = None) -> Socle:
    donnees: list[dict[str, Any]] = [
        {"id": f"{serie}_an{rang}", "libelle": f"{serie} {rang}", "valeur": valeur,
         "unite": "EUR", "annee": 2026 + rang, "perimetre": "entreprise",
         "fiabilite": "declaree"}
        for serie, valeurs in (series or SERIES).items()
        for rang, valeur in enumerate(valeurs, start=1)
    ]
    donnees += [
        {"id": "marge_brute_taux", "libelle": "Taux de marge", "valeur": 60.0, "unite": "%",
         "annee": 2027, "perimetre": "entreprise", "fiabilite": "scenario"},
        {"id": "panier_moyen", "libelle": "Panier moyen", "valeur": 100.0, "unite": "EUR",
         "annee": 2027, "perimetre": "entreprise", "fiabilite": "declaree"},
    ]
    return Socle.model_validate({
        "secteur": "loisirs", "zone": {"pays": "France"}, "date_socle": "2026-09-01",
        "donnees": donnees, "concurrents": [],
    })


def _reference() -> Reference:
    return Reference(memoire=MemoireEtude.construire(_socle(), {}, "business_plan"),
                     livrable="business_plan")


def _section(numero: str, *paragraphes: str, tableaux: tuple[Tableau, ...] = ()) -> Section:
    return Section(numero=numero, titre="", chapitre=int(numero.split(".")[0]),
                   paragraphes=list(paragraphes), tableaux=list(tableaux))


def _graves(*sections: Section) -> list[str]:
    """Les constats qui feraient reprendre le chapitre, tous contrôles confondus."""
    return [c.motif() for c in relire(Document(sections=list(sections)), _reference()) if c.grave]


def test_les_faits_de_reference_sont_ceux_qu_on_croit() -> None:
    """Seuil 2029 = 80 000 − 15 000 ÷ 0,6 = 55 000 € ; marge de sécurité 31,25 %."""
    faits = faits_de_l_etude(_socle())
    assert faits["seuil_rentabilite_an3"].valeur == pytest.approx(55_000.0)
    assert faits["marge_securite_an3"].valeur == pytest.approx(31.25, abs=0.06)
    memoire = _reference().memoire
    assert memoire is not None
    assert memoire.faits["resultat_net_moins_10_pc_an3"].valeur == pytest.approx(10_200.0)


# ── B1. Le tableau de sensibilité de la consigne 16 ──────────────────────────


def test_le_tableau_de_sensibilite_de_la_consigne_16_ne_fait_rien_reprendre() -> None:
    """Trois lignes de CA, trois de résultat, une colonne par exercice (consigne 16).

    Résultat à −10 % : R − 10 % × CA × 60 % ; à −20 % : R − 20 % × CA × 60 %.
    """
    tableau = Tableau(
        entetes=("Scénario", "2027", "2028", "2029"),
        lignes=(
            ("Chiffre d'affaires — scénario central", "20 000 €", "40 000 €", "80 000 €"),
            ("Chiffre d'affaires inférieur de 10 %", "18 000 €", "36 000 €", "72 000 €"),
            ("Chiffre d'affaires inférieur de 20 %", "16 000 €", "32 000 €", "64 000 €"),
            ("Résultat net — scénario central", "100 €", "6 000 €", "15 000 €"),
            ("Résultat net, CA −10 %", "−1 100 €", "3 600 €", "10 200 €"),
            ("Résultat net, CA −20 %", "−2 300 €", "1 200 €", "5 400 €"),
        ),
    )
    assert _graves(_section(
        "16.5",
        "À −20 %, le résultat net passe à 1 200 € en 2028 et reste positif.",
        "Avec un chiffre d'affaires inférieur de 10 %, le résultat net tombe à 10 200 € en 2029.",
        "L'exercice 2027 devient déficitaire dès une baisse de 10 %.",
        tableaux=(tableau,),
    )) == []


def test_le_tableau_de_sensibilite_en_colonnes_ne_fait_rien_reprendre() -> None:
    """Même analyse, disposée en colonnes « −10 % » / « −20 % »."""
    tableau = Tableau(
        entetes=("Exercice", "Résultat net central", "Résultat net −10 %", "Résultat net −20 %"),
        lignes=(
            ("2028", "6 000 €", "3 600 €", "1 200 €"),
            ("2029", "15 000 €", "10 200 €", "5 400 €"),
        ),
    )
    assert _graves(_section("16.5", tableaux=(tableau,))) == []


def test_une_baisse_ecrite_en_operation_est_une_baisse() -> None:
    """« 80 000 € − 10 % = 72 000 € » est juste ; « = 70 000 € » ne l'est pas."""
    juste = Document(sections=[_section("16.5", "Soit 80 000 € − 10 % = 72 000 € en 2029.")])
    faux = Document(sections=[_section("16.5", "Soit 80 000 € − 10 % = 70 000 € en 2029.")])
    assert formules(juste, _reference()) == []
    assert [c.classe for c in formules(faux, _reference())] == ["formule"]


# ── B2 et B3. Le compte de résultat d'une société à l'IS ─────────────────────


def _compte_de_resultat(signe: str = "") -> Tableau:
    """2029 : CA 80 000 − 10 000 − 20 000 − 1 000 − 24 000 = EBE 25 000 ; net 15 000."""
    return Tableau(
        entetes=("Poste", "2029"),
        lignes=(
            ("Chiffre d'affaires HT", "80 000 €"),
            ("Achats consommés", f"{signe}10 000 €"),
            ("Charges externes", f"{signe}20 000 €"),
            ("Impôts et taxes", f"{signe}1 000 €"),
            ("Rémunération du dirigeant", f"{signe}24 000 €"),
            ("Excédent brut d'exploitation", "25 000 €"),
            ("Dotations aux amortissements", f"{signe}2 000 €"),
            ("Résultat d'exploitation", "23 000 €"),
            ("Résultat financier", "−500 €"),
            ("Résultat courant avant impôts", "22 500 €"),
            ("Impôt sur les sociétés", f"{signe}7 500 €"),
            ("Résultat net", "15 000 €"),
        ),
    )


def test_le_compte_de_resultat_d_une_sarl_ne_fait_rien_reprendre() -> None:
    """Résultat financier, RCAI : d'autres lignes que le résultat net ; la rémunération
    du dirigeant et les impôts et taxes sont des charges."""
    assert _graves(_section("16.2", tableaux=(_compte_de_resultat(),))) == []


def test_des_charges_ecrites_en_negatif_bouclent_aussi() -> None:
    assert _graves(_section("16.2", tableaux=(_compte_de_resultat("−"),))) == []


def test_un_tableau_d_indicateurs_ne_pretend_pas_boucler() -> None:
    """Business plan ÉCLORE, 11.3 : « Résultat net » et « Trésorerie » entre le CA et l'EBE."""
    tableau = Tableau(
        entetes=("Indicateur", "2028", "2029"),
        lignes=(
            ("Chiffre d'affaires HT", "40 000 €", "80 000 €"),
            ("Résultat net (avant impôt)", "6 000 €", "15 000 €"),
            ("Trésorerie de fin d'exercice", "9 000 €", "21 000 €"),
            ("Excédent brut d'exploitation", "6 500 €", "25 000 €"),
        ),
    )
    constats = tableaux(Document(sections=[_section("11.3", tableaux=(tableau,))]), _reference())
    assert "tableau" not in [c.classe for c in constats]


def test_un_compte_de_resultat_faux_reste_signale() -> None:
    """Contre-épreuve de la contre-épreuve : l'EBE ne suit pas les charges."""
    lignes = list(_compte_de_resultat().lignes)
    lignes[5] = ("Excédent brut d'exploitation", "31 000 €")
    constats = tableaux(Document(sections=[_section("16.2", tableaux=(
        Tableau(entetes=("Poste", "2029"), lignes=tuple(lignes)),
    ))]), _reference())
    assert "tableau" in [c.classe for c in constats]


def _compte(*charges: tuple[str, str], ebe: str = "25 000 €") -> Tableau:
    """2029 : CA 80 000 €, les lignes données, puis l'EBE."""
    return Tableau(entetes=("Poste", "2029"), lignes=(
        ("Chiffre d'affaires HT", "80 000 €"), *charges, ("Excédent brut d'exploitation", ebe),
    ))


def _boucles(tableau: Tableau) -> list[Any]:
    document = Document(sections=[_section("16.2", tableaux=(tableau,))])
    return [c for c in tableaux(document, _reference()) if c.classe == "tableau"]


@pytest.mark.parametrize("charges", [
    # Porte finale du 30/09/2026 : chacun de ces comptes JUSTES devenait grave.
    (("Achats de produits", "20 000 €"), ("Charges externes", "10 000 €"),
     ("Charges de personnel", "25 000 €")),
    (("Achats de produits d'entretien", "20 000 €"), ("Charges externes", "10 000 €"),
     ("Salaires", "25 000 €")),
    (("Charges externes", "30 000 €"), ("Charges de personnel", "25 000 €"),
     ("dont rémunération du dirigeant", "18 000 €")),
    (("Charges externes", "30 000 €"), ("Salaires", "15 000 €"),
     ("Cotisations sociales (taux de 47 %)", "10 000 €")),
    (("Charges externes", "30 000 €"), ("Salaires et charges (effectif : 1 ETP)", "25 000 €")),
    (("Achats de marchandises", "32 000 €"), ("Variation de stock", "−2 000 €"),
     ("Charges externes", "25 000 €")),
    (("Total des charges d'exploitation", "55 000 €"),),
    (("Loyer", "12 000 €"), ("Assurance", "3 000 €"), ("Charges externes", "40 000 €")),
])
def test_un_compte_de_resultat_juste_ne_fait_rien_reprendre(
    charges: tuple[tuple[str, str], ...],
) -> None:
    assert _boucles(_compte(*charges)) == []


@pytest.mark.parametrize("charges", [
    # Porte finale du 30/09/2026, second passage : même classe que « Achats de
    # produits » — une charge qui nomme des produits, une recette sans le mot.
    (("Coût des produits vendus", "20 000 €"), ("Charges externes", "10 000 €"),
     ("Salaires", "25 000 €")),
    (("Consommation de produits", "20 000 €"), ("Fournitures et produits d'entretien", "10 000 €"),
     ("Salaires", "25 000 €")),
    (("Cotisations des adhérents", "5 000 €"), ("Dons", "2 000 €"),
     ("Charges externes", "37 000 €"), ("Salaires", "25 000 €")),
    (("Transfert de charges", "1 000 €"), ("Charges externes", "31 000 €"),
     ("Salaires", "25 000 €")),
    (("Charges externes", "30 000 €"), ("Salaires", "25 000 €"), ("Charges totales", "55 000 €")),
    (("Charges externes", "30 000 €"), ("Salaires", "25 000 €"),
     ("Charges d'exploitation", "55 000 €")),
    (("Charges d'exploitation", "—"), ("Charges externes", "30 000 €"), ("Salaires", "25 000 €")),
    (("Subvention d'exploitation", "—"), ("Charges externes", "30 000 €"),
     ("Salaires", "25 000 €")),
    (("Charges externes", "30 000 €"), ("Salaires", "25 000 €"),
     ("Taux de marge sur coûts variables", "100 %"), ("Cotisations sociales au taux de 47 %", "—")),
    (("Marge sur coûts variables", "80 000 €"), ("Charges externes", "30 000 €"),
     ("Salaires", "25 000 €")),
])
def test_un_compte_juste_d_une_autre_forme_ne_fait_rien_reprendre(
    charges: tuple[tuple[str, str], ...],
) -> None:
    assert _boucles(_compte(*charges)) == []


@pytest.mark.parametrize("charges", [
    # Porte finale, troisième passage (NO-GO sur `1d526db`) : un mot de recette
    # AILLEURS que dans le nom en tête ne fait pas une recette.
    (("Achats", "10 000 €"), ("Charges externes", "20 000 €"),
     ("Salaires des aides à domicile", "25 000 €")),
    (("Achats d'ingrédients pour les recettes", "10 000 €"), ("Charges externes", "20 000 €"),
     ("Salaires", "25 000 €")),
    (("Aide-comptable", "5 000 €"), ("Charges externes", "25 000 €"), ("Salaires", "25 000 €")),
    # N1 : la ventilation du CA sous lui n'est pas un flux.
    (("Ventes de marchandises", "50 000 €"), ("Prestations de services", "30 000 €"),
     ("Charges externes", "30 000 €"), ("Salaires", "25 000 €")),
    # N5, N6 : une charge illisible coupe l'exercice, elle ne disparaît pas.
    (("Charges variables", "40 %"), ("Charges fixes", "23 000 €")),
    (("Charges externes", "30 000 €"), ("Salaires", "25 000")),
    # Déjà graves avant le chantier : le nom en tête les règle aussi.
    (("Produits d'entretien", "5 000 €"), ("Produits capillaires", "5 000 €"),
     ("Charges externes", "20 000 €"), ("Salaires", "25 000 €")),
    (("Prix d'achat des marchandises vendues", "10 000 €"), ("Charges externes", "20 000 €"),
     ("Rémunération des aides-soignantes", "25 000 €")),
])
def test_le_nom_en_tete_dit_la_nature_de_la_ligne(charges: tuple[tuple[str, str], ...]) -> None:
    assert _boucles(_compte(*charges)) == []


@pytest.mark.parametrize(("charges", "ebe"), [
    # M8 : des salaires comptés comme une recette dans l'EBE.
    ((("Achats", "10 000 €"), ("Charges externes", "20 000 €"),
      ("Salaires des aides à domicile", "25 000 €")), "75 000 €"),
    # M1 : deux charges égales, l'EBE en oublie une.
    ((("Charges externes", "25 000 €"), ("Salaires", "25 000 €")), "55 000 €"),
    # M2 : une ligne vaut la somme des autres, l'EBE l'oublie.
    ((("Achats", "10 000 €"), ("Charges externes", "15 000 €"), ("Salaires", "25 000 €")),
     "55 000 €"),
])
def test_aucun_sous_total_implicite_ne_sauve_un_compte_faux(
    charges: tuple[tuple[str, str], ...], ebe: str,
) -> None:
    constats = _boucles(_compte(*charges, ebe=ebe))
    assert len(constats) == 1 and constats[0].grave


def _ventile(premiere: str, seconde: str, ebe: str = "25 000 €") -> Tableau:
    """« Chiffre d'affaires HT » puis sa ventilation (50 000 + 30 000 €), puis les charges."""
    return Tableau(entetes=("Poste", "2029"), lignes=(
        ("Chiffre d'affaires HT", "80 000 €"), (premiere, "50 000 €"), (seconde, "30 000 €"),
        ("Charges externes", "30 000 €"), ("Salaires", "25 000 €"),
        ("Excédent brut d'exploitation", ebe),
    ))


@pytest.mark.parametrize(("premiere", "seconde"), [
    # Porte finale, quatrième passage (NO-GO sur `e0f8024`) : W1, W2.
    ("Recettes ateliers", "Recettes boutique"),
    ("Produits des activités de formation", "Produits des activités de conseil"),
    ("Ventes de marchandises", "Prestations de services"),
])
def test_la_ventilation_du_ca_sous_lui_n_est_pas_un_flux(premiere: str, seconde: str) -> None:
    assert _boucles(_ventile(premiere, seconde)) == []


@pytest.mark.parametrize("charges", [
    # W3, W4 : « Prestations … » hors de la ventilation du CA est une charge.
    (("Achats", "10 000 €"), ("Prestations de sous-traitance", "20 000 €"),
     ("Salaires", "25 000 €")),
    (("Prestations extérieures", "30 000 €"), ("Salaires", "25 000 €")),
])
def test_des_prestations_parmi_les_charges_sont_une_charge(
    charges: tuple[tuple[str, str], ...],
) -> None:
    assert _boucles(_compte(*charges)) == []


def test_un_ca_detaille_puis_totalise_sans_le_mot_total() -> None:
    """W5 : « Chiffre d'affaires HT » en pied de sa ventilation en est le total."""
    tableau = Tableau(entetes=("Poste", "2029"), lignes=(
        ("Chiffre d'affaires cours", "50 000 €"), ("Chiffre d'affaires boutique", "30 000 €"),
        ("Chiffre d'affaires HT", "80 000 €"), ("Charges externes", "30 000 €"),
        ("Salaires", "25 000 €"), ("Excédent brut d'exploitation", "25 000 €"),
    ))
    assert _boucles(tableau) == []


@pytest.mark.parametrize("tableau", [
    # X1 : l'EBE compte la ventilation du CA une seconde fois (105 000 €).
    _ventile("Recettes ateliers", "Recettes boutique", ebe="105 000 €"),
    # X2 : l'EBE oublie la sous-traitance (45 000 €).
    _compte(("Achats", "10 000 €"), ("Prestations de sous-traitance", "20 000 €"),
            ("Salaires", "25 000 €"), ebe="45 000 €"),
    # W8 : « Apport personnel » dans un tableau d'indicateurs, compte juste.
    _compte(("Apport personnel", "5 000 €"), ("Charges externes", "30 000 €"),
            ("Salaires", "25 000 €")),
])
def test_une_ligne_a_double_lecture_donne_un_signal_sans_montant_attendu(
    tableau: Tableau,
) -> None:
    """Règle 2 : sur une ligne dont la nature n'est pas sûre, le motif n'impose aucun EBE.

    Le compte n'est pas validé en silence (le constat reste tracé), mais il ne
    fait rien reprendre, et ne chiffre aucun « attendu » qui pourrait être faux.
    """
    constats = _boucles(tableau)
    assert len(constats) == 1 and not constats[0].grave
    assert "=" not in constats[0].detail


def _sous_ligne(libelle: str, montant: str, ebe: str) -> Tableau:
    """« Chiffre d'affaires HT » 80 000 €, une sous-ligne dessous, puis 55 000 € de charges."""
    return Tableau(entetes=("Poste", "2029"), lignes=(
        ("Chiffre d'affaires HT", "80 000 €"), (libelle, montant),
        ("Achats", "10 000 €"), ("Charges externes", "20 000 €"), ("Salaires", "25 000 €"),
        ("Excédent brut d'exploitation", ebe),
    ))


@pytest.mark.parametrize("tableau", [
    # Porte finale, cinquième passage (NO-GO sur `86ab31c`) : la lecture par
    # défaut de la sous-ligne donnait EXACTEMENT l'EBE faux — aucun constat.
    _sous_ligne("Recettes ateliers", "50 000 €", "75 000 €"),        # Y1
    _sous_ligne("Ventes de marchandises", "50 000 €", "75 000 €"),   # Y3
    _sous_ligne("Produits", "50 000 €", "75 000 €"),                 # Y4
    _sous_ligne("Prestations de services", "30 000 €", "−5 000 €"),  # Y9
])
def test_un_compte_faux_n_est_pas_valide_par_une_lecture_incertaine(tableau: Tableau) -> None:
    constats = _boucles(tableau)
    assert len(constats) == 1 and not constats[0].grave
    assert "=" not in constats[0].detail


def test_une_vraie_recette_annexe_sous_le_ca_n_est_qu_un_signal() -> None:
    """Y8 : juste si « Recettes annexes » s'ajoute au CA ; jamais grave, au pire un signal."""
    constats = _boucles(_sous_ligne("Recettes annexes", "5 000 €", "30 000 €"))
    assert not any(c.grave for c in constats)


@pytest.mark.parametrize("tableau", [
    # Y6 : « Aides à domicile » (des salaires) n'est plus une recette sûre.
    _compte(("Aides à domicile", "25 000 €"), ("Achats", "10 000 €"),
            ("Charges externes", "20 000 €")),
    # Y7 : « Prix de revient des prestations » est une charge, pas un prix.
    _compte(("Prix de revient des prestations", "25 000 €"), ("Achats", "10 000 €"),
            ("Charges externes", "20 000 €")),
])
def test_aucune_tete_incertaine_ne_rend_grave_un_compte_juste(tableau: Tableau) -> None:
    assert not any(c.grave for c in _boucles(tableau))


def test_un_compte_faux_sous_toutes_les_lectures_reste_grave_sans_attendu() -> None:
    """Aucune lecture de la ventilation ne donne 60 000 € : grave, mais sans chiffrer d'attendu."""
    constats = _boucles(_ventile("Recettes ateliers", "Recettes boutique", ebe="60 000 €"))
    assert len(constats) == 1 and constats[0].grave
    assert "aucune lecture" in constats[0].detail and "=" not in constats[0].detail


def test_un_ca_coiffe_n_est_pas_additionne_a_sa_ventilation() -> None:
    """M5 : l'EBE compte le CA ateliers deux fois (80 000 + 50 000 − 55 000 = 75 000 €)."""
    tableau = Tableau(entetes=("Poste", "2029"), lignes=(
        ("Chiffre d'affaires HT", "80 000 €"), ("Chiffre d'affaires ateliers", "50 000 €"),
        ("Charges externes", "30 000 €"), ("Salaires", "25 000 €"),
        ("Excédent brut d'exploitation", "75 000 €"),
    ))
    assert len(_boucles(tableau)) == 1


def test_un_ca_ventile_sans_ligne_qui_le_coiffe_s_additionne() -> None:
    tableau = Tableau(entetes=("Poste", "2029"), lignes=(
        ("Chiffre d'affaires cours", "50 000 €"), ("Chiffre d'affaires boutique", "30 000 €"),
        ("Charges externes", "30 000 €"), ("Salaires", "25 000 €"),
        ("Excédent brut d'exploitation", "25 000 €"),
    ))
    assert _boucles(tableau) == []


def test_le_motif_ne_montre_pas_de_ligne_a_zero() -> None:
    constats = _boucles(_compte(
        ("Subvention d'exploitation", "—"), ("Charges externes", "30 000 €"),
        ("Salaires", "25 000 €"), ebe="40 000 €",
    ))
    assert len(constats) == 1 and " 0 €" not in constats[0].detail


def test_un_chiffre_d_affaires_ventile_se_lit_sur_son_total() -> None:
    tableau = Tableau(entetes=("Poste", "2029"), lignes=(
        ("Chiffre d'affaires cours", "50 000 €"), ("Chiffre d'affaires boutique", "30 000 €"),
        ("Chiffre d'affaires total", "80 000 €"), ("Charges externes", "30 000 €"),
        ("Salaires", "25 000 €"), ("Excédent brut d'exploitation", "25 000 €"),
    ))
    assert _boucles(tableau) == []


@pytest.mark.parametrize(("charges", "ebe"), [
    # K1 : le total est mal additionné (55 000 € réels), l'EBE calculé dessus.
    ((("Achats", "10 000 €"), ("Charges externes", "20 000 €"), ("Salaires", "25 000 €"),
      ("Total des charges", "50 000 €")), "30 000 €"),
    # K4 : un total PARTIEL « sauve » un EBE qui oublie les charges variables.
    ((("Charges variables", "30 000 €"), ("Loyer", "10 000 €"), ("Salaires", "15 000 €"),
      ("Total charges fixes", "25 000 €")), "55 000 €"),
    # K6 : un « — » sur une ligne ne coupe pas le contrôle de l'exercice.
    ((("Subvention d'exploitation", "—"), ("Charges externes", "30 000 €"),
      ("Salaires", "25 000 €")), "40 000 €"),
    # Business plan ÉCLORE, 9.2 : un taux en % entre le CA et l'EBE ne coupe pas
    # le contrôle de l'exercice.
    ((("Charges fixes annuelles", "30 000 €"), ("Taux de marge sur coûts variables", "100 %")),
     "782 €"),
    # Une subvention oubliée dans l'EBE n'est pas sauvée par « les seules charges ».
    ((("Subvention d'exploitation", "5 000 €"), ("Charges externes", "30 000 €"),
      ("Salaires", "25 000 €")), "25 000 €"),
])
def test_un_compte_faux_n_est_pas_sauve_par_une_autre_lecture(
    charges: tuple[tuple[str, str], ...], ebe: str,
) -> None:
    """Porte finale du 30/09/2026 (NO-GO sur `63be6a3`) : chacun passait sans constat."""
    constats = _boucles(_compte(*charges, ebe=ebe))
    assert len(constats) == 1 and constats[0].grave


def test_un_compte_faux_qui_ne_porte_qu_un_total_reste_signale() -> None:
    """80 000 − 55 000 = 25 000 €, pas 31 000 € — et l'opération affichée est la vraie."""
    constats = _boucles(_compte(("Total des charges d'exploitation", "55 000 €"), ebe="31 000 €"))
    assert len(constats) == 1 and constats[0].grave
    assert "80 000 € − 55 000 € = 25 000 €" in constats[0].detail


def test_le_motif_d_un_compte_faux_montre_une_arithmetique_juste() -> None:
    """Règle 2 : l'opération du motif se refait à la main et tombe juste."""
    constats = _boucles(_compte(
        ("Achats de produits", "20 000 €"), ("Charges externes", "10 000 €"),
        ("Charges de personnel", "25 000 €"), ebe="31 000 €",
    ))
    assert len(constats) == 1
    assert "80 000 € − 20 000 € − 10 000 € − 25 000 € = 25 000 €" in constats[0].detail


# ── M1. Arrondis et chiffres d'un autre acteur ──────────────────────────────


def test_un_arrondi_ecrit_n_est_pas_une_erreur() -> None:
    """31,25 % écrit « 31 % » ; 55 000 € écrit « près de 55 000 € »."""
    assert _graves(_section(
        "9.3",
        "La marge de sécurité atteint 31 % en 2029.",
        "Le seuil de rentabilité s'établit à près de 55 000 € en 2029.",
    )) == []


def test_le_chiffre_d_affaires_du_marche_n_est_pas_celui_du_projet() -> None:
    assert _graves(_section(
        "3.1", "Le marché représente un chiffre d'affaires de 3,4 Md€ en 2027.",
    )) == []


def test_un_ecart_reel_sur_un_fait_date_reste_signale() -> None:
    """Contre-épreuve : 2029 porte le seuil de 2028 (30 000 €)."""
    graves = _graves(_section("9.3", "Le seuil de rentabilité atteint 30 000 € en 2029."))
    assert any("[fait_par_annee]" in g for g in graves)


# ── M2. Périodes : une coïncidence n'est pas une division ────────────────────


def test_un_prix_n_est_pas_une_remuneration_divisee() -> None:
    """15 840 € ÷ 144 = 110 € : le prix d'un atelier, par hasard."""
    doc = Document(sections=[_section(
        "12.2",
        "La rémunération mensuelle visée est de 1 320 €. Chaque atelier est facturé 110 €.",
        "Pour une rémunération de 1 320 € par mois, la dirigeante anime 12 ateliers à 110 €.",
    )])
    assert periodes(doc, _reference()) == []


def test_une_remuneration_redivisee_reste_signalee() -> None:
    """Contre-épreuve : 15 840 € ÷ 12 ÷ 12 = 110 €, présenté comme revenu mensuel."""
    doc = Document(sections=[_section(
        "12.2", "Le revenu mensuel de la dirigeante ressort à 110 € en 2027.",
    )])
    assert [c.classe for c in periodes(doc, _reference())] == ["periode"]


# ── M3. Formules : la marge de sécurité, les charges mensuelles, la fréquence ─


def test_la_marge_de_securite_n_est_pas_un_taux_de_marge() -> None:
    assert _graves(_section(
        "9.3",
        "Le seuil de rentabilité (30 000 €) couvre des charges fixes de 18 000 € et laisse "
        "une marge de sécurité de 25 % en 2028.",
    )) == []


def test_des_charges_fixes_mensuelles_ne_se_divisent_pas_comme_des_annuelles() -> None:
    """1 500 € par mois × 12 ÷ 60 % = 30 000 €."""
    assert _graves(_section(
        "9.3",
        "Avec des charges fixes de 1 500 € par mois et un taux de marge de 60 %, le seuil "
        "de rentabilité atteint 30 000 € en 2028.",
    )) == []


def test_un_effectif_avec_son_produit_ecrit_ou_sa_frequence_passe() -> None:
    assert _graves(_section(
        "6.4",
        "200 clientes au panier moyen de 100 € représentent 20 000 €, soit 25 % du chiffre "
        "d'affaires visé en 2029.",
        "200 adhérentes au panier moyen de 100 € par mois portent l'objectif de chiffre "
        "d'affaires de 2029.",
    )) == []


# ── M6. TVA : l'année précédente compte ─────────────────────────────────────


def test_apres_un_depassement_la_tva_s_applique_au_1er_janvier() -> None:
    """39 000 € en 2028 (au-dessus de 37 500 €), 36 000 € en 2029 : TVA en 2029."""
    decision = regime_de_tva(36_000.0, 2029, Nature.SERVICES, ca_precedent=39_000.0)
    assert decision is not None and decision.valeur == "TVA obligatoire"
    assert "1er janvier" in decision.justification


def test_le_registre_juge_chaque_annee_avec_la_precedente() -> None:
    socle = _socle({"ca_previsionnel": (39_000.0, 36_000.0)})
    faits = faits_de_l_etude(socle)
    tva = {d.annee: d.valeur for d in decisions_de_l_etude(socle, {}, faits)
           if d.sujet == "regime_tva"}
    assert tva == {2027: "franchise en base, TVA au 1er janvier suivant",
                   2028: "TVA obligatoire"}


def test_sans_depassement_anterieur_la_franchise_reste() -> None:
    """Contre-épreuve."""
    decision = regime_de_tva(36_000.0, 2029, Nature.SERVICES, ca_precedent=30_000.0)
    assert decision is not None and decision.valeur == "franchise en base"


def test_la_tva_au_1er_janvier_suivant_n_est_pas_une_approximation() -> None:
    doc = Document(sections=[_section(
        "11.3",
        "Le chiffre d'affaires 2028 dépasse le seuil de franchise (37 500 €) : la TVA "
        "s'applique dès le 1er janvier 2029.",
    )])
    assert comptages(doc, _reference()) == []


# ── M8. Superlatifs : un prix le plus bas PAR SEGMENT ────────────────────────


def test_un_prix_le_plus_bas_par_segment_n_est_pas_une_contradiction() -> None:
    doc = Document(sections=[_section(
        "5.3",
        "Prix le plus bas des cours collectifs : 25 € (acteur A).",
        "Prix le plus bas des cours particuliers : 60 € (acteur B).",
        "La rémunération médiane du secteur atteint 2 100 € ; prix médian du panel : 45 €.",
    )])
    assert tableaux(doc, _reference()) == []


def test_un_meme_superlatif_a_deux_valeurs_reste_grave_dans_son_chapitre() -> None:
    """Contre-épreuve : même segment, même chapitre, deux valeurs."""
    doc = Document(sections=[
        _section("5.3", "Prix le plus bas des cours collectifs : 25 € (acteur A)."),
        _section("5.4", "Prix le plus bas des cours collectifs : 30 € (acteur C)."),
    ])
    constats = [c for c in tableaux(doc, _reference()) if c.classe == "libelle_unique"]
    assert len(constats) == 2 and all(c.grave for c in constats)


def test_d_un_chapitre_a_l_autre_la_contradiction_est_un_signal() -> None:
    """Une reprise ne corrige que SON chapitre : l'autre valeur est hors de portée."""
    doc = Document(sections=[
        _section("5.3", "Prix le plus bas du panel : 25 € (acteur A)."),
        _section("7.4", "Prix le plus bas du panel : 30 € (acteur C)."),
    ])
    constats = [c for c in tableaux(doc, _reference()) if c.classe == "libelle_unique"]
    assert len(constats) == 2 and not any(c.grave for c in constats)


# ── Mineur. Les chiffres clés sont relus ─────────────────────────────────────


def test_la_grille_de_chiffres_cles_est_relue() -> None:
    """15 840 € ÷ 144 = 110 € : un revenu mensuel redivisé, dans une grille de KPI."""
    document = document_du_chapitre({
        "chapitre": 12, "titre": "Rémunération",
        "blocs": [
            {"type": "titre_sous_section", "numero": "12.1", "intitule": "Repères"},
            {"type": "grille_kpi", "cellules": [
                {"valeur": "110 €", "libelle": "Revenu mensuel de la dirigeante"},
                {"valeur": "20", "libelle": "Ateliers par mois"},
            ]},
        ],
    })
    assert "Revenu mensuel de la dirigeante : 110 €" in document.sections[0].paragraphes
    assert [c.classe for c in periodes(document, _reference())] == ["periode"]


# ── Porte finale : ce qui ne doit PAS cesser d'être détecté ─────────────────


def test_le_scenario_central_se_juge_comme_le_previsionnel() -> None:
    """30 000 € est le seuil de 2028 : écrit pour 2029, même « dans le scénario central »."""
    graves = _graves(_section(
        "9.3", "Dans le scénario central, le seuil de rentabilité atteint 30 000 € en 2029.",
    ))
    assert any("[fait_par_annee]" in g for g in graves)


def test_une_incise_entre_tirets_n_est_pas_une_baisse() -> None:
    """Une marge de 25 % en 2029 (celle de 2028), dans une incise : elle se juge."""
    doc = Document(sections=[_section(
        "9.3", "La marge de sécurité – 25 % en 2029 – reste confortable.",
    )])
    assert "fait_par_annee" in [c.classe for c in coherence(doc, _reference())]


def test_un_revenu_redivise_la_premiere_annee_reste_signale() -> None:
    """« ressort à 110 € la première année » n'est pas un prix unitaire."""
    doc = Document(sections=[_section(
        "12.2", "Le revenu mensuel de la dirigeante ressort à 110 € la première année.",
    )])
    assert [c.classe for c in periodes(doc, _reference())] == ["periode"]


def test_des_charges_fixes_mensuelles_ecrites_avant_le_montant() -> None:
    assert _graves(_section(
        "9.3",
        "Avec des charges fixes mensuelles de 1 500 € et un taux de marge de 60 %, le seuil "
        "de rentabilité atteint 30 000 € en 2028.",
    )) == []


def test_une_marge_nette_n_est_pas_le_taux_de_marge_du_seuil() -> None:
    assert _graves(_section(
        "9.3",
        "Le seuil de rentabilité (30 000 €) couvre des charges fixes de 18 000 € ; le taux de "
        "marge nette atteint 15 % en 2028.",
    )) == []


def test_la_tolerance_suit_l_unite_ecrite() -> None:
    """« 1,2 M€ » arrondit à 100 000 € près : ±50 000 €, pas ±0,05 €."""
    from generation.relecture.valeurs import nombres, tolerance_ecrite

    assert tolerance_ecrite(nombres("1,2 M€")[0]) == pytest.approx(50_000.0)
    assert tolerance_ecrite(nombres("16 %")[0]) == pytest.approx(0.5)


def test_un_prix_apres_une_frequence_n_est_pas_une_remuneration_divisee() -> None:
    """« 12 ateliers par mois à 110 € » : trois mots entre le compte et le prix."""
    doc = Document(sections=[_section(
        "12.2",
        "Pour une rémunération de 1 320 € par mois, la dirigeante anime 12 ateliers par mois "
        "à 110 €.",
    )])
    assert periodes(doc, _reference()) == []


def test_une_annee_n_est_pas_un_compte_de_choses() -> None:
    """Contre-épreuve : « en 2027 le revenu mensuel passe à 110 € » reste signalé."""
    doc = Document(sections=[_section(
        "12.2", "En 2027 le revenu mensuel de la dirigeante passe à 110 €.",
    )])
    assert [c.classe for c in periodes(doc, _reference())] == ["periode"]
