"""Ce qu'un paiement de livrable produit : un compte, et un crédit.

Le parcours du public direct tient en trois gestes — cliquer, payer, écrire son
brief — et ce module porte le milieu. Il est appelé de DEUX endroits :

- le webhook Stripe, quand l'événement arrive ;
- la page de retour, quand la personne revient de Stripe.

Les deux peuvent gagner la course, et l'ordre n'est pas garanti : Stripe
redirige le navigateur et poste son événement en parallèle. C'est pourquoi tout
ici est **idempotent**, et pourquoi la page de retour n'attend pas le webhook.
Faire patienter quelqu'un qui vient de payer 149 EUR devant un écran de
chargement, en espérant qu'un serveur tiers se manifeste, serait le pire moment
du parcours pour lui demander de la confiance.

La garde d'idempotence est la référence de session Stripe, portée par le
mouvement de crédit. Deux appels sur la même session ne créditent qu'une fois,
que l'appelant soit le webhook, la page de retour, ou les deux à la seconde
près.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from catalog.models import Offer
from customers.models import Customer
from organisations import courriels, identifiants, services
from organisations import credits as credits_service
from organisations.models import (
    CompteClient,
    Encaissement,
    MembreOrganisation,
    Organisation,
    TypeDeCompte,
)

_log = logging.getLogger(__name__)

#: Un achat à l'unité donne droit à UN livrable. Le coût d'une commande vaut 1
#: crédit (`organisations.commandes`), et les deux nombres doivent rester égaux :
#: verser deux crédits offrirait une seconde étude, en verser zéro encaisserait
#: sans rien livrer.
CREDITS_PAR_ACHAT = 1


class AchatInexploitable(RuntimeError):
    """Le paiement est passé mais on ne sait pas à qui, ni quoi, livrer.

    C'est une situation d'incident et non une erreur d'utilisateur : l'argent a
    été pris. Elle doit être bruyante (règle 1).
    """


@dataclass(frozen=True)
class Achat:
    """Ce qu'un paiement a produit, tel que l'appelant en a besoin."""

    organisation: Organisation
    compte: CompteClient
    offre: Offer
    #: Faux quand la session avait déjà été traitée — le webhook et la page de
    #: retour se croisant, c'est le cas NORMAL une fois sur deux.
    nouveau: bool


def _texte(source: dict[str, Any], *chemins: str) -> str:
    """Première valeur non vide parmi des chemins pointés."""
    for chemin in chemins:
        courant: Any = source
        for partie in chemin.split("."):
            if not isinstance(courant, dict):
                courant = None
                break
            courant = courant.get(partie)
        if courant not in (None, ""):
            return str(courant).strip()
    return ""


def est_un_achat_de_livrable(session: dict[str, Any]) -> bool:
    return str((session.get("metadata") or {}).get("achat") or "") == "livrable"


def _raison_sociale(email: str, session: dict[str, Any]) -> str:
    """Le nom de l'espace, à défaut de l'avoir demandé.

    On n'exige PAS de raison sociale à l'achat : un porteur de projet qui teste
    une idée n'a souvent pas encore de société, et un champ obligatoire de plus
    avant le paiement se paie en abandons. Le nom que Stripe a collecté fait
    l'affaire, et la personne peut le corriger dans son espace.
    """
    nom = _texte(session, "customer_details.name", "customer_details.email")
    return (nom or email.split("@", 1)[0] or "Mon espace")[:200]


def _organisation_existante(
    contact: Customer, session: dict[str, Any]
) -> Organisation | None:
    """L'espace que cette personne possède déjà, s'il y en a un.

    Un second achat ne doit PAS ouvrir un second espace : la personne se
    retrouverait avec deux historiques, deux portefeuilles, et un crédit dans
    celui où elle n'est pas connectée. On crédite l'espace existant — y compris
    celui d'une abonnée, qui a parfaitement le droit d'acheter une étude à
    l'unité en plus de sa dotation.

    **Deux façons de le retrouver, dans cet ordre.**

    1. L'identifiant posé dans les métadonnées, quand l'achat part de l'espace
       client : la personne est connectée, on SAIT qui elle est.
    2. À défaut, son adresse — le seul lien disponible pour un achat public.

    L'ordre compte. Stripe laisse modifier l'adresse sur sa propre page : un
    acheteur connecté qui la corrige, ou qui paie avec celle de sa société,
    ferait échouer la reconnaissance par adresse. Il aurait payé, tout serait
    en règle, et son crédit l'attendrait dans un espace où il ne se connectera
    jamais.
    """
    identifiant = str((session.get("metadata") or {}).get("organisation_id") or "").strip()
    if identifiant:
        connue = Organisation.objects.filter(id=identifiant).first()
        if connue is not None:
            return connue
        # Elle a disparu entre l'ouverture du paiement et son encaissement.
        # On ne se rabat PAS silencieusement sur l'adresse : le dire fort vaut
        # mieux que créditer un espace que personne n'a désigné (règle 1).
        _log.warning(
            "Achat rattaché à l'organisation %s, introuvable ; "
            "on retombe sur l'adresse.", identifiant,
        )

    appartenances = list(
        MembreOrganisation.objects.select_related("organisation")
        .filter(customer=contact, revoque_le__isnull=True)
        .order_by("created_at")
    )
    for appartenance in appartenances:
        if _rattachement_accepte(contact, appartenance):
            return appartenance.organisation

    # Restent les invitations que la personne n'a JAMAIS acceptées. Son achat
    # ne va pas à qui l'a invitée : elle ouvre son propre espace, et
    # l'invitation tombe — un seul rattachement actif par personne, c'est ce
    # que suppose tout le cloisonnement de l'espace.
    for appartenance in appartenances:
        try:
            services.revoquer_membre(appartenance)
        except services.AccesRefuseError:
            # Seule propriétaire d'une organisation qu'on ne peut pas laisser
            # sans personne : c'est la sienne, faute de mieux.
            return appartenance.organisation
        _log.warning(
            "Invitation jamais acceptée de %s dans %s : révoquée, son achat "
            "ouvre son propre espace.", contact.email, appartenance.organisation,
        )
    return None


def _rattachement_accepte(contact: Customer, appartenance: MembreOrganisation) -> bool:
    """Cette personne est-elle VRAIMENT de cette organisation ?

    ## Le défaut, trouvé à l'audit de sécurité du 19/11/2026

    Inviter rattache tout de suite, sans que l'invitée ait rien accepté, et la
    reconnaissance d'un achat public se faisait sur ce seul rattachement. Il
    suffisait donc d'ouvrir un compte gratuit et d'inviter l'adresse de
    quelqu'un : le jour où cette personne achetait une étude sur la page
    publique, son crédit et son encaissement allaient à l'organisation de
    l'inviteur, qui pouvait le dépenser et lire ses dossiers.

    ## La règle

    Un rattachement compte quand la personne l'a fait sien :

    - elle est le contact de l'organisation — c'est elle qui l'a ouverte, par
      son inscription ou par un premier achat ;
    - ou elle s'y est CONNECTÉE depuis qu'elle y est rattachée : elle a suivi
      le lien de l'invitation, posé son mot de passe, vu où elle arrivait.

    Une adresse inscrite par quelqu'un d'autre et jamais venue n'engage pas
    son titulaire.
    """
    if appartenance.organisation.contact_id == contact.id:
        return True
    compte = CompteClient.objects.filter(customer=contact, actif=True).first()
    return (
        compte is not None
        and compte.derniere_connexion is not None
        and compte.derniere_connexion >= appartenance.created_at
    )


def espace_de_l_acheteur(
    session: dict[str, Any], *, email: str, reference: str
) -> tuple[Organisation, CompteClient]:
    """L'espace et le compte que CE paiement crédite — créés s'il n'y en a pas.

    Une seule écriture pour l'achat d'une étude et l'achat de boutique : les
    deux portaient la même suite de lignes, et chaque garde ajoutée à l'une
    manquait à l'autre (règle 5).

    Deux gardes y vivent, toutes deux de l'audit du 19/11/2026.

    **Une arrivée à la fois par personne.** Le webhook et la page de retour
    arrivent ensemble. Chacune lisait « aucun espace » et en créait un : deux
    organisations pour un achat, et — pour quelqu'un qui avait déjà un compte —
    deux crédits, chaque portefeuille étant verrouillé séparément. La fiche de
    la personne est verrouillée dès qu'elle est connue ; la seconde arrivée
    attend, puis trouve l'espace que la première a ouvert.

    **Le compte n'est dit « né de l'achat » que si l'ESPACE l'est.** La marque
    ouvre une session sans mot de passe au retour du paiement. Posée dès que
    l'identifiant de connexion était neuf, elle l'était aussi pour une
    personne rattachée de longue date à une organisation et qui n'avait
    simplement jamais eu de compte : payer avec son adresse ouvrait cet
    espace-là.
    """
    contact, _ = Customer.objects.get_or_create(
        email=email,
        defaults={
            "first_name": _texte(session, "customer_details.name")[:150],
            "company_name": "",
        },
    )
    Customer.objects.select_for_update().get(pk=contact.pk)

    organisation = _organisation_existante(contact, session)
    ouvert_par_ce_paiement = organisation is None
    if organisation is None:
        organisation = services.creer_organisation(
            raison_sociale=_raison_sociale(email, session), contact=contact
        )
        organisation.type_de_compte = TypeDeCompte.A_L_UNITE
        organisation.save(update_fields=["type_de_compte", "updated_at"])

    compte = identifiants.compte_sans_mot_de_passe(
        contact, ne_de_l_achat=reference if ouvert_par_ce_paiement else ""
    )
    return organisation, compte


def _enregistrer_l_encaissement(
    organisation: Organisation, offre: Offer, session: dict[str, Any], reference: str
) -> None:
    """Une recette réelle, à côté de celles des abonnements.

    Sans cette ligne, un achat à l'unité serait invisible du chiffre d'affaires
    réalisé : la supervision ne compte que des `Encaissement`, et un paiement
    qui n'en produit pas est de l'argent perçu que la plateforme ignore.

    `reference_facture` est unique en base : c'est le second verrou, et il ne
    juge pas sur la même évidence que le mouvement de crédit (règle 9).
    """
    montant = int(session.get("amount_total") or offre.prix_unitaire_cents or 0)
    if montant <= 0:
        return
    Encaissement.objects.get_or_create(
        reference_facture=reference,
        defaults={
            "organisation": organisation,
            # Pas de formule : cet achat n'en dépend d'aucune. Le champ garde
            # le SLUG de l'offre, pour que la ligne dise ce qui a été vendu.
            "formule_code": offre.slug,
            "montant_cents": montant,
            "devise": str(session.get("currency") or "eur").upper()[:3],
            "paye_le": timezone.now(),
        },
    )


@transaction.atomic
def livrer_l_achat(session: dict[str, Any]) -> Achat:
    """Crée le compte de l'acheteur et lui verse son unique crédit.

    Rejouable sans effet : appelée deux fois sur la même session, la seconde
    rend l'achat déjà constitué avec `nouveau=False`.
    """
    reference = str(session.get("id") or "").strip()
    if not reference:
        msg = "Session de paiement sans identifiant."
        raise AchatInexploitable(msg)

    # Stripe ne dit pas « payé » de la même façon selon le mode. Sur un
    # paiement unique, `payment_status` fait foi ; `status: complete` signifie
    # seulement que le formulaire est allé au bout.
    if str(session.get("payment_status") or "") != "paid":
        msg = f"Session {reference} non payée ({session.get('payment_status')!r})."
        raise AchatInexploitable(msg)

    slug = str((session.get("metadata") or {}).get("offre_slug") or "").strip()
    offre = Offer.objects.filter(slug=slug, is_active=True).first()
    if offre is None:
        msg = f"Session {reference} : offre « {slug} » inconnue ou inactive."
        raise AchatInexploitable(msg)

    email = _texte(session, "customer_details.email", "customer_email").lower()
    if not email:
        msg = f"Session {reference} : aucune adresse collectée par Stripe."
        raise AchatInexploitable(msg)

    organisation, compte = espace_de_l_acheteur(session, email=email, reference=reference)

    # `verser_un_achat` verse en ACHAT et non en DOTATION :
    # `credits.ENTREES_PERENNES` distingue les deux, et une dotation EXPIRE en
    # fin de période. Quelqu'un qui achète une étude le 30 verrait son crédit
    # disparaître le 31.
    verse = credits_service.verser_un_achat(
        organisation,
        CREDITS_PAR_ACHAT,
        motif=f"Achat à l'unité — {offre.name}",
        reference=reference,
        auteur="stripe",
        # Le credit est paye POUR CETTE ETUDE. Sans ce marquage, 89 EUR verses
        # pour une etude de concurrence ouvriraient une strategie a 195 EUR :
        # le prix affiche sur la page de vente cesserait de vouloir dire quoi
        # que ce soit.
        livrable=offre.deliverable_type,
    )
    if verse is None:
        # Le webhook et la page de retour se sont croisés. Ce n'est pas une
        # anomalie : c'est le fonctionnement normal, et le dire en journal
        # évite qu'on le prenne un jour pour un bug.
        _log.info("Achat %s déjà livré, second appel sans effet.", reference)
        return Achat(organisation, compte, offre, nouveau=False)
    _enregistrer_l_encaissement(organisation, offre, session, reference)

    _log.info(
        "Achat à l'unité livré : %s pour %s (organisation %s).",
        offre.slug, email, organisation.id,
    )
    return Achat(organisation, compte, offre, nouveau=True)


def prevenir_l_acheteur(achat: Achat) -> bool:
    """Le courriel qui donne l'accès, envoyé HORS de la transaction.

    Un envoi à l'intérieur du `atomic` partirait puis serait démenti par un
    retour arrière : la personne aurait reçu son lien vers un espace qui
    n'existe pas. Ici l'inverse est vrai — l'espace existe, et un envoi raté
    n'annule rien : la personne est déjà connectée par la page de retour, et
    peut redemander un lien par la procédure d'oubli.
    """
    return courriels.souhaiter_la_bienvenue(
        destinataire=achat.compte.customer.email,
        livrable=achat.offre.name.lower(),
        lien=identifiants.lien_pour(achat.compte),
    )
