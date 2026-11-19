"""La sauvegarde quotidienne existe-t-elle vraiment ?

Audit du 19/11/2026. La base — comptes, crédits payés, dossiers — vit dans un
volume Docker du serveur, et rien ne la copiait : aucune sauvegarde dans le
dépôt, aucune base gérée par l'hébergeur (API de Coolify : zéro). Une
migration fautive ou une suppression malheureuse était sans retour.

Le service `sauvegarde` de `docker-compose.prod.yml` écrit désormais une copie
par jour. Ce module est son TÉMOIN, et il existe pour une raison précise : une
sauvegarde que personne ne regarde est la garantie la plus trompeuse qui soit.
Elle échoue en silence — disque plein, mot de passe changé, conteneur arrêté —
et on l'apprend le jour où l'on en a besoin (règle 1).

Ce que ce témoin ne dit PAS : la copie est sur le MÊME serveur que la base.
Elle protège d'une erreur, pas de la perte de la machine. La copie hors site
demande une destination et des clés que seul le client peut fournir.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

#: Le service écrit une copie par jour. Trente-six heures : un jour, plus la
#: marge d'un redémarrage — au-delà, une copie a été manquée.
DELAI_MAXIMAL = timedelta(hours=36)

#: En dessous, ce n'est pas une sauvegarde : `pg_dump` écrit un en-tête même
#: quand il échoue à mi-course, et un fichier de quelques octets ne restaure
#: rien. Une base EVKHA vide pèse déjà davantage.
TAILLE_MINIMALE_OCTETS = 10_000

#: Le motif des fichiers écrits par le service : `evkha-jour-JJ.dump`, un
#: emplacement par jour du mois. La copie en cours porte un autre nom
#: (`en-cours.partiel`) et n'est donc jamais prise pour une copie finie.
MOTIF = "evkha-*.dump"


def dossier_des_sauvegardes() -> Path | None:
    """Le dossier surveillé, ou `None` là où aucune sauvegarde n'est attendue
    (poste de développement, intégration continue)."""
    chemin = str(getattr(settings, "EVKHA_DOSSIER_SAUVEGARDES", "") or "").strip()
    return Path(chemin) if chemin else None


def etat_des_sauvegardes(maintenant: datetime | None = None) -> dict[str, Any]:
    """Ce que l'on SAIT de la dernière sauvegarde. Lecture seule, ne lève pas.

    `etat` vaut « non configurée », « dossier absent », « aucune », « en
    retard » ou « à jour ». Seul le dernier est une bonne nouvelle ; les autres
    disent chacun une panne différente, pour que l'incident nomme la bonne.
    """
    dossier = dossier_des_sauvegardes()
    if dossier is None:
        return {"etat": "non configurée"}
    if not dossier.is_dir():
        return {"etat": "dossier absent", "dossier": str(dossier)}

    copies: list[tuple[float, int, str]] = []
    for fichier in dossier.glob(MOTIF):
        try:
            infos = fichier.stat()
        except OSError:
            continue
        if infos.st_size >= TAILLE_MINIMALE_OCTETS:
            copies.append((infos.st_mtime, infos.st_size, fichier.name))
    if not copies:
        return {"etat": "aucune", "dossier": str(dossier)}

    copies.sort()
    ecrite, taille, nom = copies[-1]
    quand = datetime.fromtimestamp(ecrite, tz=timezone.get_current_timezone())
    age = (maintenant or timezone.now()) - quand
    return {
        "etat": "à jour" if age <= DELAI_MAXIMAL else "en retard",
        "derniere": quand.isoformat(),
        "age_heures": round(age.total_seconds() / 3600, 1),
        "taille_octets": taille,
        "fichier": nom,
        "copies_gardees": len(copies),
    }
