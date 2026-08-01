"""La fiche client de l'administration dit la vérité sur un abonné B2B.

`customer_detail` ne lisait que l'ancien flux Systeme.io : les abonnements du
modèle `Subscription` et les tickets de crédit comptés depuis les commandes. Il
ignorait `Organisation`, son abonnement et son portefeuille — c'est-à-dire tout
le lot 4.

Conséquence mesurée sur le déploiement : un abonné disposant d'une formule
Structure et de dix crédits s'affichait **« Aucun abonnement actif · 0 crédit(s)
disponible(s) »**. Un chiffre faux dans le sens le plus dangereux : un
exploitant en conclut que le client n'a rien payé, et agit en conséquence.

Deux systèmes de crédits coexistent bel et bien, et les réunir est un chantier
à part. Mais un écran qui n'en connaît qu'un ne doit pas afficher zéro pour
l'autre — il doit afficher les deux.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from customers.models import Customer, CustomerType
from organisations import credits, services
from organisations.models import Formule, ReportCredits, TypeMouvement
from tests.conftest import JETON_ADMIN

pytestmark = pytest.mark.django_db

@pytest.fixture
def client() -> Client:
    """Redefinit la fixture de pytest-django pour TOUT ce module.

    Chaque route testee ici vit sous `/api/dashboard/`, c'est-a-dire derriere
    la garde d'administration. Le client de test presente donc le jeton, comme
    le fera le navigateur de l'equipe. Sans cela ces tests ne passaient que
    grace au contournement de developpement lu dans le `.env` local — une
    porte qu'on vient justement de fermer.
    """
    return Client(HTTP_AUTHORIZATION=f"Bearer {JETON_ADMIN}")



@pytest.fixture
def formule() -> Formule:
    return Formule.objects.create(
        code="structure",
        libelle="Structure",
        credits_par_echeance=10,
        prix_mensuel_cents=42_900,
        devise="EUR",
        report_credits=ReportCredits.AUCUN,
        plafond_report=0,
        regenerations_offertes=1,
        active=True,
    )


def _fiche(client: Client, contact: Customer) -> dict[str, Any]:
    reponse = client.get(f"/api/dashboard/customers/{contact.id}/")
    assert reponse.status_code == 200, reponse.content
    charge: dict[str, Any] = json.loads(reponse.content)
    return charge


def test_un_abonne_b2b_voit_sa_formule_et_son_solde(
    client: Client, formule: Formule
) -> None:
    """LE test du défaut. Sans le correctif, `organisation` n'existe pas."""
    contact = Customer.objects.create(
        email="abonne@exemple.fr", customer_type=CustomerType.B2B
    )
    organisation = services.creer_organisation(
        raison_sociale="Pirabel Labs", contact=contact
    )
    services.souscrire(organisation, formule)

    fiche = _fiche(client, contact)

    assert fiche["organisation"] is not None
    assert fiche["organisation"]["raison_sociale"] == "Pirabel Labs"
    assert fiche["organisation"]["formule"] == "Structure"
    assert fiche["organisation"]["solde"] == 10
    assert fiche["organisation"]["role"] == "proprietaire"


def test_le_solde_distingue_l_abonnement_de_l_achat(
    client: Client, formule: Formule
) -> None:
    """L'exploitant doit voir ce qui expirera et ce qui restera."""
    contact = Customer.objects.create(email="mixte@exemple.fr")
    organisation = services.creer_organisation(
        raison_sociale="Mixte", contact=contact
    )
    services.souscrire(organisation, formule)
    credits.crediter(
        organisation, 4, motif="Achat de 4 crédits", type_mouvement=TypeMouvement.ACHAT
    )

    detail = _fiche(client, contact)["organisation"]

    assert detail["solde"] == 14
    assert detail["solde_abonnement"] == 10
    assert detail["solde_achete"] == 4


def test_sans_formule_l_organisation_apparait_quand_meme(client: Client) -> None:
    """Une organisation sans abonnement n'est pas une absence d'organisation.

    Renvoyer `null` ici ramènerait exactement le message trompeur d'origine.
    """
    contact = Customer.objects.create(email="sansformule@exemple.fr")
    services.creer_organisation(raison_sociale="En attente", contact=contact)

    detail = _fiche(client, contact)["organisation"]

    assert detail is not None
    assert detail["raison_sociale"] == "En attente"
    assert detail["formule"] is None
    assert detail["solde"] == 0


def test_un_client_b2c_n_a_pas_d_organisation(client: Client) -> None:
    """Contre-épreuve : le correctif ne doit pas inventer une organisation.

    Sans ce test, renvoyer un objet vide pour tout le monde ferait passer le
    premier test tout en cassant l'affichage des clients B2C.
    """
    contact = Customer.objects.create(
        email="particulier@exemple.fr", customer_type=CustomerType.B2C
    )

    fiche = _fiche(client, contact)

    assert fiche["organisation"] is None
    # L'ancien flux reste décrit, il n'est pas remplacé.
    assert "subscriptions" in fiche
    assert "credits_available" in fiche


def test_un_membre_revoque_ne_rattache_plus_le_contact(
    client: Client, formule: Formule
) -> None:
    """Un accès révoqué ne doit pas continuer d'afficher les crédits d'autrui."""
    from django.utils import timezone

    from organisations.models import MembreOrganisation

    contact = Customer.objects.create(email="parti@exemple.fr")
    organisation = services.creer_organisation(raison_sociale="Ancienne", contact=contact)
    services.souscrire(organisation, formule)
    MembreOrganisation.objects.filter(customer=contact).update(
        revoque_le=timezone.now()
    )

    assert _fiche(client, contact)["organisation"] is None
