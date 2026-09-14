"""Une réponse libre du client ne prête pas tous ses montants à un seul fait.

## Le défaut mesuré

Corpus du 14/09/2026, business plans `256e63d8`, `1fdc457b`, `9f8f144a` : à la
question « apport », la cliente a répondu par un paragraphe — financements
recherchés, charges fixes, rémunération des trois années, une enveloppe de
sécurité, et « 1600e ont déjà été investis dans la plateforme ».

Le contrôle de cohérence prenait TOUS ces montants pour l'apport. Le document
écrivait « apport personnel de 1 600 € », exactement ce qu'elle avait dit, et
recevait : « le brief client dit » suivi du paragraphe entier. Motif faux
(règle 2), routé vers une réécriture payée qui ne pouvait pas le fermer.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.gate import _check_numeric_coherence
from generation.models import FactKind, FactProvenance
from generation.rendering import RenderedSection

#: La forme de la réponse réelle, recomposée sans les données de la cliente.
REPONSE_LIBRE = (
    "Financements recherchés : prioritairement subventions et aides à la "
    "création.\nCharges fixes actuelles :\nenviron 200 €/mois de logiciels ;\n"
    "environ 200 €/mois d'expert-comptable ;\nsoit environ 400 €/mois de charges "
    "fixes courantes.\nRémunération envisagée :\nAnnée 1 : 1 000 €/mois "
    "Année 2 : 1 300 €/mois Année 3 : 1 800 €/mois\nUne enveloppe de 8 000 € "
    "est prévue pour sécuriser les six premiers mois."
)


def _job(db: Any, apport: str) -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(
        name="BP", slug="bp", deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email="apport@example.com")
    order = Order.objects.create(systeme_order_id="o_apport", customer=customer, offer=offer)
    job = GenerationJob.objects.create(
        order=order, deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    job.coherence_facts.create(
        kind=FactKind.ASSUMPTION, key="apport", value=apport,
        is_locked=True, provenance=FactProvenance.CLIENT,
    )
    return job


def _motifs(job: Any, texte: str) -> list[tuple[str, int | None]]:
    section = RenderedSection(number=15, title="Financement", kind="chapter", body=texte)
    return [(f.check, f.chapter_number) for f in _check_numeric_coherence(job, (section,))]


@pytest.mark.django_db
def test_le_montant_que_la_cliente_a_ecrit_n_est_pas_une_contradiction(db: Any) -> None:
    """`256e63d8` : « 1600e ont déjà été investis » — le document dit 1 600 €."""
    job = _job(db, REPONSE_LIBRE + " 1600e ont déjà été investis dans la plateforme.")
    assert _motifs(job, "L'apport personnel de 1 600 € finance le prototype.") == []


@pytest.mark.django_db
def test_une_faute_de_frappe_ne_fait_pas_accuser_le_document(db: Any) -> None:
    """`1fdc457b` : « evkha a déjà invetsi 1600e » — le mot attendu manque."""
    job = _job(db, REPONSE_LIBRE + " La société a déjà invetsi 1600e dans le logiciel.")
    assert _motifs(job, "L'apport personnel de 1 600 € finance le prototype.") == []


@pytest.mark.django_db
def test_sans_apport_dans_la_reponse_on_dit_qu_il_manque_sans_reecrire(db: Any) -> None:
    """`9f8f144a` : aucun apport dans la réponse. Rien n'est CONTREDIT.

    Le motif dit ce qui manque, une seule fois, et sans chapitre : aucune
    réécriture ne fera apparaître un chiffre que le client n'a pas donné.
    """
    job = _job(db, REPONSE_LIBRE)
    motifs = _motifs(
        job,
        "L'apport personnel de 1 600 € finance le prototype. Un apport de 1 600 € "
        "est retenu.",
    )
    assert motifs == [("reference_client_illisible", None)]


@pytest.mark.django_db
def test_la_phrase_qui_parle_de_l_apport_reste_jugee_en_tolerance_zero(db: Any) -> None:
    """CONTRE-ÉPREUVE : la réponse libre donne l'apport, le document en écrit un autre."""
    job = _job(db, REPONSE_LIBRE + " Mon apport personnel sera de 5 000 €.")
    assert _motifs(job, "L'apport personnel de 8 000 € finance le prototype.") == [
        ("coherence_chiffree", 15),
    ], "8 000 € est dans la réponse, mais c'est l'enveloppe, pas l'apport"


@pytest.mark.django_db
def test_une_reponse_simple_reste_jugee_comme_avant(db: Any) -> None:
    """CONTRE-ÉPREUVE : « 25 000 € » n'est pas une réponse libre."""
    job = _job(db, "25 000 €")
    assert _motifs(job, "L'apport personnel de 20 000 € finance le prototype.") == [
        ("coherence_chiffree", 15),
    ]
