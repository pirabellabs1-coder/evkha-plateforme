"""Une reprise se paie sur le SURPLUS du budget — le dossier va au bout sous son plafond.

Reprise ÉCLORE `bf98827c` (29/09/2026) : 32 reprises payées sans que rien ne
demande s'il resterait de quoi écrire la suite ; le plafond a coupé le dossier
au chapitre 16 sur 22. Désormais, sans surplus une fois réservés les chapitres
à écrire, l'essai en cours est déclaré dernier : le chapitre est accepté avec
ses replis au lieu d'être réécrit.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres import services
from generation.cost import cout_estime_d_un_chapitre, reprise_financable
from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

pytestmark = pytest.mark.django_db


def _dossier(suffixe: str) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="bp-surplus",
        defaults={"name": "BP", "deliverable_type": DeliverableType.BUSINESS_PLAN},
    )
    client = Customer.objects.create(email=f"surplus-{suffixe}@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id=f"surplus-{suffixe}", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "x", "PAYS": "France", "ZONE": "Lyon", "PROJET": "T"},
    )
    with override_settings(EVKHA_ANTHROPIC_MODEL_ID="claude-sonnet-5"):
        return bootstrap_generation_job(soumission)


def _depenser(job: GenerationJob, montant: str) -> None:
    """La recherche et les premiers chapitres ont déjà coûté `montant` (chapitre 0)."""
    ChapterGeneration.objects.filter(job=job, chapter_number=0).update(
        cost_eur=Decimal(montant), status=ChapterStatus.DONE,
    )


def _capter(appels: list[Any]) -> Any:
    """Un `produire_chapitre` qui note ce qu'on lui dit de la dernière tentative."""
    def produire(*_a: Any, **k: Any) -> object:
        appels.append(k.get("derniere_tentative"))
        return object()
    return produire


def test_au_depart_une_reprise_est_financable() -> None:
    job = _dossier("a")
    assert reprise_financable(job)


def test_quand_le_budget_ne_couvre_plus_la_suite_la_reprise_ne_l_est_plus() -> None:
    """Plafond 8 € : 7,50 € dépensés, 21 chapitres à écrire — la reprise attendra."""
    job = _dossier("b")
    _depenser(job, "7.50")
    assert not reprise_financable(job)


def test_le_cout_d_un_chapitre_suit_ceux_deja_ecrits() -> None:
    """Contre-épreuve : l'estimation n'est pas figée, elle apprend du dossier."""
    job = _dossier("c")
    ChapterGeneration.objects.filter(job=job, chapter_number__in=[1, 2]).update(
        cost_eur=Decimal("0.1000"), status=ChapterStatus.DONE,
    )
    assert cout_estime_d_un_chapitre(job) == Decimal("0.1000") * Decimal("1.5")


def test_sans_surplus_le_premier_essai_est_le_dernier(monkeypatch: pytest.MonkeyPatch) -> None:
    job = _dossier("d")
    appels: list[Any] = []
    monkeypatch.setattr("generation.cost.reprise_financable", lambda _job: False)
    monkeypatch.setattr(services, "produire_chapitre", _capter(appels))

    services.produire_avec_reprises(job, 3, client=None)

    assert appels == [True], "sans surplus, le premier essai est déclaré dernier"


def test_avec_surplus_le_premier_essai_garde_sa_reprise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contre-épreuve : quand le budget le permet, rien ne change."""
    job = _dossier("e")
    appels: list[Any] = []
    monkeypatch.setattr("generation.cost.reprise_financable", lambda _job: True)
    monkeypatch.setattr(services, "produire_chapitre", _capter(appels))

    services.produire_avec_reprises(job, 3, client=None)

    assert appels == [False]
