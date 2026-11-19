"""Business plan de test `68b6ab61` (19/11/2026) : 22 chapitres sur 22, un seul
motif bloquant — et il était faux.

Le gate a opposé « 13 002 € » (le résultat net 2028 du scénario à −10 %, que la
mémoire calcule et que le chapitre 16 doit écrire) aux « 23 335 € » du
prévisionnel central. La relecture, elle, a classé GRAVES — donc renvoyé en
réécriture payante — trois passages justes :

- un tableau de cinq INDICATEURS lu comme un compte de résultat ;
- « le résultat net de 21 625 € est en léger retrait sur 2028 » lu comme le
  résultat net 2028 ;
- « 395 000 000 de personnes », une faute réelle mais réparable sans modèle.
"""
from __future__ import annotations

from typing import Any

from generation.chapitres.typographie import reparer_texte
from generation.gate import _check_chiffre_contre_chiffre
from generation.relecture import Reference, Section, Tableau
from generation.relecture.document import Document
from generation.relecture.tableaux import controler as controler_les_tableaux
from generation.relecture.valeurs import valeurs_datees
from generation.rendering import RenderedSection

# ── Le gate : une valeur de scénario n'est pas une seconde valeur ───────────

CH16 = (
    "En 2027, une baisse de 10 % ramène le résultat net à -3 067 €. "
    "En 2028, le même choc de 10 % laisse un résultat net de 13 002 €, encore positif."
)
CH18 = "En 2028, le résultat net atteint 23 335 €, nettement supérieur à la rémunération."


def _sections(*corps: tuple[int, str]) -> tuple[Any, ...]:
    return tuple(
        RenderedSection(number=numero, title=f"Chapitre {numero}", kind="chapter", body=texte)
        for numero, texte in corps
    )


def test_le_gate_opposait_le_scenario_au_previsionnel() -> None:
    """Le défaut, tel qu'il a bloqué le document : sans la mémoire, « le même choc
    de 10 % » n'est pas reconnu comme un scénario."""
    echecs = _check_chiffre_contre_chiffre(_sections((16, CH16), (18, CH18)))

    assert any("13 002" in e.detail and "23 335" in e.detail for e in echecs)


def test_une_valeur_que_la_memoire_calcule_pour_le_scenario_n_est_pas_opposee() -> None:
    echecs = _check_chiffre_contre_chiffre(
        _sections((16, CH16), (18, CH18)), scenarios=[13_002.0, -3_067.0],
    )

    assert echecs == []


def test_deux_valeurs_centrales_differentes_restent_bloquees() -> None:
    """Contre-épreuve : la contradiction que la cliente avait relevée (SYNAPSES)."""
    echecs = _check_chiffre_contre_chiffre(
        _sections(
            (16, "En 2028, le résultat net atteint 19 800 €."),
            (18, CH18),
        ),
        scenarios=[13_002.0, -3_067.0],
    )

    assert any("19 800" in e.detail for e in echecs)


# ── La relecture : trois lectures fausses ───────────────────────────────────


def _section(numero: str, *paragraphes: str, tableaux: tuple[Tableau, ...] = ()) -> Section:
    return Section(
        numero=numero, titre="", chapitre=int(numero.split(".")[0]),
        paragraphes=list(paragraphes), tableaux=list(tableaux),
    )


def _datees(phrase: str) -> list[tuple[str, int, float]]:
    document = Document(sections=[_section("18.3", phrase)])
    return [(v.serie, v.annee, v.nombre.valeur) for v in valeurs_datees(document)]


def test_l_annee_d_une_comparaison_n_est_pas_celle_de_la_valeur() -> None:
    assert _datees(
        "En 2029, le résultat net de 21 625 € est en léger retrait sur 2028 (23 335 €)."
    ) == []


def test_une_valeur_suivie_de_son_annee_reste_lue() -> None:
    """Contre-épreuve."""
    assert _datees("Le résultat net atteint 23 335 € en 2028.") == [
        ("resultat_net", 2028, 23_335.0),
    ]


def test_le_volume_de_ventes_et_le_chiffre_d_affaires_sont_deux_series() -> None:
    assert _datees(
        "Il faut distinguer le volume de ventes, ce que paient les clients (280 000 € en "
        "2027), et le chiffre d’affaires, ce que nous gardons (136 800 € en 2027)."
    ) == []


def test_le_seuil_qui_porte_sa_valeur_n_est_pas_lu_comme_le_chiffre_d_affaires() -> None:
    lues = _datees(
        "Le seuil de rentabilité de 130 535 € en 2027 laisse une marge de sécurité de "
        "4,6 % du chiffre d’affaires."
    )

    assert ("ca_previsionnel", 2027, 130_535.0) not in lues


INDICATEURS = Tableau(
    entetes=("Indicateur", "2027", "2028", "2029"),
    lignes=(
        ("Chiffre d'affaires HT", "136 800 €", "281 556 €", "513 280 €"),
        ("Volume de ventes réglé par les clients", "280 000 €", "648 000 €", "1 332 000 €"),
        ("Excédent brut d'exploitation", "15 500 €", "40 270 €", "37 863 €"),
        ("Résultat net", "1 954 €", "23 335 €", "21 625 €"),
        ("Seuil de rentabilité (chiffre d'affaires)", "130 535 €", "206 744 €", "443 950 €"),
    ),
)
COMPTE_FAUX = Tableau(
    entetes=("Poste", "2027"),
    lignes=(
        ("Chiffre d'affaires HT", "100 000 €"),
        ("Achats et charges externes", "40 000 €"),
        ("Charges de personnel", "30 000 €"),
        ("Excédent brut d'exploitation", "55 000 €"),
    ),
)


def _constats_de_tableau(tableau: Tableau) -> list[Any]:
    document = Document(sections=[_section("1.4", tableaux=(tableau,))])
    return [c for c in controler_les_tableaux(document, Reference()) if c.classe == "tableau"]


def test_un_tableau_d_indicateurs_n_est_pas_un_compte_de_resultat() -> None:
    assert _constats_de_tableau(INDICATEURS) == []


def test_un_compte_de_resultat_qui_ne_boucle_pas_reste_grave() -> None:
    """Contre-épreuve : 100 000 − 40 000 − 30 000 ne font pas 55 000."""
    constats = _constats_de_tableau(COMPTE_FAUX)

    assert constats and constats[0].grave


# ── Un nombre rond prend son mot d'échelle, sans modèle ─────────────────────


def test_un_nombre_rond_suivi_de_de_prend_son_mot_d_echelle() -> None:
    assert reparer_texte("soit une population estimée à 395 000 000 de personnes.") == (
        "soit une population estimée à 395 millions de personnes."
    )
    assert "2 milliards d" in reparer_texte("un marché de 2 000 000 000 d’euros")
    assert "1,5 million de clients" in reparer_texte("1 500 000 de clients")


def test_un_nombre_non_rond_perd_seulement_son_de() -> None:
    assert reparer_texte("un marché de 275 400 de dollars") == "un marché de 275 400 dollars"


def test_un_de_legitime_n_est_pas_touche() -> None:
    """Contre-épreuve : « 5 000 de plus » est correct, et la réparation est idempotente."""
    texte = "Il en faut 5 000 de plus, soit 395 millions de personnes."

    assert reparer_texte(texte) == texte
