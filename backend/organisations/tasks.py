"""Tâches périodiques du portefeuille de crédits B2B (lot 4).

`appliquer_echeance` existait depuis le lot 4 et n'était appelée que par
`souscrire` — la dotation initiale — et par une action manuelle de
l'administration Django, celle-là même que le §10.2 remplace. **Aucune tâche
périodique ne l'appelait.** Un abonné recevait donc ses crédits une fois, à la
souscription, et plus jamais : ni réinitialisation en fin de mois, ni nouvelle
dotation. L'abonnement se vendait au mois et ne se renouvelait pas.

Le défaut ne se voyait pas avant la bascule d'un mois sur l'autre, ce qui est
la pire des échéances pour le découvrir : sur une facture.

## Pourquoi une vérification horaire et non mensuelle

Une tâche déclenchée uniquement le 1er à 02:00 ne rattrape rien si le worker
était arrêté à cet instant — mise à jour, redémarrage du serveur, panne. La
vérification est donc horaire et l'échéance idempotente : `appliquer_echeance`
compare `derniere_periode_dotee` à la période courante et ne fait rien si elle
est déjà passée. Vingt-trois exécutions sur vingt-quatre n'écrivent rien.

C'est la même stratégie que `customers.refresh_monthly_credits`, et c'est
volontaire : deux rythmes différents pour deux systèmes de crédits obligeraient
à savoir lequel regarde quoi.
"""
from __future__ import annotations

import logging

from celery import shared_task

from . import services
from .models import AbonnementOrganisation, StatutAbonnement, StatutOrganisation

_log = logging.getLogger(__name__)


@shared_task(name="organisations.appliquer_echeances")  # type: ignore[untyped-decorator]
def appliquer_echeances() -> dict[str, int]:
    """Applique l'échéance du mois à chaque abonnement actif.

    Les organisations **suspendues** sont écartées : les doter reviendrait à
    livrer ce qu'on vient de leur couper. Leur abonnement reprendra à la
    réactivation, et l'échéance sera appliquée à ce moment-là.

    Une organisation en échec n'interrompt pas les autres. Un abonnement qui
    lève doit être visible dans les journaux, pas faire échouer la tâche
    entière : sinon un seul cas bloque la dotation de tous les suivants.

    ## Les abonnements payés par Stripe sont écartés, et c'est la règle 5

    Depuis le 06/08/2026, un abonnement souscrit par carte est doté par
    l'événement `invoice.paid` — c'est-à-dire **quand l'argent est réellement
    encaissé**. Laisser cette tâche les doter aussi donnerait deux réponses à la
    question « ce mois-ci est-il payé ? » : notre calendrier, et la banque.

    Elles se contrediraient dans les deux sens, et les deux coûtent :

    - une carte refusée le 3 n'empêcherait pas la dotation du 1er. Stripe
      retente pendant des jours, finit par abandonner — et pendant tout ce
      temps le client produit des études gratuitement. Le mois suivant
      recommence. C'est une fuite de revenu qui ne se voit sur aucun écran ;
    - un abonnement souscrit le 20 est prélevé le 20 de chaque mois, alors que
      `periode_courante()` bascule le 1er. Le client serait donc doté dix jours
      avant d'avoir payé, tous les mois.

    Le critère est `reference_paiement`, l'identifiant d'abonnement Stripe :
    non vide, Stripe décide ; vide, cette tâche reste seule maîtresse — ce qui
    couvre les abonnements ouverts à la main depuis l'administration, qui n'ont
    aucun prélèvement derrière eux.
    """
    dotees = 0
    deja = 0
    ecartees = 0
    en_echec = 0
    payees_par_stripe = 0

    abonnements = AbonnementOrganisation.objects.filter(
        statut=StatutAbonnement.ACTIF
    ).select_related("organisation", "formule")

    for abonnement in abonnements:
        if str(abonnement.reference_paiement or "").strip():
            payees_par_stripe += 1
            continue
        if abonnement.organisation.statut != StatutOrganisation.ACTIVE:
            ecartees += 1
            continue
        try:
            ajoutes = services.appliquer_echeance(abonnement)
        except Exception:
            # On loggue avec la trace et on continue : la dotation des autres
            # abonnés ne doit pas dépendre du cas qui casse.
            en_echec += 1
            _log.exception(
                "Échéance en échec pour l'organisation %s.",
                abonnement.organisation_id,
            )
            continue
        if ajoutes:
            dotees += 1
            _log.info(
                "Échéance appliquée : %s crédit(s) pour %s.",
                ajoutes,
                abonnement.organisation,
            )
        else:
            deja += 1

    # La reserve des abonnements RESILIES.
    #
    # `expirer_solde` n'etait appele que pour les abonnements ACTIFS. Une fois
    # resilie, plus d'echeance — donc plus JAMAIS d'expiration : l'ancien
    # abonne gardait sa reserve indefiniment et continuait de consommer l'API,
    # alors que sa formule annonce que les credits non consommes expirent.
    #
    # On ne reprend rien au moment du clic sur « resilier » : le mois en cours
    # est paye. C'est a la bascule de periode, ici, que la reserve s'eteint.
    expirees = _expirer_les_reserves_resiliees()

    resultat: dict[str, int] = {
        "dotees": dotees,
        "deja_a_jour": deja,
        "ecartees_suspendues": ecartees,
        # Comptées et non tues : le jour où ce nombre vaut tout l'effectif et
        # que `dotees` reste à zéro, c'est normal ; le jour où il tombe à zéro
        # alors que des abonnés paient par carte, quelque chose a effacé les
        # références Stripe et cette tâche s'est remise à doter en double.
        "payees_par_stripe": payees_par_stripe,
        "en_echec": en_echec,
        "reserves_resiliees_expirees": expirees,
    }
    if dotees or en_echec:
        _log.info("Échéances B2B : %s", resultat)
    return resultat


def _expirer_les_reserves_resiliees() -> int:
    """Éteint la réserve des abonnements résiliés dont la période est écoulée.

    `derniere_periode_dotee` porte la période que le client a payée. Tant
    qu'elle vaut la période courante, il utilise ce qu'il a acheté. Dès qu'on
    en change, cette réserve n'a plus de contrepartie.

    Les crédits ACHETÉS ne sont pas touchés : `expirer_solde` ne purge que la
    part expirable, ce que `test_credits_achetes_survivent` verrouille déjà.
    """
    from . import credits, services  # noqa: PLC0415

    courante = services.periode_courante()
    expirees = 0

    resilies = (
        AbonnementOrganisation.objects.filter(statut=StatutAbonnement.RESILIE)
        .exclude(derniere_periode_dotee=courante)
        .select_related("organisation")
    )

    # Une organisation qui a resouscrit depuis n'est pas concernée : son
    # abonnement ACTIF gouverne, et l'échéance ordinaire s'en charge.
    actives = set(
        AbonnementOrganisation.objects.filter(
            statut=StatutAbonnement.ACTIF
        ).values_list("organisation_id", flat=True)
    )

    for abonnement in resilies:
        if abonnement.organisation_id in actives:
            continue
        try:
            mouvement = credits.expirer_solde(
                abonnement.organisation, periode=courante
            )
        except Exception:  # noqa: BLE001 — un cas qui casse n'arrête pas les autres
            _log.exception(
                "Expiration post-résiliation en échec pour %s",
                abonnement.organisation_id,
            )
            continue
        if mouvement is not None:
            expirees += 1
            _log.info(
                "Réserve expirée après résiliation pour %s.", abonnement.organisation
            )

    return expirees
