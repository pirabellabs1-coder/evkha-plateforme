"""Phase 43 — Un CHECK de bloc non resolu BLOQUE la livraison.

Manuel EVKHA, repete a la fin de CHACUN des 9 blocs (pp. 8-16) :
  « Si une reponse est non : corriger le bloc concerne, refaire le controle,
    puis seulement continuer. »
Et p.17, encadre « Livraison autorisee » :
  « La livraison est possible uniquement lorsque le fond, les chiffres, les
    demandes client, les sources, la continuite et la presentation sont tous
    valides. »

Avant ce correctif : le runner rejouait le bloc une fois, puis — si le CHECK
echouait encore — ouvrait un incident MEDIUM purement informatif et CONTINUAIT.
Le verdict du relecteur n'etait persiste nulle part et n'atteignait jamais
`run_delivery_gate`. Resultat : une etude avec un controle non valide partait
quand meme chez le client, exactement ce que l'encadre « Livraison autorisee »
interdit.

Desormais l'incident porte un marqueur `details["type"]` que le gate lit. Tant
qu'il est OPEN, la livraison est bloquee ; l'admin qui traite l'incident
(ACKNOWLEDGED / RESOLVED) la debloque.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from generation.checks_blocs import INCIDENT_TYPE_CHECK_BLOC
from generation.gate import _check_blocs_evangeline
from generation.models import ChapterStatus
from monitoring.models import IncidentSeverity, IncidentStatus, OperationalIncident


def _make_job():
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(
        name="Test", slug="test-check-bloc-livraison",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="t@test.local")
    order = Order.objects.create(
        systeme_order_id="test-check-bloc-1", customer=customer, offer=offer,
    )
    job = GenerationJob.objects.create(
        order=order,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("3.20"),
    )
    ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Marche mondial",
        prompt_key="em.01.marche_mondial_europeen",
        status=ChapterStatus.DONE, content="Contenu.",
    )
    return job


def _incident_check_bloc(job, *, status=IncidentStatus.OPEN):
    return OperationalIncident.objects.create(
        title="CHECK 1 (bloc A) echoue apres retry",
        severity=IncidentSeverity.MEDIUM,
        status=status,
        job=job,
        order=job.order,
        details={
            "type": INCIDENT_TYPE_CHECK_BLOC,
            "bloc": "A",
            "check": "1",
            "intitule": "Fondations du marche",
            "chapitres": [1, 2],
            "note_corrective": "Ch. 1 : le TCAC ne correspond pas a la projection.",
        },
    )


@pytest.mark.django_db
def test_check_bloc_ouvert_bloque_la_livraison() -> None:
    """Incident CHECK bloc encore OPEN -> le gate refuse la livraison."""
    job = _make_job()
    _incident_check_bloc(job)

    failures = _check_blocs_evangeline(job)

    # UNE entree par chapitre nomme depuis le 11/08/2026 : sans numero, la
    # note du relecteur ne pouvait rien reparer, meme sur decision humaine
    # (`cc0dfe14`, sept CHECK bloquants, sept chapitres cites, zero routable).
    assert sorted(f.chapter_number for f in failures) == [1, 2]
    assert all(f.check == "check_bloc_non_resolu" for f in failures)
    # La note du relecteur doit remonter a l'admin, sur chaque entree.
    assert all("TCAC" in f.detail for f in failures)
    assert all("bloc A" in f.detail for f in failures)


@pytest.mark.django_db
def test_check_bloc_resolu_par_admin_debloque_la_livraison() -> None:
    """L'admin traite l'incident -> la livraison redevient possible.

    C'est la traduction de « corriger le bloc, refaire le controle, puis
    seulement continuer » : la reprise est humaine, pas automatique.
    """
    job = _make_job()
    _incident_check_bloc(job, status=IncidentStatus.RESOLVED)

    assert _check_blocs_evangeline(job) == []


@pytest.mark.django_db
def test_sans_incident_check_la_livraison_passe() -> None:
    """Cas nominal : tous les CHECKs sont passes, rien ne bloque."""
    job = _make_job()

    assert _check_blocs_evangeline(job) == []


@pytest.mark.django_db
def test_perimetre_le_garde_fou_ne_touche_pas_bp_ec_str() -> None:
    """Le manuel se limite lui-meme a l'etude de marche (p.1 « Perimetre :
    Etude de marche uniquement »). Les blocs A-J et leurs CHECKs n'existent
    que pour l'EM : un business plan ne doit jamais etre bloque par ce check.
    """
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(
        name="BP", slug="test-bp-perimetre",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email="bp@test.local")
    order = Order.objects.create(
        systeme_order_id="test-bp-perimetre-1", customer=customer, offer=offer,
    )
    job = GenerationJob.objects.create(
        order=order,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        budget_eur=Decimal("3.20"),
    )

    assert _check_blocs_evangeline(job) == []


@pytest.mark.django_db
def test_incident_non_lie_a_un_check_ne_bloque_pas() -> None:
    """Un incident d'un autre type (budget, echec reseau...) ne doit pas etre
    confondu avec un CHECK de bloc non valide."""
    job = _make_job()
    OperationalIncident.objects.create(
        title="Budget depasse",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        job=job,
        order=job.order,
        details={"type": "budget", "montant": "3.20"},
    )

    assert _check_blocs_evangeline(job) == []
