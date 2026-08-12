"""Refaire un livrable ne doit pas dépendre d'un copier-coller.

Le 12/08/2026, le business plan `2a8872d0` s'est terminé sans son analyse
concurrentielle : son socle ne portait aucun concurrent. Le refaire proprement
demandait un dossier NEUF — le sien avait déjà dépensé 4,19 € sur un plafond
de 5,50 €, et le plafond appliqué est `min(budget du dossier, table du
livrable)`, donc infranchissable.

Or un dossier neuf demande le brief, et les réponses de la cliente vivaient
dans `IntakeSubmission.normalized_variables`, qu'aucune route n'exposait. Le
seul recours : les recopier à la main depuis l'administration Django, une
vingtaine de champs, avec le risque de ne pas reproduire à l'identique le
brief d'une cliente.

Refaire un livrable est une opération NORMALE — un défaut corrigé, un dossier
à reprendre. Elle ne doit pas reposer sur la patience de celui qui recopie.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def dossier_avec_brief():  # type: ignore[no-untyped-def]
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="BP", slug="test-brief",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email="brief@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-brief", customer=client, offer=offre,
    )
    IntakeSubmission.objects.create(
        order=commande,
        source=IntakeSource.TALLY,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "conseil aux dirigeants",
            "PAYS": "France",
            "ZONE": "Lyon et sa métropole",
            "PROJET": "Cabinet de conseil en structuration",
            "CA_PREVISIONNEL": "je vise 8 abonnés puis 20",
        },
        raw_payload={"champ_interne_42": "métadonnée de collecte"},
        missing_fields=["EBE_PREVISIONNEL"],
    )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN,
    )


@pytest.mark.django_db
def test_le_brief_se_relit_en_entier(client_admin, dossier_avec_brief) -> None:  # type: ignore[no-untyped-def]
    """Les réponses telles qu'elles ont produit le livrable, sans retouche."""
    reponse = client_admin.get(f"/api/dashboard/jobs/{dossier_avec_brief.id}/brief/")

    assert reponse.status_code == 200
    charge = json.loads(reponse.content)
    assert charge["variables"]["SECTEUR"] == "conseil aux dirigeants"
    assert charge["variables"]["ZONE"] == "Lyon et sa métropole"
    # Y COMPRIS la réponse en texte libre : c'est elle qu'il faut relire pour
    # comprendre pourquoi un contrôle a comparé un montant à de la prose.
    assert charge["variables"]["CA_PREVISIONNEL"] == "je vise 8 abonnés puis 20"
    assert charge["missing_fields"] == ["EBE_PREVISIONNEL"]
    assert charge["customer_email"] == "brief@test.local"


@pytest.mark.django_db
def test_la_charge_brute_ne_sort_pas(client_admin, dossier_avec_brief) -> None:  # type: ignore[no-untyped-def]
    """On expose ce qui sert, pas tout ce qu'on a.

    `raw_payload` porte des métadonnées de collecte — identifiants de champs,
    horodatages, parfois l'adresse de l'envoyeur — dont relancer une
    génération n'a aucun besoin.
    """
    reponse = client_admin.get(f"/api/dashboard/jobs/{dossier_avec_brief.id}/brief/")

    assert "champ_interne_42" not in reponse.content.decode("utf-8")


@pytest.mark.django_db
def test_un_dossier_sans_soumission_le_dit(client_admin, dossier_avec_brief) -> None:  # type: ignore[no-untyped-def]
    """Règle 1 : un brief introuvable n'est pas un brief vide.

    Rendre `{}` laisserait croire que la cliente n'a rien répondu, et on
    relancerait une génération sur un brief inventé.
    """
    from intake.models import IntakeSubmission

    IntakeSubmission.objects.all().delete()
    reponse = client_admin.get(f"/api/dashboard/jobs/{dossier_avec_brief.id}/brief/")

    assert reponse.status_code == 404
    assert "Aucune soumission" in json.loads(reponse.content)["error"]


@pytest.mark.django_db
def test_un_identifiant_inconnu_ne_casse_pas(client_admin) -> None:  # type: ignore[no-untyped-def]
    """Un UUID valide mais absent, et une chaîne qui n'est pas un UUID."""
    assert client_admin.get(
        "/api/dashboard/jobs/8f14e45f-ceea-467a-9f8b-000000000000/brief/"
    ).status_code == 404
    assert client_admin.get("/api/dashboard/jobs/pas-un-uuid/brief/").status_code == 400


@pytest.mark.django_db
def test_la_route_brief_ne_masque_pas_le_detail(client_admin, dossier_avec_brief) -> None:  # type: ignore[no-untyped-def]
    """CONTRE-ÉPREUVE d'ordonnancement : `<str:job_id>` avalerait « id/brief ».

    Django retient la PREMIÈRE route qui correspond. Déclarée après
    `jobs/<job_id>/`, la nouvelle route ne serait jamais atteinte — et
    déclarée avant, elle ne doit pas empêcher le détail de répondre.
    """
    reponse = client_admin.get(f"/api/dashboard/jobs/{dossier_avec_brief.id}/")

    assert reponse.status_code == 200
    assert "chapters" in json.loads(reponse.content)
