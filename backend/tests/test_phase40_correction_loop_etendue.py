"""Phase 40 — Boucle de correction elargie aux nouveaux checks.

Avant cette phase, `_CHAPTER_LEVEL_CHECKS` ne routait que 4 checks legacy
(contamination, coherence_chiffree, troncature, ordre_de_grandeur). Les
checks post-refonte (fourchette_interdite, doublon_titre, ton_publicitaire,
prudence_juridique_*, sources_non_tracables_*, strategy_*) etaient ignores :
le gate refusait mais la boucle ne reparait rien.

Cas concret : sur WAOME v2 (22/07/2026, job c7bddf29), 38 defauts detectes,
0 route vers la boucle -> pipeline coincé.
"""
from __future__ import annotations

from generation.correction import _feedback_by_chapter, _is_regenerable
from generation.gate import GateFailure


def test_fourchette_interdite_est_regenerable() -> None:
    """Cas WAOME v2 le plus frequent : 26 fourchettes non sourcees."""
    assert _is_regenerable("fourchette_interdite")


def test_doublon_titre_est_regenerable() -> None:
    """Cas exact Evangeline WAOME v1 : titre « 2.4 » en double."""
    assert _is_regenerable("doublon_titre")


def test_ton_publicitaire_est_regenerable() -> None:
    assert _is_regenerable("ton_publicitaire")


def test_prudence_juridique_est_regenerable() -> None:
    """Cas « acquise par Canva en 2021 » sans source."""
    assert _is_regenerable("prudence_juridique_evenement_corporate")
    assert _is_regenerable("prudence_juridique_diffamation")


def test_sources_non_tracables_est_regenerable() -> None:
    """3 sous-motifs, tous routes vers la boucle."""
    assert _is_regenerable("sources_non_tracables_vide")
    assert _is_regenerable("sources_non_tracables_ratio_faible")
    assert _is_regenerable("sources_non_tracables_url_bidon")


def test_strategy_par_livrable_est_regenerable_via_prefix() -> None:
    """Les checks metier « strategy_market_study_tcac_cardinal »,
    « strategy_business_plan_is_bracket », etc. sont attrapes par prefixe."""
    assert _is_regenerable("strategy_market_study_tcac_cardinal")
    assert _is_regenerable("strategy_business_plan_is_bracket")
    assert _is_regenerable("strategy_business_strategy_pilier_manquant")
    assert _is_regenerable("strategy_competitor_study_matrice_absente")


def test_verticales_reste_non_regenerable() -> None:
    """`verticales` est au niveau document — pas de chapitre unique,
    la regeneration ciblee n'aiderait pas. Reste bloquant a la source."""
    assert not _is_regenerable("verticales")


def test_feedback_by_chapter_route_les_nouveaux_checks() -> None:
    """Un rapport avec 3 defauts de types varies → tous routes."""
    failures = (
        GateFailure(
            check="fourchette_interdite",
            chapter_number=3,
            detail="Fourchette « 100-120 kEUR » sans mediane.",
        ),
        GateFailure(
            check="doublon_titre",
            chapter_number=11,
            detail="Titre « Contexte professionnel » x4.",
        ),
        GateFailure(
            check="strategy_market_study_tcac_cardinal",
            chapter_number=0,  # transverse — sera route au chap. 1
            detail="6 TCAC distincts.",
        ),
    )
    routed = _feedback_by_chapter(failures)

    assert 3 in routed
    assert 11 in routed
    assert 1 in routed  # ch. 0 → 1 par convention
    assert "fourchette" in routed[3].lower()
    assert "doublon" in routed[11].lower() or "titre" in routed[11].lower()
    assert "tcac" in routed[1].lower()


def test_failure_sans_chapitre_est_ignoree() -> None:
    """Une echec transverse sans chapter_number ne peut pas etre reparee
    par regeneration ciblee — il est ignore par la boucle (reste bloquant)."""
    failures = (
        GateFailure(
            check="fourchette_interdite",
            chapter_number=None,
            detail="Fourchette detectee.",
        ),
    )
    assert _feedback_by_chapter(failures) == {}
