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
    MouvementCredit,
    Organisation,
    TentativePaiement,
    TypeDeCompte,
    TypeMouvement,
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
    #: `None` au REJEU d'une session déjà livrée à quelqu'un qui avait un
    #: compte : il n'y a alors ni session à ouvrir, ni courriel à envoyer.
    compte: CompteClient | None
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


#: Ce qu'une référence abrégée garde de son début et de sa fin.
_DEBUT_DE_REFERENCE = 12
_FIN_DE_REFERENCE = 4


def reference_abregee(reference: object) -> str:
    """Une référence de paiement telle qu'on l'écrit dans un journal.

    L'identifiant d'une session Checkout n'est pas un simple numéro de
    dossier : présenté à une page de retour, il ouvre la première session du
    compte né de ce paiement (`authentification.ouvrir_la_session_d_un_achat`).
    Écrit en entier dans un journal ou dans un incident, il est lisible par
    quiconque lit ce journal.

    Le début dit l'environnement et commence l'identifiant, la fin le
    distingue de ses voisins : assez pour reconnaître une ligne, trop peu
    pour la rejouer. La référence ENTIÈRE reste en base, là où elle sert de
    verrou (`AchatFormation.reference_paiement`, `Encaissement`,
    `TentativePaiement`).

    Une seule écriture, pour les journaux, les incidents et l'administration
    (règle 5).
    """
    texte = str(reference or "")
    if len(texte) <= _DEBUT_DE_REFERENCE + _FIN_DE_REFERENCE:
        # Trop courte pour être coupée sans être rendue entière : on n'en
        # garde que la moitié.
        return f"{texte[: len(texte) // 2]}…" if texte else ""
    return f"{texte[:_DEBUT_DE_REFERENCE]}…{texte[-_FIN_DE_REFERENCE:]}"


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
            "Achat rattaché à une organisation introuvable (%s) ; "
            "on retombe sur l'adresse.",
            # Venu des métadonnées : borné, et sans saut de ligne. Pas abrégé :
            # ce n'est pas un secret, et il sert à retrouver l'organisation.
            repr(identifiant[:64]),
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
        # Sans l'adresse : la fiche et l'organisation suffisent à retrouver
        # qui, et un journal n'a pas à porter des adresses de clients.
        _log.warning(
            "Invitation jamais acceptée (fiche %s, organisation %s) : révoquée, "
            "son achat ouvre son propre espace.",
            contact.pk, appartenance.organisation_id,
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


def compte_ne_de_l_achat(reference: str) -> CompteClient | None:
    """Le compte que CE paiement a créé, s'il en a créé un. Ne modifie rien.

    Sert au REJEU d'une session déjà livrée (audit du 20/11/2026) : la
    livraison ne repasse alors plus par `espace_de_l_acheteur`, qui révoque
    des invitations et ouvre un espace — un rejeu ne doit rien écrire.

    `None` quand l'acheteur avait déjà un compte : la page de retour n'ouvre
    de toute façon de session que sur le compte né du paiement
    (`authentification.ouvrir_la_session_d_un_achat`), et le courriel
    d'annonce ne part qu'à la première livraison.
    """
    if not reference:
        return None
    return (
        CompteClient.objects.select_related("customer", "user")
        # Même coupe que `identifiants.compte_sans_mot_de_passe`, qui l'inscrit.
        .filter(ne_de_l_achat=reference[:255])
        .first()
    )


def _entier_strict(valeur: object) -> int | None:
    """Un entier, ou `None`. `True` n'est pas 1, « 100 » n'est pas 100."""
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return None
    return valeur


def exiger_ce_qui_a_ete_ouvert(
    session: dict[str, Any], *, reference: str, prix_cents: int, devise: str
) -> None:
    """Refuse une session payée qui n'est pas celle que nous avons ouverte.

    ## Le défaut, trouvé à l'audit de sécurité du 20/11/2026

    La livraison d'une formation ou d'une étude de boutique ne regardait que
    `payment_status` et le slug des métadonnées. Elle ne vérifiait ni que la
    session était un paiement UNIQUE, ni que le montant encaissé était le
    prix : toute session payée portant le bon slug ouvrait l'accès, quel
    qu'en soit le montant.

    ## La règle

    - `mode == "payment"` : une session d'abonnement ou d'enregistrement de
      carte n'achète rien ici ;
    - `amount_total` et `currency` sont ceux du PANIER enregistré à
      l'ouverture de cette session (`TentativePaiement`), quand il existe. Le
      prix du catalogue peut changer entre l'ouverture et l'encaissement : qui
      a payé le prix affiché au clic est livré, et un prix baissé depuis ne
      rend pas juste un montant qui n'est pas celui qui a été ouvert ;
    - à défaut de panier — son enregistrement ne lève jamais, il peut donc
      manquer —, le prix courant passé par l'appelant.

    Un écart lève `AchatInexploitable` : rien n'est livré, et le webhook en
    fait un incident. Sans montant de référence, on refuse aussi (règle 1).

    Une seule écriture pour la boutique et les formations (règle 5).

    **Non couvert ici** : une session réglée dans une autre devise que celle
    du prix (conversion proposée par le prestataire sur sa page) serait
    refusée, et signalée. C'est le comportement voulu tant que personne n'a
    décidé de vendre en plusieurs devises.
    """
    abrege = reference_abregee(reference)
    mode = str(session.get("mode") or "")
    if mode != "payment":
        msg = f"Session {abrege} : ce n'est pas un paiement unique (mode {mode!r})."
        raise AchatInexploitable(msg)

    panier = TentativePaiement.objects.filter(reference_session=reference).first()
    if panier is not None and panier.montant_cents > 0:
        attendu, devise_attendue, origine = (
            int(panier.montant_cents), str(panier.devise or ""), "ouvert",
        )
    else:
        attendu, devise_attendue, origine = int(prix_cents or 0), str(devise or ""), "courant"
    devise_attendue = devise_attendue.upper()[:3]

    paye = _entier_strict(session.get("amount_total"))
    devise_payee = str(session.get("currency") or "").upper()
    if attendu <= 0 or not devise_attendue or paye != attendu or devise_payee != devise_attendue:
        msg = (
            f"Session {abrege} : le montant payé "
            f"({session.get('amount_total')!r} {devise_payee or 'sans devise'}) ne "
            f"correspond pas au prix {origine} ({attendu} {devise_attendue or 'sans devise'})."
        )
        raise AchatInexploitable(msg)


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

    ## Les deux défauts, laissés ouverts par l'audit du 20/11/2026

    La boutique et les formations avaient reçu ces deux gardes ; l'étude à
    l'unité, le plus ancien des trois achats, non.

    **L'idempotence d'abord.** Le crédit déjà versé n'était reconnu qu'APRÈS
    `espace_de_l_acheteur`, qui révoque des invitations jamais acceptées et
    ouvre une organisation. Or une session se rejoue — le prestataire renvoie
    ses événements pendant trois jours, l'identifiant se représente à volonté
    sur la page de retour — et un rejeu ne doit plus rien écrire. Même règle
    que `boutique.livrer_le_produit`.

    **Ce qui est livré est ce qui a été ouvert.** Seuls `payment_status` et le
    slug étaient lus : toute session payée portant le slug d'une étude versait
    son crédit, quel que soit le montant encaissé
    (`exiger_ce_qui_a_ete_ouvert`).
    """
    reference = str(session.get("id") or "").strip()
    if not reference:
        msg = "Session de paiement sans identifiant."
        raise AchatInexploitable(msg)
    abrege = reference_abregee(reference)

    slug = str((session.get("metadata") or {}).get("offre_slug") or "").strip()

    deja = (
        MouvementCredit.objects.select_related("portefeuille__organisation")
        # Le VERSEMENT de cet achat, et lui seul : la référence sert aussi aux
        # gestes manuels, et un geste saisi avec l'identifiant d'une session
        # ne doit pas la faire passer pour livrée.
        .filter(reference=reference, type=TypeMouvement.ACHAT)
        .order_by("created_at")
        .first()
    )
    if deja is not None:
        # L'offre a pu être désactivée, renommée ou retirée depuis : pour un
        # rejeu, elle sert seulement à dire ce qui a été acheté. Un achat
        # DÉJÀ livré ne devient pas « inexploitable » — incident à l'appui —
        # parce que le catalogue a bougé : à défaut, une offre non enregistrée
        # porte le type de livrable que le crédit a gardé.
        vendue = Offer.objects.filter(slug=slug).first() or Offer(
            slug=slug[:80], name="Votre étude", deliverable_type=deja.livrable
        )
        _log.info("Achat %s déjà livré, rejeu sans effet.", abrege)
        return Achat(
            deja.portefeuille.organisation,
            compte_ne_de_l_achat(reference),
            vendue,
            nouveau=False,
        )

    # Stripe ne dit pas « payé » de la même façon selon le mode. Sur un
    # paiement unique, `payment_status` fait foi ; `status: complete` signifie
    # seulement que le formulaire est allé au bout.
    if str(session.get("payment_status") or "") != "paid":
        msg = f"Session {abrege} non payée ({session.get('payment_status')!r})."
        raise AchatInexploitable(msg)

    offre = Offer.objects.filter(slug=slug, is_active=True).first()
    if offre is None:
        # Le slug vient des métadonnées : borné, et sans saut de ligne.
        msg = f"Session {abrege} : offre {slug[:80]!r} inconnue ou inactive."
        raise AchatInexploitable(msg)

    exiger_ce_qui_a_ete_ouvert(
        session,
        reference=reference,
        prix_cents=int(offre.prix_unitaire_cents or 0),
        # `stripe_api.creer_paiement_de_livrable` ouvre en euros, sans autre
        # choix : une offre n'a pas de devise à elle.
        devise="EUR",
    )

    email = _texte(session, "customer_details.email", "customer_email").lower()
    if not email:
        msg = f"Session {abrege} : aucune adresse collectée par Stripe."
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
        _log.info("Achat %s déjà livré, second appel sans effet.", abrege)
        return Achat(organisation, compte, offre, nouveau=False)
    _enregistrer_l_encaissement(organisation, offre, session, reference)

    # Sans l'adresse de l'acheteur : l'organisation suffit à le retrouver.
    _log.info(
        "Achat à l'unité livré : %s (organisation %s).", offre.slug, organisation.id,
    )
    return Achat(organisation, compte, offre, nouveau=True)


def prevenir_l_acheteur(achat: Achat) -> bool:
    """Le courriel qui donne l'accès, envoyé HORS de la transaction.

    Un envoi à l'intérieur du `atomic` partirait puis serait démenti par un
    retour arrière : la personne aurait reçu son lien vers un espace qui
    n'existe pas. Ici l'inverse est vrai — l'espace existe, et un envoi raté
    n'annule rien : la personne est déjà connectée par la page de retour, et
    peut redemander un lien par la procédure d'oubli.

    Rien ne part pour un rejeu, qui peut ne plus avoir de compte à désigner.
    """
    if achat.compte is None:
        return False
    return courriels.souhaiter_la_bienvenue(
        destinataire=achat.compte.customer.email,
        livrable=achat.offre.name.lower(),
        lien=identifiants.lien_pour(achat.compte),
    )
