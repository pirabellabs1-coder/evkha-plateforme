"""Phase 42 — Le CHECK INITIAL est un gate BLOQUANT (manuel Evangeline simplifie).

Manuel EVKHA « Etude de marche simplifiee » :
  - p.3 : « Si la fiche projet est complete, coherente et fidele a la demande,
    commencer le chapitre 1. Sinon, corriger la fiche ou demander la precision
    necessaire AVANT TOUTE REDACTION. »
  - p.2 : « On ne continue jamais par automatisme. »

Avant ce correctif, un CHECK INITIAL en echec ouvrait un incident MEDIUM puis
laissait la generation continuer : les 21 chapitres etaient rediges sur une
fiche projet defectueuse (exactement ce que le manuel interdit). Un CHECK
INITIAL 'fix' declenche desormais une REPRISE de la fiche avec la note du
relecteur, et :
  - ouvre un incident HIGH si le refus survit a la reprise,
  - ne degrade PAS la fiche projet (chapitre 0), qui reste DONE,
  - laisse la redaction CONTINUER — decision cliente du 12/08/2026 : « quand il
    s'agit d'une incoherence, au lieu de mettre en echec, il faut plutot
    corriger et mettre de la logique dedans ».

Le blocage a ete leve sur une mesure : business plan `2b6cc7d6`, arrete a dix
centimes parce que le relecteur reclamait de justifier des montants absents du
brief. La correction demandee etait impossible, et la cliente n'avait rien.
C'est le gate de livraison qui juge le document a la fin.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from generation.checks_blocs import BLOCS_PAR_IDENTIFIANT, CheckResult
from generation.models import ChapterStatus
from generation.runner import _after_chapter_hook
from monitoring.models import IncidentSeverity, OperationalIncident


def _make_job_avec_fiche():
    """Construit un job EM minimal avec une fiche projet (chapitre 0) DONE."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(
        name="Test", slug="test-check-initial",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="t@test.local")
    order = Order.objects.create(
        systeme_order_id="test-check-initial-1", customer=customer, offer=offer,
    )
    job = GenerationJob.objects.create(
        order=order,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("3.20"),
    )
    fiche = ChapterGeneration.objects.create(
        job=job,
        chapter_number=0,
        chapter_title="Fiche projet",
        prompt_key="em.00.fiche_projet",
        status=ChapterStatus.DONE,
        content="Porteur : ... / Marche : kits solaires B2C. (PAYS manquant)",
    )
    return job, fiche


def _fix_result() -> CheckResult:
    bloc = BLOCS_PAR_IDENTIFIANT["INITIAL"]
    return CheckResult(
        bloc_identifiant=bloc.identifiant,
        verdict="fix",
        note_corrective="Fiche incomplete : le pays cible n'est pas renseigne.",
    )


def _pass_result() -> CheckResult:
    bloc = BLOCS_PAR_IDENTIFIANT["INITIAL"]
    return CheckResult(bloc_identifiant=bloc.identifiant, verdict="pass")


@pytest.mark.django_db
def test_check_initial_fix_laisse_une_trace_haute_et_poursuit() -> None:
    """Un CHECK INITIAL 'fix' PERSISTANT ouvre un incident HIGH, sans tuer l'etude.

    Depuis le 05/08/2026, une fiche refusee est d'abord regeneree une fois avec
    la note du relecteur (voir `test_phase46_...`). Depuis le 12/08/2026, un
    refus qui SURVIT a cette correction n'arrete plus la generation — decision
    cliente : « quand il s'agit d'une incoherence, au lieu de mettre en echec,
    il faut plutot corriger et mettre de la logique dedans ».

    Ce qui est verifie ici reste ce qui comptait : la fiche demeure DONE, et
    l'incident est HIGH — la trace ne s'efface pas, seule la mort de l'etude
    disparait. Le gate juge le document a la fin.
    """
    job, fiche = _make_job_avec_fiche()

    with patch("generation.runner.check_bloc", return_value=_fix_result()), \
         patch("generation.runner.regenerate_chapter"):
        _after_chapter_hook(job, fiche, client=object())

    # La fiche projet reste DONE : elle est valide en soi, c'est son CONTENU
    # que l'admin doit corriger. On ne la marque pas FAILED.
    fiche.refresh_from_db()
    assert fiche.status == ChapterStatus.DONE

    # Un incident HIGH est ouvert (et non MEDIUM comme les CHECKs A-J).
    incidents = OperationalIncident.objects.filter(job=job)
    assert incidents.count() == 1
    assert incidents.first().severity == IncidentSeverity.HIGH


@pytest.mark.django_db
def test_check_initial_pass_laisse_continuer() -> None:
    """Un CHECK INITIAL 'pass' ne leve rien et n'ouvre aucun incident."""
    job, fiche = _make_job_avec_fiche()

    with patch("generation.runner.check_bloc", return_value=_pass_result()):
        _after_chapter_hook(job, fiche, client=object())  # ne doit pas lever

    fiche.refresh_from_db()
    assert fiche.status == ChapterStatus.DONE
    assert OperationalIncident.objects.filter(job=job).count() == 0
