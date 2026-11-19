"""Accorder une résiliation doit résilier.

`traiter_demande` enchaînait `if changement_formule` … `elif
credits_additionnels` … puis marquait la demande **TRAITÉE**. Sans branche pour
`RESILIATION`, et **sans `else`**.

Or `TypeDemande.RESILIATION` existe, l'espace client permet de la demander, et
l'administration affiche un bouton « Accorder ». Cliquer marquait donc la
demande « Traitée » pendant que l'abonnement restait ACTIF : doté chaque mois
par la tâche horaire, et compté dans le revenu récurrent.

Un statut qui affirme une action non faite est pire que pas de statut : il
empêche de s'apercevoir qu'il reste quelque chose à faire (règle 1).

Le correctif ne se contente pas d'ajouter la branche manquante. Il ajoute un
`else` qui REFUSE : le prochain type ajouté à `TypeDemande` ne pourra plus être
marqué « Traité » par le simple fait de traverser la suite de `elif` (règle 4).
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from organisations import credits, inscription, services

pytestmark = pytest.mark.django_db

EMAIL = "claire@cabinet-duval.fr"


@pytest.fixture
def abonne() -> Any:
    from django.core.management import call_command

    from organisations.models import Formule

    call_command("seed_formules", "--forcer", verbosity=0)
    formule = Formule.objects.get(code="pro")
    return inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email=EMAIL,
        mot_de_passe="un-mot-de-passe-solide-42",
        formule=formule,
        activer_abonnement=True,
    ).organisation


def _demande(organisation: Any, type_demande: str) -> Any:
    from organisations.models import DemandeCommerciale, StatutDemande

    return DemandeCommerciale.objects.create(
        organisation=organisation,
        type=type_demande,
        statut=StatutDemande.OUVERTE,
        message="Nous arrêtons.",
    )


def _accorder(client_admin: Any, demande: Any) -> Any:
    return client_admin.post(
        f"/api/dashboard/supervision/demandes/{demande.id}/traiter/",
        data=json.dumps({"decision": "accorder", "motif": "Accord direction"}),
        content_type="application/json",
    )


# ── Le défaut ────────────────────────────────────────────────────────────────


def test_accorder_une_resiliation_resilie_vraiment(
    client_admin: Any, abonne: Any
) -> None:
    """Le test qui échoue sur le code d'avant : l'abonnement restait ACTIF."""
    from organisations.models import StatutAbonnement, StatutDemande, TypeDemande

    demande = _demande(abonne, TypeDemande.RESILIATION)
    assert abonne.abonnements.filter(statut=StatutAbonnement.ACTIF).exists()

    reponse = _accorder(client_admin, demande)

    assert reponse.status_code == 200, reponse.content
    demande.refresh_from_db()
    assert demande.statut == StatutDemande.TRAITEE
    assert not abonne.abonnements.filter(statut=StatutAbonnement.ACTIF).exists(), (
        "la demande est marquee TRAITEE et l'abonnement est toujours actif"
    )


def test_un_abonnement_resilie_n_est_plus_dote(
    client_admin: Any, abonne: Any
) -> None:
    """La conséquence qui coûte : la tâche horaire continuait de créditer.

    Vérifier le seul statut ne prouverait rien — c'est la dotation mensuelle
    qui fait la différence entre une résiliation et une étiquette (règle 7).
    """
    from organisations.models import TypeDemande
    from organisations.tasks import appliquer_echeances

    _accorder(client_admin, _demande(abonne, TypeDemande.RESILIATION))
    solde_apres_resiliation = credits.solde(abonne)

    appliquer_echeances()

    assert credits.solde(abonne) == solde_apres_resiliation, (
        "un abonnement resilie continue d'etre dote"
    )


def test_les_credits_deja_dotes_ne_sont_pas_repris(
    client_admin: Any, abonne: Any
) -> None:
    """Contre-épreuve : résilier n'est pas confisquer.

    Les crédits au portefeuille ont été dotés au titre d'une échéance payée.
    C'est l'échéance SUIVANTE qui n'aura pas lieu.
    """
    from organisations.models import TypeDemande

    avant = credits.solde(abonne)
    assert avant > 0, "l'amorce du test est fausse"

    _accorder(client_admin, _demande(abonne, TypeDemande.RESILIATION))

    assert credits.solde(abonne) == avant


# ── Le prochain oubli est impossible ─────────────────────────────────────────


def test_un_type_de_demande_non_gere_refuse_au_lieu_de_se_taire(
    client_admin: Any, abonne: Any, monkeypatch: Any
) -> None:
    """Ce qui rend la classe du défaut impossible, pas seulement le cas.

    Le vrai problème n'était pas « la résiliation manque » : c'était qu'un type
    non traité traversait la suite de `elif` et ressortait « Traité ». Le
    prochain type ajouté à `TypeDemande` aurait subi exactement le même sort.
    """
    from organisations.models import DemandeCommerciale, StatutDemande

    demande = _demande(abonne, "changement_formule")
    # Un type que le code ne connait pas — on ecrit directement en base pour
    # simuler le type qui sera ajoute demain.
    DemandeCommerciale.objects.filter(pk=demande.pk).update(type="type_de_demain")
    demande.refresh_from_db()

    reponse = _accorder(client_admin, demande)

    assert reponse.status_code == 409, (
        "un type inconnu a ete marque « Traite » sans que rien ne soit fait"
    )
    assert reponse.json()["code"] == "type_non_gere"
    demande.refresh_from_db()
    assert demande.statut == StatutDemande.OUVERTE, "la demande a ete cloturee a tort"


# ── Le service, isolément ────────────────────────────────────────────────────


def test_resilier_est_idempotent(abonne: Any) -> None:
    """Un second appel ne doit rien casser ni rien inventer."""
    assert services.resilier(abonne, motif="essai") == 1
    assert services.resilier(abonne, motif="essai") == 0


def test_resilier_n_empeche_pas_de_se_reabonner(abonne: Any) -> None:
    """Contre-épreuve : une résiliation n'est pas une porte fermée.

    Un abonné qui revient six mois plus tard doit pouvoir souscrire — la
    contrainte d'unicité ne porte que sur les abonnements ACTIFS.
    """
    from organisations.models import Formule, StatutAbonnement

    services.resilier(abonne)
    services.souscrire(abonne, Formule.objects.get(code="solo"))

    assert abonne.abonnements.filter(statut=StatutAbonnement.ACTIF).count() == 1


# ── Un abonnement par carte ne change pas de formule depuis la console ──────


def _demande_de_changement(organisation: Any) -> Any:
    from organisations.models import DemandeCommerciale, Formule, StatutDemande

    return DemandeCommerciale.objects.create(
        organisation=organisation,
        type="changement_formule",
        statut=StatutDemande.OUVERTE,
        formule_visee=Formule.objects.exclude(code="pro").filter(active=True).first(),
        message="Nous voulons la formule du dessus.",
    )


def test_accorder_un_changement_sur_un_abonnement_par_carte_est_refuse(
    client_admin: Any, abonne: Any
) -> None:
    """Audit de sécurité du 19/11/2026. Accorder ici résiliait l'ancien
    abonnement chez nous et en ouvrait un neuf sans référence : Stripe
    continuait de prélever l'ancien tarif, et le nouveau était doté chaque mois
    sans jamais être payé."""
    from organisations.models import AbonnementOrganisation, StatutAbonnement, StatutDemande

    AbonnementOrganisation.objects.filter(organisation=abonne).update(
        reference_paiement="sub_par_carte"
    )
    demande = _demande_de_changement(abonne)

    reponse = _accorder(client_admin, demande)

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "abonnement_par_carte"
    demande.refresh_from_db()
    assert demande.statut == StatutDemande.OUVERTE
    actif = AbonnementOrganisation.objects.get(
        organisation=abonne, statut=StatutAbonnement.ACTIF
    )
    assert actif.reference_paiement == "sub_par_carte" and actif.formule.code == "pro"


def test_accorder_un_changement_sans_carte_reste_possible(
    client_admin: Any, abonne: Any
) -> None:
    """Contre-épreuve : un abonnement posé à la main n'a aucun prélèvement à
    tenir d'accord, la console reste le bon endroit."""
    from organisations.models import AbonnementOrganisation, StatutAbonnement

    demande = _demande_de_changement(abonne)

    reponse = _accorder(client_admin, demande)

    assert reponse.status_code == 200, reponse.content
    actif = AbonnementOrganisation.objects.get(
        organisation=abonne, statut=StatutAbonnement.ACTIF
    )
    assert actif.formule == demande.formule_visee
