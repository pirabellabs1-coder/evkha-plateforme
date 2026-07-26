"""Tache #11 — cache Anthropic compte, deux breakpoints, thinking uniforme.

Trois defauts couverts, tous issus de la relecture des docs Anthropic
(« Prompt caching », juillet 2026) :

1. `usage.input_tokens` EXCLUT les tokens caches. Le Cost Engine ne voyait donc
   ni les ecritures (200 %) ni les lectures (10 %) de cache : sur un job EM,
   ~5 000 tokens de system prompt par appel manquaient au calcul, et le
   throttle de `max_tokens` raisonnait sur un chiffre faux.
2. Un seul breakpoint de cache : changer de pays invalidait la charte et le
   role, identiques pour tous les clients.
3. Le thinking doit etre uniforme sur tout le job — le basculer invalide le
   cache system + messages et re-paie une ecriture a 200 %.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.cost import max_tokens_for_job
from generation.models import GenerationJob
from generation.prompts import build_system_prompt
from integrations.claude import (
    SYSTEM_CACHE_BREAK,
    _cacheable_system,
    _input_facturable,
    _thinking_budget,
)
from orders.models import Order


class _Usage:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# ── 1. Comptage du cache ─────────────────────────────────────────────────────


def test_input_facturable_compte_lecriture_de_cache_a_200_pct():
    usage = _Usage(
        input_tokens=100,
        cache_creation_input_tokens=1000,
        cache_read_input_tokens=0,
    )
    facturable, ecritures, lectures = _input_facturable(usage)
    assert facturable == 100 + 2000
    assert (ecritures, lectures) == (1000, 0)


def test_input_facturable_compte_la_lecture_de_cache_a_10_pct():
    usage = _Usage(
        input_tokens=100,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=5000,
    )
    facturable, ecritures, lectures = _input_facturable(usage)
    assert facturable == 100 + 500
    assert (ecritures, lectures) == (0, 5000)


def test_input_facturable_distingue_les_ttl_quand_le_sdk_les_expose():
    usage = _Usage(
        input_tokens=0,
        cache_creation_input_tokens=2000,
        cache_read_input_tokens=0,
        cache_creation=_Usage(
            ephemeral_1h_input_tokens=1000,
            ephemeral_5m_input_tokens=1000,
        ),
    )
    facturable, ecritures, _ = _input_facturable(usage)
    assert facturable == 1000 * 2 + 1000 * 1.25  # 3250
    assert ecritures == 2000


def test_input_facturable_tolere_un_sdk_sans_champs_de_cache():
    """Le defaut historique : ces champs absents ne doivent pas lever."""
    facturable, ecritures, lectures = _input_facturable(_Usage(input_tokens=42))
    assert (facturable, ecritures, lectures) == (42, 0, 0)


# ── 2. Deux breakpoints ──────────────────────────────────────────────────────


def test_system_prompt_porte_le_marqueur_de_coupure():
    prompt = build_system_prompt(
        DeliverableType.MARKET_STUDY, country="France", plan="PLAN PHASE 0"
    )
    assert SYSTEM_CACHE_BREAK in prompt
    stable, _, par_job = prompt.partition(SYSTEM_CACHE_BREAK)
    # Le pays et le plan — tout ce qui varie d'un job a l'autre — sont APRES
    # la coupure, sinon le prefixe stable ne serait pas reutilisable.
    assert "PLAN PHASE 0" in par_job
    assert "PLAN PHASE 0" not in stable


def test_le_prefixe_stable_est_identique_quel_que_soit_le_pays():
    france = build_system_prompt(DeliverableType.MARKET_STUDY, country="France", plan="A")
    senegal = build_system_prompt(DeliverableType.MARKET_STUDY, country="Senegal", plan="B")
    assert france.partition(SYSTEM_CACHE_BREAK)[0] == senegal.partition(SYSTEM_CACHE_BREAK)[0]


def test_cacheable_system_emet_deux_blocs_caches():
    blocs = _cacheable_system("STABLE" + SYSTEM_CACHE_BREAK + "PAR_JOB")
    assert isinstance(blocs, list)
    assert len(blocs) == 2
    assert [b["text"] for b in blocs] == ["STABLE", "PAR_JOB"]
    for bloc in blocs:
        assert bloc["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_le_marqueur_ne_part_jamais_vers_le_modele():
    for bloc in _cacheable_system("A" + SYSTEM_CACHE_BREAK + "B"):
        assert "EVKHA_CACHE_BREAK" not in str(bloc["text"])


def test_cacheable_system_reste_a_un_bloc_sans_marqueur():
    """Les CHECKs inter-blocs construisent leur propre system prompt."""
    blocs = _cacheable_system("RELECTEUR EVKHA ...")
    assert isinstance(blocs, list)
    assert len(blocs) == 1


def test_system_prompt_sans_partie_variable_na_pas_de_marqueur():
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)
    assert SYSTEM_CACHE_BREAK not in prompt


def test_le_marqueur_est_un_token_interdit_du_gate():
    """Filet : si un appelant contourne `_cacheable_system`, le gate bloque."""
    from generation.internal_labels import INTERNAL_LABEL_NAMES

    assert "EVKHA_CACHE_BREAK" in INTERNAL_LABEL_NAMES


# ── 3. Thinking uniforme et budgete ──────────────────────────────────────────


@override_settings(EVKHA_THINKING_BUDGET_TOKENS=1024)
def test_thinking_actif_par_defaut():
    assert _thinking_budget() == 1024


@override_settings(EVKHA_THINKING_BUDGET_TOKENS=512)
def test_thinking_sous_le_minimum_api_est_desactive():
    """L'API refuse budget_tokens < 1024 : mieux vaut off que 400."""
    assert _thinking_budget() == 0


@override_settings(EVKHA_THINKING_BUDGET_TOKENS=0)
def test_thinking_desactivable():
    assert _thinking_budget() == 0


@pytest.fixture
def em_job() -> GenerationJob:
    offer = Offer.objects.create(
        name="EM cache", slug="em-cache",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="cache@b.c")
    order = Order.objects.create(systeme_order_id="o-cache", customer=customer, offer=offer)
    return GenerationJob.objects.create(
        order=order,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("4.0000"),
    )


@pytest.mark.django_db
def test_le_throttle_provisionne_le_cout_de_la_reflexion(em_job: GenerationJob) -> None:
    """Sans provision, le job meurt sur CostBudgetExceededError vers 90 %."""
    with override_settings(EVKHA_THINKING_BUDGET_TOKENS=0):
        sans = max_tokens_for_job(em_job, default_max_tokens=8192, call_count=12)
    with override_settings(EVKHA_THINKING_BUDGET_TOKENS=1024):
        avec = max_tokens_for_job(em_job, default_max_tokens=8192, call_count=12)
    assert avec < sans


def test_budget_em_releve_pour_absorber_la_reflexion() -> None:
    """3,05 EUR mesures (run 010e3bf2) + 0,41 de thinking > l'ancien 3,20."""
    from generation.services import _BUDGET_EUR_BY_TYPE

    assert _BUDGET_EUR_BY_TYPE[DeliverableType.MARKET_STUDY] >= Decimal("4.0000")
