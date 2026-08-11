"""Un verdict doit pouvoir être rejoué quand le JUGE a changé.

Le 10/08/2026, `026fecea` — dix chapitres propres, 1,94 € — est bloqué par
trois contrôles qui jugeaient le contrat structuré avec les yeux de l'ancien
moteur (chapitre fermé sur sa figure « tronqué », cardinaux additionnés entre
chapitres, annexes numérotées comptées zéro). Les contrôles sont réparés le
soir même — mais le verdict reste écrit en base, et l'écran continue
d'afficher un blocage que plus rien ne justifie.

Sans recontrôle, deux issues, toutes deux mauvaises : livrer sous dérogation
en assumant un blocage FAUX, ou repayer 3,50 € une génération dont le
document existe déjà. Le recontrôle rejoue le gate — lecture seule, zéro
appel IA — et met l'étiquette à jour, dans les deux sens.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import Client, override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import GenerationJob, JobStatus, QAStatus
from monitoring.models import OperationalIncident
from orders.models import Order


def _job(statut: str = JobStatus.DONE, qa: str = QAStatus.BLOCKED) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="recontrole",
        defaults={"name": "Étude de la concurrence",
                  "deliverable_type": DeliverableType.COMPETITOR_STUDY},
    )
    client, _ = Customer.objects.get_or_create(email="recontrole@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"recontrole-{statut}-{qa}", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(order=commande, status=statut, qa_status=qa)


class _Rapport:
    def __init__(self, passed: bool) -> None:
        self.passed = passed
        self.failures = () if passed else ({"check": "x"},)

    def as_details(self) -> dict[str, object]:
        return {"passed": self.passed, "failures": list(self.failures)}


def _poster(job: GenerationJob) -> Any:
    with override_settings(DEBUG=True, EVKHA_DASHBOARD_AUTH_DISABLED=True):
        return Client().post(f"/api/dashboard/jobs/{job.id}/reverifier/")


@pytest.mark.django_db
def test_un_blocage_devenu_faux_est_efface(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le cas `026fecea` : contrôles réparés, verdict rejoué, étiquette juste."""
    import generation.gate as gate

    monkeypatch.setattr(gate, "run_delivery_gate", lambda _job: _Rapport(passed=True))
    job = _job()

    reponse = _poster(job)

    assert reponse.status_code == 200, reponse.content
    job.refresh_from_db()
    assert job.qa_status == QAStatus.PASSED


@pytest.mark.django_db
def test_un_blocage_toujours_justifie_est_confirme_avec_motifs_frais(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRE-ÉPREUVE : le recontrôle n'est pas un tampon.

    Un gate qui échoue encore laisse le blocage EN PLACE et ouvre un incident
    aux motifs frais — relire d'anciens échecs ferait chercher dans le
    document des défauts qui n'y sont plus (règle 2).
    """
    import generation.gate as gate

    monkeypatch.setattr(gate, "run_delivery_gate", lambda _job: _Rapport(passed=False))
    job = _job()

    reponse = _poster(job)

    assert reponse.status_code == 200, reponse.content
    job.refresh_from_db()
    assert job.qa_status == QAStatus.BLOCKED
    assert OperationalIncident.objects.filter(
        job=job, title__contains="recontrôle"
    ).exists()


@pytest.mark.django_db
def test_corriger_part_en_tache_de_fond_jamais_dans_la_requete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`{"corriger": true}` : la boucle s'ENQUEUE, la requête répond 202.

    La première version corrigeait DANS la requête : le serveur web a tué le
    worker à son délai de garde — 500, et un chapitre fantôme en `running`
    (10/08/2026, `026fecea`). Une régénération est une génération ; elle vit
    en tâche de fond, là où le délai de garde n'existe pas.
    """
    import generation.gate as gate
    import generation.tasks as tasks

    lancements: list[str] = []
    monkeypatch.setattr(gate, "run_delivery_gate", lambda _job: _Rapport(passed=False))
    monkeypatch.setattr(
        tasks.recontroler_et_corriger_task, "delay",
        lambda job_id: lancements.append(job_id),
    )
    job = _job()

    with override_settings(DEBUG=True, EVKHA_DASHBOARD_AUTH_DISABLED=True):
        reponse = Client().post(
            f"/api/dashboard/jobs/{job.id}/reverifier/",
            data='{"corriger": true}',
            content_type="application/json",
        )

    assert reponse.status_code == 202, reponse.content
    assert lancements == [str(job.id)]


@pytest.mark.django_db
def test_la_tache_de_correction_ecrit_le_verdict_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La tâche rend le verdict de la boucle — le rapport que `tasks.py` consomme."""
    import generation.tasks as tasks

    import generation.correction as correction

    monkeypatch.setattr(
        correction, "run_correction_loop",
        lambda _job, **_kw: _Rapport(passed=True),
    )
    job = _job()

    tasks.recontroler_et_corriger_task(str(job.id))

    job.refresh_from_db()
    assert job.qa_status == QAStatus.PASSED


@pytest.mark.django_db
def test_sans_corriger_la_boucle_ne_tourne_jamais(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRE-ÉPREUVE : le recontrôle nu reste GRATUIT — zéro appel IA.

    Une boucle de correction qui partirait sur un simple recontrôle
    dépenserait sans accord : c'est précisément l'interdit du dépôt.
    """
    import generation.correction as correction
    import generation.gate as gate

    def _interdit(_job: object) -> None:
        raise AssertionError("run_correction_loop appelé sans corriger=true")

    monkeypatch.setattr(gate, "run_delivery_gate", lambda _job: _Rapport(passed=False))
    monkeypatch.setattr(correction, "run_correction_loop", _interdit)
    job = _job()

    reponse = _poster(job)

    assert reponse.status_code == 200, reponse.content
    job.refresh_from_db()
    assert job.qa_status == QAStatus.BLOCKED


@pytest.mark.django_db
def test_un_dossier_non_termine_ne_se_recontrole_pas() -> None:
    """Un gate sans document complet n'a rien à juger (règle 1)."""
    job = _job(statut=JobStatus.RUNNING)

    reponse = _poster(job)

    assert reponse.status_code == 400


# ── Les CHECK de bloc deviennent réparables sur décision humaine ─────────────


@pytest.mark.django_db
def test_un_check_de_bloc_nomme_ses_chapitres() -> None:
    """Sans numéro, la note du relecteur ne peut rien réparer.

    Sur `cc0dfe14` (11/08/2026), sept CHECK bloquants nommaient leurs
    chapitres dans leur TEXTE — « non valide sur les chapitres [21, 22] » —
    et arrivaient avec `chapter_number: None`. Les notes étaient pourtant les
    plus actionnables du lot : « dédupliquer les deux entrées Xerfi du tableau
    21.2 ». Sept motifs précis, zéro routable.
    """
    from generation.checks_blocs import INCIDENT_TYPE_CHECK_BLOC
    from generation.gate import _check_blocs_evangeline
    from monitoring.models import IncidentSeverity, OperationalIncident

    job = _job()
    OperationalIncident.objects.create(
        title="CHECK FINAL non valide",
        severity=IncidentSeverity.HIGH,
        job=job,
        order=job.order,
        details={
            "type": INCIDENT_TYPE_CHECK_BLOC,
            "check": "FINAL", "bloc": "J", "intitule": "Contrôle final",
            "chapitres": [21, 22],
            "note_corrective": "Dédupliquer les deux entrées Xerfi.",
        },
    )

    failures = _check_blocs_evangeline(job)

    assert sorted(f.chapter_number for f in failures) == [21, 22]
    assert all("Xerfi" in f.detail for f in failures)


def test_le_chemin_automatique_ne_rejoue_jamais_un_check_de_bloc() -> None:
    """CONTRE-ÉPREUVE : la génération ne boucle pas dessus toute seule.

    Elle l'a déjà retenté une fois ; recommencer dépenserait sans rien
    garantir. Le manuel demande une reprise HUMAINE — c'est le bouton
    « corriger », et lui seul ouvre la porte.
    """
    from generation.correction import _feedback_by_chapter
    from generation.gate import GateFailure

    echec = GateFailure(
        check="check_bloc_non_resolu", chapter_number=21, detail="Note.",
    )

    assert _feedback_by_chapter((echec,)) == {}
    assert 21 in _feedback_by_chapter((echec,), inclure_les_checks=True)
