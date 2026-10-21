"""La prospection AUTOMATIQUE quotidienne (Celery beat).

Motif du projet : vérifier chaque heure, n'agir qu'une fois par jour, de façon
idempotente. Rien ne part : la tâche ne fait que CHERCHER, QUALIFIER et PRÉPARER
des brouillons — la validation humaine reste requise avant tout envoi.

Rien ne tourne tant que les réglages ne sont pas `active=True` : la tâche est
planifiée mais rend aussitôt la main si l'automatisation est désactivée (donc
aucune dépense par défaut).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from celery import shared_task
from django.utils import timezone

from . import agents
from .models import ReglageAutomatisation

if TYPE_CHECKING:
    from datetime import datetime

_log = logging.getLogger(__name__)

#: Plafond dur : même si le réglage demande plus, on ne prépare jamais plus que
#: ça en une journée (garde-fou de coût).
_MAX_PAR_JOUR = 50


def executer_si_du(
    *,
    maintenant: datetime | None = None,
    recherche: Any = None,
    client: Any = None,
) -> dict[str, Any]:
    """Exécute la prospection du jour SI les réglages le demandent, sinon rien.

    Rend un résumé de ce qui a été (ou non) fait — la tâche Celery s'en sert pour
    le journal. `recherche`/`client` injectables pour les tests (aucun réseau).
    """
    maintenant = maintenant or timezone.now()
    reglage = ReglageAutomatisation.charger()

    if not reglage.active:
        return {"execute": False, "raison": "inactive"}
    if reglage.campagne is None:
        return {"execute": False, "raison": "aucune campagne visée"}
    if maintenant.weekday() not in reglage.jours_autorises():
        return {"execute": False, "raison": "jour non autorisé"}
    if reglage.derniere_execution and reglage.derniere_execution.date() == maintenant.date():
        return {"execute": False, "raison": "déjà exécuté aujourd'hui"}

    limite = max(1, min(reglage.prospects_par_jour, _MAX_PAR_JOUR))
    crees = agents.rechercher_des_prospects(
        reglage.campagne, limite=limite, recherche=recherche, client=client
    )
    qualifies = rediges = 0
    for prospect in crees:
        try:
            agents.qualifier_un_prospect(prospect, client=client)
            qualifies += 1
            agents.rediger_les_messages(prospect, client=client)
            rediges += 1
        except Exception:  # noqa: BLE001 — un prospect raté ne bloque pas les autres
            _log.exception("Prospection auto : échec sur le prospect %s", prospect.pk)

    reglage.derniere_execution = maintenant
    reglage.save(update_fields=["derniere_execution", "updated_at"])
    resume = {"execute": True, "crees": len(crees), "qualifies": qualifies, "rediges": rediges}
    _log.info("Prospection quotidienne : %s", resume)
    return resume


@shared_task(name="prospection.prospection_quotidienne")  # type: ignore[untyped-decorator]
def prospection_quotidienne() -> dict[str, Any]:
    """Tâche beat horaire : délègue au service, qui décide s'il y a lieu d'agir."""
    return executer_si_du()
