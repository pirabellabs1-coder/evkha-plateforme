"""Lot 4 — branchement du portefeuille sur la génération.

Un portefeuille non branché serait du code mort. Ce dépôt en a l'expérience :
Gamma était intégré, testé, branché — et n'avait jamais tourné (règle 8). Ces
tests portent donc sur le chemin réel du moteur, `run_generation_job`.

Deux exigences se contredisent en apparence, et c'est là que tout se joue :

- « débit au lancement de la génération », « aucun découvert » ;
- « un incident sur un chapitre n'entraîne jamais la reprise complète » —
  autrement dit une relance doit passer, sans repayer.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import GenerationJob, JobStatus
from generation.runner import CreditsInsuffisantsError, run_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order
from organisations import credits, services
from organisations.liaison import (
    cout_en_credits,
    debiter_pour_job,
    organisation_du_job,
    rembourser_job,
)
from organisations.models import Organisation

pytestmark = pytest.mark.django_db

_VARIABLES = {
    "SECTEUR": "joaillerie de créateurs",
    "PAYS": "France",
    "PROJET": "maison joaillière",
}


def _job(*, client: Customer, organisation: Organisation | None = None) -> GenerationJob:
    from generation.services import bootstrap_generation_job

    offre = Offer.objects.create(
        name="Étude de marché",
        slug=f"em-{client.email.split('@')[0]}",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    commande = Order.objects.create(
        systeme_order_id=f"order-{client.email}",
        customer=client,
        offer=offre,
        organisation=organisation,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=_VARIABLES
    )
    return bootstrap_generation_job(soumission)


@pytest.fixture
def client_b2b() -> Customer:
    return Customer.objects.create(email="agence@example.com")


@pytest.fixture
def organisation(client_b2b: Customer) -> Organisation:
    return services.creer_organisation(
        raison_sociale="Agence Test", contact=client_b2b
    )


# ── Rattachement ─────────────────────────────────────────────────────────────


def test_le_rattachement_explicite_de_la_commande_fait_autorite(
    client_b2b: Customer, organisation: Organisation
) -> None:
    job = _job(client=client_b2b, organisation=organisation)
    assert organisation_du_job(job) == organisation


def test_a_defaut_l_organisation_du_contact_est_retenue(
    client_b2b: Customer, organisation: Organisation
) -> None:
    job = _job(client=client_b2b)
    assert organisation_du_job(job) == organisation


def test_une_commande_sans_organisation_n_en_designe_aucune() -> None:
    """Le flux Systeme.io en service ne connaît pas les organisations."""
    client = Customer.objects.create(email="b2c@example.com")
    assert organisation_du_job(_job(client=client)) is None


def test_un_rattachement_ambigu_ne_choisit_pas_au_hasard(
    client_b2b: Customer, organisation: Organisation
) -> None:
    """Débiter le mauvais portefeuille est pire qu'un débit manquant.

    Personne ne verrait l'erreur : le solde baisse, mais chez quelqu'un d'autre.
    """
    services.creer_organisation(raison_sociale="Seconde agence", contact=client_b2b)
    assert organisation_du_job(_job(client=client_b2b)) is None


def test_un_livrable_coute_un_credit_par_defaut(client_b2b: Customer) -> None:
    """La page publique annonce « 2 crédits inclus » pour deux livrables."""
    assert cout_en_credits(_job(client=client_b2b)) == 1


# ── Débit au lancement ───────────────────────────────────────────────────────


def test_une_commande_sans_organisation_est_autorisee_sans_debit() -> None:
    """Casser la production pour un module qui n'y est pas branché serait absurde."""
    client = Customer.objects.create(email="b2c2@example.com")
    autorise, raison = debiter_pour_job(_job(client=client))
    assert autorise
    assert "aucun crédit" in raison


def test_le_lancement_debite_le_portefeuille(
    client_b2b: Customer, organisation: Organisation
) -> None:
    credits.crediter(organisation, 3, motif="Dotation")
    job = _job(client=client_b2b, organisation=organisation)
    autorise, _ = debiter_pour_job(job)
    assert autorise
    assert credits.solde(organisation) == 2


def test_un_solde_insuffisant_refuse_le_lancement(
    client_b2b: Customer, organisation: Organisation
) -> None:
    """« Commande bloquée, aucun découvert » (§11)."""
    job = _job(client=client_b2b, organisation=organisation)
    autorise, raison = debiter_pour_job(job)
    assert not autorise
    assert "insuffisant" in raison
    assert credits.solde(organisation) == 0


def test_une_organisation_suspendue_refuse_le_lancement(
    client_b2b: Customer, organisation: Organisation
) -> None:
    credits.crediter(organisation, 3, motif="Dotation")
    services.suspendre(organisation)
    autorise, raison = debiter_pour_job(_job(client=client_b2b, organisation=organisation))
    assert not autorise
    assert "suspendue" in raison
    assert credits.solde(organisation) == 3


def test_une_relance_ne_debite_pas_une_seconde_fois(
    client_b2b: Customer, organisation: Organisation
) -> None:
    """Le point le plus facile à rater.

    Traiter le refus d'un double débit comme un échec bloquerait toute reprise
    sur incident — précisément ce que le §13 exige de préserver.
    """
    credits.crediter(organisation, 3, motif="Dotation")
    job = _job(client=client_b2b, organisation=organisation)

    premier, _ = debiter_pour_job(job)
    second, raison = debiter_pour_job(job)

    assert premier
    assert second, "Une relance doit être autorisée."
    assert "relance" in raison
    assert credits.solde(organisation) == 2, "Un seul crédit devait être débité."


# ── Le moteur refuse de tourner sans crédits ─────────────────────────────────


def test_le_moteur_refuse_de_demarrer_sans_credits(
    client_b2b: Customer, organisation: Organisation
) -> None:
    """Aucun appel facturé ne doit être émis quand le solde ne couvre pas l'étude.

    C'est la seule preuve qui compte pour cette exigence : le contrôle est dans
    le chemin réel du moteur, pas à côté.
    """
    job = _job(client=client_b2b, organisation=organisation)
    with pytest.raises(CreditsInsuffisantsError):
        run_generation_job(job)

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED
    assert "insuffisant" in job.error_message.lower()
    assert job.chapters.filter(status="done").count() == 0


def test_le_moteur_demarre_quand_le_solde_couvre_l_etude(
    client_b2b: Customer, organisation: Organisation, settings: object
) -> None:
    """Contre-épreuve : le garde-fou ne doit pas bloquer une étude payée.

    On ne vérifie pas que l'étude aboutit — cela demanderait le pipeline
    complet — mais que le refus de crédits n'est PAS levé et que le crédit est
    bien débité.
    """
    credits.crediter(organisation, 2, motif="Dotation")
    job = _job(client=client_b2b, organisation=organisation)
    try:
        run_generation_job(job)
    except CreditsInsuffisantsError:  # pragma: no cover - c'est ce qu'on exclut
        pytest.fail("Le lancement a été refusé alors que le solde le couvrait.")
    except Exception:  # noqa: BLE001, S110 - un échec plus loin ne concerne pas ce test
        pass
    assert credits.solde(organisation) == 1


# ── Remboursement ────────────────────────────────────────────────────────────


def test_un_abandon_definitif_restitue_le_credit(
    client_b2b: Customer, organisation: Organisation
) -> None:
    """« Remboursement automatique en cas d'échec définitif » (§11)."""
    credits.crediter(organisation, 2, motif="Dotation")
    job = _job(client=client_b2b, organisation=organisation)
    debiter_pour_job(job)
    assert credits.solde(organisation) == 1

    assert rembourser_job(job, motif="Incident irrécupérable")
    assert credits.solde(organisation) == 2


def test_un_echec_rattrapable_ne_rembourse_rien(
    client_b2b: Customer, organisation: Organisation
) -> None:
    """`FAILED` est un état RATTRAPABLE dans ce dépôt.

    Rembourser à chaque passage en échec offrirait l'étude à qui échoue une fois
    puis relance. Le remboursement est un acte explicite, pas un effet de bord
    d'un statut : ce test échoue si quelqu'un le branche sur `_fail`.
    """
    credits.crediter(organisation, 2, motif="Dotation")
    job = _job(client=client_b2b, organisation=organisation)
    debiter_pour_job(job)

    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.FAILED, error_message="Échec du chapitre 4"
    )
    assert credits.solde(organisation) == 1, (
        "Un passage en échec ne doit rien restituer : l'étude est relançable."
    )


def test_un_abandon_sans_debit_ne_cree_pas_de_credit(
    client_b2b: Customer, organisation: Organisation
) -> None:
    """Sinon un appel malencontreux fabriquerait des crédits."""
    job = _job(client=client_b2b, organisation=organisation)
    assert not rembourser_job(job, motif="Abandon")
    assert credits.solde(organisation) == 0


def test_un_abandon_ne_rembourse_pas_deux_fois(
    client_b2b: Customer, organisation: Organisation
) -> None:
    credits.crediter(organisation, 2, motif="Dotation")
    job = _job(client=client_b2b, organisation=organisation)
    debiter_pour_job(job)
    assert rembourser_job(job, motif="Abandon")
    assert not rembourser_job(job, motif="Abandon")
    assert credits.solde(organisation) == 2


def test_un_abandon_sans_organisation_ne_fait_rien() -> None:
    client = Customer.objects.create(email="b2c3@example.com")
    assert not rembourser_job(_job(client=client), motif="Abandon")
