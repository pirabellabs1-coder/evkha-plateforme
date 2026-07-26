"""Phase 44 — Le CHECK INITIAL doit VOIR la fiche projet redigee.

Manuel EVKHA p.3 : « Si la fiche projet est complete, coherente et fidele a la
demande, commencer le chapitre 1. Sinon, corriger la fiche ou demander la
precision necessaire AVANT TOUTE REDACTION. » Le controle porte donc sur la
FICHE REDIGEE, pas sur le brief brut du client.

Bug constate en generation reelle (job 283a0cab, 24/07/2026) : le hook lancait
le CHECK INITIAL avec `chapitres=[]`. Le relecteur ne recevait que les variables
normalisees du brief et reclamait de « collecter et verrouiller dans la fiche »
l'objectif de l'etude, les questions du client, le modele economique et le
lecteur final — six elements tous deja rediges dans le chapitre 0. Verdict
`fix`, generation stoppee avant le chapitre 1 : un faux positif bloquant.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from generation.checks_blocs import BLOCS_PAR_IDENTIFIANT, _construire_prompt_check
from generation.models import ChapterStatus

_FICHE_MARQUEUR = "Cycle de vente estime : 6 a 12 mois pour grands comptes."


def _make_job_avec_fiche():
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(
        name="EM", slug="test-check-initial-fiche",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="fiche@test.local")
    order = Order.objects.create(
        systeme_order_id="test-check-initial-fiche-1", customer=customer, offer=offer,
    )
    job = GenerationJob.objects.create(
        order=order,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("3.20"),
    )
    fiche = ChapterGeneration.objects.create(
        job=job, chapter_number=0, chapter_title="Fiche projet",
        prompt_key="em.00.fiche_projet",
        status=ChapterStatus.DONE,
        content=f"| Rubrique | Contenu |\n|---|---|\n| Clientele | {_FICHE_MARQUEUR} |",
    )
    return job, fiche


@pytest.mark.django_db
def test_le_prompt_du_check_initial_contient_la_fiche_redigee() -> None:
    """Le relecteur doit lire la fiche, sinon il juge a l'aveugle."""
    job, fiche = _make_job_avec_fiche()
    bloc = BLOCS_PAR_IDENTIFIANT["INITIAL"]

    prompt = _construire_prompt_check(bloc, job, [fiche])

    assert _FICHE_MARQUEUR in prompt, "La fiche projet n'est pas dans le prompt."
    assert "FICHE PROJET REDIGEE — document a valider" in prompt
    # Le cadrage qui empeche de reclamer une donnee deja presente.
    assert "Ne demande pas de collecter une donnee qui y figure deja" in prompt


@pytest.mark.django_db
def test_le_hook_transmet_bien_le_chapitre_0_au_check() -> None:
    """Garde-fou sur le point de branchement : le hook ne doit plus passer [].

    C'est la ligne exacte qui a produit le faux positif en production.
    """
    from generation.runner import _after_chapter_hook

    job, fiche = _make_job_avec_fiche()
    captures: list[list] = []

    def _capture(job_, bloc_, chapitres_, **_kwargs):
        captures.append(list(chapitres_))
        from generation.checks_blocs import CheckResult
        return CheckResult(bloc_identifiant=bloc_.identifiant, verdict="pass")

    with patch("generation.runner.check_bloc", side_effect=_capture):
        _after_chapter_hook(job, fiche, client=None)

    assert captures, "Le CHECK INITIAL n'a pas ete declenche apres la fiche."
    assert [c.chapter_number for c in captures[0]] == [0], (
        "Le CHECK INITIAL doit recevoir le chapitre 0 (la fiche redigee)."
    )


@pytest.mark.django_db
def test_les_checks_de_bloc_gardent_leur_intitule_de_chapitres() -> None:
    """Le renommage de section ne concerne QUE le CHECK INITIAL.

    Les CHECK 1-9 continuent de lire « CHAPITRES DU BLOC » et « FICHE PROJET —
    donnees client verrouillees » : leurs questions du manuel s'y referent.
    """
    job, fiche = _make_job_avec_fiche()
    bloc_a = BLOCS_PAR_IDENTIFIANT["A"]

    prompt = _construire_prompt_check(bloc_a, job, [])

    assert "## CHAPITRES DU BLOC" in prompt
    assert "## FICHE PROJET — donnees client verrouillees" in prompt
    assert "CADRAGE DU CHECK INITIAL" not in prompt
