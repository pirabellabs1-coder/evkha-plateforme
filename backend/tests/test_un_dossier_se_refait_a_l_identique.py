"""Refaire un dossier ne doit pas appauvrir le brief en silence.

## Le défaut mesuré

Business plan `2a8872d0`, 12/08/2026. Socle sans concurrents, chapitre 7 mort
cinq fois, 4,19 € dépensés sur un plafond de 5,50 €. Le dossier est
économiquement clos : le plafond appliqué est `min(budget du dossier, table du
livrable)`, un minimum qu'aucune valeur saisie ne franchit.

Restait la génération manuelle du dashboard. Sur le brief RÉEL de ce dossier,
elle aurait gardé 18 variables sur 28 : dix disparaissaient, soit près de
6 600 signes de réponses client — `RESUME_EXECUTIF` (1 513 signes),
`OFFRE` (1 233), `PARCOURS_PORTEUR` (941), `STRATEGIE_COMMERCIALE`,
`MOTIVATIONS`, `TENDANCES_MARCHE`, `DATE_CREATION`, `TABLEAUX_FINANCIERS`,
`PORTEUR_PROJET`, `CONTACT_PRO`.

Pour un business plan dont le chapitre 1 s'appelle « Résumé exécutif » et le
chapitre 2 « Présentation du porteur de projet », c'est rédhibitoire. Et le
filtre est SILENCIEUX : on aurait payé une génération pour un document plus
pauvre que celui qu'on répare.

## Pourquoi recopier plutôt que réconcilier

Le questionnaire de l'espace client est plus riche que la liste qu'accepte la
génération manuelle. Les deux ont divergé parce qu'aucun chemin ne les
confrontait. On ne les aligne pas ici : on recopie le brief VERBATIM, ce qui
rend la question sans objet — la soumission d'origine est la seule source de
ce que le client a répondu (règle 5).
"""
from __future__ import annotations

import json

import pytest

#: Un brief qui déborde largement la liste de la génération manuelle, comme
#: celui d'une vraie cliente.
BRIEF_RICHE = {
    "SECTEUR": "SaaS / intelligence artificielle appliquée à l'entrepreneuriat",
    "PAYS": "France et pays francophones",
    "ZONE": "France, DOM-TOM, puis marchés francophones",
    "PROJET": "Développement de la plateforme SaaS",
    # Les dix que le filtre de la génération manuelle laissait tomber.
    "RESUME_EXECUTIF": "Ambition : faire de la plateforme une référence française.",
    "PORTEUR_PROJET": "Fondatrice, quinze ans d'entrepreneuriat.",
    "PARCOURS_PORTEUR": "Consultante spécialisée dans la création d'entreprise.",
    "OFFRE": "Livrables à l'unité en B2C, abonnements en B2B.",
    "MOTIVATIONS": "Après plusieurs années d'accompagnement de créateurs.",
    "TENDANCES_MARCHE": "Développement rapide de l'IA générative.",
    "STRATEGIE_COMMERCIALE": "Référencement naturel et contenus.",
    "TABLEAUX_FINANCIERS": "Verticales : B2C livrables, SaaS B2B abonnements.",
    "DATE_CREATION": "Entreprise déjà en activité.",
    "CONTACT_PRO": "contact@exemple.fr",
}


@pytest.fixture
def dossier_epuise():  # type: ignore[no-untyped-def]
    """Un dossier terminé, budget consommé, avec un brief riche."""
    from decimal import Decimal

    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob, JobStatus
    from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="BP", slug="test-reprise",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email="reprise@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-reprise", customer=client, offer=offre,
    )
    IntakeSubmission.objects.create(
        order=commande,
        source=IntakeSource.MANUAL,
        status=IntakeStatus.NORMALIZED,
        normalized_variables=dict(BRIEF_RICHE),
    )
    return GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        status=JobStatus.FAILED,
        total_cost_eur=Decimal("4.1864"),
        budget_eur=Decimal("4.0000"),
    )


@pytest.mark.django_db
def test_la_reprise_recopie_le_brief_en_entier(
    client_admin, dossier_epuise, monkeypatch  # type: ignore[no-untyped-def]
) -> None:
    """LE test : aucune des dix variables perdues ne doit disparaître."""
    from generation import tasks
    from intake.models import IntakeSubmission

    monkeypatch.setattr(tasks.run_generation_job_task, "delay", lambda *a, **k: None)
    reponse = client_admin.post(
        f"/api/dashboard/jobs/{dossier_epuise.id}/regenerer/"
    )

    assert reponse.status_code == 202, reponse.content
    charge = json.loads(reponse.content)
    assert charge["variables_reprises"] == len(BRIEF_RICHE)

    reprise = IntakeSubmission.objects.exclude(order=dossier_epuise.order).get()
    assert reprise.normalized_variables == BRIEF_RICHE


@pytest.mark.django_db
def test_le_nouveau_dossier_repart_avec_un_budget_neuf(
    client_admin, dossier_epuise, monkeypatch  # type: ignore[no-untyped-def]
) -> None:
    """Le dossier d'origine avait consommé son plafond : celui-ci part de zéro."""
    from decimal import Decimal

    from generation import tasks
    from generation.cost import PLAFOND_PAR_LIVRABLE
    from generation.models import GenerationJob

    monkeypatch.setattr(tasks.run_generation_job_task, "delay", lambda *a, **k: None)
    reponse = client_admin.post(
        f"/api/dashboard/jobs/{dossier_epuise.id}/regenerer/"
    )
    nouveau = GenerationJob.objects.get(id=json.loads(reponse.content)["job_id"])

    assert nouveau.total_cost_eur == Decimal("0")
    assert nouveau.budget_eur == PLAFOND_PAR_LIVRABLE[nouveau.deliverable_type]


@pytest.mark.django_db
def test_le_dossier_d_origine_n_est_pas_touche(
    client_admin, dossier_epuise, monkeypatch  # type: ignore[no-untyped-def]
) -> None:
    """CONTRE-ÉPREUVE comptable : les 4,19 € restent inscrits là où ils ont eu lieu.

    Les effacer ferait mentir le grand livre — `total_cost_eur` EST la
    comptabilité de ce projet, il n'y a pas de registre séparé.
    """
    from decimal import Decimal

    from generation import tasks

    monkeypatch.setattr(tasks.run_generation_job_task, "delay", lambda *a, **k: None)
    client_admin.post(f"/api/dashboard/jobs/{dossier_epuise.id}/regenerer/")
    dossier_epuise.refresh_from_db()

    assert dossier_epuise.total_cost_eur == Decimal("4.1864")


@pytest.mark.django_db
def test_la_reprise_passe_par_l_offre_manuelle(
    client_admin, dossier_epuise, monkeypatch  # type: ignore[no-untyped-def]
) -> None:
    """Une reprise est à NOS frais : elle ne consomme aucun crédit du client.

    Et son identifiant de commande porte la filiation, sans quoi un dossier
    repris serait indiscernable d'une commande ordinaire — personne ne saurait
    dans six mois pourquoi ce client a deux business plans.
    """
    from generation import tasks
    from generation.models import GenerationJob

    monkeypatch.setattr(tasks.run_generation_job_task, "delay", lambda *a, **k: None)
    reponse = client_admin.post(
        f"/api/dashboard/jobs/{dossier_epuise.id}/regenerer/"
    )
    nouveau = GenerationJob.objects.get(id=json.loads(reponse.content)["job_id"])

    assert nouveau.order.offer.slug == "manuel-business-plan"
    assert nouveau.order.systeme_order_id.startswith("reprise-")
    assert str(dossier_epuise.id)[:8] in nouveau.order.systeme_order_id
    assert nouveau.order.customer_id == dossier_epuise.order.customer_id


@pytest.mark.django_db
def test_un_dossier_sans_brief_est_refuse(
    client_admin, dossier_epuise  # type: ignore[no-untyped-def]
) -> None:
    """Règle 1 : une reprise sur un brief vide produirait un document inventé."""
    from intake.models import IntakeSubmission

    IntakeSubmission.objects.all().delete()
    reponse = client_admin.post(
        f"/api/dashboard/jobs/{dossier_epuise.id}/regenerer/"
    )

    assert reponse.status_code == 409
    assert "brief" in json.loads(reponse.content)["error"]


@pytest.mark.django_db
def test_un_dossier_qui_travaille_ne_se_refait_pas(
    client_admin, dossier_epuise  # type: ignore[no-untyped-def]
) -> None:
    """CONTRE-ÉPREUVE : deux générations pour un client, c'est payer deux fois."""
    from django.utils import timezone

    from generation.models import JobStatus

    dossier_epuise.status = JobStatus.RUNNING
    dossier_epuise.started_at = timezone.now()
    dossier_epuise.save(update_fields=["status", "started_at"])

    reponse = client_admin.post(
        f"/api/dashboard/jobs/{dossier_epuise.id}/regenerer/"
    )

    assert reponse.status_code == 409


@pytest.mark.django_db
def test_la_lecture_seule_ne_declenche_rien(
    client_admin, dossier_epuise  # type: ignore[no-untyped-def]
) -> None:
    """Une reprise coûte de l'argent : elle ne part JAMAIS sur un GET.

    Un lien visité par erreur, un préchargement de navigateur, un robot
    d'indexation — et une génération démarre.
    """
    assert client_admin.get(
        f"/api/dashboard/jobs/{dossier_epuise.id}/regenerer/"
    ).status_code == 405
