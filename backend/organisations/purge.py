"""Durée de vie des fichiers déposés par le client — et leur départ du disque.

Deux choses vivent ici, et elles se répondent.

## 1. Le fichier meurt avec sa ligne, quel que soit le chemin

`supprimer_piece_jointe` appelait `piece.fichier.delete(save=False)`, et c'était
**le seul** des quatre chemins de suppression à libérer le volume. Mesuré avant
correction, sur les trois autres :

    QUERYSET DELETE (remplacement de logo) -> fichier encore sur disque : True
    CASCADE (suppression d'organisation)   -> fichier encore sur disque : True
    vider(PieceJointe) du script de remise à zéro -> idem

Autrement dit : **chaque changement de logo abandonnait déjà un orphelin**, sans
attendre aucune rétention. Le défaut existait avant la purge qu'on ajoute ici.

Ajouter un `fichier.delete()` devant chacun de ces trois appels aurait été un
correctif qui énumère des cas — donc incomplet au quatrième (règle 4), et le
quatrième était précisément la purge qu'on écrit aujourd'hui.

Le point unique est `post_delete`. Enregistrer ce récepteur a un effet de bord
**voulu** : Django cesse alors d'employer son chemin « fast delete », qui
supprime en une requête sans instancier les objets ni émettre de signal. Le
récepteur se paie donc en requêtes sur les suppressions en masse, et c'est le
prix de la garantie.

## 2. Douze mois, à partir du dépôt

La durée vit dans `evkha.retention.jours_pieces_jointes()` — une seule source
(règle 5), un réglage réellement lu, pas un bouton mort.

Le **logo est exclu**, et l'exclusion est écrite ici plutôt que devinée :
`organisation.logo_url` pointe sur son fichier et le moteur le charge à chaque
génération. Un logo purgé éteindrait la marque de tous les livrables suivants.

## 3. Le mode « compte sans supprimer »

`purger_les_pieces_jointes(simulation=True)` ne touche ni la base ni le disque
et énumère ce qui partirait, fichier par fichier. La première exécution réelle
supprimera des documents appartenant à de vrais clients, et cette
suppression-là ne se rattrape pas : les tests tournent sur des doublures, ils
ne prouvent rien sur le volume de production (règle 7).

La simulation et la purge lisent la **même** requête, `_expirees`. C'est la
seule chose qui rende le mode d'essai utile : un dénombrement obtenu par un
filtre recopié rassurerait sur un ensemble que la purge n'emporte pas, et
enverrait vérifier ce qui n'est pas en cause (règle 2).

Le rapport distingue les fichiers **déjà absents** du volume. Compter la ligne
comme un octet libéré ferait promettre un espace que la purge ne rend pas.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.core.files.storage import default_storage
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from evkha import retention

from .models import CategorieFichier, PieceJointe

_log = logging.getLogger(__name__)


@receiver(post_delete, sender=PieceJointe, dispatch_uid="piece_jointe_efface_son_fichier")
def _effacer_le_fichier(sender: Any, instance: PieceJointe, **kwargs: Any) -> None:
    """Libère le volume dès qu'une pièce jointe disparaît de la base.

    `save=False` est impératif : la ligne n'existe plus, un `save()` la
    ressusciterait.

    Un fichier déjà absent — nettoyage manuel, volume recréé — ne doit pas faire
    échouer la suppression de la ligne : `FileSystemStorage.delete` ignore
    l'absence, et le reste est journalisé sans être relancé.
    """
    if not instance.fichier:
        return
    try:
        instance.fichier.delete(save=False)
    except Exception:  # noqa: BLE001 — la ligne est déjà partie, on ne la retient pas
        _log.exception(
            "Pièce jointe %s : suppression du fichier impossible (%s)",
            instance.pk, instance.fichier.name,
        )


@dataclass(frozen=True)
class Depot:
    """Un fichier que la purge emporterait — de quoi le retrouver à la main."""

    id: str
    organisation: str
    nom: str
    depose_le: datetime
    octets: int
    #: Le fichier est-il encore sur le volume ? `False` = la ligne existe mais
    #: le fichier a déjà disparu. Ce n'est pas une erreur, c'est une
    #: information : la purge libérera moins d'octets qu'annoncé.
    sur_le_disque: bool

    def __str__(self) -> str:
        manquant = "" if self.sur_le_disque else "  [fichier déjà absent]"
        return (
            f"{self.depose_le:%Y-%m-%d}  {self.organisation}  "
            f"{self.nom} ({self.octets} o){manquant}"
        )


@dataclass(frozen=True)
class RapportPurge:
    """Ce que la purge a fait — ou ferait, en simulation."""

    simulation: bool
    echeance: datetime
    depots: tuple[Depot, ...]

    @property
    def compte(self) -> int:
        return len(self.depots)

    @property
    def octets(self) -> int:
        """Octets réellement récupérables : les fichiers déjà absents ne comptent pas.

        Annoncer la somme des `taille_octets` de la base ferait promettre un
        espace que la purge ne rendra pas — un chiffre invérifiable est pire
        qu'aucun chiffre (règle 2).
        """
        return sum(d.octets for d in self.depots if d.sur_le_disque)

    @property
    def fichiers_deja_absents(self) -> int:
        return sum(1 for d in self.depots if not d.sur_le_disque)

    def resume(self) -> str:
        verbe = "seraient supprimés" if self.simulation else "supprimés"
        lignes = [
            f"{self.compte} document(s) déposé(s) {verbe} "
            f"(déposés avant le {self.echeance:%Y-%m-%d}), "
            f"{self.octets} octet(s) libérés."
        ]
        if self.fichiers_deja_absents:
            lignes.append(
                f"Dont {self.fichiers_deja_absents} dont le fichier a déjà "
                f"disparu du volume : la ligne part, le disque ne bouge pas."
            )
        return " ".join(lignes)


def _expirees(maintenant: datetime) -> tuple[Any, datetime]:
    """LA requête. Une seule, partagée par la simulation et par la purge.

    C'est le point sensible de ce module. Si le mode « compte sans supprimer »
    interrogeait la base autrement que la purge — ne serait-ce qu'un filtre
    recopié — il rendrait compte d'un ensemble que la purge n'emporte pas. Un
    contrôle qui compare à une donnée mal extraite envoie corriger ce qui n'est
    pas faux, et fait perdre plus de temps qu'un contrôle absent (règle 2).

    Les logos sont exclus ici, et à cet endroit seulement (règle 5).
    """
    echeance = maintenant - retention.duree_pieces_jointes()
    return (
        PieceJointe.objects.filter(
            categorie=CategorieFichier.DOCUMENT, created_at__lte=echeance
        ).select_related("organisation"),
        echeance,
    )


def purger_les_pieces_jointes(
    *, maintenant: datetime | None = None, simulation: bool = False
) -> RapportPurge:
    """Supprime les documents déposés arrivés à échéance.

    `simulation=True` : **rien n'est touché**, ni la base ni le disque. Le
    rapport énumère ce que la purge emporterait, fichier par fichier. C'est le
    mode à jouer avant la première exécution réelle en production, où les
    fichiers appartiennent à de vrais clients et où la suppression ne se
    rattrape pas.

    La simulation et la purge lisent la MÊME requête (`_expirees`) : un mode
    d'essai qui sélectionnerait autrement rassurerait sur un ensemble différent
    de celui qu'on supprime ensuite.

    La suppression se fait **instance par instance**, jamais en `queryset
    .delete()` en masse. Ce n'est pas de la prudence de style : c'est ce qui
    fait passer chaque objet par `post_delete`, donc par le disque. Une purge
    qui viderait la base en une requête laisserait exactement les orphelins
    qu'elle prétend supprimer — le défaut que `purge_expired_artifacts` a déjà
    dû corriger (règle 3 : ce qui refait le travail après le contrôle doit être
    contrôlé à son tour).
    """
    maintenant = maintenant or timezone.now()
    expirees, echeance = _expirees(maintenant)

    # Relevé AVANT toute suppression : après, il n'y a plus rien à décrire, et
    # un rapport reconstitué de mémoire ne se vérifie pas.
    depots: list[Depot] = []
    for piece in expirees.iterator():
        depots.append(
            Depot(
                id=str(piece.id),
                organisation=piece.organisation.raison_sociale,
                nom=piece.nom_original,
                depose_le=piece.created_at,
                octets=piece.taille_octets,
                sur_le_disque=bool(
                    piece.fichier and default_storage.exists(piece.fichier.name)
                ),
            )
        )
        if not simulation:
            piece.delete()  # `post_delete` efface le fichier

    rapport = RapportPurge(
        simulation=simulation, echeance=echeance, depots=tuple(depots)
    )
    if rapport.compte:
        _log.info("Purge des pièces jointes : %s", rapport.resume())
    return rapport
