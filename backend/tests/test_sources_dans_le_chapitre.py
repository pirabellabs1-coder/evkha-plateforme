"""Un chapitre doit recevoir de la matière, pas seulement des chiffres verrouillés.

Défaut mesuré, et cause la plus lourde des redites relevées par la cliente.

Le moteur structuré est celui qui tourne (`EVKHA_SOCLE_ENABLED=true` en
production). Or il ne donnait à chaque chapitre que deux choses : le SOCLE —
**vingt-neuf emplacements de données pour l'étude entière** — et les résumés des
chapitres précédents. Le brief de recherche web, lui, était consommé UNE fois
pour remplir ces vingt-neuf cases, puis jeté : aucun chapitre ne le voyait.

Vingt-et-un chapitres de trois à cinq pages écrits à partir de vingt-neuf
chiffres n'ont rien de neuf à dire passé le troisième. Et le manuel exige « 35 à
60 sources distinctes » au chapitre 21 : avec au plus vingt-neuf données portant
chacune une source, souvent la même, la cible était hors d'atteinte quelle que
soit la qualité de la rédaction.

Ces tests échouent sur le code d'avant : `_bloc_sources` n'existait pas et
`construire_prompt_chapitre` n'assemblait aucun bloc de sources.
"""
from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.configuration import type_document
from generation.chapitres.runner import construire_prompt_chapitre
from generation.models import GenerationJob
from generation.services import bootstrap_generation_job
from generation.socle.services import etablir_socle, socle_verrouille
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order

EM = DeliverableType.MARKET_STUDY

_VARIABLES: dict[str, Any] = {
    "SECTEUR": "coworking",
    "PAYS": "France",
    "ZONE": "Lyon",
    "PROJET": "espace de coworking",
}


@pytest.fixture
def job_em(db: object) -> GenerationJob:
    offer = Offer.objects.create(name="EM", slug="em-sources", deliverable_type=EM)
    customer = Customer.objects.create(email="sources@example.com")
    order = Order.objects.create(
        systeme_order_id="order-sources-01", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED, normalized_variables=_VARIABLES
    )
    job = bootstrap_generation_job(submission)
    etablir_socle(job, client=StubClaudeClient(), variables=_VARIABLES)
    return job


#: Brief au format produit par `collect_research_brief`, réduit à trois axes
#: dont un commun. Écrit à la main : un vrai appel réseau dans la suite la
#: rendrait lente et dépendante de DuckDuckGo.
BRIEF = """SOURCES WEB COLLECTÉES — 4 sources distinctes collectées sur 23 axes.

### AXE licences [chapitres: 6] — coworking France licence activité 2025 2026
- Service-public, obligations d'ouverture
  URL : https://www.service-public.fr/coworking
  Extrait : Déclaration préalable exigée depuis 2024.

### AXE frequence_achat [chapitres: 10,11] — coworking France fréquence d'achat 2025 2026
- Observatoire des tiers-lieux
  URL : https://observatoire-tiers-lieux.fr/usages
  Extrait : Abonnement mensuel majoritaire, 3,4 jours par semaine en moyenne.

### AXE taille_marche [chapitres: tous] — coworking France taille du marché 2025 2026
- INSEE, services aux entreprises
  URL : https://www.insee.fr/coworking
  Extrait : 1,2 Md EUR en 2025.
"""


def _prompt(job: GenerationJob, numero: int) -> str:
    socle = socle_verrouille(job)
    assert socle is not None
    prompt, _ = construire_prompt_chapitre(
        job.chapters.get(chapter_number=numero),
        socle=socle,
        variables=_VARIABLES,
        document=type_document(EM),
    )
    return prompt


@pytest.mark.django_db
def test_le_chapitre_recoit_les_sources_web_de_son_sujet(job_em: GenerationJob) -> None:
    """Le test qui échoue sur le code d'avant : aucun bloc de sources.

    Avant, la seule matière d'un chapitre était le socle : vingt-neuf chiffres
    pour vingt-et-un chapitres.
    """
    job_em.research_brief = BRIEF
    job_em.save(update_fields=["research_brief"])

    prompt = _prompt(job_em, 6)
    assert "SOURCES WEB RÉELLES POUR CE CHAPITRE" in prompt
    assert "service-public.fr/coworking" in prompt


@pytest.mark.django_db
def test_deux_chapitres_ne_recoivent_pas_la_meme_matiere(job_em: GenerationJob) -> None:
    """La CLASSE du défaut : la répétition vient de la matière, pas du style."""
    job_em.research_brief = BRIEF
    job_em.save(update_fields=["research_brief"])

    reglementation = _prompt(job_em, 6)
    comportements = _prompt(job_em, 10)

    assert "service-public.fr" in reglementation
    assert "service-public.fr" not in comportements
    assert "observatoire-tiers-lieux.fr" in comportements
    assert "observatoire-tiers-lieux.fr" not in reglementation

    # Et le socle commun leur parvient aux deux : filtrer ne doit pas les
    # priver de la référence sur laquelle tout le document s'accorde.
    assert "insee.fr/coworking" in reglementation
    assert "insee.fr/coworking" in comportements


@pytest.mark.django_db
def test_le_socle_reste_l_autorite_sur_les_chiffres(job_em: GenerationJob) -> None:
    """Sans règle de préséance écrite, le modèle citerait le web contre le socle.

    Le socle est verrouillé et contrôlé : c'est lui qui garantit qu'un montant
    ne change pas d'un chapitre à l'autre — le défaut nommé par la cliente sur
    WAOME (« TCAC 20 % au chapitre 1, 31 % au chapitre 8 »).
    """
    job_em.research_brief = BRIEF
    job_em.save(update_fields=["research_brief"])

    prompt = _prompt(job_em, 6)
    assert "SOCLE VERROUILLÉ" in prompt
    assert "le socle gagne" in prompt
    # Le socle est annoncé AVANT les sources : l'ordre de lecture compte.
    assert prompt.index("SOCLE VERROUILLÉ") < prompt.index("SOURCES WEB RÉELLES")


@pytest.mark.django_db
def test_sans_brief_le_chapitre_est_prevenu_au_lieu_d_etre_muet(
    job_em: GenerationJob,
) -> None:
    """Un bloc absent laisserait croire qu'il n'y a rien à citer — donc à inventer.

    C'est la règle 1 : se taire quand on n'a rien est le pire des silences.
    """
    assert not job_em.research_brief
    prompt = _prompt(job_em, 6)
    assert "aucune source collectée pour ce chapitre" in prompt
    assert "N'invente" in prompt


@pytest.mark.django_db
def test_le_chapitre_des_sources_recoit_toute_la_bibliographie(
    job_em: GenerationJob,
) -> None:
    """Le chapitre 21 recense TOUT, y compris ce qui a servi à confirmer.

    Sans cela, il ne pourrait citer que les sources des vingt-neuf données du
    socle — bien en dessous des 35 à 60 références du manuel.
    """
    job_em.research_brief = BRIEF
    job_em.save(update_fields=["research_brief"])

    prompt = _prompt(job_em, 21)
    for url in (
        "service-public.fr",
        "observatoire-tiers-lieux.fr",
        "insee.fr/coworking",
    ):
        assert url in prompt, f"source absente du chapitre 21 : {url}"
