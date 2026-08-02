"""Cycle de vie d'une organisation : membres, abonnement, échéances (lot 4)."""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from customers.models import Customer

from . import credits
from .models import (
    AbonnementOrganisation,
    ClientFinal,
    Formule,
    MembreOrganisation,
    Organisation,
    ReportCredits,
    RoleOrganisation,
    StatutAbonnement,
    StatutOrganisation,
)

_log = logging.getLogger(__name__)

#: Droits du §12, exprimés par rôle. Une seule table : la dupliquer côté
#: interface la ferait diverger du serveur au premier ajout d'action.
DROITS: dict[str, frozenset[str]] = {
    RoleOrganisation.PROPRIETAIRE: frozenset({
        "commander", "consulter_livrables", "gerer_clients_finaux",
        "gerer_membres", "gerer_abonnement", "consulter_factures",
        "gerer_marque",
    }),
    RoleOrganisation.MEMBRE: frozenset({
        "commander", "consulter_livrables", "gerer_clients_finaux",
        # La charte part sur CHAQUE document livre chez les clients de
        # l'abonne : un membre peut la regler, un compte en lecture seule non.
        "gerer_marque",
    }),
    RoleOrganisation.LECTURE: frozenset({"consulter_livrables"}),
}

#: Actions réservées à EVKHA, jamais accordées à un rôle d'organisation :
#: corriger un socle, relancer une génération, modifier trames et gabarits,
#: créer un type de document, doter un compte.
ACTIONS_ADMIN = frozenset({
    "corriger_socle", "relancer_generation", "modifier_trames",
    "gerer_types_documents", "doter_credits",
})


class AccesRefuseError(PermissionError):
    """Le rôle du membre ne permet pas cette action."""


def periode_courante() -> str:
    maintenant = timezone.now()
    return f"{maintenant.year:04d}-{maintenant.month:02d}"


def peut(membre: MembreOrganisation, action: str) -> bool:
    """Ce membre a-t-il le droit d'effectuer cette action ?

    Un membre révoqué n'a aucun droit, quel que soit son rôle : sans ce
    contrôle, révoquer un accès ne révoquerait rien.
    """
    if not membre.actif:
        return False
    if action in ACTIONS_ADMIN:
        return False
    return action in DROITS.get(str(membre.role), frozenset())


def exiger(membre: MembreOrganisation, action: str) -> None:
    if not peut(membre, action):
        msg = (
            f"{membre.customer.email} ({membre.role}) n'a pas le droit "
            f"d'effectuer l'action « {action} »."
        )
        raise AccesRefuseError(msg)


@transaction.atomic
def creer_organisation(
    *, raison_sociale: str, contact: Customer, marque_blanche: bool = True
) -> Organisation:
    """Crée l'organisation, son portefeuille et son propriétaire d'un seul geste.

    Les trois sont indissociables : une organisation sans propriétaire ne peut
    plus être administrée, et un portefeuille créé plus tard laisserait une
    fenêtre où une commande échouerait sans raison compréhensible.
    """
    organisation = Organisation.objects.create(
        raison_sociale=raison_sociale, contact=contact, marque_blanche=marque_blanche
    )
    MembreOrganisation.objects.create(
        organisation=organisation,
        customer=contact,
        role=RoleOrganisation.PROPRIETAIRE,
        invite_le=timezone.now(),
    )
    credits.portefeuille_de(organisation)
    return organisation


@transaction.atomic
def inviter_membre(
    organisation: Organisation,
    customer: Customer,
    *,
    role: str = RoleOrganisation.MEMBRE,
) -> MembreOrganisation:
    """Rattache une personne à l'organisation, ou réactive un accès révoqué.

    Réactiver plutôt que créer : la contrainte d'unicité interdit deux
    rattachements pour le même couple, et une révocation suivie d'une nouvelle
    invitation est un cas normal, pas une erreur.
    """
    membre, cree = MembreOrganisation.objects.get_or_create(
        organisation=organisation,
        customer=customer,
        defaults={"role": role, "invite_le": timezone.now()},
    )
    if not cree:
        # Cette fonction ECRASE le role d'un membre existant. Le dernier
        # proprietaire pouvait donc se « reinviter » avec le role « membre » et
        # se demettre lui-meme : la garde de `revoquer_membre` etait contournee
        # sans etre touchee, et l'organisation devenait inadministrable pour
        # toujours.
        #
        # Le garde-fou etait pose sur UN CHEMIN — la revocation — alors que la
        # propriete a tenir est « une organisation garde toujours un
        # proprietaire ». Elle est desormais verifiee partout ou un role
        # change (regle 4).
        if membre.role == RoleOrganisation.PROPRIETAIRE != role:
            _exiger_un_autre_proprietaire(membre, geste="retrograder")
        membre.role = role
        membre.revoque_le = None
        membre.invite_le = membre.invite_le or timezone.now()
        membre.save(update_fields=["role", "revoque_le", "invite_le", "updated_at"])
    return membre


def _exiger_un_autre_proprietaire(membre: MembreOrganisation, *, geste: str) -> None:
    """Refuse si `membre` est le SEUL propriétaire actif de son organisation.

    Une seule écriture de cette règle, appelée par tous les gestes qui peuvent
    retirer un propriétaire — révocation et changement de rôle. Deux copies
    finiraient par ne plus dire la même chose, et c'est exactement ce qui s'est
    produit : la révocation était gardée, le changement de rôle non (règle 5).
    """
    autres = (
        MembreOrganisation.objects.filter(
            organisation=membre.organisation,
            role=RoleOrganisation.PROPRIETAIRE,
            revoque_le__isnull=True,
        )
        .exclude(pk=membre.pk)
        .exists()
    )
    if not autres:
        msg = (
            f"Impossible de {geste} le dernier propriétaire de "
            f"{membre.organisation} : l'organisation deviendrait "
            "inadministrable."
        )
        raise AccesRefuseError(msg)


@transaction.atomic
def revoquer_membre(membre: MembreOrganisation) -> MembreOrganisation:
    """Révoque un accès. Refuse de retirer le dernier propriétaire.

    Sans ce garde-fou, une organisation devient inadministrable et il faut
    intervenir en base pour la récupérer.
    """
    if membre.role == RoleOrganisation.PROPRIETAIRE:
        _exiger_un_autre_proprietaire(membre, geste="révoquer")
    membre.revoque_le = timezone.now()
    membre.save(update_fields=["revoque_le", "updated_at"])
    return membre


# ── Abonnement et échéances ──────────────────────────────────────────────────


@transaction.atomic
def souscrire(
    organisation: Organisation,
    formule: Formule,
    *,
    doter_immediatement: bool = True,
) -> AbonnementOrganisation:
    """Souscrit une formule. Résilie l'abonnement actif s'il en existe un.

    La contrainte d'unicité en base n'accepte qu'un abonnement actif par
    organisation ; on résilie donc explicitement au lieu de laisser
    l'`IntegrityError` remonter, ce qui est le comportement attendu d'un
    changement de formule (§9.6 : montée et descente de gamme).
    """
    AbonnementOrganisation.objects.filter(
        organisation=organisation, statut=StatutAbonnement.ACTIF
    ).update(
        statut=StatutAbonnement.RESILIE, fin_le=timezone.now(),
        updated_at=timezone.now(),
    )

    abonnement = AbonnementOrganisation.objects.create(
        organisation=organisation,
        formule=formule,
        statut=StatutAbonnement.ACTIF,
        debut_le=timezone.now(),
    )
    # Les options de la formule descendent sur l'organisation : c'est elle que
    # le moteur interroge, et lire la formule à chaque fois obligerait chaque
    # appelant à savoir qu'un abonnement existe.
    organisation.validation_socle_par_client = formule.validation_socle_par_client
    organisation.controle_qualite_avant_envoi = formule.controle_qualite_avant_envoi
    organisation.save(
        update_fields=[
            "validation_socle_par_client", "controle_qualite_avant_envoi",
            "updated_at",
        ]
    )

    if doter_immediatement and formule.credits_par_echeance > 0:
        appliquer_echeance(abonnement)
    return abonnement


@transaction.atomic
def appliquer_echeance(
    abonnement: AbonnementOrganisation, *, periode: str = ""
) -> int:
    """Applique une échéance : expire le solde selon la règle, puis dote.

    Retourne le nombre de crédits ajoutés, ou 0 si la période était déjà dotée.

    L'ordre compte. Expirer AVANT de doter, sinon la dotation du mois entrant
    serait purgée par l'expiration du mois sortant — le client perdrait ce qu'il
    vient de payer.
    """
    periode = periode or periode_courante()
    if abonnement.derniere_periode_dotee == periode:
        return 0

    formule = abonnement.formule
    if formule.report_credits == ReportCredits.AUCUN:
        credits.expirer_solde(abonnement.organisation, periode=periode)
    elif formule.report_credits == ReportCredits.PLAFONNE:
        credits.expirer_solde(
            abonnement.organisation, periode=periode,
            plafond_conserve=formule.plafond_report,
        )

    try:
        credits.doter(
            abonnement.organisation,
            formule.credits_par_echeance,
            periode=periode,
            # L'identifiant de l'abonnement fait partie de la cle : sans lui,
            # une montee de gamme en cours de mois expirait le solde puis se
            # voyait refuser la nouvelle dotation comme doublon.
            abonnement_id=abonnement.id,
        )
    except credits.MouvementDejaEnregistreError:
        # La dotation existe déjà : on aligne le marqueur et on n'ajoute rien.
        _log.info(
            "Échéance %s déjà dotée pour %s.", periode, abonnement.organisation
        )
        abonnement.derniere_periode_dotee = periode
        abonnement.save(update_fields=["derniere_periode_dotee", "updated_at"])
        return 0

    abonnement.derniere_periode_dotee = periode
    abonnement.save(update_fields=["derniere_periode_dotee", "updated_at"])
    return formule.credits_par_echeance


@transaction.atomic
def suspendre(organisation: Organisation, *, motif: str = "") -> Organisation:
    """Suspend une organisation. Elle ne peut plus consommer, ses documents restent."""
    organisation.statut = StatutOrganisation.SUSPENDUE
    organisation.save(update_fields=["statut", "updated_at"])
    _log.info("Organisation %s suspendue. %s", organisation, motif)
    return organisation


@transaction.atomic
def reactiver(organisation: Organisation) -> Organisation:
    organisation.statut = StatutOrganisation.ACTIVE
    organisation.save(update_fields=["statut", "updated_at"])
    return organisation


# ── Clients finaux ───────────────────────────────────────────────────────────


def clients_finaux_actifs(organisation: Organisation) -> list[ClientFinal]:
    return list(
        organisation.clients_finaux.filter(archive_le__isnull=True).order_by(
            "raison_sociale"
        )
    )


@transaction.atomic
def archiver_client_final(client: ClientFinal) -> ClientFinal:
    """Archive une fiche sans toucher aux documents déjà produits (§9.2)."""
    client.archive_le = timezone.now()
    client.save(update_fields=["archive_le", "updated_at"])
    return client


def charte_du_client_final(client: ClientFinal) -> dict[str, str]:
    """Charte au format attendu par le moteur de rendu.

    Traduit la fiche vers les clés que `rendu_word.depuis_json` consomme déjà.
    C'est ici, et nulle part ailleurs, que la correspondance est faite : le
    moteur de rendu n'a pas à connaître le modèle de données de l'espace client.
    """
    return {
        "nom": client.raison_sociale,
        "logo_url": client.logo_url,
        "couleur_principale": client.couleur_principale,
        "couleur_secondaire": client.couleur_secondaire,
        "couleur_fond": client.couleur_fond,
    }
