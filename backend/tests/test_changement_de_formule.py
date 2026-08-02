"""Monter en gamme ne doit pas faire tomber le solde à zéro.

L'enchaînement, vérifié ligne à ligne avant correction :

1. un abonné est doté pour le mois en cours ;
2. il demande une formule supérieure, l'équipe accorde ;
3. `souscrire` résilie l'ancien abonnement et en crée un neuf, dont
   `derniere_periode_dotee` est vide ;
4. la tâche horaire appelle `appliquer_echeance`, qui **expire d'abord le
   solde** — report AUCUN — puis appelle `doter` ;
5. `doter` était idempotent sur la seule PÉRIODE : il retrouvait la dotation
   déjà passée par l'ancien abonnement, la refusait comme doublon, et
   n'ajoutait rien.

Solde à zéro jusqu'au 1er du mois suivant. Le client avait demandé PLUS, et il
recevait ZÉRO — sur une demande qu'on venait de lui accorder.

La confusion était dans la clé : une dotation appartient à un **abonnement** et
à une période, pas à une période seule. Deux abonnements successifs dans le
même mois sont deux droits distincts.
"""
from __future__ import annotations

from typing import Any

import pytest

from organisations import credits, inscription, services

pytestmark = pytest.mark.django_db

EMAIL = "claire@cabinet-duval.fr"


@pytest.fixture
def formules() -> Any:
    from django.core.management import call_command

    from organisations.models import Formule

    call_command("seed_formules", "--forcer", verbosity=0)
    return {f.code: f for f in Formule.objects.all()}


@pytest.fixture
def abonne(formules: Any) -> Any:
    ouverture = inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email=EMAIL,
        mot_de_passe="un-mot-de-passe-solide-42",
        formule=formules["solo"],
        activer_abonnement=True,
    )
    return ouverture.organisation


# ── Le défaut ────────────────────────────────────────────────────────────────


def test_monter_en_gamme_en_cours_de_mois_dote_la_nouvelle_formule(
    abonne: Any, formules: Any
) -> None:
    """Le test qui échoue sur le code d'avant : le solde tombait à zéro."""
    depart = credits.solde(abonne)
    assert depart == formules["solo"].credits_par_echeance
    assert depart > 0, "l'abonne doit avoir ete dote pour que le test ait un sens"

    services.souscrire(abonne, formules["pro"], doter_immediatement=True)

    apres = credits.solde(abonne)
    assert apres == formules["pro"].credits_par_echeance, (
        f"solde {apres} apres une montee de gamme vers une formule a "
        f"{formules['pro'].credits_par_echeance} credits"
    )
    assert apres > 0, "le client a demande PLUS et recu ZERO"


def test_la_tache_horaire_ne_vide_pas_le_solde_apres_un_changement(
    abonne: Any, formules: Any
) -> None:
    """Le vrai chemin : c'est la tâche périodique qui déclenchait la perte.

    Vérifier `souscrire` seul ne prouverait rien — le défaut se produisait
    dans l'heure qui suivait, quand la tâche rattrapait l'abonnement neuf
    (règle 7).
    """
    from organisations.tasks import appliquer_echeances

    services.souscrire(abonne, formules["pro"], doter_immediatement=True)
    avant = credits.solde(abonne)

    appliquer_echeances()

    assert credits.solde(abonne) == avant, "la tache horaire a vide le solde"


# ── Ce que le correctif ne doit PAS casser ───────────────────────────────────


def test_la_tache_ne_dote_pas_deux_fois_le_meme_mois(
    abonne: Any, formules: Any
) -> None:
    """Contre-épreuve : l'idempotence d'origine reste entière.

    C'est la raison d'être de la clé. La relâcher pour corriger le changement
    de formule aurait offert une dotation à chaque passage horaire.
    """
    from organisations.tasks import appliquer_echeances

    depart = credits.solde(abonne)

    for _ in range(3):
        appliquer_echeances()

    assert credits.solde(abonne) == depart, "la dotation a ete rejouee"


def test_une_descente_de_gamme_donne_la_dotation_de_la_nouvelle_formule(
    abonne: Any, formules: Any
) -> None:
    """Le correctif vaut dans les deux sens, pas seulement à la montée."""
    services.souscrire(abonne, formules["structure"], doter_immediatement=True)
    assert credits.solde(abonne) == formules["structure"].credits_par_echeance

    services.souscrire(abonne, formules["solo"], doter_immediatement=True)
    assert credits.solde(abonne) == formules["solo"].credits_par_echeance


def test_les_credits_achetes_ne_sont_pas_touches_par_le_changement(
    abonne: Any, formules: Any
) -> None:
    """Ce qui a été payé en plus ne relève pas de l'échéance.

    Un abonné qui a acheté des crédits supplémentaires ne doit pas les perdre
    parce qu'il change de formule — c'est une garantie distincte, déjà tenue
    par `expirer_solde`, et le correctif ne doit pas l'entamer.
    """
    credits.crediter(
        abonne, 4, motif="Crédits supplémentaires", reference="achat-1",
        type_mouvement=credits.TypeMouvement.ACHAT,
    )
    avant = credits.solde(abonne)

    services.souscrire(abonne, formules["pro"], doter_immediatement=True)

    assert credits.solde(abonne) >= 4, (
        f"les credits achetes ont disparu (solde {credits.solde(abonne)}, "
        f"{avant} avant le changement)"
    )


# ── Le parcours réel, depuis l'administration ────────────────────────────────


def test_accorder_une_demande_de_formule_credite_immediatement(
    client_admin: Any, abonne: Any, formules: Any
) -> None:
    """Le chemin que l'équipe emprunte réellement (règle 7).

    `traiter_demande` passait `doter_immediatement=False` : même la clé
    corrigée, l'abonné aurait attendu le prochain passage horaire en regardant
    un solde vidé.
    """
    from organisations.models import DemandeCommerciale, StatutDemande, TypeDemande

    demande = DemandeCommerciale.objects.create(
        organisation=abonne,
        type=TypeDemande.CHANGEMENT_FORMULE,
        formule_visee=formules["pro"],
        statut=StatutDemande.OUVERTE,
        message="Nous produisons davantage.",
    )

    reponse = client_admin.post(
        f"/api/dashboard/supervision/demandes/{demande.id}/traiter/",
        data='{"decision": "accorder", "motif": "Montee de gamme validee"}',
        content_type="application/json",
    )

    assert reponse.status_code in (200, 201), reponse.content
    assert credits.solde(abonne) == formules["pro"].credits_par_echeance
