"""Le plafond de prose ne doit plus brider le livrable ni couper en silence.

Le modèle validé par la cliente est un STANDARD, pas un plafond. Or
`MOTS_AMORCE_MAX` valait 90, une valeur calibrée pour reproduire le volume de
prose du modèle — 90 mots × ~50 sections ≈ 4 500, ses 4 838 mots. Le réglage
visait donc à ATTEINDRE la référence, et interdisait mécaniquement de la
dépasser : un client au besoin plus large recevait la même chose, tronquée.

Second défaut, plus grave : la coupe était SILENCIEUSE. Un chapitre de 200 mots
d'analyse en perdait 110 sans trace — ni log, ni rapport d'assemblage. Quelque
chose refaisait le document après la génération et l'amputait (règle 3).

Ces tests échouent sur le code d'avant (règle 6).
"""
from __future__ import annotations

from django.test import override_settings

from generation.rendu_word.assemblage import (
    RapportAssemblage,
    _amorce,
    mots_paragraphe_max,
)

#: 40 phrases de 7 mots = 280 mots. Au-dessus de tous les plafonds testés.
PAVE = " ".join(["Le marché premium progresse nettement cette année."] * 40)


def test_le_plafond_par_defaut_depasse_celui_du_modele() -> None:
    """90 reproduisait le modèle ; il faut pouvoir le dépasser."""
    assert mots_paragraphe_max() > 90


@override_settings(EVKHA_MOTS_PARAGRAPHE_MAX=150)
def test_le_plafond_est_reglable_sans_redeploiement() -> None:
    assert mots_paragraphe_max() == 150

    rendu = _amorce(PAVE)
    assert len(rendu.split()) <= 150


@override_settings(EVKHA_MOTS_PARAGRAPHE_MAX=0)
def test_zero_desactive_toute_coupe() -> None:
    """Le levier qui rend le document integralement fidele a ce qui a ete ecrit."""
    assert mots_paragraphe_max() == 0

    rendu = _amorce(PAVE)
    assert len(rendu.split()) == len(PAVE.split())


@override_settings(EVKHA_MOTS_PARAGRAPHE_MAX=100)
def test_une_coupe_est_declaree_au_rapport() -> None:
    """LE defaut : la prose disparaissait sans que rien ne le dise."""
    rapport = RapportAssemblage()

    _amorce(PAVE, rapport)

    assert rapport.paragraphes_tronques == 1
    assert rapport.mots_tronques > 0
    # Un livrable ampute ne doit pas passer pour intact.
    assert rapport.complet is False


@override_settings(EVKHA_MOTS_PARAGRAPHE_MAX=100)
def test_un_texte_sous_le_plafond_ne_declare_rien() -> None:
    """Contre-épreuve : pas de faux positif sur un paragraphe normal."""
    rapport = RapportAssemblage()

    court = "Le marché progresse. La demande se structure."
    rendu = _amorce(court, rapport)

    assert rendu == court
    assert rapport.paragraphes_tronques == 0
    assert rapport.mots_tronques == 0
    assert rapport.complet is True


@override_settings(EVKHA_MOTS_PARAGRAPHE_MAX=100)
def test_la_coupe_reste_sur_une_frontiere_de_phrase() -> None:
    """Contre-épreuve : le correctif ne doit pas casser ce qui marchait."""
    rendu = _amorce(PAVE)

    assert rendu.endswith(".")
    assert "premium progresse nettement" in rendu
