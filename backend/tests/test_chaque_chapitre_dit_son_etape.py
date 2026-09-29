"""Chaque chapitre dit son étape — rédaction, vérification, ajustement, validé.

29/09/2026 : le client ne voyait qu'une étape « Rédaction des chapitres », et
l'écran déduisait lui-même un état « échec » quand un dossier tombait. L'étape
est désormais posée par la boucle de production (`produire_chapitre`), dans les
mots que le client lit : jamais « erreur », jamais « échec ».
"""
from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres import services as chapitres_services
from generation.chapitres.runner import ChapitreInvalideError
from generation.chapitres.services import produire_avec_reprises
from generation.models import ChapterGeneration, GenerationJob
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order

pytestmark = pytest.mark.django_db

EM = DeliverableType.MARKET_STUDY
VARIABLES = {"SECTEUR": "joaillerie", "PAYS": "France", "ZONE": "Paris", "PROJET": "Test"}
ETAPES_CLIENT = {"", "redaction", "verification", "ajustement", "valide"}


@pytest.fixture
def job() -> GenerationJob:
    offre = Offer.objects.create(name="EM", slug="em-etape", deliverable_type=EM)
    client = Customer.objects.create(email="etape@exemple.fr")
    commande = Order.objects.create(systeme_order_id="cmd-etape", customer=client, offer=offre)
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=VARIABLES,
    )
    dossier = bootstrap_generation_job(soumission)
    etablir_socle(dossier, client=StubClaudeClient(), variables=VARIABLES)
    return dossier


def test_un_chapitre_produit_est_valide(job: GenerationJob) -> None:
    chapitre = produire_avec_reprises(job, 1, client=StubClaudeClient())
    assert chapitre.etape == "valide"
    assert ChapterGeneration.objects.get(pk=chapitre.pk).etape == "valide"


def test_une_reprise_se_dit_ajustement_puis_valide(
    job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    vues: list[str] = []
    vrai = chapitres_services.generer_chapitre
    appels = {"n": 0}

    def generer(**kwargs: Any) -> Any:
        vues.append(ChapterGeneration.objects.get(pk=kwargs["chapter"].pk).etape)
        appels["n"] += 1
        if appels["n"] == 1:
            raise ChapitreInvalideError(["motif de test"])
        return vrai(**kwargs)

    monkeypatch.setattr(chapitres_services, "generer_chapitre", generer)

    chapitre = produire_avec_reprises(job, 1, client=StubClaudeClient())

    assert vues == ["redaction", "ajustement"]
    assert chapitre.etape == "valide"


def test_les_etapes_sont_dans_les_mots_du_client(job: GenerationJob) -> None:
    produire_avec_reprises(job, 1, client=StubClaudeClient())
    assert set(job.chapters.values_list("etape", flat=True)) <= ETAPES_CLIENT
