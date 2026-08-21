"""Ce qu'un paiement de produit de boutique produit : un compte, et un acces.

Frere de `paiement.achats`, et volontairement separe. Les deux repondent au
meme evenement de paiement, mais ne livrent pas la meme chose :

- `achats` verse un CREDIT, qui declenchera une production ;
- `boutique` ouvre un ACCES a un fichier ecrit il y a des mois.

Les fondre dans une seule fonction aurait donne un traitement a deux branches
ou chaque correctif devrait se demander laquelle il touche.

Ce qui est commun — reconnaitre l'acheteur, retrouver ou creer son espace —
est importe de `achats` plutot que recopie.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import AchatProduit, ProduitBoutique
from customers.models import Customer
from organisations import courriels, identifiants, services
from organisations.models import CompteClient, Encaissement, Organisation, TypeDeCompte

from .achats import AchatInexploitable as AchatInexploitable
from .achats import _organisation_existante, _raison_sociale, _texte

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AchatDeProduit:
    """Ce qu'un paiement de boutique a produit."""

    organisation: Organisation
    compte: CompteClient
    produit: ProduitBoutique
    achat: AchatProduit
    #: Faux quand la session avait deja ete traitee — le webhook et la page de
    #: retour se croisant, c'est le cas NORMAL une fois sur deux.
    nouveau: bool


def est_un_achat_de_produit(session: dict[str, Any]) -> bool:
    return str((session.get("metadata") or {}).get("achat") or "") == "produit"


def _enregistrer_l_encaissement(
    organisation: Organisation,
    produit: ProduitBoutique,
    session: dict[str, Any],
    reference: str,
) -> None:
    """Une recette reelle, a cote de celles des abonnements et des livrables.

    Sans cette ligne, une vente de boutique serait invisible du chiffre
    d'affaires : la supervision ne compte que des `Encaissement`.
    """
    montant = int(session.get("amount_total") or produit.prix_cents or 0)
    if montant <= 0:
        return
    Encaissement.objects.get_or_create(
        reference_facture=reference,
        defaults={
            "organisation": organisation,
            # Pas de formule : cette vente n'en depend d'aucune. Le champ garde
            # le slug du produit, pour que la ligne dise ce qui a ete vendu.
            "formule_code": produit.slug[:60],
            "montant_cents": montant,
            "devise": str(session.get("currency") or "eur").upper()[:3],
            "paye_le": timezone.now(),
        },
    )


@transaction.atomic
def livrer_le_produit(session: dict[str, Any]) -> AchatDeProduit:
    """Ouvre l'acces au fichier achete, et le compte s'il n'existe pas encore.

    Rejouable sans effet. La garde est l'unicite de `reference_paiement` sur
    `AchatProduit` : deux appels concurrents sur la meme session ne creent
    qu'une ligne, le second recevant `nouveau=False`.
    """
    reference = str(session.get("id") or "").strip()
    if not reference:
        msg = "Session de paiement sans identifiant."
        raise AchatInexploitable(msg)

    # Sur un paiement unique, `payment_status` fait foi. `status: complete` dit
    # seulement que le formulaire est alle au bout.
    if str(session.get("payment_status") or "") != "paid":
        msg = f"Session {reference} non payée ({session.get('payment_status')!r})."
        raise AchatInexploitable(msg)

    slug = str((session.get("metadata") or {}).get("produit_slug") or "").strip()
    produit = ProduitBoutique.objects.filter(slug=slug).first()
    if produit is None:
        msg = f"Session {reference} : produit « {slug} » inconnu."
        raise AchatInexploitable(msg)

    email = _texte(session, "customer_details.email", "customer_email").lower()
    if not email:
        msg = f"Session {reference} : aucune adresse collectée par Stripe."
        raise AchatInexploitable(msg)

    contact, _ = Customer.objects.get_or_create(
        email=email,
        defaults={
            "first_name": _texte(session, "customer_details.name")[:150],
            "company_name": "",
        },
    )

    organisation = _organisation_existante(contact, session)
    if organisation is None:
        organisation = services.creer_organisation(
            raison_sociale=_raison_sociale(email, session), contact=contact
        )
        organisation.type_de_compte = TypeDeCompte.A_L_UNITE
        organisation.save(update_fields=["type_de_compte", "updated_at"])

    compte = identifiants.compte_sans_mot_de_passe(contact)

    existant = AchatProduit.objects.filter(reference_paiement=reference).first()
    if existant is not None:
        # Le webhook et la page de retour se sont croises. C'est le
        # fonctionnement normal, et le dire en journal evite qu'on le prenne
        # un jour pour une anomalie.
        _log.info("Achat de boutique %s déjà livré, second appel sans effet.", reference)
        return AchatDeProduit(organisation, compte, produit, existant, nouveau=False)

    try:
        achat = AchatProduit.objects.create(
            organisation=organisation,
            produit=produit,
            reference_paiement=reference,
            montant_cents=int(session.get("amount_total") or produit.prix_cents or 0),
            devise=str(session.get("currency") or produit.devise or "EUR").upper()[:3],
            email=email,
        )
    except IntegrityError:
        # Deux appels exactement simultanes : la base a tranche. On relit la
        # ligne gagnante plutot que de faire echouer un paiement encaisse.
        achat = AchatProduit.objects.get(reference_paiement=reference)
        return AchatDeProduit(organisation, compte, produit, achat, nouveau=False)

    _enregistrer_l_encaissement(organisation, produit, session, reference)
    solder_la_tentative(reference, organisation)

    _log.info(
        "Produit de boutique livré : %s pour %s (organisation %s).",
        produit.slug, email, organisation.id,
    )
    return AchatDeProduit(organisation, compte, produit, achat, nouveau=True)


def solder_la_tentative(reference: str, organisation: Any = None) -> None:
    """Marque le panier comme PAYE, et lui rattache l'organisation nee du paiement.

    Le webhook le fait deja de son cote. On le refait ici parce que la page de
    retour livre sans lui : si le webhook tarde ou n'arrive pas, un achat bel
    et bien encaisse resterait « ouvert » puis passerait « abandonne » au bout
    de vingt-quatre heures. La cliente relancerait alors quelqu'un qui a paye —
    exactement le contraire de ce que cet ecran doit permettre.

    Ne leve jamais : le suivi commercial ne fait pas echouer une livraison.
    """
    from django.utils import timezone  # noqa: PLC0415

    from organisations.models import EtatTentative, TentativePaiement  # noqa: PLC0415

    if not reference:
        return
    try:
        champs: dict[str, Any] = {
            "etat": EtatTentative.PAYEE,
            "payee_le": timezone.now(),
        }
        if organisation is not None:
            champs["organisation"] = organisation
        TentativePaiement.objects.filter(reference_session=reference).update(**champs)
    except Exception:  # noqa: BLE001
        _log.exception("Tentative de boutique non soldee (%s)", reference)


def noter_la_tentative(
    *, session: Any, produit: Any, email: str = "", organisation: Any = None
) -> None:
    """Enregistre qu'un paiement de boutique a ete OUVERT, abouti ou non.

    C'est ce qui rend un panier abandonne VISIBLE. Sans cette ligne, un
    visiteur qui clique « Acheter » et referme la page de paiement ne laisse
    aucune trace : la vente est perdue et personne ne le sait — or c'est
    l'abandon le plus frequent de la boutique, puisqu'on y achete sans compte.

    La tentative porte l'ADRESSE plutot qu'une organisation : il n'y en a pas
    encore, elle naitra de l'encaissement. C'est aussi le seul point de contact
    pour relancer.

    **Ne leve jamais.** Un defaut de suivi ne doit pas empecher un client de
    payer : le geste qui rapporte passe avant celui qui l'observe.
    """
    from organisations.models import ObjetTentative, TentativePaiement  # noqa: PLC0415

    reference = str(session.get("id") or "") if isinstance(session, dict) else ""
    if not reference:
        reference = str(getattr(session, "identifiant", "") or "")
    if not reference:
        return
    try:
        TentativePaiement.objects.get_or_create(
            reference_session=reference,
            defaults={
                "organisation": organisation,
                "email": email,
                "produit": produit,
                "objet": ObjetTentative.PRODUIT,
                "montant_cents": int(getattr(produit, "prix_cents", 0) or 0),
                "devise": str(getattr(produit, "devise", "EUR") or "EUR"),
            },
        )
    except Exception:  # noqa: BLE001
        _log.exception("Tentative de boutique non enregistree (%s)", reference)


def lien_de_telechargement(achat: AchatProduit, *, editable: bool = False) -> str:
    """Lien signé et horodaté vers le fichier acheté.

    Le lien n'est pas stocke : il est CALCULE a chaque affichage, avec une
    validite courte. Un lien conserve en base finirait par etre transmis, et
    resterait valable aussi longtemps qu'on le garderait.

    **Absolu**, et c'est la moitie de l'affaire : ce lien s'affiche sur
    `app2.evkha.fr` — la page de retour de paiement et « Mes achats » — alors
    que `/media/` est servi par `api2.evkha.fr`. Un chemin relatif y tombe sur
    le repli SPA de nginx, et l'acheteur telecharge la page de l'application au
    lieu de son etude, en 200.
    """
    from evkha import signatures  # noqa: PLC0415 — evite un cycle a l'import

    fichier = achat.produit.fichier_editable if editable else achat.produit.fichier
    if not fichier:
        return ""
    return signatures.lien_absolu(fichier.name)


def prevenir_l_acheteur(resultat: AchatDeProduit) -> bool:
    """Le courriel qui donne l'acces, envoye HORS de la transaction.

    Un envoi a l'interieur du `atomic` partirait puis serait dementi par un
    retour arriere : la personne aurait recu un lien vers un achat qui
    n'existe pas.
    """
    return courriels.souhaiter_la_bienvenue(
        destinataire=resultat.compte.customer.email,
        livrable=resultat.produit.titre,
        lien=identifiants.lien_pour(resultat.compte),
    )
