"""Reparer un chapitre a les memes droits a l'erreur que l'ecrire.

Mesure, generation reelle `4c8cfa53` du 05/08/2026, commit `d657500` :

    [465s] running  4/23 chapitres  cout=0.3864     <- le chapitre 3 est ecrit
    [495s] running  3/23 chapitres  cout=0.4292     <- le CHECK demande sa reparation
    [510s] failed   3/23 chapitres  cout=0.4292
    erreur : volume : 966 signes contre 792 au modele, 22 % au-dessus de la
             tolerance de 15 %
    ch. 3 failed  essais=1

**Une seule tentative.** La boucle de reprise, ajoutee le 02/08 apres trois
etudes mortes, vivait dans `generation.runner` et ne servait donc qu'a la
PREMIERE ecriture d'un chapitre. La reparation — celle qu'un CHECK inter-bloc
ou le gate declenche — appelait `produire_chapitre` une fois, et sans jamais
declarer de derniere tentative : l'arbitrage de conformite, qui n'accepte un
ecart de forme que sur la derniere, n'etait donc jamais atteint. Tout ecart de
volume redevenait fatal, exactement comme au run nº1 du 02/08.

J'avais corrige l'instance et pas la classe (regle 4) : ce qui ecrit un
chapitre et ce qui le REECRIT doivent avoir les memes droits.

Second defaut, independant : l'exception de la reparation remontait jusqu'au
filet generique de `run_generation_job`, qui arrete tout. Or le module dit
lui-meme le contraire quelques lignes plus haut — « un echec persistant apres
retry ouvre un incident MEDIUM (non bloquant) : le contenu reste livre au
client ». Trois chapitres et 0,43 EUR ont ete perdus pour une correction
cosmetique impossible sur un chapitre qui avait deja une version acceptee.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, cast
from unittest.mock import patch

import pytest

from generation.checks_blocs import CheckResult
from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
from monitoring.models import OperationalIncident


@pytest.fixture
def job_em() -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from orders.models import Order

    offre = Offer.objects.create(
        name="EM", slug="test-reparation-reprises",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="reparation@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-reparation", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("6.00"),
    )


@pytest.mark.django_db
def test_la_reparation_reessaie_et_declare_sa_derniere_tentative(job_em: Any) -> None:
    """Trois tentatives, et la derniere se declare comme telle.

    Sur le code d'avant, `regenerer_chapitre` appelait `produire_chapitre` UNE
    fois, avec `derniere_tentative=None`.
    """
    from generation.chapitres import services

    ChapterGeneration.objects.create(
        job=job_em, chapter_number=3, chapter_title="Segmentation",
        prompt_key="em.03.segmentation", status=ChapterStatus.DONE,
        payload={"chapitre": 3}, content="Version precedente.",
    )
    appels: list[bool | None] = []

    def _produire(
        job: Any, numero: int, *, client: Any,
        socle: Any = None, derniere_tentative: bool | None = None,
    ) -> Any:
        appels.append(derniere_tentative)
        if len(appels) < 3:
            msg = "volume : 966 signes contre 792 au modele"
            raise RuntimeError(msg)
        return job.chapters.get(chapter_number=numero)

    with patch.object(services, "produire_chapitre", side_effect=_produire):
        services.regenerer_chapitre(job_em, 3, client=object(), note_corrective="Trop long.")

    assert appels == [False, False, True], (
        "Trois tentatives, et seule la derniere s'annonce comme telle."
    )


@pytest.mark.django_db
def test_une_reparation_impossible_ne_fait_pas_disparaitre_le_chapitre(
    job_em: Any,
) -> None:
    """Le chapitre garde sa version d'avant, STATUT COMPRIS.

    `payload` et `content` etaient deja preserves. Le STATUT, lui, restait sur
    l'echec — et `payloads_du_job` n'assemble que les chapitres TERMINES : le
    document perdait un chapitre entier alors qu'une version acceptable
    existait toujours.
    """
    from generation.chapitres import services

    ChapterGeneration.objects.create(
        job=job_em, chapter_number=3, chapter_title="Segmentation",
        prompt_key="em.03.segmentation", status=ChapterStatus.DONE,
        payload={"chapitre": 3}, content="Version precedente.",
    )

    def _echoue(
        job: Any, numero: int, *, client: Any,
        socle: Any = None, derniere_tentative: bool | None = None,
    ) -> Any:
        msg = "volume : 966 signes contre 792 au modele"
        raise RuntimeError(msg)

    with patch.object(services, "produire_chapitre", side_effect=_echoue), \
         pytest.raises(RuntimeError):
        services.regenerer_chapitre(job_em, 3, client=object(), note_corrective="Trop long.")

    chapitre = job_em.chapters.get(chapter_number=3)
    assert chapitre.status == ChapterStatus.DONE
    assert chapitre.content == "Version precedente."


@pytest.mark.django_db
def test_une_reparation_impossible_ne_tue_pas_l_etude(job_em: Any) -> None:
    """Le CHECK ouvre un incident et laisse continuer — ce que le code annonce.

    Sur le code d'avant, l'exception traversait `_after_chapter_hook` et
    `run_generation_job` marquait le job FAILED. Trois chapitres perdus pour
    une correction cosmetique impossible.
    """
    from generation.checks_blocs import BLOCS_PAR_IDENTIFIANT
    from generation.runner import _executer_check_avec_retry

    chapitre = ChapterGeneration.objects.create(
        job=job_em, chapter_number=3, chapter_title="Segmentation",
        prompt_key="em.03.segmentation", status=ChapterStatus.DONE,
        payload={"chapitre": 3}, content="Version precedente.",
    )
    bloc = BLOCS_PAR_IDENTIFIANT["B"]
    refus = CheckResult(
        bloc_identifiant="B", verdict="fix", note_corrective="Chapitre trop long.",
    )

    def _echoue(
        job: Any, chap: Any, *, corrective_note: str = "", client: Any = None,
    ) -> None:
        msg = "volume : 966 signes contre 792 au modele"
        raise RuntimeError(msg)

    with patch("generation.runner.check_bloc", return_value=refus), \
         patch("generation.runner.regenerate_chapter", side_effect=_echoue):
        _executer_check_avec_retry(
            job_em, bloc, chapitres=[chapitre], client=cast("Any", object()),
        )  # ne doit PAS lever

    incidents = OperationalIncident.objects.filter(job=job_em)
    assert incidents.count() == 1, "L'echec doit rester visible, pas silencieux."
    assert "echoue apres retry" in incidents[0].title

    chapitre.refresh_from_db()
    assert chapitre.status == ChapterStatus.DONE
