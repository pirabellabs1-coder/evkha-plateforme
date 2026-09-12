"""Un chapitre absent se refait. Il n'attend pas une main qui ne peut rien.

## Le défaut mesuré

12/09/2026, reprise Zenitek `db0d9508` : deux chapitres meurent en cours de
génération — dont `str.20.sources`. Le livrable part sans eux, le contrôle
d'intégrité le retient, et le dossier s'arrête en « intervention requise ».

La cliente, en voyant l'écran : « je ne sais pas pourquoi ça, alors qu'on ne
peut rien faire sur le document, nous ». Elle a raison, et c'est le fond du
problème : **personne ne réécrit un chapitre à la main**. Le dossier attendait
un geste qui n'existe pas.

Le contrôleur final savait pourtant déjà réécrire des chapitres — mais
seulement les chapitres PRÉSENTS et fautifs. Le cas le plus grave, celui du
chapitre absent, était précisément le seul qu'il ne traitait pas : la règle 9
du dépôt, où le contrôle et sa réparation ne regardent pas la même chose.

Ces tests échouent sur le code d'avant : `_refaire_les_chapitres_manquants`
n'existait pas, et le dossier restait amputé.
"""
from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.controle_final import (
    RapportRelecture,
    _refaire_les_chapitres_manquants,
)
from generation.models import ChapterStatus, GenerationJob
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order

_VARIABLES = {
    "SECTEUR": "assistance informatique",
    "PAYS": "France",
    "ZONE": "Paris",
    "PROJET": "abonnement d'assistance",
}


@pytest.fixture
def job(db: Any) -> GenerationJob:
    offre = Offer.objects.create(
        name="EM", slug="em-rattrapage", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="rattrapage@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-rattrapage", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=_VARIABLES,
    )
    dossier = bootstrap_generation_job(soumission)
    etablir_socle(dossier, client=StubClaudeClient(), variables=_VARIABLES)
    # Tout est fait SAUF un chapitre : l'état exact du dossier `db0d9508`.
    dossier.chapters.all().update(status=ChapterStatus.DONE, content="Du texte.")
    dossier.chapters.filter(chapter_number=2).update(
        status=ChapterStatus.FAILED, content="",
    )
    return dossier


@pytest.mark.django_db
def test_le_chapitre_absent_est_refait(job: GenerationJob) -> None:
    """LE test : le dossier ne doit pas rester amputé en attendant un humain."""
    rapport = RapportRelecture()
    _refaire_les_chapitres_manquants(job, rapport, client=StubClaudeClient())

    assert rapport.chapitres_rattrapes == [2], rapport.as_details()
    chapitre = job.chapters.get(chapter_number=2)
    assert chapitre.status == ChapterStatus.DONE
    assert chapitre.content, "un chapitre rattrapé sans texte n'est pas rattrapé"


@pytest.mark.django_db
def test_un_dossier_complet_ne_repaye_rien(job: GenerationJob) -> None:
    """CONTRE-ÉPREUVE : le rattrapage ne doit pas se déclencher pour rien.

    Une passe qui rejouerait un chapitre déjà fait ferait payer deux fois
    chaque dossier sain — le défaut `[[UNDERSTAND]]` de ce dépôt, à l'identique.
    """
    job.chapters.all().update(status=ChapterStatus.DONE, content="Du texte.")

    class _Interdit:
        def complete_structured(self, **kwargs: Any) -> None:
            raise AssertionError("Aucun appel sur un dossier complet.")

    rapport = RapportRelecture()
    _refaire_les_chapitres_manquants(job, rapport, client=_Interdit())

    assert rapport.chapitres_rattrapes == []
    assert rapport.chapitres_perdus == []
    assert not rapport.a_corrige


@pytest.mark.django_db
def test_un_chapitre_qui_resiste_est_NOMME(job: GenerationJob) -> None:
    """Un rattrapage raté en silence ressemblerait à un dossier qui allait bien.

    C'est la règle 1 : ce qui échoue se dit. Le document partira amputé — mais
    la trace du dossier saura lequel manque, et pourquoi.
    """
    class _Defaillant:
        def complete_structured(self, **kwargs: Any) -> None:
            raise RuntimeError("le modèle ne répond pas")

    rapport = RapportRelecture()
    _refaire_les_chapitres_manquants(job, rapport, client=_Defaillant())

    assert rapport.chapitres_rattrapes == []
    assert rapport.chapitres_perdus == [2]
    assert rapport.as_details()["chapitres_perdus"] == [2]
