"""Relecture des chiffres : périodes, définitions, formules, faits par année, tableaux.

Classes 1 à 5 de la relecture du texte final (business plan ÉCLORE `28a257bf`,
30/09/2026). Chiffres et textes FICTIFS ; chaque contrôle a sa contre-épreuve :
le texte juste n'est pas signalé.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.memoire.etude import MemoireEtude
from generation.relecture import Reference, Section, Tableau
from generation.relecture.coherence import controler as coherence
from generation.relecture.document import Document
from generation.relecture.formules import controler as formules
from generation.relecture.periodes import controler as periodes
from generation.relecture.tableaux import controler as tableaux
from generation.socle.schema import Socle

pytestmark = pytest.mark.django_db


def _reference() -> Reference:
    """CA 20 000 / 40 000 / 80 000 €, résultat 100 / 6 000 / 20 000 €, marge 100 %."""
    donnees: list[dict[str, Any]] = [
        {"id": f"{serie}_an{rang}", "libelle": f"{nom} exercice {rang}", "valeur": valeur,
         "unite": "EUR", "annee": 2026 + rang, "perimetre": "entreprise",
         "fiabilite": "declaree"}
        for serie, nom, valeurs in (
            ("ca_previsionnel", "Chiffre d'affaires", (20_000.0, 40_000.0, 80_000.0)),
            ("resultat_net", "Résultat net", (100.0, 6_000.0, 20_000.0)),
            ("caf", "CAF", (400.0, 6_300.0, 20_300.0)),
            ("ebe", "EBE", (500.0, 6_500.0, 20_500.0)),
        )
        for rang, valeur in enumerate(valeurs, start=1)
    ]
    donnees += [
        {"id": "seuil_rentabilite", "libelle": "Seuil", "valeur": 19_900.0, "unite": "EUR",
         "annee": 2027, "perimetre": "entreprise", "fiabilite": "declaree"},
        {"id": "marge_brute_taux", "libelle": "Taux de marge", "valeur": 100.0, "unite": "%",
         "annee": 2027, "perimetre": "entreprise", "fiabilite": "scenario"},
        {"id": "panier_moyen", "libelle": "Panier moyen", "valeur": 100.0, "unite": "EUR",
         "annee": 2027, "perimetre": "entreprise", "fiabilite": "declaree"},
    ]
    socle = Socle.model_validate({
        "secteur": "loisirs", "zone": {"pays": "France"}, "date_socle": "2026-09-01",
        "donnees": donnees, "concurrents": [],
    })
    return Reference(memoire=MemoireEtude.construire(socle, {}, "business_plan"),
                     livrable="business_plan", document_entier=True)


def _doc(*sections: Section) -> Document:
    return Document(sections=list(sections))


def _section(numero: str, *paragraphes: str, tableaux: tuple[Tableau, ...] = ()) -> Section:
    return Section(numero=numero, titre="", chapitre=int(numero.split(".")[0]),
                   paragraphes=list(paragraphes), tableaux=list(tableaux))


def _classes(constats: list[Any]) -> list[str]:
    return [c.classe for c in constats]


# ── 1. Périodes ─────────────────────────────────────────────────────────────


def test_un_revenu_redivise_par_douze_est_signale() -> None:
    """CAF 2029 = 20 300 € ; ÷ 12 = 1 691,67 € ; ÷ 12 encore = 140,97 €."""
    doc = _doc(_section("2.1", "Le revenu mensuel de la gérante atteint 140,97 € en 2029."))
    assert _classes(periodes(doc, _reference())) == ["periode"]


def test_un_montant_mensuel_sous_un_libelle_annuel_est_signale() -> None:
    doc = _doc(_section("2.2", tableaux=(Tableau(
        entetes=("Exercice", "Revenu annuel avant impôt"),
        lignes=(("2029", "1 692 €"),),
    ),)))
    assert "periode" in _classes(periodes(doc, _reference()))


def test_une_moyenne_mensuelle_juste_n_est_pas_signalee() -> None:
    """Contre-épreuve : résultat net 2029 ÷ 12 = 1 666,67 € par mois, écrit comme tel."""
    doc = _doc(_section(
        "2.3", "Le résultat net mensuel moyen atteint 1 666,67 € par mois en 2029.",
    ))
    assert periodes(doc, _reference()) == []


def test_un_prix_qui_tombe_par_hasard_sur_une_division_n_est_pas_signale() -> None:
    """Contre-épreuve : 140,97 € dans une grille de prix n'est pas un revenu."""
    doc = _doc(_section("8.1", "L'atelier découverte est vendu 140,97 € la séance."))
    assert periodes(doc, _reference()) == []


# ── 2. Définitions contre calculs ───────────────────────────────────────────


def test_un_revenu_calcule_sur_la_caf_est_signale() -> None:
    doc = _doc(_section("16.3", "Le revenu mensuel part de la CAF annuelle divisée par douze."))
    assert _classes(coherence(doc, _reference())) == ["definition"]


def test_une_definition_juste_n_est_pas_un_calcul() -> None:
    """Contre-épreuve : « ni la CAF » définit, il ne calcule pas."""
    doc = _doc(_section(
        "16.3",
        "Le revenu du dirigeant se définit comme le chiffre d'affaires diminué des charges "
        "décaissées et des cotisations : il n'est ni le résultat net, ni la CAF.",
    ))
    assert coherence(doc, _reference()) == []


def test_l_ebe_moins_les_dotations_n_est_pas_le_resultat_net() -> None:
    doc = _doc(_section("16.2", "L'EBE diminué des dotations donne le résultat net : 400 €."))
    assert "definition" in _classes(coherence(doc, _reference()))


# ── 4. Faits par année ──────────────────────────────────────────────────────


def test_le_seuil_d_un_exercice_repris_pour_le_suivant_est_signale() -> None:
    """Seuils calculés : 19 900 / 34 000 / 60 000 €."""
    doc = _doc(_section("17.3", tableaux=(Tableau(
        entetes=("Indicateur", "2027", "2028", "2029"),
        lignes=(("Seuil de rentabilité", "19 900 €", "19 900 €", "19 900 €"),),
    ),)))
    constats = [c for c in coherence(doc, _reference()) if c.classe == "fait_par_annee"]
    assert len(constats) == 2 and "celui de 2027" in constats[0].detail


def test_une_marge_de_securite_reprise_par_un_pronom_est_lue() -> None:
    """Marges calculées : 0,5 / 15 / 25 %. « Elle » reprend la marge de la phrase d'avant."""
    doc = _doc(_section(
        "9.3",
        "Une marge de sécurité de 0,5 % en 2027 est étroite. Elle s'élargit ensuite : "
        "50,3 % en 2028, à mesure que le chiffre d'affaires croît.",
    ))
    constats = [c for c in coherence(doc, _reference()) if c.classe == "fait_par_annee"]
    assert len(constats) == 1 and "2028" in constats[0].detail


def test_des_faits_dates_justes_ne_sont_pas_signales() -> None:
    """Contre-épreuve."""
    doc = _doc(_section("9.3", tableaux=(Tableau(
        entetes=("Indicateur", "2027", "2028", "2029"),
        lignes=(
            ("Seuil de rentabilité", "19 900 €", "34 000 €", "60 000 €"),
            ("Marge de sécurité", "0,5 %", "15 %", "25 %"),
        ),
    ),)))
    assert coherence(doc, _reference()) == []


# ── 3. Formules écrites en toutes lettres ───────────────────────────────────


def test_une_formule_de_seuil_fausse_est_recalculee() -> None:
    doc = _doc(_section(
        "9.3",
        "Avec des charges fixes de 5 000 € en 2027 et une marge de 100 %, le seuil de "
        "rentabilité se fixe à 19 900 €.",
    ))
    assert _classes(formules(doc, _reference())) == ["formule"]


def test_une_formule_de_seuil_juste_passe() -> None:
    """Contre-épreuve."""
    doc = _doc(_section(
        "9.3",
        "Avec des charges fixes de 19 900 € en 2027 et une marge de 100 %, le seuil de "
        "rentabilité se fixe à 19 900 €.",
    ))
    assert formules(doc, _reference()) == []


def test_une_operation_ecrite_fausse_est_signalee_et_la_juste_passe() -> None:
    faux = _doc(_section("16.4", "Le calcul est simple : 1 200 € ÷ 12 = 150 €."))
    juste = _doc(_section("16.4", "Le calcul est simple : 1 200 € ÷ 12 = 100 €."))
    assert _classes(formules(faux, _reference())) == ["formule"]
    assert formules(juste, _reference()) == []


def test_un_effectif_fois_un_panier_confronte_a_l_objectif() -> None:
    """80 000 € visés la troisième année à 100 € de panier : 800 personnes, pas 200."""
    faux = _doc(_section(
        "6.4",
        "Capter 200 femmes, rapporté au panier moyen de 100 €, situe l'ambition de la "
        "troisième année.",
    ))
    juste = _doc(_section(
        "6.4",
        "Capter 800 femmes, rapporté au panier moyen de 100 €, situe l'ambition de la "
        "troisième année.",
    ))
    assert _classes(formules(faux, _reference())) == ["formule"]
    assert formules(juste, _reference()) == []


def test_une_quantite_vague_confrontee_a_l_ordre_de_grandeur() -> None:
    """80 000 € à 100 € : 800 participantes — « quelques centaines », pas « quelques dizaines »."""
    faux = _doc(_section(
        "5.5", "Le chiffre d'affaires visé en 2029 est 80 000 €.",
        "Quelques dizaines de participantes suffisent à l'atteindre.",
    ))
    juste = _doc(_section(
        "5.5", "Le chiffre d'affaires visé en 2029 est 80 000 €.",
        "Quelques centaines de participantes suffisent à l'atteindre.",
    ))
    assert _classes(formules(faux, _reference())) == ["formule"]
    assert formules(juste, _reference()) == []


# ── 5. Tableaux qui bouclent, un libellé une valeur ─────────────────────────


def test_un_compte_de_resultat_qui_ne_boucle_pas_est_signale() -> None:
    faux = _doc(_section("16.2", tableaux=(Tableau(
        entetes=("Poste", "2027"),
        lignes=(("Chiffre d'affaires HT", "20 000 €"), ("Charges fixes", "5 000 €"),
                ("Excédent brut d'exploitation", "500 €")),
    ),)))
    juste = _doc(_section("16.2", tableaux=(Tableau(
        entetes=("Poste", "2027"),
        lignes=(("Chiffre d'affaires HT", "20 000 €"), ("Charges externes", "14 500 €"),
                ("Cotisations sociales", "5 000 €"), ("Excédent brut d'exploitation", "500 €")),
    ),)))
    assert _classes(tableaux(faux, _reference())) == ["tableau"]
    assert tableaux(juste, _reference()) == []


def test_un_superlatif_a_deux_valeurs_est_signale() -> None:
    doc = _doc(
        _section("5.3", "Prix le plus haut : 900 € (acteur A)."),
        _section("7.4", tableaux=(Tableau(
            entetes=("Repère", "Concurrent", "Prix"),
            lignes=(("Prix le plus haut du panel", "Acteur B", "700 €"),),
        ),)),
    )
    constats = tableaux(doc, _reference())
    assert sorted(c.section for c in constats if c.classe == "libelle_unique") == ["5.3", "7.4"]


def test_une_valeur_datee_qui_est_celle_d_une_autre_serie_est_signalee() -> None:
    """« Résultat 2029 » = 20 300 € : c'est la CAF 2029 ; le résultat net vaut 20 000 €."""
    doc = _doc(_section("4.3", tableaux=(Tableau(
        entetes=("Modèle", "Résultat 2029"),
        lignes=(("Modèle A", "12 000 €"), ("Modèle B (retenu)", "20 300 €")),
    ),)))
    constats = [c for c in tableaux(doc, _reference()) if c.classe == "libelle_unique"]
    assert len(constats) == 1 and "CAF" in constats[0].detail


def test_une_variante_non_retenue_n_est_pas_comparee_au_previsionnel() -> None:
    """Contre-épreuve : la ligne du modèle écarté porte ses propres chiffres."""
    doc = _doc(_section("4.3", tableaux=(Tableau(
        entetes=("Modèle", "Résultat 2029"),
        lignes=(("Modèle A", "12 000 €"), ("Modèle B (retenu)", "20 000 €")),
    ),)))
    assert tableaux(doc, _reference()) == []
