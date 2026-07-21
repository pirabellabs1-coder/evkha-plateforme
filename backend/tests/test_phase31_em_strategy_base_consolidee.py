"""Phase 31 — EM strategy : base chiffree consolidee + checks arithmetiques.

Constats mesures sur WAOME EM v1 (job 49953f14, retour Evangeline 21/07/2026) :

  - « TCAC mondial 20 % dans un chapitre, 31 % dans un autre »
  - « 40 Md$ 2024 -> 120 Md$ 2030 correspond a 20 %, pas 31 % »
  - « marche francais 2,1 Md€ presente comme 16 % du marche europeen 3,6
    Md€ -> le calcul donne 576 M€ »

Ces defauts ne peuvent PAS etre attrapes par un check textuel : ils
existent seulement au niveau des RELATIONS entre chiffres. Deux verrous
posés ici :

1. Une base chiffree consolidee, produite apres les chapitres 1-2, est
   injectee au contexte des chapitres 3-22. Le modele voit la reference
   avant d'ecrire, ne peut pas ignorer un chiffre verrouille.

2. Deux checks arithmetiques :
   - TCAC recalcule depuis la projection (val_fin/val_deb)^(1/n) - 1 :
     ecart > 1 point = defaut.
   - Ratio « X = P % de Y » : X compare a Y * P/100, ecart > 5 % = defaut.

Tous les tests partent d'un cas nomme par Evangeline dans son retour, pas
d'un exemple theorique (regle 8 du CLAUDE.md).
"""
from __future__ import annotations

import pytest

from generation.strategies.em import (
    EMStrategy,
    verifier_cardinal_tcac,
    verifier_ratio,
    verifier_tcac_coherent_par_niveau,
    verifier_tcac_projection,
)

# ══════════════════════════════════════════════════════════════════════════
# 1. Base chiffree consolidee — injection dans le contexte
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_la_base_consolidee_apparait_dans_les_chapitres_3_a_22() -> None:
    """Constat WAOME : sans base consolidee visible dans le prompt du
    chapitre 3, le modele reinvente ses propres chiffres. La strategy
    doit injecter cette base des le chapitre 3."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.coherence import extract_and_lock_chiffres_cles
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offer = Offer.objects.create(
        name="EM base",
        slug="em-base-31",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="em31@example.com")
    order = Order.objects.create(
        systeme_order_id="ord_em31", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "coworking", "PAYS": "France",
            "ZONE": "Beziers", "PROJET": "coworking",
        },
    )
    job = bootstrap_generation_job(submission)

    # Simule les chapitres 1 et 2 : chiffres verrouilles.
    extract_and_lock_chiffres_cles(job, chapter_number=1, content=(
        "Le marche mondial du coworking pese 30 milliards en 2025. "
        "TCAC mondial de 12,5 % sur la periode."
    ))
    extract_and_lock_chiffres_cles(job, chapter_number=2, content=(
        "Le marche europeen represente 8 milliards. "
        "Le marche national francais atteint 900 millions."
    ))

    strategy = EMStrategy()

    # Chapitres 1 et 2 : pas de base consolidee (elle n'existe pas encore).
    ch1 = job.chapters.get(chapter_number=1)
    assert strategy.contexte_supplementaire(job, ch1) is None

    ch2 = job.chapters.get(chapter_number=2)
    assert strategy.contexte_supplementaire(job, ch2) is None

    # Chapitres 3, 5, 15 : la base doit apparaitre.
    for numero in (3, 5, 15):
        ch = job.chapters.get(chapter_number=numero)
        ctx = strategy.contexte_supplementaire(job, ch)
        assert ctx is not None, f"chapitre {numero} : base consolidee absente"
        assert "BASE CHIFFREE CONSOLIDEE" in ctx.corps
        assert "30 milliards" in ctx.corps
        assert "8 milliards" in ctx.corps
        assert "900 millions" in ctx.corps


@pytest.mark.django_db
def test_la_base_consolidee_est_vide_sans_chiffres_verrouilles() -> None:
    """Contre-epreuve : sans chiffres extraits aux chapitres 1-2, on
    n'injecte RIEN plutot que d'injecter un tableau creux qui embrouille."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offer = Offer.objects.create(
        name="EM vide",
        slug="em-vide-31",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="emvide@example.com")
    order = Order.objects.create(
        systeme_order_id="ord_emvide", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "x", "PAYS": "France", "ZONE": "Paris", "PROJET": "x",
        },
    )
    job = bootstrap_generation_job(submission)
    strategy = EMStrategy()
    ch5 = job.chapters.get(chapter_number=5)
    assert strategy.contexte_supplementaire(job, ch5) is None


# ══════════════════════════════════════════════════════════════════════════
# 2. Check arithmetique TCAC
# ══════════════════════════════════════════════════════════════════════════


def test_tcac_annonce_faux_est_detecte() -> None:
    """Cas WAOME textuel : « passer de 40 Md$ en 2024 a 120 Md$ en 2030,
    soit un TCAC de 31 % ». Le calcul reel donne ~20 %."""
    texte = (
        "Le marche mondial de l'IA generative devrait passer de 40 Md$ en "
        "2024 a 120 Md$ en 2030, soit un TCAC de 31 %."
    )
    problemes = verifier_tcac_projection(texte)

    assert len(problemes) == 1
    assert "31" in problemes[0]
    assert "20" in problemes[0] or "19" in problemes[0]  # recalcul


def test_tcac_annonce_correct_ne_declenche_pas() -> None:
    """Contre-epreuve : 40 Md$ en 2024 -> 120 Md$ en 2030 = 20 %/an bien
    annonce. Pas de defaut."""
    texte = (
        "Le marche mondial passe de 40 Md$ en 2024 a 120 Md$ en 2030, "
        "soit un TCAC de 20 %."
    )
    assert verifier_tcac_projection(texte) == []


def test_tcac_dans_la_tolerance_est_accepte() -> None:
    """Contre-epreuve : un ecart d'1 point (arrondi) est tolere.
    40 -> 120 en 6 ans = 20.09 %. On accepte 20 % ou 21 %."""
    for annonce in ("20 %", "21 %", "20,5 %"):
        texte = (
            f"Le marche passe de 40 Md$ en 2024 a 120 Md$ en 2030, soit un "
            f"TCAC de {annonce}."
        )
        assert verifier_tcac_projection(texte) == [], (
            f"faux positif pour {annonce}"
        )


def test_le_tcac_est_verifie_meme_hors_forme_canonique() -> None:
    """Variante lexicale : « croissance annuelle de X % »."""
    texte = (
        "Le marche europeen devrait passer de 10 Md€ en 2024 a 40 Md€ en "
        "2030, avec une croissance annuelle moyenne de 10 %."
    )
    # 10 -> 40 en 6 ans = 26.0 %/an. 10 % annonce = defaut.
    problemes = verifier_tcac_projection(texte)
    assert len(problemes) == 1
    assert "10" in problemes[0]


# ══════════════════════════════════════════════════════════════════════════
# 3. Check arithmetique ratio X = P % de Y
# ══════════════════════════════════════════════════════════════════════════


def test_ratio_faux_est_detecte() -> None:
    """Cas WAOME nomme par Evangeline : « le marche francais de 2,1 Md€ est
    presente comme correspondant a 16 % d'un marche europeen de 3,6 Md€ ».
    Calcul reel : 3,6 x 16 % = 0,576 Md€, PAS 2,1."""
    texte = (
        "Le marche francais atteint 2,1 Md€ en 2025, ce qui represente 16 % "
        "d'un marche europeen de 3,6 Md€."
    )
    problemes = verifier_ratio(texte)

    assert len(problemes) == 1
    assert "16" in problemes[0]
    # Le message doit chiffrer l'attendu pour etre lisible.
    assert "576" in problemes[0] or "0.6" in problemes[0].lower()


def test_ratio_juste_ne_declenche_pas() -> None:
    """Contre-epreuve : 576 M€ = 16 % de 3,6 Md€ est mathematiquement bon."""
    texte = (
        "Le marche francais atteint 576 M€ en 2025, ce qui correspond a 16 % "
        "du marche europeen de 3,6 Md€."
    )
    assert verifier_ratio(texte) == []


def test_ratio_tolere_l_arrondi() -> None:
    """Contre-epreuve : ecart faible tolere (5 %). 580 M€ ≈ 576 M€."""
    texte = (
        "Le marche francais atteint 580 M€, ce qui equivaut a 16 % du "
        "marche europeen de 3,6 Md€."
    )
    assert verifier_ratio(texte) == []


# ══════════════════════════════════════════════════════════════════════════
# 4. Check inter-chapitres : TCAC identique par niveau
# ══════════════════════════════════════════════════════════════════════════


def test_tcac_mondial_divergent_entre_chapitres_est_signale() -> None:
    """Cas WAOME reel : « TCAC mondial 20 % » chap 1 vs « TCAC mondial
    31 % » chap 8. Meme perimetre, deux chiffres. Avant : aucun check ne
    l'attrapait."""
    corpus = {
        1: "Le TCAC mondial retenu est de 20 % sur la periode 2024-2030.",
        8: "Nous prenons un TCAC mondial de 31 % pour cette projection.",
    }
    problemes = verifier_tcac_coherent_par_niveau(corpus)

    assert len(problemes) == 1
    assert "mondial" in problemes[0]
    assert "20" in problemes[0] and "31" in problemes[0]


def test_tcac_du_meme_niveau_identique_ne_declenche_pas() -> None:
    """Contre-epreuve : citer le meme TCAC dans 3 chapitres est LE
    comportement attendu (base consolidee respectee)."""
    corpus = {
        1: "TCAC mondial 12 % sur la periode.",
        3: "TCAC mondial : 12 %.",
        7: "Le TCAC mondial retenu est de 12 %.",
    }
    assert verifier_tcac_coherent_par_niveau(corpus) == []


def test_tcac_de_niveaux_differents_ne_sont_pas_compares() -> None:
    """Contre-epreuve : mondial 20 %, europeen 15 %, national 8 % — chacun
    dans son niveau, aucune contradiction."""
    corpus = {
        1: "TCAC mondial de 20 %.",
        2: "TCAC europeen de 15 %, TCAC national francais de 8 %.",
    }
    assert verifier_tcac_coherent_par_niveau(corpus) == []


def test_tcac_avec_ecart_arrondi_est_tolere() -> None:
    """12,5 % arrondi a 12,7 % (< 1 point) reste accepte."""
    corpus = {
        1: "TCAC mondial 12,5 %.",
        5: "TCAC mondial retenu : 12,7 %.",
    }
    assert verifier_tcac_coherent_par_niveau(corpus) == []


# ══════════════════════════════════════════════════════════════════════════
# 4bis. Cardinal des TCAC — trop de valeurs distinctes = incoherence
# ══════════════════════════════════════════════════════════════════════════


def test_cardinal_tcac_au_dela_de_3_valeurs_est_signale() -> None:
    """Cas WAOME v1 mesure : 5 valeurs distinctes (20, 28, 30, 31, 38 %).
    Le max legitime metier est 3 (mondial/continental/national). Au-dela,
    le lecteur ne sait plus laquelle retenir."""
    corpus = {
        1: "TCAC retenu de 20 %.",
        3: "TCAC europeen retenu 28 %.",
        5: "TCAC de 30 % sur ce segment.",
        8: "TCAC mondial de 31 %.",
        12: "TCAC regional le plus eleve : 38 %.",
    }
    problemes = verifier_cardinal_tcac(corpus)

    assert len(problemes) == 1
    for v in ("20", "28", "30", "31", "38"):
        assert v in problemes[0], f"{v} % absent du message"


def test_cardinal_tcac_dans_la_limite_ne_declenche_pas() -> None:
    """Contre-epreuve : 3 valeurs de TCAC = maximum legitime (mondial,
    continental, national). Pas de signal."""
    corpus = {
        1: "TCAC mondial 12 %.",
        3: "TCAC europeen 8 %.",
        7: "TCAC national francais 5 %.",
    }
    assert verifier_cardinal_tcac(corpus) == []


# ══════════════════════════════════════════════════════════════════════════
# 5. Integration : la strategy est bien selectionnee
# ══════════════════════════════════════════════════════════════════════════


def test_get_strategy_retourne_em_strategy_pour_market_study() -> None:
    from catalog.models import DeliverableType
    from generation.strategies import get_strategy

    strategy = get_strategy(DeliverableType.MARKET_STUDY)

    assert strategy.deliverable_type == DeliverableType.MARKET_STUDY


def test_get_strategy_retourne_fallback_neutre_pour_les_autres() -> None:
    """Les autres livrables n'ont pas encore de strategy dediee. Le
    fallback neutre ne bloque rien, n'ajoute rien : le socle commun
    continue d'operer comme avant. Migration progressive assumee."""
    from catalog.models import DeliverableType
    from generation.strategies import get_strategy

    for dt in (
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.COMPETITOR_STUDY,
        DeliverableType.BUSINESS_STRATEGY,
    ):
        strategy = get_strategy(dt)
        # Fallback : contexte None, aucun probleme detecte.
        assert strategy.contexte_supplementaire(None, None) is None  # type: ignore[arg-type]
        assert strategy.problemes_de_coherence(None, {}) == []  # type: ignore[arg-type]
