"""La prospection AUTOMATIQUE quotidienne (Celery beat).

Motif du projet : vérifier chaque heure, n'agir qu'une fois par jour, de façon
idempotente. Rien ne part : la tâche ne fait que CHERCHER, QUALIFIER et PRÉPARER
des brouillons — la validation humaine reste requise avant tout envoi.

Rien ne tourne tant que les réglages ne sont pas `active=True` : la tâche est
planifiée mais rend aussitôt la main si l'automatisation est désactivée (donc
aucune dépense par défaut).

## La tentative s'inscrit AVANT (audit du 19/11/2026)

`derniere_execution` n'était écrite qu'après la boucle, et la recherche
n'était entourée d'aucun `try`. Une panne — crédits épuisés, recherche web en
erreur, conteneur redémarré par un déploiement — ne laissait donc aucune
trace : « une fois par jour » devenait « toutes les heures », en repayant à
chaque fois la recherche et tout ce qui la précédait, et l'écran affichait
« Activée ✓ » sans un mot.

La tentative est désormais inscrite avant le premier appel payant (date, état
« en cours »), puis close avec son bilan et sa dernière erreur. C'est elle qui
vaut « déjà fait aujourd'hui » : un échec se LIT à l'écran, il ne se rejoue pas
en silence.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from celery import shared_task
from django.utils import timezone

from . import agents, services
from .models import EtatAutomatisation, ReglageAutomatisation

if TYPE_CHECKING:
    from datetime import datetime

_log = logging.getLogger(__name__)


def _deja_tente(reglage: ReglageAutomatisation, maintenant: datetime) -> str | None:
    """La raison de ne pas relancer aujourd'hui, ou None s'il y a lieu d'agir."""
    jour = maintenant.date()
    if reglage.derniere_tentative and reglage.derniere_tentative.date() == jour:
        etat = reglage.etat_affiche(maintenant)
        if etat in ("", EtatAutomatisation.REUSSIE, EtatAutomatisation.PARTIELLE):
            return "déjà exécuté aujourd'hui"
        libelle = EtatAutomatisation(etat).label.lower()
        return f"déjà tenté aujourd'hui ({libelle}) : voir l'écran Automatisation"
    # Les exécutions d'avant l'audit n'ont que `derniere_execution`.
    if reglage.derniere_execution and reglage.derniere_execution.date() == jour:
        return "déjà exécuté aujourd'hui"
    return None


def _inscrire_la_tentative(reglage: ReglageAutomatisation, maintenant: datetime) -> bool:
    """Inscrit la tentative AVANT tout appel payant. False si une autre l'a prise.

    Mise à jour conditionnelle sur la valeur lue : deux ouvriers qui se
    réveillent à la même heure ne lancent pas deux recherches.
    """
    prises = ReglageAutomatisation.objects.filter(
        pk=reglage.pk, derniere_tentative=reglage.derniere_tentative
    ).update(
        derniere_tentative=maintenant,
        dernier_etat=EtatAutomatisation.EN_COURS,
        dernier_bilan={},
        derniere_erreur="",
        updated_at=timezone.now(),
    )
    return prises == 1


def _clore(
    reglage: ReglageAutomatisation,
    maintenant: datetime,
    etat: str,
    bilan: dict[str, int],
    erreur: str = "",
) -> dict[str, Any]:
    """Écrit l'issue de la tentative : état, bilan, dernière erreur. Rend le résumé."""
    reglage.derniere_tentative = maintenant
    reglage.dernier_etat = etat
    reglage.dernier_bilan = bilan
    reglage.derniere_erreur = erreur[:1000]
    champs = ["derniere_tentative", "dernier_etat", "dernier_bilan", "derniere_erreur"]
    if etat in (EtatAutomatisation.REUSSIE, EtatAutomatisation.PARTIELLE):
        reglage.derniere_execution = maintenant
        champs.append("derniere_execution")
    reglage.save(update_fields=[*champs, "updated_at"])
    resume: dict[str, Any] = {"execute": True, "etat": etat, **bilan}
    if erreur:
        resume["erreur"] = erreur
    _log.info("Prospection quotidienne : %s", resume)
    return resume


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
    raison = _deja_tente(reglage, maintenant)
    if raison is not None:
        return {"execute": False, "raison": raison}
    if not _inscrire_la_tentative(reglage, maintenant):
        return {"execute": False, "raison": "une autre exécution vient de démarrer"}

    # Le plafond de la recherche, lu sur sa seule source : cette tâche portait
    # son propre « 50 », que la recherche ramenait à 25 sans le dire (règle 5).
    limite = max(1, min(reglage.prospects_par_jour, agents._MAX_PROSPECTS_PAR_RECHERCHE))
    bilan = {
        "proposees": 0, "crees": 0, "deja_connues": 0, "qualifies": 0,
        "rediges": 0, "non_contactables": 0, "echecs": 0,
    }
    try:
        trouves = agents.rechercher_avec_bilan(
            reglage.campagne, limite=limite, recherche=recherche, client=client
        )
    except Exception as erreur:  # noqa: BLE001 — la panne se TRACE, elle ne se rejoue pas
        _log.exception("Prospection auto : la recherche a échoué")
        return _clore(
            reglage, maintenant, EtatAutomatisation.ECHOUEE, bilan,
            f"Recherche : {type(erreur).__name__}: {erreur}",
        )
    bilan["proposees"] = trouves.proposees
    bilan["crees"] = len(trouves.crees)
    bilan["deja_connues"] = trouves.deja_connues

    derniere_erreur = ""
    for prospect in trouves.crees:
        # Une fiche née DÉSINSCRITE (son adresse s'était déjà opposée dans une
        # autre campagne) : ni note ni rédaction — on ne paie rien pour
        # quelqu'un à qui on n'écrira jamais.
        if prospect.consentement_retire:
            bilan["non_contactables"] += 1
            continue
        try:
            agents.qualifier_un_prospect(prospect, client=client)
            bilan["qualifies"] += 1
            # On ne RÉDIGE pas pour une fiche à qui on ne peut pas écrire —
            # sans adresse surtout : c'était un appel payant pour des
            # brouillons dont l'envoi est refusé. La fiche reste, qualifiée, à
            # compléter à la main.
            if services.motif_de_non_contact(prospect) is not None:
                bilan["non_contactables"] += 1
                continue
            agents.rediger_les_messages(prospect, client=client)
            bilan["rediges"] += 1
        except Exception as erreur:  # noqa: BLE001 — un prospect raté ne bloque pas les autres
            _log.exception("Prospection auto : échec sur le prospect %s", prospect.pk)
            bilan["echecs"] += 1
            derniere_erreur = f"{prospect.raison_sociale} : {type(erreur).__name__}: {erreur}"

    etat = EtatAutomatisation.PARTIELLE if bilan["echecs"] else EtatAutomatisation.REUSSIE
    return _clore(reglage, maintenant, etat, bilan, derniere_erreur)


@shared_task(name="prospection.prospection_quotidienne")  # type: ignore[untyped-decorator]
def prospection_quotidienne() -> dict[str, Any]:
    """Tâche beat horaire : délègue au service, qui décide s'il y a lieu d'agir."""
    return executer_si_du()
