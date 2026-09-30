"""Qualité rédactionnelle et cohérence des indicateurs (points 2, 9, 11, 12 de la cliente).

Business plan ÉCLORE `28a257bf`, repris à la main le 30/09/2026. Textes FICTIFS
sauf les tournures exactes que la cliente a citées. Chaque contrôle a sa
contre-épreuve : le texte correct n'est pas signalé (règle 6).
"""
from __future__ import annotations

from typing import Any

from generation.relecture import Reference, Section, Tableau
from generation.relecture.document import Document
from generation.relecture.redaction import controler


def _doc(*sections: Section) -> Document:
    return Document(sections=list(sections))


def _sec(numero: str, *paragraphes: str, tableaux: tuple[Tableau, ...] = ()) -> Section:
    return Section(numero=numero, titre="", chapitre=int(numero.split(".")[0]),
                   paragraphes=list(paragraphes), tableaux=list(tableaux))


def _classes(constats: list[Any]) -> list[str]:
    return [c.classe for c in constats]


def _graves(document: Document) -> list[Any]:
    return [c for c in controler(document, Reference()) if c.grave]


# ── 2. Un libellé n'assimile pas deux indicateurs ────────────────────────────


def test_un_libelle_qui_nomme_deux_indicateurs_est_signale() -> None:
    """La tournure exacte de la cliente."""
    doc = _doc(_sec("16.2", tableaux=(Tableau(
        entetes=("Poste", "2027"),
        lignes=(("Résultat net (revenu de la dirigeante avant impôt)", "50 €"),),
    ),)))
    constats = [c for c in controler(doc, Reference()) if c.classe == "libelle_melange"]
    assert len(constats) == 1 and constats[0].grave


def test_une_precision_du_meme_indicateur_n_est_pas_signalee() -> None:
    """Contre-épreuve : « (avant impôt) » précise le résultat net, ne le confond pas."""
    doc = _doc(_sec("16.2", tableaux=(Tableau(
        entetes=("Poste", "2027"),
        lignes=(
            ("Résultat net (avant impôt)", "50 €"),
            ("Résultat net après rémunération du dirigeant", "50 €"),
            ("CAF", "400 €"),
        ),
    ),)))
    assert "libelle_melange" not in _classes(controler(doc, Reference()))


# ── 9. Pas d'évolution en pourcentage sur une base faible ────────────────────


def test_une_evolution_sur_une_base_faible_est_signalee() -> None:
    """EBE 782 € → 8 772 € = +1 021,7 % : la base est sous mille euros."""
    doc = _doc(_sec("11.3", tableaux=(Tableau(
        entetes=("Indicateur", "2027", "2028", "Évolution"),
        lignes=(("Excédent brut d'exploitation", "782 €", "8 772 €", "1 021,7 %"),),
    ),)))
    constats = [c for c in controler(doc, Reference()) if c.classe == "evolution"]
    assert len(constats) == 1 and constats[0].grave


def test_une_evolution_en_prose_sur_base_faible_est_signalee() -> None:
    """« de 4,58 € à 60,08 €, soit +1 210,9 % » : l'exemple exact de la cliente."""
    doc = _doc(_sec(
        "18.2",
        "Le revenu mensuel progresse de 4,58 € en 2027 à 60,08 € en 2028, "
        "soit une évolution de 1 210,9 %.",
    ))
    assert "evolution" in _classes(controler(doc, Reference()))


def test_une_evolution_sur_base_normale_n_est_pas_signalee() -> None:
    """Contre-épreuve : 20 000 € → 40 000 € = +100 %, base bien au-dessus de mille euros."""
    doc = _doc(_sec("5.1", tableaux=(Tableau(
        entetes=("Indicateur", "2027", "2028", "Évolution"),
        lignes=(("Chiffre d'affaires", "20 000 €", "40 000 €", "100 %"),),
    ),)))
    assert "evolution" not in _classes(controler(doc, Reference()))


def test_un_pourcentage_qui_n_est_pas_une_evolution_passe() -> None:
    """Contre-épreuve : « marge de 60 % » sur des petits montants n'est pas une évolution."""
    doc = _doc(_sec("9.3", "Sur un panier de 100 €, la marge sur coûts variables est de 60 %."))
    assert "evolution" not in _classes(controler(doc, Reference()))


# ── 11. Pas de répétition dans une même phrase ou cellule ────────────────────


def test_une_redite_dans_une_phrase_est_signalee() -> None:
    """La tournure exacte de la cliente, malgré l'accord « quitte » / « quitté »."""
    doc = _doc(_sec(
        "11.4",
        "Carine quitte son poste et passe à temps plein après avoir quitté son poste.",
    ))
    assert "repetition" in _classes(controler(doc, Reference()))


def test_une_redite_est_un_signal_jamais_une_reprise_payee() -> None:
    """Une reformulation automatique sur une répétition rejouerait les faux positifs
    graves : la passe signale, elle ne fait pas reprendre le chapitre."""
    doc = _doc(_sec(
        "3.1",
        "Le marché des loisirs créatifs progresse, et le marché des loisirs créatifs séduit "
        "un public plus large.",
    ))
    constats = [c for c in controler(doc, Reference()) if c.classe == "repetition"]
    assert constats and not any(c.grave for c in constats)


def test_un_terme_qui_revient_d_une_cellule_a_l_autre_n_est_pas_une_redite() -> None:
    """Contre-épreuve : une ligne de tableau répète « (donnée du projet) » par colonne."""
    doc = _doc(_sec("16.1", tableaux=(Tableau(
        entetes=("Panier", "2027", "2028", "2029"),
        lignes=(("Panier moyen", "182 € TTC (donnée du projet)",
                 "224 € TTC (donnée du projet)", "260 € TTC (donnée du projet)"),),
    ),)))
    assert "repetition" not in _classes(controler(doc, Reference()))


def test_une_ligne_de_source_n_est_pas_une_redite() -> None:
    """Contre-épreuve : « Nom : Site officiel Nom, https://… » est une citation."""
    doc = _doc(_sec("5.6", tableaux=(Tableau(
        entetes=("Source",),
        lignes=(("Les Retraites créatives : Site officiel Les Retraites créatives, "
                 "https://exemple.fr",),),
    ),)))
    assert "repetition" not in _classes(controler(doc, Reference()))


def test_une_phrase_sans_redite_passe() -> None:
    doc = _doc(_sec("1.1", "Le projet ouvre en 2027 et vise la rentabilité en 2029."))
    assert controler(doc, Reference()) == []


# ── 12. Trésorerie et prélèvement ne sont pas disponibles deux fois ──────────


def test_la_tresorerie_et_le_prelevement_ensemble_sont_signales() -> None:
    doc = _doc(_sec(
        "18.6",
        "La trésorerie de fin d'exercice est disponible, et la dirigeante peut se verser "
        "un revenu du même montant.",
    ))
    constats = [c for c in controler(doc, Reference()) if c.classe == "double_compte"]
    assert len(constats) == 1 and not constats[0].grave


def test_une_tresorerie_nette_des_prelevements_n_est_pas_signalee() -> None:
    """Contre-épreuve : « après prélèvement » dit que l'argent n'est compté qu'une fois."""
    doc = _doc(_sec(
        "18.6",
        "Après prélèvement de la rémunération de la dirigeante, la trésorerie de fin "
        "d'exercice disponible s'élève à 2 062 €.",
    ))
    assert "double_compte" not in _classes(controler(doc, Reference()))
