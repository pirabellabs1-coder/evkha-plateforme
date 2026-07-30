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
    """
    dotees = 0
    deja = 0
    ecartees = 0
    en_echec = 0

    abonnements = AbonnementOrganisation.objects.filter(
        statut=StatutAbonnement.ACTIF
    ).select_related("organisation", "formule")

    for abonnement in abonnements:
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

    resultat: dict[str, int] = {
        "dotees": dotees,
        "deja_a_jour": deja,
        "ecartees_suspendues": ecartees,
        "en_echec": en_echec,
    }
    if dotees or en_echec:
        _log.info("Échéances B2B : %s", resultat)
    return resultat
