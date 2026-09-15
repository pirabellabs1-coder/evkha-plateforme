"""Le gate juge le texte que le client lit — pas la fiche projet interne.

## Le défaut mesuré

Génération de preuve `7567ca2f` (15/09/2026, reprise du business plan
`8bda1173`). Le gate déclarait le chapitre 0 « tronqué » :

    Chapitre « Fiche projet » tronque : la derniere ligne ne se termine pas
    par une ponctuation forte. Fin capturee : « ...éments futurs de revenus :
    montants non définis, provisoires ».

Or la fiche projet n'est pas imprimée dans le Word (`pour_le_client`) : relu
dans le document livré, aucune de ces lignes n'y figure. Le corpus du
15/09/2026 comptait aussi des fourchettes du chapitre 0 (`b8da2640`,
`5c5e91b9`, `d667fbb4`). Des motifs sur un texte que personne ne lira, qui
bloquaient l'envoi et faisaient réécrire la fiche à nos frais (règles 2 et 3).

Et un faux motif de cohérence, relu dans le même document : « les 4 800 € de
charges fixes annuelles représentent 8,8 % du chiffre d'affaires prévisionnel
de l'année 1 (4 800 € sur 54 276 €) » opposait 4 800 € au chiffre d'affaires.

## Ce qui ne change pas

Le chapitre 0 doit exister (complétude), et un chapitre IMPRIMÉ reste jugé en
entier : la même ligne tronquée au chapitre 3 reste signalée.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from generation.checks_evangeline import collecter_mentions, detecter_divergences
from generation.gate import run_delivery_gate

FICHE = (
    "## Fiche projet\n\n"
    "Budget de consultation : 100 à 300 €\n"
    "Éléments futurs de revenus : montants non définis, provisoires"
)
TRONQUE = "Le projet repose sur trois moteurs de revenus dont le premier reste le mar"


def _job(slug: str, chapitres: dict[int, str]) -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(
        name="T", slug=slug, deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email=f"{slug}@test.local")
    order = Order.objects.create(systeme_order_id=slug, customer=customer, offer=offer)
    job = GenerationJob.objects.create(
        order=order, deliverable_type=DeliverableType.BUSINESS_PLAN, budget_eur=Decimal("8.00"),
    )
    for numero, contenu in chapitres.items():
        ChapterGeneration.objects.create(
            job=job, chapter_number=numero, chapter_title=f"Chapitre {numero}",
            prompt_key=f"bp.{numero:02d}.test", status=ChapterStatus.DONE, content=contenu,
        )
    return job


def _motifs(job: Any, check: str) -> list[tuple[int | None, str]]:
    return [
        (f.chapter_number, f.detail) for f in run_delivery_gate(job).failures if f.check == check
    ]


@pytest.mark.django_db
def test_la_fiche_projet_interne_n_est_ni_tronquee_ni_en_fourchette() -> None:
    job = _job("fiche", {0: FICHE, 1: "Le résumé du projet tient en une phrase."})
    assert [m for m in _motifs(job, "troncature_rendu") if m[0] == 0] == []
    assert [m for m in _motifs(job, "fourchette_interdite") if m[0] == 0] == []


@pytest.mark.django_db
def test_un_chapitre_imprime_reste_juge_en_entier() -> None:
    """CONTRE-ÉPREUVE : la même fin tronquée au chapitre 3 reste vue."""
    job = _job("imprime", {0: "Fiche.", 3: TRONQUE})
    assert [m for m in _motifs(job, "troncature_rendu") if m[0] == 3] != []


def test_une_part_entre_parentheses_n_est_pas_la_valeur_du_libelle() -> None:
    phrase = (
        "L'ordre de grandeur à retenir est que les 4 800 € de charges fixes annuelles "
        "représentent 8,8 % du chiffre d'affaires prévisionnel de l'année 1 (4 800 € sur "
        "54 276 €), une proportion qui baisse."
    )
    autre = "Le chiffre d'affaires prévisionnel de l'année 1 s'élève à 54 276 €."
    mentions = collecter_mentions(12, phrase) + collecter_mentions(4, autre)
    assert detecter_divergences(mentions) == []
