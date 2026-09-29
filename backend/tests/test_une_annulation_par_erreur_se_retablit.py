"""Une étude annulée PAR ERREUR se rétablit, sans rien effacer du journal.

## Le cas réel

29/09/2026, business plan `cb59cede` : tombé en échec au socle, il attendait
sa relance une fois le défaut corrigé et déployé. Il a été annulé par erreur.
L'annulation a rendu le crédit — c'est voulu —, et une étude remboursée ne se
relance plus (`debiter_pour_job`) — c'est voulu aussi. Il ne restait qu'à
repasser commande, questionnaire et pièces jointes compris.

## Ce que ce fichier verrouille

1. le rétablissement reprend EXACTEMENT le crédit rendu, par une écriture de
   plus, sans toucher au statut (une tâche encore active doit continuer à
   lire « annulé » et s'arrêter) : la relance repasse sans nouveau débit ;
2. il se décide sur le JOURNAL : un dossier repassé en échec par sa tâche
   après l'annulation se rétablit aussi ;
3. une seconde annulation, après rétablissement, rend encore le crédit — le
   remboursement vise le débit qui paie l'étude AUJOURD'HUI ;
4. une étude déjà payée se relance même quand le crédit restant est typé pour
   une autre étude ;
5. contre-épreuves (règle 6) : rien à rétablir sans remboursement ; pas de
   découvert si le crédit rendu a déjà servi ; pas deux rétablissements ; pas
   de rétablissement tant que le dossier a travaillé récemment ; une étude en
   cours ou livrée ne se rétablit pas ; la route exige le jeton.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from organisations import credits, inscription, liaison

pytestmark = pytest.mark.django_db

EMAIL = "eva@eclore-conseil.fr"


@pytest.fixture
def atelier() -> Any:
    """Une organisation à un crédit, une commande de business plan, par les vrais chemins."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from orders.models import Order
    from organisations.models import TypeMouvement

    ouverture = inscription.ouvrir_compte(
        raison_sociale="Éclore Conseil",
        email=EMAIL,
        mot_de_passe="un-mot-de-passe-solide-42",
        activer_abonnement=False,
    )
    organisation = ouverture.organisation
    credits.crediter(
        organisation, 1, motif="Geste", reference="geste-1",
        type_mouvement=TypeMouvement.GESTE,
    )
    offre = Offer.objects.create(
        name="Business plan",
        slug="bp-retablissement",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    commande = Order.objects.create(
        systeme_order_id="cmd-retablissement",
        customer=Customer.objects.get(email=EMAIL),
        offer=offre,
        organisation=organisation,
    )

    return SimpleNamespace(organisation=organisation, commande=commande)


def _job_paye_puis_annule(atelier: Any) -> Any:
    """Le parcours du 29/09/2026 : débité, en échec, puis annulé (crédit rendu)."""
    from catalog.models import DeliverableType
    from generation.models import GenerationJob, JobStatus

    job = GenerationJob.objects.create(
        order=atelier.commande,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        status=JobStatus.FAILED,
        error_message="Socle non établi : …",
    )
    autorise, _ = liaison.debiter_pour_job(job)
    assert autorise
    assert credits.solde(atelier.organisation) == 0

    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.CANCELLED)
    job.refresh_from_db()
    assert liaison.rembourser_job(job, motif="Étude annulée avant livraison")
    assert credits.solde(atelier.organisation) == 1
    assert liaison.credits_restitues(job)
    return job


# ── Le rétablissement ────────────────────────────────────────────────────────


def test_le_retablissement_reprend_le_credit_et_rouvre_la_relance(atelier: Any) -> None:
    """Le test qui échoue sur le code d'avant : `retablir_job` n'existait pas."""
    from generation.models import JobStatus

    job = _job_paye_puis_annule(atelier)

    fait, message = liaison.retablir_job(job, auteur="console")

    assert fait, message
    job.refresh_from_db()
    assert job.status == JobStatus.CANCELLED, "le statut ne bouge pas"
    assert credits.solde(atelier.organisation) == 0
    assert not liaison.credits_restitues(job)
    # La relance passe, et ne débite rien de plus.
    autorise, raison = liaison.debiter_pour_job(job)
    assert autorise, raison
    assert "déjà passé" in raison
    assert credits.solde(atelier.organisation) == 0


def test_le_journal_s_allonge_et_ne_se_corrige_pas(atelier: Any) -> None:
    from organisations.models import TypeMouvement

    job = _job_paye_puis_annule(atelier)
    mouvements = credits.portefeuille_de(atelier.organisation).mouvements
    avant = set(mouvements.values_list("id", flat=True))

    liaison.retablir_job(job, auteur="console")

    nouveaux = mouvements.exclude(id__in=avant)
    assert nouveaux.count() == 1
    reprise = nouveaux.get()
    assert reprise.type == TypeMouvement.DEBIT
    assert reprise.quantite == -1
    assert reprise.reference == liaison.reference_de_retablissement(job)
    assert reprise.auteur == "console"
    # Le reflet exact du remboursement : même marquage.
    remboursement = mouvements.get(type=TypeMouvement.REMBOURSEMENT)
    assert reprise.livrable == remboursement.livrable
    assert set(mouvements.exclude(id=reprise.id).values_list("id", flat=True)) == avant


def test_une_seconde_annulation_rend_encore_le_credit(atelier: Any) -> None:
    """Sans la référence en vigueur, le remboursement butait sur le premier."""
    from generation.models import GenerationJob, JobStatus

    job = _job_paye_puis_annule(atelier)
    liaison.retablir_job(job, auteur="console")
    assert credits.solde(atelier.organisation) == 0

    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.CANCELLED)
    job.refresh_from_db()

    assert liaison.rembourser_job(job, motif="Étude annulée avant livraison")
    assert credits.solde(atelier.organisation) == 1
    assert liaison.credits_restitues(job)
    autorise, _ = liaison.debiter_pour_job(job)
    assert not autorise, "une étude remboursée ne se relance toujours pas gratuitement"


# ── Contre-épreuves ──────────────────────────────────────────────────────────


def test_pas_deux_retablissements(atelier: Any) -> None:
    from generation.models import GenerationJob, JobStatus

    job = _job_paye_puis_annule(atelier)
    liaison.retablir_job(job, auteur="console")
    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.CANCELLED)
    job.refresh_from_db()
    liaison.rembourser_job(job, motif="Étude annulée avant livraison")

    fait, message = liaison.retablir_job(job, auteur="console")

    assert not fait
    assert "déjà été rétablie" in message
    assert credits.solde(atelier.organisation) == 1


def test_pas_de_decouvert_si_le_credit_rendu_a_deja_servi(atelier: Any) -> None:
    from generation.models import JobStatus

    job = _job_paye_puis_annule(atelier)
    credits.debiter(atelier.organisation, 1, reference="autre-etude", motif="Autre étude")
    assert credits.solde(atelier.organisation) == 0

    fait, message = liaison.retablir_job(job, auteur="console")

    assert not fait
    assert "déjà été utilisé" in message
    job.refresh_from_db()
    assert job.status == JobStatus.CANCELLED
    assert credits.solde(atelier.organisation) == 0
    assert liaison.credits_restitues(job)


def test_rien_a_retablir_sans_remboursement(atelier: Any) -> None:
    from catalog.models import DeliverableType
    from generation.models import GenerationJob, JobStatus

    job = GenerationJob.objects.create(
        order=atelier.commande,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        status=JobStatus.CANCELLED,
    )
    fait, message = liaison.retablir_job(job, auteur="console")
    assert not fait
    assert "rien à rétablir" in message
    assert credits.solde(atelier.organisation) == 1


def test_un_dossier_repasse_en_echec_apres_l_annulation_se_retablit(atelier: Any) -> None:
    """Annulé en file d'attente, puis sa tâche a démarré et écrit `failed`."""
    from generation.models import GenerationJob, JobStatus

    job = _job_paye_puis_annule(atelier)
    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.FAILED)
    job.refresh_from_db()

    fait, message = liaison.retablir_job(job, auteur="console")

    assert fait, message
    assert credits.solde(atelier.organisation) == 0
    assert liaison.debiter_pour_job(job)[0]


def test_pas_de_retablissement_tant_que_le_dossier_a_travaille_recemment(
    atelier: Any,
) -> None:
    """Une tâche peut encore finir son chapitre : la relance en lancerait une seconde."""
    from datetime import timedelta

    from django.utils import timezone

    from generation.models import GenerationJob

    job = _job_paye_puis_annule(atelier)
    GenerationJob.objects.filter(pk=job.pk).update(started_at=timezone.now())
    job.refresh_from_db()

    fait, message = liaison.retablir_job(job, auteur="console")

    assert not fait
    assert "une tâche peut encore tourner" in message
    assert credits.solde(atelier.organisation) == 1

    GenerationJob.objects.filter(pk=job.pk).update(
        started_at=timezone.now() - timedelta(minutes=30)
    )
    job.refresh_from_db()
    assert liaison.retablir_job(job, auteur="console")[0]


def test_une_etude_payee_se_relance_meme_si_le_credit_restant_est_type(
    atelier: Any,
) -> None:
    """Acheteuse à l'unité d'un business plan ET d'une étude de concurrence.

    Le seul droit restant est celui de l'étude de concurrence : la relance du
    business plan, déjà payé, était refusée (« ne couvre pas cette étude »).
    """
    from catalog.models import DeliverableType
    from generation.models import GenerationJob, JobStatus
    from organisations.models import TypeMouvement

    credits.debiter(atelier.organisation, 1, reference="geste-consomme", motif="Autre")
    for livrable in (DeliverableType.BUSINESS_PLAN, DeliverableType.COMPETITOR_STUDY):
        credits.crediter(
            atelier.organisation, 1, motif=f"Achat {livrable}", reference=f"achat-{livrable}",
            type_mouvement=TypeMouvement.ACHAT, livrable=livrable,
        )
    job = GenerationJob.objects.create(
        order=atelier.commande,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        status=JobStatus.FAILED,
    )
    assert liaison.debiter_pour_job(job)[0]
    assert credits.droits_par_livrable(atelier.organisation) == {
        DeliverableType.COMPETITOR_STUDY: 1
    }

    autorise, raison = liaison.debiter_pour_job(job)

    assert autorise, raison
    assert credits.solde(atelier.organisation) == 1


@pytest.mark.parametrize("statut", ["done", "running", "pending"])
def test_une_etude_non_annulee_ne_se_retablit_pas(atelier: Any, statut: str) -> None:
    from generation.models import GenerationJob

    job = _job_paye_puis_annule(atelier)
    GenerationJob.objects.filter(pk=job.pk).update(status=statut)
    job.refresh_from_db()

    fait, _ = liaison.retablir_job(job, auteur="console")

    assert not fait
    assert credits.solde(atelier.organisation) == 1


# ── La route de la console ───────────────────────────────────────────────────


def test_la_route_retablit_puis_la_relance_repart(
    client_admin: Any, atelier: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from generation.tasks import run_generation_job_task

    lancees: list[str] = []
    monkeypatch.setattr(
        run_generation_job_task, "delay", lambda job_id, **_k: lancees.append(job_id)
    )
    job = _job_paye_puis_annule(atelier)

    reponse = client_admin.post(f"/api/dashboard/jobs/{job.id}/retablir/")

    assert reponse.status_code == 200, reponse.content
    assert "remboursement" in reponse.json()["message"]
    assert credits.solde(atelier.organisation) == 0

    relance = client_admin.post(f"/api/dashboard/jobs/{job.id}/relaunch/")

    assert relance.status_code == 202, relance.content
    assert lancees == [str(job.id)]
    job.refresh_from_db()
    autorise, raison = liaison.debiter_pour_job(job)
    assert autorise, raison
    assert credits.solde(atelier.organisation) == 0, "la relance ne débite rien de plus"


def test_la_route_dit_son_refus_en_clair(client_admin: Any, atelier: Any) -> None:
    job = _job_paye_puis_annule(atelier)
    credits.debiter(atelier.organisation, 1, reference="autre-etude", motif="Autre étude")

    reponse = client_admin.post(f"/api/dashboard/jobs/{job.id}/retablir/")

    assert reponse.status_code == 409
    assert "déjà été utilisé" in reponse.json()["error"]


def test_la_route_exige_le_jeton(client: Any, atelier: Any) -> None:
    job = _job_paye_puis_annule(atelier)

    reponse = client.post(f"/api/dashboard/jobs/{job.id}/retablir/")

    assert reponse.status_code in (401, 403)
    assert credits.solde(atelier.organisation) == 1


def test_la_fiche_dit_si_le_credit_a_ete_rendu(client_admin: Any, atelier: Any) -> None:
    """C'est ce fait, lu dans le journal, qui choisit entre Rétablir et Relancer."""
    job = _job_paye_puis_annule(atelier)
    url = f"/api/dashboard/jobs/{job.id}/"

    assert client_admin.get(url).json()["credits_restitues"] is True
    liaison.retablir_job(job, auteur="console")
    assert client_admin.get(url).json()["credits_restitues"] is False
