"""Smoke test — une etude de marche complete traverse tout le pipeline.

Test de bout en bout SANS appel reseau (StubClaudeClient) : intake normalise
-> bootstrap du job -> generation des 22 chapitres (fiche projet + 21) avec
les CHECK inter-blocs -> gate de livraison -> rendu du document client.

Objectif : verifier que les correctifs de conformite au manuel Evangeline
(CHECK INITIAL bloquant, CHECK de bloc bloquant la livraison) n'ont pas casse
le chemin nominal, et que le livrable produit respecte la structure du manuel
(21 chapitres dans l'ordre + fiche projet, aucun marqueur de controle interne).
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.gate import run_delivery_gate
from generation.models import ChapterStatus, JobStatus
from generation.rendering import render_client_document
from generation.runner import run_generation_job
from generation.services import bootstrap_generation_job
from integrations.claude import StubClaudeClient
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order


@pytest.fixture
def soumission_em() -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Etude de marche", slug="em-smoke",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="client@example.com")
    order = Order.objects.create(
        systeme_order_id="order_em_smoke", customer=customer, offer=offer,
    )
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "kits solaires domestiques",
            "PAYS": "Benin",
            "ZONE": "Cotonou",
            "PROJET": "distribution de kits solaires B2C",
        },
    )


@pytest.mark.django_db
def test_em_complete_traverse_le_pipeline(soumission_em: IntakeSubmission) -> None:
    job = bootstrap_generation_job(soumission_em)

    run_generation_job(job, client=StubClaudeClient())
    job.refresh_from_db()

    # 1. Le job va au bout : aucun CHECK ne l'a bloque sur le chemin nominal.
    assert job.status == JobStatus.DONE, job.error_message

    # 2. Structure du manuel : fiche projet (ch. 0) + 21 chapitres.
    numeros = sorted(job.chapters.values_list("chapter_number", flat=True))
    assert numeros == list(range(0, 22)), f"Chapitres inattendus : {numeros}"
    assert job.chapters.filter(status=ChapterStatus.DONE).count() == 22
    # Le manuel s'arrete au chapitre 21 (Sources et methodologie).
    assert max(numeros) == 21

    # 3. Le gate de livraison se prononce sans exploser.
    rapport = run_delivery_gate(job)
    # Sur le chemin nominal (stub), aucun CHECK de bloc ne doit rester ouvert.
    checks_blocs_ouverts = [
        f for f in rapport.failures if f.check == "check_bloc_non_resolu"
    ]
    assert checks_blocs_ouverts == [], checks_blocs_ouverts

    # 4. Le document client est rendu, dans l'ordre, sans controle interne.
    document = render_client_document(job)
    assert document.sections, "Aucune section rendue."
    ordre = [s.number for s in document.sections]
    assert ordre == sorted(ordre), f"Chapitres dans le desordre : {ordre}"

    corpus = "\n".join(s.body for s in document.sections).lower()
    # Manuel p.5 : « les controles ne doivent jamais apparaitre dans le
    # document remis au client » ; p.4 : ne pas parler de prompt, controle,
    # modele ou automatisation dans le livrable.
    # Marqueurs volontairement NON ambigus : « pipeline » et « check » seuls
    # sont du vocabulaire commercial francais courant (« pipeline commercial »,
    # « check-list ») — les interdire ferait echouer un livrable conforme, ce
    # qu'a confirme la generation reelle du 24/07/2026 (« Pipeline strategique :
    # dual (grands comptes + ETI) » dans la fiche projet WAOME).
    for interdit in ("note_corrective", "prompt_key", "```json",
                     "check inter-bloc", "verdict :", "claude", "max_tokens"):
        assert interdit not in corpus, f"Fuite de controle interne : « {interdit} »"


@pytest.mark.django_db
def test_check_initial_ko_stoppe_le_pipeline_avant_le_chapitre_1(
    soumission_em: IntakeSubmission,
) -> None:
    """Preuve en conditions reelles du gate amont du manuel (p.3).

    « Si la fiche projet est complete [...] commencer le chapitre 1. Sinon,
    corriger la fiche ou demander la precision necessaire AVANT TOUTE
    REDACTION. » Le test unitaire de la phase 42 couvre le hook ; ici on
    verifie que `run_generation_job` lui-meme s'arrete, et surtout qu'aucun
    des 21 chapitres n'a ete redige sur une fiche defectueuse.
    """
    from unittest.mock import patch

    from generation.checks_blocs import CheckResult
    from generation.runner import CheckInitialBlockedError

    def _check_ko_sur_initial(job, bloc, chapitres, **_kwargs):
        if bloc.identifiant == "INITIAL":
            return CheckResult(
                bloc_identifiant="INITIAL", verdict="fix",
                note_corrective="Le pays cible n'est pas renseigne dans la fiche.",
            )
        return CheckResult(bloc_identifiant=bloc.identifiant, verdict="pass")

    job = bootstrap_generation_job(soumission_em)

    with patch("generation.runner.check_bloc", side_effect=_check_ko_sur_initial):
        with pytest.raises(CheckInitialBlockedError):
            run_generation_job(job, client=StubClaudeClient())

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED
    assert "CHECK INITIAL" in job.error_message

    # Le coeur du manuel : AUCUNE redaction n'a commence. Seule la fiche
    # projet (ch. 0) existe ; les chapitres 1 a 21 sont restes intouches.
    rediges = job.chapters.filter(status=ChapterStatus.DONE)
    assert [c.chapter_number for c in rediges] == [0], (
        "Des chapitres ont ete rediges malgre une fiche projet invalide."
    )
