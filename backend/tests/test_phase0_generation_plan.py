from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import ChapterStatus
from generation.prompts import build_section_prompt
from generation.runner import _build_phase0_plan, run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order


@pytest.fixture
def competitor_submission() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Etude concurrentielle",
        slug="etude-concurrentielle",
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
    )
    customer = Customer.objects.create(email="client@example.com")
    order = Order.objects.create(systeme_order_id="order_ec_phase0", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "mode",
            "PAYS": "France",
            "ZONE": "Paris",
            "PROJET": "marque textile responsable",
            "CONCURRENTS": ["Nike", "Adidas", "Veja"],
            "DEMANDES_SPECIFIQUES": "Comparer le digital.",
            "ELEMENTS_A_RETENIR": "Positionnement premium accessible.",
        },
    )


@pytest.mark.django_db
def test_phase0_plan_does_not_duplicate_client_brief(
    competitor_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(competitor_submission)

    plan = _build_phase0_plan(job, competitor_submission.normalized_variables)

    assert "VARIABLES_PROJET" in plan
    assert "Nike" not in plan
    assert "['Nike'" not in plan
    assert "Comparer le digital" not in plan
    assert "Chapitre 2" not in plan
    assert "sélectionner" in plan


@pytest.mark.django_db
def test_run_generation_job_keeps_existing_phase0_plan_on_relaunch(
    competitor_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(competitor_submission)
    job.phase0_plan = "PLAN EXISTANT"
    job.save(update_fields=["phase0_plan", "updated_at"])
    job.chapters.update(status=ChapterStatus.DONE, content="ok", operational_summary="ok")

    run_generation_job(job, client=StubClaudeClient())

    job.refresh_from_db()
    assert job.phase0_plan == "PLAN EXISTANT"


@pytest.mark.django_db
def test_build_section_prompt_keeps_recent_previous_context(
    competitor_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(competitor_submission)
    chapter = job.chapters.get(chapter_number=2)
    previous_context = "DEBUT_ANCIEN " + ("x" * 4100) + " FIN_RECENTE"

    prompt = build_section_prompt(chapter, "ec.02.a.directs", previous_context=previous_context)

    assert "FIN_RECENTE" in prompt
    assert "DEBUT_ANCIEN" not in prompt


@pytest.mark.django_db
def test_market_study_budget_keeps_phase0_margin() -> None:
    offer = Offer.objects.create(
        name="Etude de marche",
        slug="etude-marche-phase0",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="client-em@example.com")
    order = Order.objects.create(systeme_order_id="order_em_phase0", customer=customer, offer=offer)
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "beaute", "PAYS": "Benin"},
    )

    job = bootstrap_generation_job(submission)

    # Budget releve a 3.20 EUR pour supporter le plancher _MIN_MAX_TOKENS=2500
    # (evite les chapitres etrangles a 1200 tok), puis a 4.00 EUR : le run reel
    # 010e3bf2 a coute 3.05 EUR (95 % de l'ancien plafond, plus de marge pour un
    # retry) et l'extended thinking ajoute ~0.41 EUR sur 30 appels. Puis a
    # 4.60 EUR : le cout des 11 CHECKs, jusque-la enregistre nulle part, entre
    # dans le grand livre (~0.46 EUR) avec l'advisor des blocs quantifies
    # (~0.22 EUR).
    #
    # Puis a 6.00 EUR (05/08/2026) pour la bascule vers claude-sonnet-5. Ce
    # n'est pas une depense nouvelle : le tarif de Sonnet 5 est celui de
    # Sonnet 4.6. C'est son TOKENIZER qui change — le meme texte y compte
    # environ 30 % de tokens en plus. A 4,60 le throttle aurait rabote
    # max_tokens sur les derniers chapitres pour tenir un plafond calibre sur
    # l'ancien decoupage, et rendu des chapitres courts : le defaut meme que le
    # plancher _MIN_MAX_TOKENS avait corrige.
    #
    # Puis RAMENE a 4,00 EUR le 05/08/2026, et c'est la mesure reelle qui prime
    # sur la projection, comme annonce ci-dessus (regles 7 et 10).
    #
    # Deux etudes de marche COMPLETES ont tourne sur Sonnet 5 : 3,12 et 3,32 EUR.
    #
    # PORTE A 6,00 PUIS 8,00 EUR LE 08/08/2026. Le passage a 8,00 est une
    # MESURE et non une projection : le dossier reel `b561c2d6` a ete coupe par
    # le garde-fou a 22 chapitres sur 23, pour 5,94 EUR. Et cette fois
    # le nombre plafonne VRAIMENT : rythme et plafond sont devenus la meme
    # table, `cost.PLAFOND_PAR_LIVRABLE`. Ils avaient diverge — rythme 4,00,
    # frein 3,10 — et le throttle cadencait alors vers un montant que le frein
    # n'autorisait pas.
    #
    # Ce test ne recopie plus la valeur : il relit la table. Le montant lui-meme
    # est verrouille par `test_plafond_de_generation`, qui le compare a la
    # decision de la cliente recopiee a la main. Ici, ce qui compte est que
    # `bootstrap_generation_job` POSE bien ce plafond sur le job — c'est le seul
    # endroit qui le fait, et un job cree sans lui retomberait sur le defaut du
    # modele (2,00 EUR), donc sur des chapitres rabotes.
    from generation.cost import PLAFOND_PAR_LIVRABLE

    assert job.budget_eur == PLAFOND_PAR_LIVRABLE[DeliverableType.MARKET_STUDY]
