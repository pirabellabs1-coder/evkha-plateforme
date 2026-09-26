"""Le contrôle « IS à 15 % sur 42 500 € » est le Code général des impôts FRANÇAIS.

Business plan `6c794b18` (26/09/2026, société suisse, montants en CHF) : deux
motifs de la stratégie BP, tous deux faux pour ce dossier —

- `is_bracket` : « IS à 15 % mentionné sans préciser le plafond légal de
  42 500 EUR » — un plafond qui ne concerne pas une société de droit suisse ;
- `remuneration_dirigeant` : « mentionnée mais sans montant chiffré », alors
  que le montant était écrit « CHF 6'500 par mois » — la regex locale ne
  connaissait que EUR, € et k€.

La devise verrouillée du dossier dit où l'on est ; hors euro, le CGI n'a rien
à juger. Et le montant se lit avec le parseur canonique (règle 5).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.coherence import upsert_locked_fact
from generation.models import FactKind, FactProvenance, GenerationJob
from generation.strategies.bp import BPStrategy
from orders.models import Order

CORPUS = {
    7: "La fondatrice percevra une rémunération de CHF 6'500 par mois dès l'an 1.",
    14: "Le prévisionnel retient un IS à 15 % sur tout le bénéfice de 60 000 CHF.",
}


def _job(db: Any, devise: str | None) -> GenerationJob:
    offre = Offer.objects.create(
        name="BP", slug=f"bp-{devise or 'sans'}", deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email=f"bp-{devise or 'sans'}@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-bp-{devise or 'sans'}", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN,
        budget_eur=Decimal("8.0000"),
    )
    if devise:
        upsert_locked_fact(
            job=job, kind=FactKind.CURRENCY, key="currency", value=devise,
            provenance=FactProvenance.CLIENT,
        )
    return job


@pytest.mark.django_db
def test_un_dossier_en_chf_ignore_le_plafond_francais(db: Any) -> None:
    problemes = BPStrategy().problemes_de_coherence(_job(db, "CHF"), CORPUS)
    assert [p.categorie for p in problemes] == []


@pytest.mark.django_db
def test_un_dossier_en_euros_y_reste_soumis(db: Any) -> None:
    """Contre-épreuve : le contrôle n'a pas disparu, il a trouvé sa juridiction."""
    problemes = BPStrategy().problemes_de_coherence(_job(db, "EUR"), CORPUS)
    assert "is_bracket" in {p.categorie for p in problemes}


@pytest.mark.django_db
def test_sans_devise_connue_on_suppose_la_france(db: Any) -> None:
    problemes = BPStrategy().problemes_de_coherence(_job(db, None), CORPUS)
    assert "is_bracket" in {p.categorie for p in problemes}


def test_une_remuneration_en_francs_suisses_est_chiffree() -> None:
    from generation.strategies.bp import verifier_remuneration_dirigeant

    assert verifier_remuneration_dirigeant({7: CORPUS[7]}) == []
    assert verifier_remuneration_dirigeant(
        {7: "La fondatrice percevra une rémunération raisonnable dès l'an 1."}
    ) != []
