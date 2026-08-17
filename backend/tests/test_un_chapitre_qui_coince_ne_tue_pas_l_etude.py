"""Un chapitre qui résiste ne doit pas emporter les vingt-deux autres.

## Le retour de la cliente, et il est sans appel

09/08/2026 : « ça ne doit rencontrer d'échec ni autres, une fois que
l'information est recherchée ça doit continuer le travail, et c'est tout. »

Ce jour-là, l'étude concurrentielle `5892daa5` est morte DEUX FOIS :

  - au chapitre 1, sur une cellule de tableau manquante — 1,05 EUR perdus ;
  - au chapitre 2, sur un contrôle de secteur trop large — 2,07 EUR perdus.

Chaque fois, les chapitres déjà écrits partaient avec. La cliente n'a rien reçu.

## Le calcul, et il n'est pas serré

Perdre vingt-deux chapitres corrects parce que le vingt-troisième résiste coûte
infiniment plus cher que livrer un document avec un trou nommé. Un chapitre
manquant se régénère seul (`regenerate_chapter`) et l'opérateur voit où il est.
Une étude morte se recommande — et se repaie.

## Continuer n'est PAS se taire

Le chapitre reste `FAILED`, son motif est enregistré, un incident HIGH est
ouvert, et le gate de livraison verra le trou. C'est toute la différence entre
poursuivre et ignorer (règle 1).

Et un dossier dont AUCUN chapitre n'aboutit reste un échec : livrer une coquille
vide en la déclarant terminée serait le silence sous une autre forme.
"""
from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import ChapterStatus, GenerationJob, JobStatus
from generation.runner import run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order

VARIABLES = {"SECTEUR": "e-commerce animalier", "PAYS": "France"}


@pytest.fixture
def job(db: Any) -> GenerationJob:
    offre = Offer.objects.create(
        name="EC", slug="chapitre-qui-coince",
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
    )
    client = Customer.objects.create(email="coince@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-coince", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=VARIABLES,
    )
    return bootstrap_generation_job(soumission)


class _ClientQuiRateUnChapitre(StubClaudeClient):
    """Doublure qui refuse le N-ième appel et honore tous les autres.

    Elle intercepte `complete` ET `complete_structured` : le moteur employé
    dépend de `EVKHA_SOCLE_ENABLED`, faux par défaut en test. Ne couvrir qu'une
    des deux méthodes ferait passer le test sans qu'aucun échec ne survienne —
    il serait vert en ne vérifiant rien (règle 6).
    """

    def __init__(self, appel_fautif: int = 2) -> None:
        super().__init__()
        self._fautif = appel_fautif
        self.appels = 0

    def _peut_etre_rater(self) -> None:
        self.appels += 1
        if self.appels == self._fautif:
            msg = "chapitre volontairement refusé par la doublure"
            raise RuntimeError(msg)

    def complete(self, *args: Any, **kwargs: Any) -> Any:
        self._peut_etre_rater()
        return super().complete(*args, **kwargs)

    def complete_structured(self, **kwargs: Any) -> Any:
        self._peut_etre_rater()
        return super().complete_structured(**kwargs)


def test_un_chapitre_en_echec_n_arrete_pas_les_suivants(job: GenerationJob) -> None:
    """Le cœur du retour cliente : l'étude CONTINUE."""
    client = _ClientQuiRateUnChapitre(2)

    run_generation_job(job, client=client)

    job.refresh_from_db()
    assert job.status == JobStatus.DONE
    ecrits = job.chapters.filter(status=ChapterStatus.DONE).count()
    assert ecrits >= job.chapters.count() - 1, "un seul chapitre devait manquer"


def test_le_chapitre_manquant_SE_VOIT(job: GenerationJob) -> None:
    """Continuer n'est pas ignorer : le trou est nommé, daté, tracé (règle 1)."""
    run_generation_job(job, client=_ClientQuiRateUnChapitre(2))

    fautif = job.chapters.filter(status=ChapterStatus.FAILED).first()
    assert fautif is not None, "un chapitre devait echouer"
    assert fautif.error_message, "le motif doit rester lisible par l'opérateur"


def test_un_incident_est_ouvert_pour_le_chapitre_perdu(job: GenerationJob) -> None:
    from monitoring.models import OperationalIncident

    run_generation_job(job, client=_ClientQuiRateUnChapitre(2))

    assert OperationalIncident.objects.filter(
        job=job, title__startswith="Echec generation chapitre"
    ).exists()


def test_un_dossier_dont_AUCUN_chapitre_n_aboutit_reste_un_echec(
    job: GenerationJob,
) -> None:
    """Contre-épreuve : livrer une coquille vide serait le silence autrement.

    Sans elle, « continuer malgré tout » deviendrait « déclarer terminé un
    document qui n'existe pas ».
    """

    class _ToutRate(StubClaudeClient):
        """Les DEUX méthodes, pour la même raison que la doublure ci-dessus."""

        def complete(self, *args: Any, **kwargs: Any) -> Any:
            msg = "tout échoue"
            raise RuntimeError(msg)

        def complete_structured(self, **kwargs: Any) -> Any:
            msg = "tout échoue"
            raise RuntimeError(msg)

    with pytest.raises(Exception):  # noqa: B017 — socle ou chapitres, l'echec doit remonter
        run_generation_job(job, client=_ToutRate())

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED
    assert not job.chapters.filter(status=ChapterStatus.DONE).exists()
