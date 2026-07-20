"""Phase 16 — Brique 1 : substitution de tokens (brief client juillet 2026).

« Le modele n'ecrit pas "environ X €", il recoit le nombre deja ecrit et le
retranscrit. » Jusqu'ici les chiffres client n'etaient qu'un bloc de contexte
que le modele restait libre de reformuler : la Brique 1 avait ete reinterpretee
en « meilleur prompt ».
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.coherence import seed_locked_facts_from_variables
from generation.context import build_context
from generation.models import GenerationJob
from generation.services import bootstrap_generation_job
from generation.substitution import (
    resolve_client_fact_tokens,
    substitutable_facts,
    tokens_catalogue,
)
from generation.validation import validate_chapter_content
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

_VARIABLES = {
    "SECTEUR": "coworking",
    "PAYS": "France",
    "ZONE": "Annecy",
    "PROJET": "SYNAPSES",
    "INVESTISSEMENT_TOTAL": "1 250 000 €",
    "EMPRUNT": "920 000 €",
    "APPORT": "250 000 €",
    "CA_PREVISIONNEL": "250 272 € / 296 000 €",
    "RESULTAT_NET_PREVISIONNEL": "44 245 €",
}


@pytest.fixture
def job(db: None) -> GenerationJob:
    offer = Offer.objects.create(
        name="BP", slug="bp-subst", deliverable_type=DeliverableType.BUSINESS_PLAN
    )
    customer = Customer.objects.create(email="subst@example.com")
    order = Order.objects.create(
        systeme_order_id="order_subst_1", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables=_VARIABLES,
    )
    generation_job = bootstrap_generation_job(submission)
    seed_locked_facts_from_variables(generation_job, _VARIABLES)
    return generation_job


@pytest.mark.django_db
def test_seuls_les_faits_scalaires_sont_substituables(job: GenerationJob) -> None:
    """Les trajectoires pluriannuelles sont exclues : un token unique ne peut
    pas resoudre vers « 250 272 € / 296 000 € » dans une phrase."""
    facts = substitutable_facts(job)

    assert facts["emprunt"] == "920 000 €"
    assert facts["investissement_total"] == "1 250 000 €"
    assert "ca_previsionnel" not in facts
    assert "resultat_net_previsionnel" not in facts


@pytest.mark.django_db
def test_le_token_est_remplace_par_la_valeur_exacte_du_brief(job: GenerationJob) -> None:
    content = "Le plan repose sur un emprunt de {{emprunt}} sur 7 ans."

    resolved, unresolved = resolve_client_fact_tokens(content, job)

    assert resolved == "Le plan repose sur un emprunt de 920 000 € sur 7 ans."
    assert unresolved == []


@pytest.mark.django_db
def test_substitution_tolerante_a_la_casse_et_aux_espaces(job: GenerationJob) -> None:
    content = "Investissement : {{ INVESTISSEMENT_TOTAL }}."

    resolved, unresolved = resolve_client_fact_tokens(content, job)

    assert resolved == "Investissement : 1 250 000 €."
    assert unresolved == []


@pytest.mark.django_db
def test_token_inconnu_reste_intact_et_est_signale(job: GenerationJob) -> None:
    """Le supprimer masquerait le probleme ; le laisser le fait bloquer."""
    content = "Le TCAC atteint {{tcac_invente}} cette annee."

    resolved, unresolved = resolve_client_fact_tokens(content, job)

    assert "{{tcac_invente}}" in resolved
    assert unresolved == ["{{tcac_invente}}"]
    # La validation post-generation le detecte -> retry correctif.
    codes = {issue.code for issue in validate_chapter_content(resolved)}
    assert "unresolved_curly_placeholder" in codes


@pytest.mark.django_db
def test_le_prompt_expose_les_tokens_avec_leur_valeur(job: GenerationJob) -> None:
    """Le modele voit le nombre deja ecrit : il n'a aucune raison de l'estimer."""
    catalogue = tokens_catalogue(job)

    assert "{{emprunt}} = 920 000 €" in catalogue
    assert "{{investissement_total}} = 1 250 000 €" in catalogue


@pytest.mark.django_db
def test_le_contexte_de_chapitre_porte_la_consigne_de_substitution(
    job: GenerationJob,
) -> None:
    chapter = job.chapters.first()
    assert chapter is not None

    context = build_context(chapter)

    assert "CHIFFRES_A_CITER" in context
    assert "{{emprunt}}" in context
    assert "JAMAIS le nombre a la main" in context


@pytest.mark.django_db
def test_contenu_sans_token_reste_inchange(job: GenerationJob) -> None:
    """Contre-epreuve : la substitution ne touche a rien d'autre."""
    content = "Le marche du coworking croit de 8,4 % par an sur la zone."

    resolved, unresolved = resolve_client_fact_tokens(content, job)

    assert resolved == content
    assert unresolved == []
