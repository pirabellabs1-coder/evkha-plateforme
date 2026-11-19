"""Les gardiens qui ne gardent aucun dossier en particulier, mais la plateforme."""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import IncidentSeverity, IncidentStatus, OperationalIncident
from .sauvegardes import etat_des_sauvegardes

_log = logging.getLogger(__name__)

#: Ce qui reconnaît l'incident d'une sauvegarde manquante, pour n'en tenir
#: qu'UN ouvert à la fois et le clore quand la copie revient.
TYPE_SAUVEGARDE = "sauvegarde"


@shared_task(name="monitoring.verifier_la_sauvegarde")  # type: ignore[untyped-decorator]
def verifier_la_sauvegarde() -> str:
    """Ouvre un incident si la copie quotidienne manque, le clôt quand elle revient.

    Rend l'état lu, pour le journal de la tâche. Là où aucune sauvegarde n'est
    attendue (réglage vide), elle ne fait rien et le dit.
    """
    etat = etat_des_sauvegardes()
    # « Pris en compte » compte comme ouvert : quelqu'un l'a lu, la copie ne
    # s'est pas faite pour autant, et en rouvrir un par heure le noierait.
    ouverts = OperationalIncident.objects.filter(details__type=TYPE_SAUVEGARDE).exclude(
        status=IncidentStatus.RESOLVED
    )
    if etat["etat"] == "non configurée":
        return "non configurée"

    if etat["etat"] == "à jour":
        clos = ouverts.update(status=IncidentStatus.RESOLVED, resolved_at=timezone.now())
        if clos:
            _log.info("Sauvegarde revenue : %s incident(s) clos.", clos)
        return "à jour"

    _log.error("Sauvegarde de la base : %s (%s).", etat["etat"], etat)
    if not ouverts.exists():
        OperationalIncident.objects.create(
            title=f"Sauvegarde de la base : {etat['etat']}",
            severity=IncidentSeverity.HIGH,
            details={
                "type": TYPE_SAUVEGARDE,
                **etat,
                "consigne": (
                    "La copie quotidienne de la base n'est pas là où elle doit "
                    "être. Tant que cet incident est ouvert, une erreur sur les "
                    "données n'a pas de retour possible : regarder le service "
                    "« sauvegarde » (espace disque, mot de passe de la base) "
                    "avant tout déploiement qui porte une migration."
                ),
            },
        )
    return str(etat["etat"])
