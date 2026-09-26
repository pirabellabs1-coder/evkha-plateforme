"""Après une correction, le client télécharge le document CORRIGÉ — pas l'ancien.

Audit de la boucle de correction, 26/09/2026. `recontroler_et_corriger_task`
réécrivait les chapitres fautifs, rejouait le gate, écrivait PASSED — et
s'arrêtait là. Les artefacts Word et PDF de l'espace client restaient ceux
d'avant : un document non corrigé, servi sous un verdict vert. C'est la règle 3
du dépôt (ce qui est refait après le contrôle se contrôle), dans sa forme la
plus trompeuse.

Le correctif appelle `assembler_sans_envoyer` — même assemblage et même contrôle
du fichier que la livraison, sans courriel : « Renvoyer » reste une décision
humaine. Ce test remplace les trois collaborateurs de la tâche par des doublures
et vérifie que l'assemblage est demandé pour le dossier, verdict vert ou non.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation import tasks
from generation.models import GenerationJob, QAStatus
from orders.models import Order


@pytest.fixture
def job(db: Any) -> GenerationJob:
    offre = Offer.objects.create(
        name="BP", slug="bp-reassemble", deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email="reassemble@test.local")
    commande = Order.objects.create(systeme_order_id="cmd-reassemble", customer=client, offer=offre)
    return GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN,
        budget_eur=Decimal("8.0000"),
    )


def _rapport(passed: bool) -> SimpleNamespace:
    return SimpleNamespace(passed=passed, as_details=lambda: {"passed": passed})


@pytest.mark.parametrize("passe", [True, False], ids=["verdict-vert", "verdict-bloque"])
def test_la_correction_reassemble_les_artefacts(
    job: GenerationJob, monkeypatch: pytest.MonkeyPatch, passe: bool,
) -> None:
    import delivery.services as livraison
    import generation.checks_blocs as blocs
    import generation.correction as correction
    import generation.gate as gate

    assembles: list[GenerationJob] = []
    monkeypatch.setattr(correction, "run_correction_loop", lambda j, **_: _rapport(passe))
    monkeypatch.setattr(blocs, "rejouer_les_checks_ouverts", lambda j: [])
    monkeypatch.setattr(gate, "run_delivery_gate", lambda j: _rapport(passe))
    monkeypatch.setattr(livraison, "assembler_sans_envoyer", lambda j: assembles.append(j))

    resultat = tasks._corriger_et_juger(job)

    assert assembles == [job], "les artefacts téléchargeables doivent être refaits"
    job.refresh_from_db()
    assert job.qa_status == (QAStatus.PASSED if passe else QAStatus.BLOCKED)
    assert resultat.endswith(str(job.qa_status))
