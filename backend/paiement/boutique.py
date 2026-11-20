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
from organisations import courriels, identifiants
from organisations.models import CompteClient, Encaissement, Organisation

from .achats import AchatInexploitable as AchatInexploitable
from .achats import (
    _texte,
    compte_ne_de_l_achat,
    espace_de_l_acheteur,
    exiger_ce_qui_a_ete_ouvert,
    reference_abregee,
)

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AchatDeProduit:
    """Ce qu'un paiement de boutique a produit."""

    organisation: Organisation
    #: `None` seulement au REJEU d'une session deja livree dont l'acheteur
    #: avait deja un compte (voir `achats.compte_ne_de_l_achat`).
    compte: CompteClient | None
    produit: ProduitBoutique
    achat: AchatProduit
    #: Faux quand la session avait deja ete traitee — le webhook et la page de
    #: retour se croisant, c'est le cas NORMAL une fois sur deux.
    nouveau: bool


def est_un_achat_de_produit(session: dict[str, Any]) -> bool:
    return str((session.get("metadata") or {}).get("achat") or "") == "produit"


def enregistrer_la_recette(
    organisation: Organisation,
    *,
    slug: str,
    prix_cents: int,
    session: dict[str, Any],
    reference: str,
) -> None:
    """Une recette reelle, a cote de celles des abonnements et des livrables.

    Sans cette ligne, une vente serait invisible du chiffre d'affaires : la
    supervision ne compte que des `Encaissement`.

    Ecrite une fois pour ce qui se vend SANS formule — l'etude de boutique et
    la formation (`paiement.formations`) : deux ecritures de la meme ligne
    comptable finiraient par ne plus arrondir, ni dater, de la meme facon
    (regle 5).

    `get_or_create` sur la reference de la session : rejouee, elle ne compte
    pas deux fois ; deux sessions distinctes font deux recettes — y compris
    quand elles paient deux fois la meme chose, ce qui est alors VRAI.
    """
    montant = int(session.get("amount_total") or prix_cents or 0)
    if montant <= 0:
        return
    Encaissement.objects.get_or_create(
        reference_facture=reference,
        defaults={
            "organisation": organisation,
            # Pas de formule : cette vente n'en depend d'aucune. Le champ garde
            # le slug de ce qui a ete vendu, pour que la ligne le dise.
            "formule_code": slug[:60],
            "montant_cents": montant,
            "devise": str(session.get("currency") or "eur").upper()[:3],
            "paye_le": timezone.now(),
        },
    )


def _enregistrer_l_encaissement(
    organisation: Organisation,
    produit: ProduitBoutique,
    session: dict[str, Any],
    reference: str,
) -> None:
    """La recette d'une etude de boutique (voir `enregistrer_la_recette`)."""
    enregistrer_la_recette(
        organisation,
        slug=produit.slug,
        prix_cents=produit.prix_cents,
        session=session,
        reference=reference,
    )


@transaction.atomic
def livrer_le_produit(session: dict[str, Any]) -> AchatDeProduit:
    """Ouvre l'acces au fichier achete, et le compte s'il n'existe pas encore.

    Rejouable sans effet. La garde est l'unicite de `reference_paiement` sur
    `AchatProduit` : deux appels concurrents sur la meme session ne creent
    qu'une ligne, le second recevant `nouveau=False`.

    **L'idempotence d'abord** (audit de securite du 20/11/2026). L'achat deja
    livre est cherche AVANT `espace_de_l_acheteur`, qui revoque des
    invitations jamais acceptees et ouvre une organisation : une session se
    rejoue — le prestataire renvoie ses evenements pendant trois jours,
    l'identifiant se represente a volonte sur la page de retour — et un rejeu
    ne doit plus rien ecrire. Meme regle que
    `paiement.formations._deja_traitee`.

    **Ce qui est livre est ce qui a ete ouvert** : un paiement unique, au
    montant et dans la devise du panier (`achats.exiger_ce_qui_a_ete_ouvert`).
    """
    reference = str(session.get("id") or "").strip()
    if not reference:
        msg = "Session de paiement sans identifiant."
        raise AchatInexploitable(msg)

    deja = (
        AchatProduit.objects.select_related("organisation", "produit")
        .filter(reference_paiement=reference)
        .first()
    )
    if deja is not None:
        _log.info(
            "Achat de boutique %s déjà livré, rejeu sans effet.",
            reference_abregee(reference),
        )
        return AchatDeProduit(
            deja.organisation,
            compte_ne_de_l_achat(reference),
            deja.produit,
            deja,
            nouveau=False,
        )

    # Sur un paiement unique, `payment_status` fait foi. `status: complete` dit
    # seulement que le formulaire est alle au bout.
    if str(session.get("payment_status") or "") != "paid":
        msg = (
            f"Session {reference_abregee(reference)} non payée "
            f"({session.get('payment_status')!r})."
        )
        raise AchatInexploitable(msg)

    slug = str((session.get("metadata") or {}).get("produit_slug") or "").strip()
    produit = ProduitBoutique.objects.filter(slug=slug).first()
    if produit is None:
        msg = f"Session {reference_abregee(reference)} : produit {slug[:80]!r} inconnu."
        raise AchatInexploitable(msg)

    exiger_ce_qui_a_ete_ouvert(
        session,
        reference=reference,
        prix_cents=produit.prix_cents,
        devise=produit.devise,
    )

    email = _texte(session, "customer_details.email", "customer_email").lower()
    if not email:
        msg = (
            f"Session {reference_abregee(reference)} : aucune adresse "
            "collectée par Stripe."
        )
        raise AchatInexploitable(msg)

    organisation, compte = espace_de_l_acheteur(session, email=email, reference=reference)

    # Relu SOUS le verrou que `espace_de_l_acheteur` vient de poser : deux
    # arrivees exactement simultanees ont toutes deux passe la garde du haut.
    existant = AchatProduit.objects.filter(reference_paiement=reference).first()
    if existant is not None:
        # Le webhook et la page de retour se sont croises. C'est le
        # fonctionnement normal, et le dire en journal evite qu'on le prenne
        # un jour pour une anomalie.
        _log.info(
            "Achat de boutique %s déjà livré, second appel sans effet.",
            reference_abregee(reference),
        )
        return AchatDeProduit(organisation, compte, produit, existant, nouveau=False)

    try:
        # Point de sauvegarde : sous PostgreSQL, une erreur d'intégrité rend la
        # transaction englobante inutilisable, et la relecture du `except`
        # échouait à son tour — le perdant d'une arrivée simultanée recevait
        # une erreur 500 au lieu de son achat (audit du 19/11/2026).
        with transaction.atomic():
            achat = AchatProduit.objects.create(
                organisation=organisation,
                produit=produit,
                reference_paiement=reference,
                # Verifies plus haut : ce sont ceux du prix ouvert.
                montant_cents=int(session["amount_total"]),
                devise=str(session["currency"]).upper()[:3],
                email=email,
            )
    except IntegrityError:
        # Deux appels exactement simultanes : la base a tranche. On relit la
        # ligne gagnante plutot que de faire echouer un paiement encaisse.
        achat = AchatProduit.objects.get(reference_paiement=reference)
        return AchatDeProduit(organisation, compte, produit, achat, nouveau=False)

    _enregistrer_l_encaissement(organisation, produit, session, reference)
    solder_la_tentative(reference, organisation)

    # Sans l'adresse de l'acheteur : l'organisation suffit a le retrouver.
    _log.info(
        "Produit de boutique livré : %s (organisation %s).",
        produit.slug, organisation.id,
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
        _log.exception(
            "Tentative de boutique non soldee (%s)", reference_abregee(reference)
        )


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
        _log.exception(
            "Tentative de boutique non enregistree (%s)",
            reference_abregee(reference),
        )


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
    if resultat.compte is None:
        # Un rejeu, qui n'annonce rien : voir `AchatDeProduit.compte`.
        return False
    return courriels.souhaiter_la_bienvenue(
        destinataire=resultat.compte.customer.email,
        livrable=resultat.produit.titre,
        lien=identifiants.lien_pour(resultat.compte),
    )
