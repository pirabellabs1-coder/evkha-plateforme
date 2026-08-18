"""Une relance releve le budget vers la table, et ne le baisse jamais.

## Le defaut, mesure

Business plan `256e63d8`, 17/08/2026 : arrete a 21 chapitres sur 22 au plafond
de 6,50 EUR. Le chapitre 02 n'a jamais ete ecrit, et le sommaire livre a la
cliente saute de « 01 Résumé exécutif » a « 03 Genèse du projet ».

La cliente releve le plafond a 8,00 EUR le lendemain. Mais le montant est grave
dans la LIGNE du dossier a sa creation, et `relaunch_generation_job` refusait de
le relever — precisement parce que le dossier avait ecrit des chapitres.

Le dossier ne pouvait donc plus JAMAIS finir : une relance echouait dans la
seconde, 6,66 EUR depenses contre 6,50 autorises.

La seule categorie de dossiers qu'un relevement de plafond devait sauver etait
exactement celle qu'il n'atteignait pas.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from catalog.models import DeliverableType
from generation.models import ChapterStatus, JobStatus


def _dossier(slug: str, budget: str, avec_chapitre_ecrit: bool):
    from catalog.models import Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, GenerationJob
    from orders.models import Order

    offre = Offer.objects.create(
        name="BP", slug=slug, deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email=f"{slug}@test.local")
    commande = Order.objects.create(
        systeme_order_id=slug, customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        status=JobStatus.FAILED,
        budget_eur=Decimal(budget),
        total_cost_eur=Decimal("6.6619"),
    )
    ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Résumé", prompt_key="bp.01",
        status=ChapterStatus.DONE if avec_chapitre_ecrit else ChapterStatus.PENDING,
    )
    return job


@pytest.mark.django_db
def test_un_dossier_ecrit_voit_son_budget_releve() -> None:
    """LE cas de la cliente. Echoue sur le code d'avant.

    21 chapitres ecrits, budget grave a 6,50, table a 8,00 : sans ce correctif
    la relance laissait 6,50 et le dossier echouait immediatement.
    """
    from generation.services import relaunch_generation_job

    job = _dossier("relance-ecrit", "6.50", avec_chapitre_ecrit=True)
    relaunch_generation_job(job)

    job.refresh_from_db()
    assert job.budget_eur == Decimal("8.0000")
    assert job.status == JobStatus.PENDING


@pytest.mark.django_db
def test_un_dossier_ecrit_ne_voit_jamais_son_budget_baisser() -> None:
    """Contre-epreuve : la protection d'origine tient.

    Un dossier dote d'un budget SUPERIEUR a la table — releve a la main pour un
    cas particulier — ne doit pas se faire rabaisser sous sa depense engagee.
    """
    from generation.services import relaunch_generation_job

    job = _dossier("relance-genereux", "12.00", avec_chapitre_ecrit=True)
    relaunch_generation_job(job)

    job.refresh_from_db()
    assert job.budget_eur == Decimal("12.0000")


@pytest.mark.django_db
def test_un_dossier_vierge_est_recale_sur_la_table() -> None:
    """Contre-epreuve : le comportement d'origine sur un dossier sans chapitre."""
    from generation.services import relaunch_generation_job

    job = _dossier("relance-vierge", "12.00", avec_chapitre_ecrit=False)
    relaunch_generation_job(job)

    job.refresh_from_db()
    assert job.budget_eur == Decimal("8.0000")
