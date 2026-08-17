"""Des parts de marché qui dépassent 100 % ne partagent pas leur périmètre.

Cliente, 11/08/2026, mot pour mot : « Toutes les parts de marché doivent
utiliser le même périmètre. Avant de comparer des parts de marché, LE SYSTÈME
DOIT CONTRÔLER : même pays, même année, même secteur, même canal, même
périmètre produit/service, même unité. »

Six critères, dont aucun ne se lit dans une cellule de tableau. Ce qui se lit,
c'est leur CONSÉQUENCE arithmétique : mélanger des périmètres fait presque
toujours déborder le total. Une part nationale à côté d'une part régionale,
2024 à côté de 2026, le canal en ligne à côté du marché entier — et la somme
dépasse cent.

C'est le seul symptôme mécaniquement vérifiable des six critères, et il est
sans appel : aucune répartition d'un même tout ne dépasse 100 %.
"""
from __future__ import annotations

import pytest

from generation.chapitres.schema import (
    BlocParagraphe,
    BlocTableau,
    ChapitrePayload,
    Tableau,
    motifs_de_balisage,
)


def _chapitre(entetes: list[str], lignes: list[list[str]]) -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=6,
        titre="Parts de marché",
        blocs=[
            BlocParagraphe(texte="Les parts se lisent sur le marché français."),
            BlocTableau(tableau=Tableau(entetes=entetes, lignes=lignes)),
        ],
        resume="Un résumé d'essai suffisamment long pour tenir sa borne basse.",
    )


def test_des_parts_qui_depassent_cent_pour_cent_sont_refusees() -> None:
    """Le symptôme d'un mélange de périmètres — 130 %, arithmétiquement faux."""
    payload = _chapitre(
        ["Acteur", "Part de marché"],
        [["VeraCash", "45 %"], ["AuCOFFRE", "50 %"], ["Degussa", "35 %"]],
    )

    motifs = motifs_de_balisage(payload)

    assert motifs
    assert "130.0 %" in motifs[0]
    # Le motif dit QUOI vérifier : sans les six critères, il faut deviner.
    assert "même canal" in motifs[0]


@pytest.mark.parametrize("entete", ["Part de marché", "Parts de marché", "PDM", "Part (%)"])
def test_la_colonne_se_reconnait_sous_ses_ecritures(entete: str) -> None:
    payload = _chapitre(["Acteur", entete], [["A", "60 %"], ["B", "60 %"]])

    assert motifs_de_balisage(payload)


# ── Les contre-épreuves : ce qui est juste doit passer ───────────────────────


def test_un_total_inferieur_a_cent_est_parfaitement_normal() -> None:
    """Un tableau des huit premiers acteurs n'épuise pas le marché."""
    payload = _chapitre(
        ["Acteur", "Part de marché"],
        [["VeraCash", "12 %"], ["AuCOFFRE", "8 %"], ["Degussa", "5 %"]],
    )

    assert motifs_de_balisage(payload) == []


def test_un_total_a_cent_pile_passe() -> None:
    payload = _chapitre(
        ["Acteur", "Part de marché"],
        [["A", "50 %"], ["B", "30 %"], ["C", "20 %"]],
    )

    assert motifs_de_balisage(payload) == []


def test_les_arrondis_ne_declenchent_pas_le_refus() -> None:
    """Trois tiers écrits « 33,4 / 33,3 / 33,4 » totalisent 100,1 sans erreur.

    CONTRE-ÉPREUVE du seuil : le poser à 100 pile ferait refuser des tableaux
    justes, et un contrôle qui crie à tort finit débranché.
    """
    payload = _chapitre(
        ["Acteur", "Part de marché"],
        [["A", "33,4 %"], ["B", "33,3 %"], ["C", "33,4 %"]],
    )

    assert motifs_de_balisage(payload) == []


def test_la_marge_suit_le_nombre_de_parts_et_leur_precision() -> None:
    """Douze parts au dixième tolèrent 0,6 point — trois n'en tolèrent que 0,15.

    Un seuil FIXE serait trop serré pour un tableau à douze acteurs, qu'il
    refuserait à tort, ou trop lâche pour trois, laissant passer une vraie
    incohérence. La marge se déduit donc de ce qui est ÉCRIT.
    """
    douze_justes = _chapitre(
        ["Acteur", "Part de marché"],
        [[f"Acteur {n}", "8,3 %"] for n in range(12)],  # 99,6 %
    )
    assert motifs_de_balisage(douze_justes) == []

    trois_faux = _chapitre(
        ["Acteur", "Part de marché"],
        [["A", "33,5 %"], ["B", "33,5 %"], ["C", "33,5 %"]],  # 100,5 > 100,15
    )
    assert motifs_de_balisage(trois_faux)


def test_une_colonne_de_pourcentages_qui_n_est_pas_une_part_est_ignoree() -> None:
    """« Taux de croissance » ou « marge » : rien n'impose qu'ils fassent 100.

    Sans cette restriction, tout tableau portant plusieurs pourcentages
    deviendrait suspect — le remède qui frappe ce qui n'était pas malade.
    """
    payload = _chapitre(
        ["Acteur", "Croissance annuelle"],
        [["A", "45 %"], ["B", "50 %"], ["C", "35 %"]],
    )

    assert motifs_de_balisage(payload) == []


def test_une_seule_part_ne_se_juge_pas() -> None:
    """Une ligne unique n'est pas une répartition : il n'y a rien à totaliser."""
    payload = _chapitre(["Acteur", "Part de marché"], [["A", "140 %"]])

    assert motifs_de_balisage(payload) == []


def test_la_consigne_porte_les_six_criteres() -> None:
    """La cause, pas seulement le garde-fou : le contrôle ne LIT pas le pays.

    Il ne voit que le débordement. Un document qui compare deux périmètres
    sans dépasser cent passe — c'est la consigne qui doit l'en empêcher, et
    elle doit donc nommer les six critères.
    """
    from generation.chapitres.runner import _FORME_PAR_LIVRABLE

    forme = _FORME_PAR_LIVRABLE["competitor_study"]
    for critere in ("même pays", "même année", "même secteur", "même canal",
                    "même unité"):
        assert critere in forme, critere
