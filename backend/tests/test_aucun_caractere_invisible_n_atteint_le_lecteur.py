"""Les caractères sans dessin ne franchissent pas le rendu.

Cliente, 12/08/2026, sur la stratégie : « nettoyer les caractères Unicode
invisibles ».

## Pourquoi la liste de cinq ne suffisait pas

Le correctif du 09/08 énumérait cinq caractères — tiret conditionnel, marque
d'ordre des octets, non-caractère, caractère de remplacement, espace de
largeur nulle. Unicode en range plus de cent cinquante dans la seule catégorie
`Cf`, et le modèle peut écrire n'importe lequel. Chaque test ci-dessous porte
sur un caractère que l'ancienne liste laissait passer : c'est ce qui les fait
échouer sur le code d'avant (règle 6).

## Et la contre-épreuve compte autant

Une purge trop large abîmerait le français : accents, ligatures, tiret
cadratin, espace insécable des typographes. Une réparation qui frappe ce qui
n'était pas malade est pire que le défaut d'origine (règle 2) — et cette
règle a déjà coûté une étude de marché sur ce projet.
"""
from __future__ import annotations

import pytest

from generation.chapitres.typographie import purger_les_invisibles, reparer_texte

#: Chacun était ABSENT de la liste fermée du 09/08/2026.
INVISIBLES_QUE_LA_LISTE_FERMEE_LAISSAIT_PASSER = [
    ("‌", "anti-liant de largeur nulle"),
    ("‍", "liant de largeur nulle"),
    ("⁠", "jointeur de mots"),
    ("‎", "marque de gauche à droite"),
    ("‏", "marque de droite à gauche"),
    ("‭", "forçage de direction"),
    ("⁡", "opérateur invisible d'application"),
    ("", "retour arrière — trace d'un script mal décodé"),
    ("", "échappement"),
]


@pytest.mark.parametrize(
    ("caractere", "nom"), INVISIBLES_QUE_LA_LISTE_FERMEE_LAISSAIT_PASSER
)
def test_un_invisible_hors_de_l_ancienne_liste_disparait(
    caractere: str, nom: str
) -> None:
    """La CLASSE, pas l'exemple (règle 4) : aucun de ceux-là n'était listé."""
    assert purger_les_invisibles(f"café{caractere}filtre") == "caféfiltre", nom


def test_les_cinq_de_l_ancienne_liste_disparaissent_toujours() -> None:
    """Élargir ne doit rien perdre en route."""
    for caractere in ("­", "﻿", "￾", "�", "​"):
        assert purger_les_invisibles(f"a{caractere}b") == "ab"


# ── Les contre-épreuves : le français ordinaire sort intact ──────────────────


def test_le_francais_traverse_la_purge_sans_une_egratignure() -> None:
    """CONTRE-ÉPREUVE : accents, ligature, tiret cadratin, insécables.

    Sans elle, une catégorie Unicode mal choisie viderait le document de ses
    accents et personne ne le verrait avant la livraison.
    """
    phrase = (
        "Étude préliminaire du marché où l'on œuvre — 12 % des acteurs, "
        "soit 1 250 M€ ; l'écart reste « significatif »."
    )

    assert purger_les_invisibles(phrase) == phrase


def test_la_mise_en_page_survit() -> None:
    """CONTRE-ÉPREUVE : saut de ligne et tabulation sont des commandes utiles.

    Ils sont de catégorie `Cc`, comme le retour arrière qu'on supprime. Les
    traiter pareil réduirait le document à un bloc.
    """
    assert purger_les_invisibles("a\nb\tc\r\nd") == "a\nb\tc\r\nd"


def test_la_purge_est_idempotente() -> None:
    """La rejouer ne doit rien changer : elle passe deux fois sur un chapitre."""
    sale = "coffre​fort­ et e⁠commerce﻿"
    une_fois = purger_les_invisibles(sale)

    assert purger_les_invisibles(une_fois) == une_fois


def test_la_reparation_de_typographie_purge_toujours() -> None:
    """Le moteur structuré passe par `reparer_texte`, pas par la purge nue."""
    assert reparer_texte("achat‍-‍vente") == "achat-vente"


# ── La cause, pas seulement la fonction ─────────────────────────────────────


def test_le_chemin_markdown_purge_lui_aussi() -> None:
    """Elle pourrait exister sans être appelée là où ça compte.

    `reparer_typographie` ne voit que le payload STRUCTURÉ. Un chapitre rendu
    en markdown — moteur hérité, chapitre de repli — ne passe jamais par elle,
    et c'est pourtant le même lecteur qui reçoit le document (règle 3 : ce qui
    refait le document après le contrôle doit être contrôlé à son tour).
    """
    from generation.blueprints import SectionKind
    from generation.rendering import _clean_chapter_body

    rendu = _clean_chapter_body(
        "Le marché du café​ de spécialité progresse.", SectionKind.CHAPTER
    )

    assert "​" not in rendu
    assert "café de spécialité" in rendu
