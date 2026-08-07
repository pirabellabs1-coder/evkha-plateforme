"""Le tableau de bord ne savait pas dire ce qui était réellement rentré.

Il affichait un revenu *contractuel* — la somme des abonnements actifs — et le
disait honnêtement : « aucun prestataire de paiement n'étant branché, les
encaissements réels ne sont pas connus ». C'était vrai jusqu'au 07/08/2026.

Stripe est désormais branché, et un premier paiement a été encaissé pour de
bon. Mais le webhook appliquait l'échéance sans garder trace du montant : la
somme réellement perçue restait introuvable côté plateforme, et l'avertissement
du tableau de bord était devenu faux — ce qui est pire que l'absence
d'information, parce qu'on ne cherche pas ce qu'on croit impossible.

Ce que ces tests tiennent :

1. une facture payée laisse une ligne, avec son montant et sa date ;
2. **elle n'en laisse qu'une**, même rejouée — Stripe réémet ses événements
   pendant trois jours, et compter deux fois un paiement gonflerait la recette
   sans que rien ne le signale ;
3. le contractuel et l'encaissé restent SÉPARÉS ;
4. un défaut de comptabilité n'empêche pas un client d'être doté.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from organisations.models import Encaissement

from .aides_abonnement import formule_de_test


def _organisation() -> tuple[Any, Any]:
    """Une organisation et sa formule, prêtes à recevoir un abonnement."""
    from customers.models import Customer
    from organisations import services

    formule = formule_de_test()
    contact = Customer.objects.create(email="encaissements@test.local")
    organisation = services.creer_organisation(
        raison_sociale="Cliente de test", contact=contact
    )
    return organisation, formule


def _facture(
    *, reference: str = "in_test_1", montant: int = 18900, abonnement: str = "sub_1"
) -> dict[str, Any]:
    """Une facture Stripe réduite aux champs que le code lit."""
    return {
        "id": reference,
        "amount_paid": montant,
        "currency": "eur",
        "subscription": abonnement,
        "status_transitions": {"paid_at": 1_754_500_000},
        "created": 1_754_500_000,
    }


@pytest.mark.django_db
def test_une_facture_payee_laisse_une_trace() -> None:
    """Sur le code d'avant, ce paiement ne laissait AUCUNE ligne en base."""
    from paiement import abonnements

    organisation, formule = _organisation()
    abonnement, _ = abonnements.assurer_abonnement(
        organisation_id=str(organisation.id),
        formule_code=formule.code,
        reference_stripe="sub_1",
    )

    abonnements._enregistrer_l_encaissement(_facture(), abonnement)

    encaissement = Encaissement.objects.get()
    assert encaissement.montant_cents == 18_900
    assert encaissement.devise == "EUR"
    assert encaissement.organisation_id == organisation.id
    assert encaissement.formule_code == formule.code
    assert encaissement.reference_facture == "in_test_1"
    # La date vient de Stripe, pas de notre horloge : un evenement rejoue le
    # lendemain ne doit pas dater le paiement du lendemain.
    assert encaissement.paye_le == datetime.fromtimestamp(1_754_500_000, tz=UTC)


@pytest.mark.django_db
def test_une_facture_rejouee_ne_compte_qu_une_fois() -> None:
    """Stripe réémet ses événements pendant trois jours en cas d'erreur.

    Sans garde, le même paiement serait compté deux fois — et un chiffre
    d'affaires gonflé ne se voit pas : il ressemble à une bonne nouvelle.
    """
    from paiement import abonnements

    organisation, formule = _organisation()
    abonnement, _ = abonnements.assurer_abonnement(
        organisation_id=str(organisation.id),
        formule_code=formule.code,
        reference_stripe="sub_1",
    )

    for _ in range(3):
        abonnements._enregistrer_l_encaissement(_facture(), abonnement)

    assert Encaissement.objects.count() == 1


@pytest.mark.django_db
def test_deux_factures_distinctes_s_additionnent() -> None:
    """Contre-épreuve : la garde ne doit pas avaler un vrai renouvellement."""
    from django.db.models import Sum
    from paiement import abonnements

    organisation, formule = _organisation()
    abonnement, _ = abonnements.assurer_abonnement(
        organisation_id=str(organisation.id),
        formule_code=formule.code,
        reference_stripe="sub_1",
    )

    abonnements._enregistrer_l_encaissement(_facture(reference="in_1"), abonnement)
    abonnements._enregistrer_l_encaissement(_facture(reference="in_2"), abonnement)

    total = Encaissement.objects.aggregate(t=Sum("montant_cents"))["t"]
    assert Encaissement.objects.count() == 2
    assert total == 37_800


@pytest.mark.django_db
def test_une_facture_a_zero_n_est_pas_un_encaissement() -> None:
    """Un essai gratuit ou un avoir ne sont pas des recettes."""
    from paiement import abonnements

    organisation, formule = _organisation()
    abonnement, _ = abonnements.assurer_abonnement(
        organisation_id=str(organisation.id),
        formule_code=formule.code,
        reference_stripe="sub_1",
    )

    abonnements._enregistrer_l_encaissement(_facture(montant=0), abonnement)

    assert not Encaissement.objects.exists()


@pytest.mark.django_db
def test_un_defaut_de_comptabilite_ne_prive_pas_le_client_de_ses_credits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L'enregistrement ne doit jamais faire échouer la dotation.

    Priver un client payant de ses crédits parce qu'une écriture comptable a
    échoué serait le remède pire que le mal. L'échec ouvre un incident — il ne
    se tait pas pour autant.
    """
    from paiement import abonnements

    from monitoring.models import OperationalIncident

    organisation, formule = _organisation()
    abonnement, _ = abonnements.assurer_abonnement(
        organisation_id=str(organisation.id),
        formule_code=formule.code,
        reference_stripe="sub_1",
    )
    monkeypatch.setattr(
        Encaissement.objects,
        "get_or_create",
        lambda **_: (_ for _ in ()).throw(RuntimeError("base indisponible")),
    )

    # Ne doit pas lever.
    abonnements._enregistrer_l_encaissement(_facture(), abonnement)

    assert OperationalIncident.objects.filter(
        title="Encaissement non enregistre"
    ).exists()


@pytest.mark.django_db
def test_la_synthese_separe_le_contractuel_de_l_encaisse() -> None:
    """Les confondre ferait passer un impayé pour une recette."""
    import json

    from django.test import Client
    from paiement import abonnements

    organisation, formule = _organisation()
    abonnement, _ = abonnements.assurer_abonnement(
        organisation_id=str(organisation.id),
        formule_code=formule.code,
        reference_stripe="sub_1",
    )
    abonnements._enregistrer_l_encaissement(_facture(montant=18_900), abonnement)

    reponse = Client().get(
        "/api/dashboard/supervision/synthese/",
        HTTP_AUTHORIZATION="Bearer " + _jeton(),
    )
    assert reponse.status_code == 200
    revenu = json.loads(reponse.content)["revenu"]

    assert revenu["recurrent_mensuel_cents"] == 18_900
    assert revenu["encaisse_total_cents"] == 18_900
    # Deux clés distinctes, et un avertissement qui ne ment plus.
    assert "aucun prestataire" not in revenu["avertissement"].lower()


def _jeton() -> str:
    from django.conf import settings

    return str(getattr(settings, "EVKHA_DASHBOARD_TOKEN", "") or "jeton-de-test")
