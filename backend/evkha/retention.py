"""Combien de temps un livrable reste disponible. **Une seule réponse.**

« Sept jours » était écrit à cinq endroits :

- `Offer.retention_days`, dont c'est la vraie place — c'est un réglage
  commercial, par offre ;
- trois fonctions `_retention_days` / `_retention` recopiées à l'identique dans
  `documents/services.py`, `delivery/services.py` et
  `documents/livrable_word.py`, chacune avec son repli `7` en dur ;
- `signatures.duree_de_validite`, pour la durée de vie des liens.

Et `EVKHA_DEFAULT_RETENTION_DAYS`, déclaré dans les réglages **et utilisé nulle
part** : le repli qui servait vraiment était le `7` en dur des trois fonctions.
Changer le réglage n'avait donc aucun effet — un bouton qui ne fait rien est
pire qu'un bouton absent (règle 1).

La conséquence n'était pas théorique. Le courriel de livraison annonce « Ce lien
de téléchargement est valable N jours », N venant de l'offre, pendant que la
signature du lien expirait sur une durée **globale**. Une offre réglée à trente
jours aurait donné un lien mort au huitième — et comme `/media/` répond 404
sans distinguer une signature expirée d'un fichier absent, le client aurait
conclu que son document avait été supprimé. Aujourd'hui toutes les offres sont à
sept jours : le défaut était **latent**, ce qui veut dire qu'il attendait qu'on
touche à un nombre en administration.

Tout passe désormais par ici, et la durée du lien se dérive de la même valeur.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone


def jours_par_defaut() -> int:
    """Repli quand l'offre ne dit rien — et il est enfin lisible dans un réglage."""
    return int(getattr(settings, "EVKHA_DEFAULT_RETENTION_DAYS", 7) or 7)


def jours(job: Any) -> int:
    """Durée de conservation applicable à ce dossier, en jours.

    `job` est volontairement non typé : l'importer d'ici créerait un cycle
    (`generation` dépend de `evkha`). On lit ce qu'on sait lire, et le repli
    couvre aussi bien l'offre absente que le champ à zéro.
    """
    repli = jours_par_defaut()
    return int(getattr(getattr(getattr(job, "order", None), "offer", None),
                       "retention_days", repli) or repli)


def duree(job: Any) -> timedelta:
    return timedelta(days=jours(job))


def duree_en_secondes(job: Any) -> int:
    """Ce que la signature d'un lien attend : des secondes.

    C'est le point qui reliait mal les deux moitiés. Le lien doit vivre
    exactement aussi longtemps que le fichier, ni plus — un lien qui survit à
    son fichier envoie sur une erreur — ni moins — un lien qui meurt avant lui
    prive le client d'un document encore disponible.
    """
    return int(duree(job).total_seconds())


def echeance(job: Any, *, maintenant: datetime | None = None) -> datetime:
    """Date à laquelle le fichier sera purgé du disque."""
    return (maintenant or timezone.now()) + duree(job)
