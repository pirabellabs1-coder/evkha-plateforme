"""Le moteur écrit des chapitres STRUCTURÉS quand le nouveau moteur est actif.

Le lot 2 produit un `ChapitrePayload` : le chapitre cite les identifiants du
socle et **demande ses graphiques**. C'est ce contrat, et lui seul, qui permet
au rendu Word du lot 3 de placer les bons visuels — un chapitre en markdown ne
dit pas quel graphique il veut ni sur quelles données.

`produire_chapitre` existait, testée, et n'était appelée par rien : le moteur
en service passait par `_generate_chapter`, qui écrit du markdown. Troisième
lot successif écrit et relié à rien.

Ces tests verrouillent aussi une décision qui ne se voit pas dans le résultat :
sur la voie structurée, la réparation QA du markdown et le CHECK inter-bloc ne
sont PAS appliqués. Tous deux réécrivent le markdown, alors que le rendu Word
emploie le `payload`. Les laisser ferait diverger deux versions du même
chapitre, et la réparation n'atteindrait pas le document livré.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation import runner as moteur
from generation.models import ChapterStatus, GenerationJob
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture
def job() -> GenerationJob:
    offre = Offer.objects.create(
        name="Étude de marché",
        slug="etude-marche-lot2",
        deliverable_type=DeliverableType.MARKET_STUDY,
        gamma_enabled=False,
    )
    client = Customer.objects.create(email="lot2@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="order_lot2_1", customer=client, offer=offre
    )
    soumission = IntakeSubmission.objects.create(
        order=commande,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "restauration",
            "PAYS": "France",
            "ZONE": "Paris",
            "PROJET": "restaurant de quartier",
        },
    )
    return bootstrap_generation_job(soumission)


class _Traces:
    def __init__(self) -> None:
        self.structures: list[int] = []
        self.markdown: list[int] = []
        self.qa: list[Any] = []
        self.checks: list[Any] = []


@pytest.fixture
def traces(monkeypatch: pytest.MonkeyPatch) -> _Traces:
    """Remplace les deux voies et les deux post-traitements, et note les appels."""
    t = _Traces()

    def _structure(job_recu: Any, numero: int, **kwargs: Any) -> Any:
        t.structures.append(numero)
        chapitre = job_recu.chapters.get(chapter_number=numero)
        chapitre.status = ChapterStatus.DONE
        chapitre.payload = {"chapitre": numero, "titre": "T", "resume": "r"}
        chapitre.content = "# markdown de secours"
        chapitre.save(
            update_fields=["status", "payload", "content", "updated_at"]
        )
        return chapitre

    def _markdown(job_recu: Any, chapitre: Any, **kwargs: Any) -> None:
        t.markdown.append(chapitre.chapter_number)
        chapitre.status = ChapterStatus.DONE
        chapitre.content = "# markdown"
        chapitre.save(update_fields=["status", "content", "updated_at"])

    monkeypatch.setattr(moteur, "produire_chapitre", _structure)
    monkeypatch.setattr(moteur, "_generate_chapter", _markdown)
    monkeypatch.setattr(moteur, "_inline_qa_repair", lambda c: t.qa.append(c))
    monkeypatch.setattr(
        moteur, "_after_chapter_hook", lambda *a, **k: t.checks.append(a)
    )
    monkeypatch.setattr(moteur, "etablir_socle", lambda job, **k: object())
    monkeypatch.setattr(moteur, "socle_verrouille", lambda job: object())
    return t


@override_settings(EVKHA_SOCLE_ENABLED=True)
def test_les_chapitres_passent_par_la_voie_structuree(
    job: GenerationJob, traces: _Traces
) -> None:
    """LE test du défaut : sans le correctif, tout passait par le markdown."""
    moteur.run_generation_job(job)

    assert traces.structures, "aucun chapitre structuré produit"
    assert traces.markdown == [], "la voie markdown ne doit pas être empruntée"


@override_settings(EVKHA_SOCLE_ENABLED=True)
def test_la_reparation_markdown_n_est_pas_appliquee(
    job: GenerationJob, traces: _Traces
) -> None:
    """Décision assumée, invisible dans le résultat, donc verrouillée ici.

    `_inline_qa_repair` et le CHECK inter-bloc réécrivent le markdown. Le rendu
    Word emploie le `payload`. Les appliquer ferait diverger deux versions du
    même chapitre (règle 5) et la réparation n'atteindrait pas le document
    livré (règle 3).
    """
    moteur.run_generation_job(job)

    assert traces.qa == [], "la QA markdown ne doit pas toucher un chapitre structuré"
    assert traces.checks == [], "le CHECK inter-bloc ne s'applique pas non plus"


@override_settings(EVKHA_SOCLE_ENABLED=False)
def test_sans_le_drapeau_l_ancienne_voie_reste_seule(
    job: GenerationJob, traces: _Traces
) -> None:
    """Contre-épreuve : le repli du §16 doit rester praticable, QA comprise."""
    moteur.run_generation_job(job)

    assert traces.markdown, "l'ancien moteur doit continuer de produire"
    assert traces.structures == []
    assert traces.qa, "la QA markdown reste appliquée sur l'ancienne voie"


@override_settings(EVKHA_SOCLE_ENABLED=True)
def test_le_socle_est_relu_une_seule_fois_pour_tout_le_run(
    job: GenerationJob, monkeypatch: pytest.MonkeyPatch, traces: _Traces
) -> None:
    """Il est identique pour tous les chapitres ; le relire à chaque tour
    multiplierait les requêtes sans rien changer."""
    lectures: list[Any] = []

    def _lire(job_recu: Any) -> Any:
        lectures.append(job_recu)
        return object()

    monkeypatch.setattr(moteur, "socle_verrouille", _lire)

    moteur.run_generation_job(job)

    assert len(lectures) == 1, f"socle relu {len(lectures)} fois"
    assert len(traces.structures) > 1, "plusieurs chapitres doivent avoir été écrits"


@override_settings(EVKHA_SOCLE_ENABLED=True)
def test_un_type_de_livrable_non_declare_reste_sur_l_ancienne_voie(
    job: GenerationJob, traces: _Traces, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contre-épreuve : le nouveau moteur ne couvre pas tout, et doit le savoir.

    Sans ce garde-fou, un livrable non déclaré dans la configuration du lot 2
    échouerait au lieu de continuer d'être produit par l'ancienne chaîne.
    """
    monkeypatch.setattr(moteur, "est_declare", lambda code: False)

    moteur.run_generation_job(job)

    assert traces.structures == []
    assert traces.markdown, "l'ancienne voie prend le relais"
