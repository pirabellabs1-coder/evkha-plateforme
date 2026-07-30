"""Le portefeuille de crédits : débit, remboursement, dotation (lot 4).

C'est le module le plus sensible du lot : il manipule ce que le client a payé.
Trois garanties, chacune née d'une exigence explicite du cahier des charges
(§11) ou d'un défaut déjà vécu sur ce projet.

**Aucun découvert.** « Commande bloquée avec proposition d'achat de crédits
additionnels. Aucun découvert. » Le débit lit le solde et écrit le mouvement
dans la même transaction, derrière un verrou de ligne sur le portefeuille.
Sans ce verrou, deux commandes lancées simultanément liraient le même solde de
1 et passeraient toutes les deux.

**Aucun double débit.** Une même référence ne peut être débitée qu'une fois,
garanti par une contrainte d'unicité en base et non par une vérification en
Python : une tâche Celery relancée après un incident réseau rejouerait sinon le
débit. Ce projet a déjà payé deux fois chaque chapitre pour une raison de cette
famille.

**Aucun crédit perdu sur échec.** « Remboursement automatique en cas d'échec
définitif. » Le remboursement est lui aussi idempotent, et il ne peut pas
exister sans le débit correspondant.
"""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.db.models import Sum

from .models import (
    MouvementCredit,
    Organisation,
    PortefeuilleCredits,
    TypeMouvement,
)

_log = logging.getLogger(__name__)


class SoldeInsuffisantError(RuntimeError):
    """Le portefeuille ne couvre pas le coût demandé. Aucun découvert n'est permis."""

    def __init__(self, solde: int, requis: int) -> None:
        self.solde = solde
        self.requis = requis
        super().__init__(
            f"Solde insuffisant : {solde} crédit(s) disponible(s) pour {requis} requis."
        )


class OrganisationSuspendueError(RuntimeError):
    """Une organisation suspendue ne peut plus consommer."""


class MouvementDejaEnregistreError(RuntimeError):
    """Cette référence a déjà donné lieu à un mouvement de ce type."""


def portefeuille_de(organisation: Organisation) -> PortefeuilleCredits:
    """Portefeuille de l'organisation, créé à la demande.

    Créer à la lecture plutôt qu'exiger une création préalable : une
    organisation sans portefeuille est un état que rien ne justifie, et le faire
    échouer ici obligerait chaque appelant à s'en préoccuper.
    """
    portefeuille, _ = PortefeuilleCredits.objects.get_or_create(
        organisation=organisation
    )
    return portefeuille


def solde(organisation: Organisation) -> int:
    """Solde courant. Somme du journal, jamais un compteur mémorisé."""
    total = MouvementCredit.objects.filter(
        portefeuille__organisation=organisation
    ).aggregate(total=Sum("quantite"))["total"]
    return int(total or 0)


def _enregistrer(
    portefeuille: PortefeuilleCredits,
    *,
    type_mouvement: str,
    quantite: int,
    motif: str,
    reference: str = "",
    auteur: str = "",
) -> MouvementCredit:
    try:
        return MouvementCredit.objects.create(
            portefeuille=portefeuille,
            type=type_mouvement,
            quantite=quantite,
            motif=motif,
            reference=reference,
            auteur=auteur,
        )
    except IntegrityError as erreur:
        msg = (
            f"Un mouvement « {type_mouvement} » existe déjà pour la référence "
            f"{reference!r}. Rien n'a été écrit."
        )
        raise MouvementDejaEnregistreError(msg) from erreur


# ── Entrées ──────────────────────────────────────────────────────────────────


@transaction.atomic
def crediter(
    organisation: Organisation,
    quantite: int,
    *,
    motif: str,
    type_mouvement: str = TypeMouvement.GESTE,
    reference: str = "",
    auteur: str = "",
) -> MouvementCredit:
    """Ajoute des crédits. Toute entrée passe par ici, quelle que soit son origine.

    Un motif est obligatoire : le cahier des charges exige qu'une dotation
    manuelle soit enregistrée avec son motif, et un journal dont la moitié des
    lignes n'explique rien ne sert à personne.
    """
    if quantite <= 0:
        msg = f"Une entrée doit être strictement positive, reçu {quantite}."
        raise ValueError(msg)
    if not motif.strip():
        msg = "Un mouvement de crédit sans motif n'est pas enregistrable."
        raise ValueError(msg)
    return _enregistrer(
        portefeuille_de(organisation),
        type_mouvement=type_mouvement,
        quantite=quantite,
        motif=motif,
        reference=reference,
        auteur=auteur,
    )


@transaction.atomic
def doter(
    organisation: Organisation, quantite: int, *, periode: str, motif: str = ""
) -> MouvementCredit:
    """Dotation d'échéance d'abonnement, idempotente par période.

    `periode` au format `AAAA-MM` sert de référence : une tâche périodique
    relancée deux fois dans le même mois ne dote qu'une fois.
    """
    portefeuille = portefeuille_de(organisation)
    deja = portefeuille.mouvements.filter(
        type=TypeMouvement.DOTATION, reference=periode
    ).first()
    if deja is not None:
        msg = f"La période {periode} a déjà été dotée pour {organisation}."
        raise MouvementDejaEnregistreError(msg)
    return _enregistrer(
        portefeuille,
        type_mouvement=TypeMouvement.DOTATION,
        quantite=quantite,
        motif=motif or f"Dotation de l'échéance {periode}",
        reference=periode,
    )


# ── Sorties ──────────────────────────────────────────────────────────────────


@transaction.atomic
def debiter(
    organisation: Organisation,
    quantite: int,
    *,
    reference: str,
    motif: str,
) -> MouvementCredit:
    """Débite le portefeuille pour une génération. Refuse tout découvert.

    `reference` identifie la génération (identifiant de commande ou de job) et
    rend l'opération idempotente : une relance ne débite pas deux fois.

    Le verrou de ligne est indispensable. Deux commandes lancées en même temps
    sur un solde de 1 liraient toutes les deux « 1 disponible » et passeraient
    toutes les deux : le client se retrouverait à −1, ce que le cahier des
    charges interdit explicitement.
    """
    if quantite <= 0:
        msg = f"Un débit doit porter sur au moins un crédit, reçu {quantite}."
        raise ValueError(msg)

    portefeuille = portefeuille_de(organisation)
    # Verrou pris sur la ligne du portefeuille, pas sur les mouvements : c'est
    # le point de sérialisation. Les mouvements, eux, n'existent pas encore.
    verrouille = (
        PortefeuilleCredits.objects.select_for_update()
        .filter(pk=portefeuille.pk)
        .first()
    )
    assert verrouille is not None

    organisation.refresh_from_db(fields=["statut"])
    if not organisation.active:
        msg = f"L'organisation {organisation} est suspendue : aucune consommation."
        raise OrganisationSuspendueError(msg)

    disponible = verrouille.solde
    if disponible < quantite:
        raise SoldeInsuffisantError(disponible, quantite)

    return _enregistrer(
        verrouille,
        type_mouvement=TypeMouvement.DEBIT,
        quantite=-quantite,
        motif=motif,
        reference=reference,
    )


@transaction.atomic
def rembourser(
    organisation: Organisation, *, reference: str, motif: str
) -> MouvementCredit:
    """Restitue les crédits d'une génération en échec définitif.

    Le montant n'est pas fourni par l'appelant : il est **relu sur le débit
    d'origine**. Laisser l'appelant le passer ouvrirait la porte à un
    remboursement supérieur au débit, et rien dans le code ne l'aurait vu.
    """
    portefeuille = portefeuille_de(organisation)
    debit = portefeuille.mouvements.filter(
        type=TypeMouvement.DEBIT, reference=reference
    ).first()
    if debit is None:
        msg = (
            f"Aucun débit enregistré pour la référence {reference!r} : il n'y a "
            "rien à rembourser."
        )
        raise MouvementDejaEnregistreError(msg)

    return _enregistrer(
        portefeuille,
        type_mouvement=TypeMouvement.REMBOURSEMENT,
        quantite=-debit.quantite,
        motif=motif,
        reference=reference,
    )


def peut_commander(organisation: Organisation, cout: int) -> tuple[bool, str]:
    """Le portefeuille couvre-t-il ce coût ? Retourne (possible, raison).

    Sert à l'écran de récapitulatif avant lancement, qui doit annoncer le coût
    et le solde restant (§9.3). Ce contrôle est **indicatif** : seul `debiter`
    fait autorité, parce que lui seul verrouille. Un contrôle préalable qui
    prétendrait décider serait faux dès que deux commandes se croisent.
    """
    if not organisation.active:
        return False, "Organisation suspendue."
    disponible = solde(organisation)
    if disponible < cout:
        return False, (
            f"Solde insuffisant : {disponible} crédit(s) pour {cout} requis."
        )
    return True, ""


# ── Fin de période ───────────────────────────────────────────────────────────


@transaction.atomic
def expirer_solde(
    organisation: Organisation, *, periode: str, plafond_conserve: int = 0
) -> MouvementCredit | None:
    """Purge le solde en fin de période, selon la règle de report de la formule.

    Décision de la cliente : **les crédits ne se reportent pas**. L'expiration
    est écrite comme un mouvement négatif plutôt que par une remise à zéro du
    solde : le journal doit rester la seule vérité, et un solde remis à zéro
    hors journal rendrait les deux chiffres incohérents.

    `plafond_conserve` couvre le cas « report plafonné » sans imposer un second
    chemin de code.
    """
    portefeuille = portefeuille_de(organisation)
    disponible = portefeuille.solde
    a_purger = disponible - max(plafond_conserve, 0)
    if a_purger <= 0:
        return None
    return _enregistrer(
        portefeuille,
        type_mouvement=TypeMouvement.EXPIRATION,
        quantite=-a_purger,
        motif=f"Crédits non consommés de la période {periode}",
        reference=f"expiration:{periode}",
    )
