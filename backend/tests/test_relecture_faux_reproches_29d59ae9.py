"""Trois faux reproches de la relecture, lus dans le business plan `29d59ae9`.

Génération de test du 19/11/2026. La relecture a rendu, entre autres :

- « Le résultat net 2027 vaut 2 806 € ici » sur la ligne « Impôt sur le
  résultat · 2027 · 2 806 € » — l'impôt, pas le résultat (trois fois) ;
- « Le chiffre d'affaires 2027 vaut 0 € » sur « calculées sur sa rémunération
  brute réelle, jamais sur le chiffre d'affaires : à 0 € en 2027 » ;
- « Le seuil de rentabilité 2028 écrit 12 000 € » sur « nous versons 12 000 €
  en 2028 », la rémunération du dirigeant.

Chaque test du défaut échoue sur le code d'avant ; chaque contre-épreuve
vérifie que la vraie contradiction reste vue. Chiffres FICTIFS, ceux de la
référence de `test_relecture_des_chiffres`.
"""
from __future__ import annotations

import pytest

from generation.relecture import Section, Tableau
from generation.relecture.coherence import controler as coherence
from generation.relecture.document import Document
from generation.relecture.tableaux import controler as tableaux
from generation.socle.schema import DonneeSocle
from tests.test_relecture_des_chiffres import _doc, _reference, _section

pytestmark = pytest.mark.django_db


def _libelles(doc: Document) -> list[str]:
    return [c.detail for c in tableaux(doc, _reference()) if c.classe == "libelle_unique"]


def _compte(impot: str, resultat: str) -> Section:
    """2028 : CA 40 000, EBE 6 500, dotations 300, impôt 200, résultat net 6 000."""
    return _section("16.2", tableaux=(Tableau(
        entetes=("Poste", "2028"),
        lignes=(
            ("Chiffre d'affaires HT", "40 000 €"),
            ("Charges d'exploitation", "33 500 €"),
            ("Excédent brut d'exploitation (EBE)", "6 500 €"),
            ("Dotations aux amortissements", "300 €"),
            ("Impôt sur le résultat", impot),
            ("Résultat net", resultat),
            ("Capacité d'autofinancement (CAF)", "6 300 €"),
        ),
    ),))


def test_l_impot_sur_le_resultat_n_est_pas_le_resultat_net() -> None:
    assert _libelles(_doc(_compte("200 €", "6 000 €"))) == []


def test_un_resultat_net_faux_reste_signale() -> None:
    """Contre-épreuve : la ligne « Résultat net » elle-même reste jugée."""
    assert len(_libelles(_doc(_compte("200 €", "5 000 €")))) == 1


def test_un_montant_de_remuneration_n_est_pas_le_chiffre_d_affaires() -> None:
    doc = _doc(_section(
        "16.4",
        "Les cotisations sociales du président sont calculées sur sa rémunération brute "
        "réelle, jamais sur le chiffre d'affaires : à 0 € en 2027, elles sont nulles.",
    ))
    assert _libelles(doc) == []


def test_un_chiffre_d_affaires_faux_reste_signale() -> None:
    """Contre-épreuve : une phrase qui ne nomme que le chiffre d'affaires."""
    doc = _doc(_section("16.4", "Le chiffre d'affaires atteint 15 000 € en 2027."))
    assert len(_libelles(doc)) == 1


def test_une_remuneration_n_est_pas_le_seuil_de_rentabilite() -> None:
    doc = _doc(_section(
        "18.3",
        "Décision : nous maintenons zéro rémunération en 2027, nous versons 12 000 € en "
        "2028 et 18 000 € en 2029, chaque palier étant conditionné au dépassement du "
        "seuil de rentabilité.",
    ))
    assert [c for c in coherence(doc, _reference()) if c.classe == "fait_par_annee"] == []


def test_un_seuil_faux_reste_signale() -> None:
    """Contre-épreuve : seuil calculé 2028 = 34 000 €."""
    doc = _doc(_section("16.5", "Le seuil de rentabilité atteint 12 000 € en 2028."))
    assert [c.classe for c in coherence(doc, _reference())] == ["fait_par_annee"]


# ── Le point bas de la trésorerie (vrai défaut du même dossier) ─────────────


def _tresorerie(*phrases: str) -> Document:
    mois = ("Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre")
    soldes = (12_300, 13_200, 14_100, 15_000, 15_900, 16_700,
              17_600, 18_500, 19_400, 20_300, 21_200, 22_046)
    return _doc(_section(
        "16.7", *phrases,
        tableaux=(Tableau(
            entetes=("Mois", "Encaissements", "Décaissements", "Solde cumulé"),
            lignes=tuple(
                (m, "11 400 €", "9 433 €", f"{s:,} €".replace(",", " "))
                for m, s in zip(mois, soldes, strict=True)
            ),
        ),),
    ))


def _tresoreries(doc: Document) -> list[str]:
    return [c.detail for c in tableaux(doc, _reference()) if c.classe == "tresorerie"]


def test_un_plancher_que_le_tableau_franchit_est_signale() -> None:
    doc = _tresorerie(
        "Le point bas est janvier, autour de 12 300 €. Il reste largement couvert par les "
        "18 000 € de trésorerie de départ et ne descend jamais en dessous de ce coussin.",
        "Notre trésorerie ne descend jamais sous le coussin de 18 000 €, même en janvier.",
    )
    constats = [c for c in tableaux(doc, _reference()) if c.classe == "tresorerie"]
    assert len(constats) == 2
    assert all(not c.grave for c in constats)
    assert "12 300 €" in constats[0].detail


def test_un_point_bas_juste_n_est_pas_signale() -> None:
    """Contre-épreuves : le plancher réel, un plancher plus bas, un solde final."""
    doc = _tresorerie(
        "Le point bas est janvier, à 12 300 € : la trésorerie de départ de 18 000 € a "
        "baissé de 5 700 €.",
        "Le solde ne descend jamais sous 12 300 € et finit l'année à 22 046 €.",
        "La trésorerie ne passe jamais sous 10 000 €.",
    )
    assert _tresoreries(doc) == []


# ── Une base relevée par l'étude n'est pas une source extérieure ────────────


def test_la_base_des_concurrents_de_l_etude_n_est_pas_une_source_a_lister() -> None:
    from generation.relecture.sources import citations_du_document

    doc = _doc(_section(
        "5.1", "Source : Base consolidée concurrents de l'étude, notation sur la grille "
        "d'accessibilité tarifaire (1 à 5)",
    ), _section("7.3", "Source : Base consolidée concurrents, notation EVKHA"))
    assert citations_du_document(doc, 21) == []


def test_une_source_exterieure_reste_une_citation() -> None:
    """Contre-épreuve."""
    from generation.relecture.sources import citations_du_document

    doc = _doc(_section("6.1", "Source : Mordor Intelligence, Asia-Pacific cross-border, 2026"))
    assert [c.nom for c in citations_du_document(doc, 21)] == ["Mordor Intelligence"]


# ── Une note de révision ne reste pas dans un libellé ───────────────────────


def _donnee(libelle: str, source: str = "Douanes chinoises, 2025") -> DonneeSocle:
    return DonneeSocle.model_validate({
        "id": "marche_national_taille", "libelle": libelle, "valeur": 176_000.0,
        "unite": "M€", "annee": 2025, "perimetre": "national", "source": source,
        "fiabilite": "estimee",
    })


def test_une_reprise_a_l_identique_ne_porte_aucune_mention() -> None:
    donnee = _donnee(
        "Importations chinoises de produits agricoles — révisé depuis le livrable "
        "business_plan déjà produit, repris à l'identique"
    )
    assert donnee.libelle == "Importations chinoises de produits agricoles"
    assert donnee.source == "Douanes chinoises, 2025"


def test_une_vraie_revision_passe_dans_la_source_sans_le_code_interne() -> None:
    donnee = _donnee(
        "Importations chinoises de produits agricoles — révisé depuis le livrable "
        "business_plan, qui retenait 150 000 M€"
    )
    assert donnee.libelle == "Importations chinoises de produits agricoles"
    assert donnee.source == (
        "Douanes chinoises, 2025 ; révisé depuis l'étude précédente, qui retenait 150 000 M€"
    )


def test_un_libelle_ordinaire_ne_change_pas() -> None:
    """Contre-épreuve : un trait d'union, un tiret qui précise le périmètre."""
    libelle = "Marché du e-commerce transfrontalier — Chine continentale, mi-2025"
    assert _donnee(libelle).libelle == libelle


# ── Contre-épreuves demandées par la relecture du diff (21/11/2026) ─────────


def test_la_caf_qui_repose_sur_le_resultat_net_n_est_pas_lue_comme_caf() -> None:
    """« sur le résultat net » nomme le résultat : deux séries, rien d'attribué."""
    doc = _doc(_section("16.3", "La CAF repose sur le résultat net : 100 € en 2027."))
    assert _libelles(doc) == []


def test_un_seuil_remuneration_comprise_reste_juge() -> None:
    """La rémunération COMPRISE n'est pas une série nommée : le seuil faux se voit."""
    doc = _doc(_section(
        "16.5",
        "Le seuil de rentabilité, rémunération du dirigeant comprise, atteint 12 000 € en 2028.",
    ))
    assert [c.classe for c in coherence(doc, _reference())] == ["fait_par_annee"]


def test_une_donnee_observee_sans_source_reste_refusee() -> None:
    import pytest as _pytest
    from pydantic import ValidationError

    with _pytest.raises(ValidationError):
        DonneeSocle.model_validate({
            "id": "marche_national_taille",
            "libelle": "Marché — révisé depuis l'étude précédente, qui retenait 1 200 M€",
            "valeur": 1_500.0, "unite": "M€", "annee": 2025, "perimetre": "national",
            "source": "", "fiabilite": "observee",
        })


def test_le_solde_du_mois_n_est_pas_le_solde_cumule() -> None:
    """Deux colonnes « solde » : le point bas se lit sur le cumul."""
    mois = ("Janvier", "Février", "Mars", "Avril", "Mai", "Juin")
    doc = _doc(_section(
        "16.7", "Notre trésorerie ne descend jamais sous 15 000 €.",
        tableaux=(Tableau(
            entetes=("Mois", "Solde du mois", "Solde cumulé"),
            lignes=tuple((m, "-2 000 €", f"{16_000 + 500 * i:,} €".replace(",", " "))
                         for i, m in enumerate(mois)),
        ),),
    ))
    assert _tresoreries(doc) == []
