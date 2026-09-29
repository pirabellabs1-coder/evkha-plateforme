"""Le gate signale un mot anglais resté dans la prose — et la relecture le fait réécrire.

29/09/2026, business plan ÉCLORE, p. 67 : « already financé ». La réparation
remplace les mots anglais sans ambiguïté avant le Word ; ceux qu'elle ne peut
pas remplacer sans risque (« overall » : global ? globalement ?) restent
signalés. Le détecteur existait, mais le gate ne l'appelait pas : un contrôle
écrit et jamais lancé ne contrôle rien (règle 1).
"""
from __future__ import annotations

from generation.correction import _CHECK_LABELS
from generation.gate import _check_texte_francais
from generation.rendering import RenderedSection


def _section(corps: str) -> RenderedSection:
    return RenderedSection(number=4, title="Offre", kind="chapter", body=corps)


def test_des_mots_anglais_ambigus_sont_signales_au_chapitre() -> None:
    """Deux occurrences au moins : un seul « overall » ne paie pas une réécriture."""
    corps = "Le bilan overall reste positif. La tendance overall se confirme sur trois ans."
    echecs = _check_texte_francais((_section(corps),))
    anglais = [e for e in echecs if e.check == "mot_anglais"]
    assert anglais and anglais[0].chapter_number == 4


def test_un_seul_mot_ambigu_ne_fait_pas_reecrire_le_chapitre() -> None:
    """Contre-épreuve : le seuil du lot langue (revue du 29/09/2026)."""
    echecs = _check_texte_francais((_section("Le bilan overall reste positif sur trois ans."),))
    assert not [e for e in echecs if e.check == "mot_anglais"]


def test_un_texte_francais_ne_l_est_pas() -> None:
    """Contre-épreuve : du français correct ne déclenche rien."""
    echecs = _check_texte_francais((_section("Le bilan global reste positif sur trois ans."),))
    assert not [e for e in echecs if e.check == "mot_anglais"]


def test_le_motif_est_reparable() -> None:
    assert "mot_anglais" in _CHECK_LABELS
