"""Une generation ne depasse jamais le plafond fixe par la cliente.

**Decision du 08/08/2026**, qui remplace le plafond unique de 3,10 EUR arrete le
05/08 : le prix d'un livrable depend de ce qu'il demande. Etude de marche 8,00,
business plan 4,00, strategie 4,00, etude concurrentielle 3,50.

L'etude de marche est passee de 6,00 a 8,00 le meme jour, sur MESURE : le
dossier reel `b561c2d6` a ete coupe par ce garde-fou a 22 chapitres sur 23,
pour 5,94 EUR. Le plafond a bien fonctionne — il a stoppe net — mais il etait
pose trop bas d'un chapitre.

## Ce que la revision a mis au jour

Le plafond unique etait porte par QUATRE endroits, et deux se contredisaient :

  - `cost.PLAFOND_DEPENSE_EUR`, a 3,10 ;
  - `settings.EVKHA_PLAFOND_DEPENSE_EUR`, avec un DEFAUT a « 3.10 » — donc le
    << frein d'urgence >> etait serre en permanence, et le plafond par livrable
    n'etait jamais atteint ;
  - `services._BUDGET_EUR_BY_TYPE`, le rythme, a 4,00 pour l'etude de marche ;
  - ce test, qui verrouillait 3,10.

Le regulateur cadencait donc vers 4,00 pendant que le frein coupait a 3,10 : il
allouait genereusement, puis le dossier etait tranche avant la fin. Et qui
lisait la table des rythmes croyait qu'une etude de marche pouvait couter 4,00.

Une seule table porte desormais les deux roles : `cost.PLAFOND_PAR_LIVRABLE`,
que `services._BUDGET_EUR_BY_TYPE` RELIT au lieu de la recopier.

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
    PLAFOND_PAR_LIVRABLE,
    PLAFOND_REPLI_EUR,
    CostBudgetExceededError,
    enforce_budget,
    plafond_de_depense,
)
from generation.services import _BUDGET_EUR_BY_TYPE

#: Les quatre montants arretes par la cliente le 08/08/2026, RECOPIES a dessein.
#: Un test qui relit la table qu'il verifie ne verifie rien : c'est le seul
#: doublon voulu du depot, et c'est sa raison d'etre.
DECISION_CLIENTE = {
    DeliverableType.MARKET_STUDY: Decimal("8.00"),
    DeliverableType.BUSINESS_PLAN: Decimal("4.00"),
    DeliverableType.BUSINESS_STRATEGY: Decimal("5.50"),
    DeliverableType.COMPETITOR_STUDY: Decimal("3.50"),
}


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


@pytest.mark.parametrize(("livrable", "montant"), sorted(DECISION_CLIENTE.items()))
def test_la_table_porte_la_decision_de_la_cliente(
    livrable: str, montant: Decimal
) -> None:
    assert PLAFOND_PAR_LIVRABLE[livrable] == montant


def test_le_rythme_et_le_plafond_sont_la_meme_table() -> None:
    """Deux tables aux memes nombres auraient diverge au premier ajustement.

    On verifie l'IDENTITE, pas l'egalite : deux dictionnaires egaux aujourd'hui
    peuvent cesser de l'etre demain sans qu'aucun test ne tombe.
    """
    assert _BUDGET_EUR_BY_TYPE is PLAFOND_PAR_LIVRABLE


@pytest.mark.django_db
@pytest.mark.parametrize(("livrable", "montant"), sorted(DECISION_CLIENTE.items()))
def test_le_plafond_applique_est_celui_du_livrable(
    livrable: str, montant: Decimal, job_em: Any
) -> None:
    """Ce que le garde-fou applique vraiment, et non ce que la table declare.

    C'est `plafond_de_depense` que `enforce_budget` interroge. Verifier la table
    seule laisserait passer une regression entre les deux — et c'est exactement
    ce qui s'etait produit : la table disait 4,00 et le frein coupait a 3,10.
    """
    job_em.deliverable_type = livrable
    job_em.budget_eur = montant

    assert plafond_de_depense(job_em) == montant


@pytest.mark.django_db
def test_une_etude_est_stoppee_a_son_plafond(job_em: Any) -> None:
    """L'arret est net, et il tombe au bon montant."""
    plafond = DECISION_CLIENTE[DeliverableType.MARKET_STUDY]
    job_em.budget_eur = plafond

    enforce_budget(job_em, current_total=plafond - Decimal("0.10"))  # ne leve pas

    with pytest.raises(CostBudgetExceededError, match="Plafond de depense"):
        enforce_budget(job_em, current_total=plafond + Decimal("0.10"))


@pytest.mark.django_db
def test_le_plus_contraignant_des_deux_l_emporte(job_em: Any) -> None:
    """Un budget de job abaisse a la main ne doit pas etre releve par la table.

    Contre-epreuve : le plafond d'un livrable ne doit jamais AUTORISER a
    depenser davantage que ce que le dossier lui-meme s'est vu accorder —
    reprise partielle, dossier de test.
    """
    job_em.budget_eur = Decimal("2.6000")
    assert plafond_de_depense(job_em) == Decimal("2.6000")

    with pytest.raises(CostBudgetExceededError):
        enforce_budget(job_em, current_total=Decimal("2.7000"))


@pytest.mark.django_db
def test_un_livrable_inconnu_tombe_sur_le_plafond_le_plus_BAS(job_em: Any) -> None:
    """Un livrable non budgete ne doit pas heriter du plafond le plus genereux.

    Il s'arrete tot, ouvre un incident, et le manque se voit. L'inverse
    depenserait en silence — et c'est le silence qu'on refuse (regle 1).
    """
    job_em.deliverable_type = "livrable_qui_n_existe_pas"

    assert plafond_de_depense(job_em) == PLAFOND_REPLI_EUR
    assert PLAFOND_REPLI_EUR == min(DECISION_CLIENTE.values())


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
