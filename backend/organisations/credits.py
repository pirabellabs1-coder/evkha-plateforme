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

**Aucun crédit ACHETÉ perdu à la bascule du mois.** L'expiration purgeait le
solde entier, sans regarder d'où venaient les crédits : un client qui achetait
des crédits additionnels les perdait au mois suivant, comme ceux de son
abonnement. Il avait payé, et le solde s'évaporait. Deux réserves sont donc
distinguées — voir `detail_solde`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum

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


#: Natures qui AJOUTENT des crédits.
ENTREES = (TypeMouvement.DOTATION, TypeMouvement.ACHAT, TypeMouvement.GESTE)

#: Natures qui en RETIRENT, ou qui corrigent une sortie. `REMBOURSEMENT` est
#: positif au journal : le compter ici le fait *réduire* la consommation nette,
#: donc rendre au client la réserve dans laquelle son débit avait puisé.
SORTIES = (
    TypeMouvement.DEBIT,
    TypeMouvement.EXPIRATION,
    TypeMouvement.REMBOURSEMENT,
)

#: Entrées qui **survivent** à la bascule du mois : le client les a payées à
#: l'unité. Les purger reviendrait à reprendre ce qu'on vient de lui vendre.
#:
#: `GESTE` n'y figure pas, et c'est une **question ouverte**, pas un oubli. Un
#: geste commercial qui s'évapore au mois suivant n'est pas vraiment un geste ;
#: mais l'inclure changerait le sort des crédits accordés à la main par
#: l'administration, ce qui est une décision commerciale et non technique. Elle
#: n'a pas été prise. En attendant, le comportement d'origine est conservé.
ENTREES_PERENNES = (TypeMouvement.ACHAT,)

#: Le reste des entrées, **dérivé** et non listé à son tour. Écrire les deux
#: listes à la main laissait `GESTE` dans aucune des deux : il comptait dans le
#: total sans compter dans aucune réserve, et l'arithmétique de répartition
#: devenait fausse en silence. Une partition doit être exhaustive par
#: construction (règles 4 et 5).
ENTREES_EXPIRABLES = tuple(t for t in ENTREES if t not in ENTREES_PERENNES)


@dataclass(frozen=True)
class DetailSolde:
    """Le solde, réparti entre ce qui expire et ce qui reste.

    `expirables + perennes == total`, toujours et par construction : `perennes`
    est calculé comme le reste. Deux additions indépendantes finiraient par ne
    plus être d'accord, et c'est exactement la famille de défaut que la règle 5
    proscrit.
    """

    expirables: int
    perennes: int

    @property
    def total(self) -> int:
        return self.expirables + self.perennes


def detail_solde(organisation: Organisation) -> DetailSolde:
    """Répartit le solde entre réserve d'abonnement et réserve payée.

    **Règle d'imputation : les sorties consomment d'abord l'expirable.** C'est
    le choix favorable au client — il garde le plus longtemps possible ce qu'il
    a payé à l'unité — et c'est celui qui rend l'expiration inoffensive pour les
    crédits achetés.

    Tout est déduit du journal, rien n'est mémorisé. `perennes` vaut le total
    moins l'expirable restant, de sorte que la répartition ne peut jamais
    inventer ni perdre un crédit, même si l'historique contient des expirations
    écrites par l'ancienne règle — qui, elle, purgeait tout.
    """
    chiffres = MouvementCredit.objects.filter(
        portefeuille__organisation=organisation
    ).aggregate(
        total=Sum("quantite"),
        entrees_perennes=Sum("quantite", filter=Q(type__in=ENTREES_PERENNES)),
        entrees_expirables=Sum("quantite", filter=Q(type__in=ENTREES_EXPIRABLES)),
    )
    total = int(chiffres["total"] or 0)
    perennes_entrees = int(chiffres["entrees_perennes"] or 0)
    expirables_entrees = int(chiffres["entrees_expirables"] or 0)

    # Sorties cumulées : débits, expirations passées, moins les remboursements.
    sorties = perennes_entrees + expirables_entrees - total
    expirables_restants = max(0, expirables_entrees - max(0, sorties))
    return DetailSolde(
        expirables=expirables_restants, perennes=total - expirables_restants
    )


def solde(organisation: Organisation) -> int:
    """Solde courant. Somme du journal, jamais un compteur mémorisé.

    Délègue à `detail_solde` : deux façons de calculer le solde finiraient par
    se contredire.
    """
    return detail_solde(organisation).total


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
def reference_de_dotation(periode: str, abonnement_id: object = None) -> str:
    """Clé d'idempotence d'une dotation.

    Elle valait la seule PÉRIODE, et c'était un trou de caisse à l'envers :
    l'abonné y perdait ses crédits.

    Enchaînement vérifié. Un abonné déjà doté ce mois-ci demande une montée de
    gamme. L'équipe accorde : `souscrire` résilie l'ancien abonnement et en crée
    un neuf, dont `derniere_periode_dotee` est vide. La tâche horaire appelle
    alors `appliquer_echeance`, qui **expire d'abord le solde** — report AUCUN —
    puis appelle `doter`… qui trouve la dotation du mois déjà passée par
    l'ancien abonnement, la refuse comme doublon, et n'ajoute rien.

    Résultat : solde à zéro jusqu'au 1er du mois suivant. Le client a demandé
    PLUS, il a reçu ZÉRO — et il l'avait demandé lui-même.

    Une dotation appartient à un **abonnement** ET à une période, pas à une
    période seule : deux abonnements successifs dans le même mois sont deux
    droits distincts. C'est cette confusion qu'on retire, pas le seul symptôme
    (règle 4).

    Sans `abonnement_id`, la clé reste la période : les dotations déjà écrites
    gardent leur référence, et les appels historiques ne changent pas de sens.
    """
    return f"{abonnement_id}:{periode}" if abonnement_id is not None else periode


def doter(
    organisation: Organisation,
    quantite: int,
    *,
    periode: str,
    motif: str = "",
    abonnement_id: object = None,
) -> MouvementCredit:
    """Dotation d'échéance d'abonnement, idempotente par abonnement ET période.

    Une tâche périodique relancée deux fois dans le même mois ne dote qu'une
    fois — mais un changement de formule en cours de mois ouvre bien un
    nouveau droit. Voir `reference_de_dotation`.
    """
    reference = reference_de_dotation(periode, abonnement_id)
    portefeuille = portefeuille_de(organisation)
    deja = portefeuille.mouvements.filter(
        type=TypeMouvement.DOTATION, reference=reference
    ).first()
    if deja is not None:
        msg = f"La période {periode} a déjà été dotée pour {organisation}."
        raise MouvementDejaEnregistreError(msg)
    return _enregistrer(
        portefeuille,
        type_mouvement=TypeMouvement.DOTATION,
        quantite=quantite,
        motif=motif or f"Dotation de l'échéance {periode}",
        reference=reference,
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

    **Seule la réserve d'abonnement est purgée.** Cette fonction lisait le solde
    entier : les crédits ACHETÉS disparaissaient donc à la bascule du mois, au
    même titre que ceux de l'abonnement. Le client avait payé et son solde
    s'évaporait — un défaut d'argent, pas d'affichage. Voir `detail_solde` pour
    la règle d'imputation.
    """
    portefeuille = portefeuille_de(organisation)
    disponible = detail_solde(organisation).expirables
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
