"""Phase 41 — La boucle de correction restaure le chapitre apres echec API.

Bug observe sur WAOME v4 (22/07/2026, job 45e0809c) : 3 chapitres restes
en statut RUNNING apres que la boucle de correction a rencontre une
erreur reseau. Cause : `except Exception: continue` (correction.py:186)
avale l'erreur sans restaurer l'etat du chapitre. Consequence : le
renderer ignore les chapitres non-DONE et livre un document ampute
(20/23 chapitres) SANS que ni l'operateur ni le gate ne le voient
(les checks portent sur les chapitres presents).

C'est le pire cas SaaS : livrable partiel, pas de signal.

Fix : la boucle sauvegarde le contenu et le statut AVANT toute
tentative de regeneration ; en cas d'erreur, elle restaure. Le chapitre
garde son ancien contenu (donc reste refuse par le gate au round
suivant) mais n'est pas laisse en statut RUNNING amputable.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from generation.correction import _MAX_REGEN_PAR_ROUND, _feedback_by_chapter
from generation.gate import GateFailure
from generation.models import ChapterStatus


def test_cap_de_regeneration_par_round_priorise_les_defauts_graves() -> None:
    """Sur un rapport avec 15 chapitres fautifs de gravites differentes, la
    boucle ne regenere QUE _MAX_REGEN_PAR_ROUND (8) chapitres — les plus
    graves d'abord (coherence_chiffree, strategy_*, prudence_juridique_*).

    Bug WAOME v4 : la boucle regenerait 15+ chapitres, prenait 106 min,
    faisait diverger d'autres chapitres corrects. On borne."""
    # Simule 15 defauts : 3 graves + 12 legers.
    failures = tuple(
        # Legers (ton publicitaire) — devraient etre relegues.
        [GateFailure(check="ton_publicitaire", chapter_number=n,
                     detail=f"« leader » ch. {n}")
         for n in range(1, 13)]
        # Graves — devraient etre priorises.
        + [GateFailure(check="coherence_chiffree", chapter_number=14,
                       detail="Marge brute divergente"),
           GateFailure(check="strategy_market_study_tcac_cardinal",
                       chapter_number=0,
                       detail="5 TCAC distincts"),
           GateFailure(check="prudence_juridique_evenement_corporate",
                       chapter_number=7,
                       detail="« Canva 2021 » sans source")]
    )

    routed = _feedback_by_chapter(failures, cap=_MAX_REGEN_PAR_ROUND)

    # Le cap est respecte.
    assert len(routed) <= _MAX_REGEN_PAR_ROUND
    # Les 3 graves sont TOUS presents (ch. 14, 1 [ch. 0 remappe], 7).
    assert 14 in routed
    assert 7 in routed
    assert 1 in routed  # ch. 0 → 1 par convention


# Note : le test unitaire `test_boucle_restaure_direct` couvre le contrat
# critique (chapitre restaure apres exception). Un test d'integration
# bout-en-bout necessiterait un mock complet du client Claude — pas
# ajoute ici pour rester lean (regle 4 : viser la classe, pas l'exemple).


@pytest.mark.django_db
def test_boucle_restaure_direct() -> None:
    """Test unitaire du contrat : la boucle capture-et-restaure quand
    regenerate_chapter leve, sans dependre du client Claude."""
    from generation.correction import run_correction_loop
    from generation.models import GenerationJob, ChapterGeneration
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from orders.models import Order

    # Construction minimale d'un job avec 1 chapitre + 1 defaut.
    offer = Offer.objects.create(
        name="Test", slug="test-restaure",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="t@test.local")
    order = Order.objects.create(
        systeme_order_id="test-restaure-1", customer=customer, offer=offer,
    )
    from decimal import Decimal
    job = GenerationJob.objects.create(
        order=order,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("3.20"),
    )
    chapter = ChapterGeneration.objects.create(
        job=job,
        chapter_number=1,
        chapter_title="Analyse marche",
        prompt_key="em.01.marche_mondial_europeen",
        status=ChapterStatus.DONE,
        content="Le marche pese entre 100 et 200 M€.",  # fourchette interdite
    )
    contenu_initial = chapter.content

    # Mock : le gate signale UN defaut, regenerate_chapter leve toujours.
    from generation.gate import GateReport, GateFailure
    fake_report = GateReport(
        passed=False,
        failures=(GateFailure(
            check="fourchette_interdite",
            chapter_number=1,
            detail="Fourchette 100-200 M€ sans mediane.",
        ),),
    )

    # Simule le vrai bug : regenerate_chapter met le chapitre en RUNNING
    # (comme le fait _generate_chapter en interne), puis leve une exception
    # reseau. Sans le fix, la boucle avale l'exception et laisse RUNNING.
    def _regen_qui_crashe(job, chapter, **_kwargs):
        chapter.status = ChapterStatus.RUNNING
        chapter.content = ""  # _generate_chapter reset le contenu
        chapter.save(update_fields=["status", "content"])
        raise RuntimeError("Connection reset by peer")

    with patch("generation.correction._gate.run_delivery_gate", return_value=fake_report), \
         patch("generation.runner.regenerate_chapter", side_effect=_regen_qui_crashe):
        result = run_correction_loop(job, max_rounds=1)

    chapter.refresh_from_db()
    # Contract : le chapitre reste DONE, contenu inchange, statut jamais en RUNNING.
    assert chapter.status == ChapterStatus.DONE, (
        f"Chapitre laisse en {chapter.status} — bug de la boucle."
    )
    assert chapter.content == contenu_initial, (
        "Contenu du chapitre modifie apres exception — bug de la boucle."
    )
    # Le rapport reste en echec (rien n'a ete repare), mais c'est attendu.
    assert not result.passed
