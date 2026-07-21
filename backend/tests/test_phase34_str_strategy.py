"""Phase 34 — STR strategy : les 4 piliers de la strategie business.

Consigne d'Evangeline (fiche 4, question 1) : pour une strategie
business, les 4 piliers sont TOUJOURS traites, dans le meme ordre :

  1. Positionnement & Specialisation
  2. Structuration de l'offre
  3. Planning editorial
  4. Analyse de la tarification

Un STR livre sans un pilier est un livrable incomplet — la strategy
doit le remonter au gate, meme si Evangeline ne peut pas relire avant
delivery (contrainte SaaS).

Regle 4 (viser la classe) : ce check est structurel pour tout STR,
pas un cas particulier lie a un projet. Il vit donc dans la strategy
STR — pas dans le socle commun, pas dans `checks_evangeline` (dont la
logique historique reste pointee par la strategy pour l'instant, mais
c'est un detail d'implementation).
"""
from __future__ import annotations

import pytest


# ══════════════════════════════════════════════════════════════════════════
# 1. La strategy remonte les piliers manquants
# ══════════════════════════════════════════════════════════════════════════


def test_document_complet_ne_remonte_aucun_probleme() -> None:
    """Contre-epreuve : les 4 piliers sont poses, la strategy passe."""
    from generation.strategies.str_ import STRStrategy

    corpus = {
        3: "PILIER 1 — Positionnement & Specialisation : on choisit le "
           "creneau haut de gamme.",
        4: "PILIER 2 — Structuration de l'offre : trois formules "
           "modulaires.",
        5: "PILIER 3 — Planning editorial : cadence bimensuelle sur "
           "LinkedIn.",
        6: "PILIER 4 — Analyse de la tarification : positionnement "
           "median +15 %.",
    }
    problemes = STRStrategy().problemes_de_coherence(None, corpus)  # type: ignore[arg-type]

    assert problemes == []


def test_pilier_editorial_absent_est_signale() -> None:
    """Un STR sans planning editorial est incomplet."""
    from generation.strategies.str_ import STRStrategy

    corpus = {
        3: "Positionnement & Specialisation : haut de gamme.",
        4: "Structuration de l'offre : trois formules.",
        6: "Analyse de la tarification : mediane +15 %.",
        # Aucune mention du pilier 3 (planning editorial).
    }
    problemes = STRStrategy().problemes_de_coherence(None, corpus)  # type: ignore[arg-type]

    categories = {p.categorie for p in problemes}
    assert "pilier_manquant" in categories
    # Le detail doit citer le pilier concerne (pour que l'operateur
    # sache quoi ajouter, pas juste « un pilier manque »).
    details = " ".join(p.detail for p in problemes)
    assert "PILIER 3" in details or "editorial" in details.lower()


def test_les_4_piliers_absents_remontent_4_problemes() -> None:
    """Corpus vide de piliers → 4 signalements distincts (regle 4 :
    chaque pilier est traite comme un item structurel, pas un pack)."""
    from generation.strategies.str_ import STRStrategy

    corpus = {3: "Introduction generique sans mention des piliers."}
    problemes = STRStrategy().problemes_de_coherence(None, corpus)  # type: ignore[arg-type]

    piliers_manques = [p for p in problemes if p.categorie == "pilier_manquant"]
    assert len(piliers_manques) == 4


# ══════════════════════════════════════════════════════════════════════════
# 2. Enregistrement dans le registre
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_get_strategy_retourne_str_strategy_pour_business_strategy() -> None:
    """Regle 4 : chaque livrable a son manuel. get_strategy renvoie
    maintenant une strategy DEDIEE pour STR au lieu du fallback neutre."""
    from catalog.models import DeliverableType
    from generation.strategies import _reset_cache, get_strategy
    from generation.strategies.str_ import STRStrategy

    _reset_cache()
    strategy = get_strategy(DeliverableType.BUSINESS_STRATEGY)

    assert strategy.deliverable_type == DeliverableType.BUSINESS_STRATEGY
    assert isinstance(strategy, STRStrategy)


def test_contexte_supplementaire_reste_neutre() -> None:
    """La STR strategy n'injecte pas encore de contexte specifique — le
    socle commun (client_facts, base consolidee via EM) suffit. Contract
    verifie pour eviter de casser silencieusement build_context."""
    from generation.strategies.str_ import STRStrategy

    assert STRStrategy().contexte_supplementaire(None, None) is None  # type: ignore[arg-type]
