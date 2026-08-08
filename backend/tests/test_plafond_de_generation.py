"""Une generation ne depasse jamais le plafond fixe par la cliente.

Decision du 05/08/2026, releve de la console Anthropic a l'appui — 44,26 $US de
credits restants, rechargement automatique actif : « on ne doit pas depasser
3 euros pour une generation, ou 3,1 au max ».

## Le piege, et il a failli me faire livrer l'inverse

`budget_eur` servait A LA FOIS de rythme et de plafond. Poser 3,00 EUR dedans
paraissait etre la reponse evidente. Mesure faite AVANT de livrer, sur le vrai
`max_tokens_for_job` :

       budget    max_tokens 1er appel
      2,60 EUR                   2500   <- plancher
      3,00 EUR                   2500   <- plancher
      3,10 EUR                   2500   <- plancher
      3,70 EUR                   2500   <- plancher
      3,80 EUR                   2528   ok
      4,00 EUR                   2707   ok

Le throttle repartit le budget RESTANT sur les appels a venir : le baisser ne
fait pas baisser la depense, il RETRECIT chaque chapitre. Sous 3,80 EUR, le
premier appel d'une etude de marche est deja borne au plancher — alors que ses
chapitres consomment environ 3 000 jetons de sortie. Poser 3,00 EUR n'aurait
donc pas coute 3,00 EUR : cela aurait produit vingt-trois chapitres rabotes,
c'est-a-dire le defaut meme que la cliente signale depuis le debut.

Les deux roles sont donc separes : le RYTHME reste dimensionne sur le travail a
faire, le PLAFOND DE DEPENSE est une decision commerciale et coupe en dur.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from catalog.models import DeliverableType
from generation.cost import (
    PLAFOND_DEPENSE_EUR,
    CostBudgetExceededError,
    enforce_budget,
    plafond_de_depense,
)
from generation.services import _BUDGET_EUR_BY_TYPE

_MAXIMUM_TOLERE = Decimal("3.1000")


@pytest.fixture
def job_em() -> Any:
    from catalog.models import Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from orders.models import Order

    offre = Offer.objects.create(
        name="EM", slug="test-plafond", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="plafond@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-plafond", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=_BUDGET_EUR_BY_TYPE[DeliverableType.MARKET_STUDY],
    )


def test_le_plafond_respecte_la_consigne() -> None:
    assert PLAFOND_DEPENSE_EUR <= _MAXIMUM_TOLERE


@pytest.mark.django_db
def test_une_etude_est_stoppee_au_plafond(job_em: Any) -> None:
    """Sur le code d'avant, l'arret n'avait lieu qu'a 6,00 EUR.

    Le budget de rythme vaut 4,00 : sans plafond distinct, une etude aurait pu
    depenser 4,00 EUR sans que rien ne l'arrete.
    """
    assert job_em.budget_eur > _MAXIMUM_TOLERE

    enforce_budget(job_em, current_total=Decimal("3.0000"))  # ne doit pas lever

    with pytest.raises(CostBudgetExceededError, match="Plafond de depense"):
        enforce_budget(job_em, current_total=Decimal("3.2000"))


@pytest.mark.django_db
def test_le_plus_contraignant_des_deux_l_emporte(job_em: Any) -> None:
    """L'etude concurrentielle a un rythme de 2,60 : c'est LUI qui doit primer.

    Contre-epreuve : un plafond commercial a 3,10 ne doit pas AUTORISER a
    depenser davantage sur le livrable le plus sobre.
    """
    job_em.budget_eur = Decimal("2.6000")
    assert plafond_de_depense(job_em) == Decimal("2.6000")

    with pytest.raises(CostBudgetExceededError):
        enforce_budget(job_em, current_total=Decimal("2.7000"))


@pytest.mark.django_db
def test_le_plafond_se_regle_sans_redeploiement(job_em: Any, settings: Any) -> None:
    """La contrainte est commerciale : elle bougera, et pas au rythme des commits."""
    settings.EVKHA_PLAFOND_DEPENSE_EUR = "1.50"

    assert plafond_de_depense(job_em) == Decimal("1.50")
    with pytest.raises(CostBudgetExceededError):
        enforce_budget(job_em, current_total=Decimal("1.60"))


def test_le_rythme_reste_au_dessus_du_seuil_d_etranglement() -> None:
    """Mesure du 05/08/2026 : sous 3,80 EUR, tous les chapitres sont rabotes.

    Ce test échouerait sur un budget de rythme posé à 3,00 — c'est-à-dire sur
    la correction « évidente » que la mesure a écartée.
    """
    seuil_mesure = Decimal("3.8000")
    assert _BUDGET_EUR_BY_TYPE[DeliverableType.MARKET_STUDY] >= seuil_mesure


def test_les_quatre_livrables_ont_un_rythme() -> None:
    """Un livrable oublié n'aurait aucun garde-fou de rythme."""
    assert set(_BUDGET_EUR_BY_TYPE) == set(DeliverableType.values)
