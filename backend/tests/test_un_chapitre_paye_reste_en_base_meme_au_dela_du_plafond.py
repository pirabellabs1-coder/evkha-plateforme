"""Le chapitre qui fait franchir le plafond a été facturé : il reste en base.

`enforce_budget` le promettait dans sa docstring — « le chapitre qui a déclenché
le dépassement est déjà sauvegardé ». Pour la chaîne structurée, c'était faux :
`enregistrer_chapitre` était `@transaction.atomic` de bout en bout, et
`record_chapter_cost` levait `CostBudgetExceededError` À L'INTÉRIEUR. Django
annulait alors d'un seul coup le chapitre (retour à `RUNNING`, payload perdu),
son coût, ET l'incident « Budget IA dépassé ». L'appel, lui, avait bien été
facturé par Anthropic.

À la relance, le chapitre — toujours `RUNNING` — était regénéré, donc repayé,
puis annulé de nouveau. Relevé par la relecture du 26/09/2026.

Ce test échoue sur le code d'avant (règle 6) : les quatre assertions après
l'exception y sont fausses ensemble.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.schema import BlocParagraphe, ChapitrePayload
from generation.chapitres.services import enregistrer_chapitre
from generation.cost import CostBudgetExceededError
from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
from monitoring.models import OperationalIncident
from orders.models import Order

#: Assez pour franchir un plafond de 1 € en un seul appel.
CONSOMMATION_HORS_PLAFOND = {"input_tokens": 400_000, "output_tokens": 16_000}


@pytest.fixture
def chapitre_en_cours(db: Any) -> ChapterGeneration:
    offre = Offer.objects.create(
        name="EM", slug="plafond-atomique", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="plafond-atomique@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-plafond-atomique", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("1.0000"),
    )
    return ChapterGeneration.objects.create(
        job=job, chapter_number=19, chapter_title="Chapitre d'essai",
        prompt_key="em.19", status=ChapterStatus.RUNNING,
    )


def _payload() -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=19,
        titre="Chapitre d'essai",
        blocs=[BlocParagraphe(texte="Un paragraphe suffisant pour tenir le contrat.")],
        resume="Un résumé d'essai suffisamment long pour tenir sa borne basse.",
    )


def test_le_chapitre_et_son_cout_survivent_au_depassement(
    chapitre_en_cours: ChapterGeneration,
) -> None:
    with pytest.raises(CostBudgetExceededError):
        enregistrer_chapitre(chapitre_en_cours, _payload(), CONSOMMATION_HORS_PLAFOND)

    chapitre_en_cours.refresh_from_db()
    assert chapitre_en_cours.status == ChapterStatus.DONE
    assert chapitre_en_cours.payload, "le payload validé ne doit pas disparaître"
    assert chapitre_en_cours.cost_eur > Decimal("0"), "l'appel facturé figure au grand livre"
    assert OperationalIncident.objects.filter(
        job=chapitre_en_cours.job, title__startswith="Budget IA depasse",
    ).exists(), "l'incident qui explique l'arrêt est écrit"


def test_sous_le_plafond_rien_ne_change(chapitre_en_cours: ChapterGeneration) -> None:
    """Contre-épreuve : le chemin nominal enregistre et ne lève pas."""
    enregistrer_chapitre(
        chapitre_en_cours, _payload(), {"input_tokens": 3_000, "output_tokens": 300},
    )

    chapitre_en_cours.refresh_from_db()
    assert chapitre_en_cours.status == ChapterStatus.DONE
    assert chapitre_en_cours.cost_eur > Decimal("0")
    assert not OperationalIncident.objects.filter(job=chapitre_en_cours.job).exists()
