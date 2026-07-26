"""Phase 33 — BP strategy : IS bracket + remuneration dirigeant.

Defauts nommes par Evangeline sur le previsionnel WAOME (retour
21/07/2026, applicables a TOUT BP) :

  - « l'impot sur les societes est calcule a 15 % sur tout le benefice,
    alors que ce taux reduit ne s'applique que sur une premiere tranche »
  - « la remuneration et les cotisations sociales de la fondatrice ne
    sont pas integrees »

Ces defauts sont bancaires : un banquier voit immediatement qu'un
previsionnel avec IS 15 % au-dela de 42 500 EUR ou sans salaire dirigeant
n'a pas ete verifie. Livrer un tel dossier detruit la credibilite du
projet EVKHA aupres du reseau bancaire — c'est le pire risque du SaaS
puisqu'aucun humain ne relit avant envoi.

Regle 4 : viser la classe. La regle fiscale (IS 15 % <= 42 500 EUR) est
une constante metier, pas un cas particulier. La regle « BP doit contenir
la remuneration dirigeante » est structurelle, pas dependant du projet.

Tous les tests partent d'une formulation qu'un modele pourrait ecrire —
pas d'un exemple theorique reformule pour l'occasion.
"""
from __future__ import annotations

import pytest

from generation.strategies.bp import (
    BPStrategy,
    verifier_is_bracket,
    verifier_remuneration_dirigeant,
)


# ══════════════════════════════════════════════════════════════════════════
# 1. IS 15 % appliquable UNIQUEMENT sur la premiere tranche 42 500 EUR
# ══════════════════════════════════════════════════════════════════════════


def test_is_15_pc_sur_tout_le_benefice_est_signale() -> None:
    """Cas WAOME/Evangeline : « IS calcule a 15 % sur tout le benefice »
    est faux, la tranche a taux reduit s'arrete a 42 500 EUR."""
    corpus = {
        14: (
            "L'impot sur les societes est calcule au taux de 15 % applique "
            "au benefice imposable de 60 000 EUR, soit 9 000 EUR d'IS."
        ),
    }
    problemes = verifier_is_bracket(corpus)

    assert len(problemes) == 1
    assert "42 500" in problemes[0] or "42500" in problemes[0]


def test_is_15_pc_annonce_sans_precision_de_tranche_est_signale() -> None:
    """« Nous appliquons un taux d'IS de 15 % » sans mention de la tranche
    est ambigu. Un banquier attend la reference explicite."""
    corpus = {
        15: (
            "Le previsionnel retient un taux d'IS de 15 % sur toute la "
            "periode."
        ),
    }
    problemes = verifier_is_bracket(corpus)

    assert len(problemes) == 1


def test_is_correctement_borne_ne_declenche_pas() -> None:
    """Contre-epreuve : la formulation correcte doit passer."""
    corpus = {
        14: (
            "L'IS est calcule au taux reduit de 15 % sur les premiers "
            "42 500 EUR de benefice, puis 25 % au-dela."
        ),
    }
    assert verifier_is_bracket(corpus) == []


def test_is_25_pc_seul_ne_declenche_pas() -> None:
    """Contre-epreuve : IS a 25 % (taux normal) ne pose aucun probleme."""
    corpus = {
        14: (
            "L'IS s'applique au taux de 25 %, soit un montant de "
            "12 500 EUR sur un benefice de 50 000 EUR."
        ),
    }
    assert verifier_is_bracket(corpus) == []


def test_is_15_pc_dans_prose_non_previsionnelle_ne_declenche_pas() -> None:
    """Contre-epreuve : citation historique / reference legislative ne
    doit pas declencher (« la loi prevoit un taux de 15 % »)."""
    corpus = {
        6: (
            "Le cadre fiscal francais prevoit un taux reduit d'IS a 15 % "
            "reserve aux PME sur les 42 500 premiers euros de benefice."
        ),
    }
    assert verifier_is_bracket(corpus) == []


# ══════════════════════════════════════════════════════════════════════════
# 2. Remuneration dirigeante presente dans le previsionnel
# ══════════════════════════════════════════════════════════════════════════


def test_previsionnel_sans_remuneration_dirigeant_est_signale() -> None:
    """Cas WAOME : « la remuneration et les cotisations sociales de la
    fondatrice ne sont pas integrees »."""
    corpus = {
        14: (
            "Le previsionnel financier retient les hypotheses suivantes : "
            "chiffre d'affaires 250 000 EUR, charges d'exploitation "
            "40 000 EUR, marge brute 210 000 EUR, EBE 145 000 EUR."
        ),
    }
    problemes = verifier_remuneration_dirigeant(corpus)

    assert len(problemes) == 1
    assert "remuneration" in problemes[0].lower() or "salaire" in problemes[0].lower()


def test_previsionnel_avec_remuneration_dirigeant_passe() -> None:
    """Contre-epreuve : la mention est presente, aucun defaut."""
    corpus = {
        14: (
            "Le previsionnel financier integre une remuneration dirigeante "
            "de 30 000 EUR brute annuelle, portant a 55 000 EUR avec les "
            "cotisations sociales URSSAF (SAS)."
        ),
    }
    assert verifier_remuneration_dirigeant(corpus) == []


def test_remuneration_dans_autre_chapitre_couvre_le_previsionnel() -> None:
    """Contre-epreuve : la remuneration peut etre ailleurs dans le doc.
    L'important est qu'elle apparaisse au moins UNE fois dans le corpus,
    avec un montant chiffre."""
    corpus = {
        7: "Le porteur envisage une remuneration mensuelle de 2 500 EUR brut.",
        14: (
            "Le previsionnel retient chiffre d'affaires 250 000 EUR, "
            "resultat net 44 000 EUR."
        ),
    }
    assert verifier_remuneration_dirigeant(corpus) == []


def test_mention_qualitative_sans_montant_reste_signalee() -> None:
    """Contre-epreuve : « le dirigeant se verse un salaire » sans chiffre
    ne suffit pas. Un banquier veut un montant."""
    corpus = {
        14: "Le dirigeant percevra un salaire adapte a la performance.",
    }
    problemes = verifier_remuneration_dirigeant(corpus)

    assert len(problemes) == 1


# ══════════════════════════════════════════════════════════════════════════
# 3. Integration : la strategy s'applique bien au BP
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_get_strategy_retourne_bp_strategy_pour_business_plan() -> None:
    """Regle 4 : chaque livrable a son manuel. get_strategy renvoie
    maintenant une strategy DEDIEE pour BP au lieu du fallback neutre."""
    from catalog.models import DeliverableType
    from generation.strategies import get_strategy

    strategy = get_strategy(DeliverableType.BUSINESS_PLAN)

    assert strategy.deliverable_type == DeliverableType.BUSINESS_PLAN
    assert isinstance(strategy, BPStrategy)


def test_les_deux_checks_sont_appliques_par_la_strategy() -> None:
    """La strategy remonte les deux categories de problemes."""
    corpus = {
        14: (
            "Le previsionnel retient un IS a 15 % sur tout le benefice de "
            "60 000 EUR. Chiffre d'affaires 250 000 EUR."
        ),
    }
    problemes = BPStrategy().problemes_de_coherence(None, corpus)  # type: ignore[arg-type]

    categories = {p.categorie for p in problemes}
    assert "is_bracket" in categories
    assert "remuneration_dirigeant" in categories
