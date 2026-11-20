"""Ce qu'un paiement de formation produit : un compte, et un accès au programme.

Troisième frère de `paiement.achats` et `paiement.boutique`, et séparé pour la
même raison qu'eux : les trois répondent au même événement de paiement, mais ne
livrent pas la même chose.

- `achats` verse un CRÉDIT, qui déclenchera une production ;
- `boutique` ouvre l'accès à un FICHIER ;
- ici, le paiement ouvre la LECTURE d'un programme dans l'espace de l'acheteur.

Ce qui est commun est importé, pas recopié : reconnaître l'acheteur
(`achats.espace_de_l_acheteur`), vérifier que la session est celle qui a été
ouverte (`achats.exiger_ce_qui_a_ete_ouvert`), enregistrer la recette
(`boutique.enregistrer_la_recette`), solder le panier
(`boutique.solder_la_tentative`).

Appelé de DEUX endroits — le webhook et la page de retour — qui arrivent sans
ordre garanti. Tout ici est donc rejouable sans effet.

## Ce que les journaux et les incidents de ce module ne portent pas

Ni adresse de courriel — l'identifiant de l'organisation la remplace —, ni
référence de session entière (`achats.reference_abregee` dit pourquoi). Audit
de sécurité du 20/11/2026.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import AchatFormation, EtatDeLAcces, Formation
from catalog.suivi import fin_d_acces
from monitoring.models import IncidentSeverity, OperationalIncident
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
from .boutique import enregistrer_la_recette, solder_la_tentative

_log = logging.getLogger(__name__)

#: Titre et type de l'incident ouvert quand une organisation paie une formation
#: qu'elle possède déjà. Le type est ce que l'on cherche pour ne pas l'ouvrir
#: deux fois ; le titre est ce que la gérante lit.
INCIDENT_PAYEE_DEUX_FOIS = "Formation payée deux fois"
TYPE_PAYEE_DEUX_FOIS = "formation_payee_deux_fois"


@dataclass(frozen=True)
class AchatDeFormation:
    """Ce qu'un paiement de formation a produit."""

    organisation: Organisation
    #: Le compte de l'acheteur. `None` seulement au REJEU d'une session déjà
    #: livrée dont l'acheteur avait déjà un compte : un rejeu ne cherche plus
    #: « l'espace de l'acheteur », il rend ce qui existe
    #: (`achats.compte_ne_de_l_achat`).
    compte: CompteClient | None
    formation: Formation
    #: L'achat qui porte l'accès. Pour un second paiement de la même
    #: formation, c'est celui du PREMIER : il n'y a qu'un accès.
    achat: AchatFormation
    #: Faux quand il n'y a rien de neuf à annoncer : la session avait déjà été
    #: traitée (le webhook et la page de retour se croisent, c'est le cas
    #: NORMAL une fois sur deux), ou l'organisation possédait déjà la formation.
    nouveau: bool
    #: Vrai quand CE paiement en double un autre. L'argent a été pris deux
    #: fois : un incident est ouvert pour que la gérante rembourse.
    en_double: bool = False


def est_un_achat_de_formation(session: dict[str, Any]) -> bool:
    return str((session.get("metadata") or {}).get("achat") or "") == "formation"


def intention_de_paiement(objet: dict[str, Any]) -> str:
    """L'intention de paiement (`pi_…`) citée par un objet du prestataire.

    Une session, un prélèvement et un litige la portent tous sous la même
    clé — tantôt comme une chaîne, tantôt comme l'objet complet, selon
    l'expansion demandée.
    """
    brut = objet.get("payment_intent")
    if isinstance(brut, dict):
        brut = brut.get("id")
    return str(brut or "").strip()[:200]


def achat_de_l_intention(intention: str) -> AchatFormation | None:
    """L'achat de formation que cette intention de paiement a réglé, s'il y en a un.

    C'est le seul rapprochement possible SANS interroger le prestataire : un
    remboursement ou une contestation cite l'intention, jamais la session.
    """
    if not intention:
        return None
    return (
        AchatFormation.objects.select_related("organisation", "formation")
        .filter(intention_de_paiement=intention)
        .order_by("-created_at")
        .first()
    )


def _empreinte(reference: str) -> str:
    """De quoi reconnaître une session dans un incident, sans l'y écrire.

    L'incident ne porte que la référence ABRÉGÉE ; deux références peuvent
    partager leur début et leur fin. L'empreinte, elle, est exacte — et ne se
    rejoue pas.
    """
    return hashlib.sha256(reference.encode("utf-8")).hexdigest()[:32]


def _signaler_le_double_paiement(
    *,
    organisation: Organisation,
    formation: Formation,
    premier: AchatFormation,
    session: dict[str, Any],
    reference: str,
) -> None:
    """Ouvre UN incident par paiement en double, pour que quelqu'un rembourse.

    Rien d'autre ne le dirait : l'accès existe déjà, l'acheteur ne voit aucune
    différence dans son espace, et la recette est juste — elle compte deux
    paiements, parce qu'il y en a eu deux.

    Un seul par session : le webhook et la page de retour passent tous deux
    ici, et deux incidents feraient rembourser deux fois. L'appelant tient le
    verrou posé par `espace_de_l_acheteur` sur la fiche de l'acheteur ; les
    deux arrivées se suivent donc, et la seconde trouve l'incident.

    Ni adresse ni raison sociale — celle-ci vaut l'adresse quand le
    prestataire n'a pas collecté de nom : l'identifiant de l'organisation
    suffit à retrouver l'acheteur dans l'administration. Le paiement se
    retrouve chez le prestataire par son intention (`paiement`).
    """
    empreinte = _empreinte(reference)
    if OperationalIncident.objects.filter(
        details__type=TYPE_PAYEE_DEUX_FOIS, details__empreinte=empreinte
    ).exists():
        return
    OperationalIncident.objects.create(
        title=INCIDENT_PAYEE_DEUX_FOIS,
        severity=IncidentSeverity.HIGH,
        details={
            "type": TYPE_PAYEE_DEUX_FOIS,
            "session": reference_abregee(reference),
            "empreinte": empreinte,
            "paiement": intention_de_paiement(session),
            "premier_paiement": reference_abregee(premier.reference_paiement),
            "formation": formation.slug,
            "organisation": str(organisation.id),
            "montant_cents": str(session.get("amount_total")),
            "devise": str(session.get("currency") or "").upper()[:3],
            "a_faire": (
                "Cette organisation possédait déjà la formation. Aucun second "
                "accès n'a été ouvert. Remboursez ce paiement dans Stripe — "
                "l'intention de paiement ci-dessus le désigne — et prévenez "
                "l'acheteur."
            ),
        },
    )
    _log.error(
        "Formation %s payée deux fois par l'organisation %s (session %s).",
        formation.slug, organisation.id, reference_abregee(reference),
    )


def _dernier_achat(organisation: Organisation, formation: Formation) -> AchatFormation | None:
    """L'achat le plus récent du couple, qu'il donne encore accès ou non."""
    return (
        AchatFormation.objects.filter(organisation=organisation, formation=formation)
        .order_by("-created_at")
        .first()
    )


def _deja_traitee(reference: str, formation: Formation | None) -> AchatDeFormation | None:
    """Ce que cette session a DÉJÀ produit, ou `None`. Ne modifie rien.

    ## Le défaut, trouvé à l'audit de sécurité du 20/11/2026

    La livraison cherchait d'abord « l'espace de l'acheteur » — qui révoque
    des invitations jamais acceptées et ouvre une organisation — et ne
    regardait qu'ENSUITE si la session avait déjà été livrée. Or une session
    se rejoue : Stripe renvoie ses événements pendant trois jours, et
    l'identifiant se représente à volonté sur la page de retour. Entre deux
    passages, l'acheteur a pu changer d'adresse, être invité ailleurs : le
    rejeu touchait alors à des comptes qui n'avaient plus rien à voir.

    ## La règle

    L'idempotence d'abord. Deux traces disent qu'une session est passée :

    - un `AchatFormation` qui porte sa référence — elle a ouvert un accès.
      Il est rendu TEL QUEL, révoqué ou non : rejouer la session d'un achat
      dont l'accès a été retiré ne le rétablit pas ;
    - à défaut, une recette qui porte sa référence — c'était un paiement en
      double, qui n'a pas ouvert d'accès et n'en ouvrira pas au rejeu.
    """
    existant = (
        AchatFormation.objects.select_related("organisation", "formation")
        .filter(reference_paiement=reference)
        .first()
    )
    if existant is not None:
        return AchatDeFormation(
            existant.organisation,
            compte_ne_de_l_achat(reference),
            existant.formation,
            existant,
            nouveau=False,
        )

    if formation is None:
        return None
    recette = (
        Encaissement.objects.select_related("organisation")
        .filter(reference_facture=reference)
        .first()
    )
    if recette is None:
        return None
    premier = _dernier_achat(recette.organisation, formation)
    if premier is None:
        # Une recette sans achat : rien que l'on sache rendre. La livraison
        # reprend son cours, et ses propres gardes jugent.
        return None
    return AchatDeFormation(
        recette.organisation,
        compte_ne_de_l_achat(reference),
        formation,
        premier,
        nouveau=False,
        en_double=True,
    )


@transaction.atomic
def livrer_la_formation(session: dict[str, Any]) -> AchatDeFormation:
    """Ouvre l'accès à la formation payée, et le compte s'il n'existe pas encore.

    Rejouable sans effet — voir `_deja_traitee`, interrogée AVANT tout ce qui
    écrit. Deux gardes d'unicité, en base :

    - `reference_paiement` : le webhook et la page de retour ne créent qu'une
      ligne pour une session, le second recevant `nouveau=False` ;
    - `(organisation, formation)` parmi les achats qui donnent accès : on
      n'achète pas deux fois la même formation. Un SECOND paiement pour une
      organisation qui a déjà accès ne lève pas — l'argent est pris, faire
      échouer la livraison n'y changerait rien. Il rend l'achat existant,
      compte la recette (elle est réelle) et ouvre un incident pour le
      remboursement.

    Un achat RÉVOQUÉ ne donne plus accès : un nouveau paiement de la même
    formation par la même organisation n'est donc pas un double, il ouvre un
    accès sur une NOUVELLE ligne.

    La formation est cherchée SANS exiger qu'elle soit encore en ligne : entre
    l'ouverture du paiement et son encaissement, la cliente a pu la retirer de
    la vente. Ce qui est payé est dû — au prix auquel le paiement a été
    ouvert (`achats.exiger_ce_qui_a_ete_ouvert`).
    """
    reference = str(session.get("id") or "").strip()
    if not reference:
        msg = "Session de paiement sans identifiant."
        raise AchatInexploitable(msg)
    abrege = reference_abregee(reference)

    slug = str((session.get("metadata") or {}).get("formation_slug") or "").strip()
    formation = Formation.objects.filter(slug=slug).first() if slug else None

    deja = _deja_traitee(reference, formation)
    if deja is not None:
        _log.info("Achat de formation %s déjà traité, rejeu sans effet.", abrege)
        return deja

    # Sur un paiement unique, `payment_status` fait foi. `status: complete` dit
    # seulement que le formulaire est allé au bout.
    if str(session.get("payment_status") or "") != "paid":
        msg = f"Session {abrege} non payée ({session.get('payment_status')!r})."
        raise AchatInexploitable(msg)

    if formation is None:
        msg = f"Session {abrege} : formation « {slug} » inconnue."
        raise AchatInexploitable(msg)

    exiger_ce_qui_a_ete_ouvert(
        session,
        reference=reference,
        prix_cents=formation.prix_cents,
        devise=formation.devise,
    )

    email = _texte(session, "customer_details.email", "customer_email").lower()
    if not email:
        msg = f"Session {abrege} : aucune adresse collectée par Stripe."
        raise AchatInexploitable(msg)

    # Jamais par le courriel brut : `espace_de_l_acheteur` porte les gardes de
    # l'audit du 19/11/2026 (organisation désignée d'abord, invitation jamais
    # acceptée écartée, une arrivée à la fois par personne).
    organisation, compte = espace_de_l_acheteur(session, email=email, reference=reference)

    # Relu SOUS le verrou que `espace_de_l_acheteur` vient de poser : deux
    # arrivées exactement simultanées ont toutes deux passé `_deja_traitee`.
    existant = AchatFormation.objects.filter(reference_paiement=reference).first()
    if existant is not None:
        _log.info("Achat de formation %s déjà livré, second appel sans effet.", abrege)
        return AchatDeFormation(organisation, compte, formation, existant, nouveau=False)

    actifs = AchatFormation.objects.filter(
        organisation=organisation, formation=formation, revoque_le__isnull=True
    )
    # Relu sous verrou de ligne : la clôture d'un accès échu, juste dessous,
    # ne doit pas croiser un geste de la gérante sur le même achat.
    premier = actifs.select_for_update().first()
    if premier is not None and premier.etat_de_l_acces == EtatDeLAcces.ECHU:
        _clore_l_acces_echu(premier)
        premier = None
    if premier is None:
        try:
            # Point de sauvegarde : sous PostgreSQL, une erreur d'intégrité
            # rend la transaction englobante inutilisable, et la relecture du
            # `except` échouerait à son tour (audit du 19/11/2026).
            with transaction.atomic():
                achat = AchatFormation.objects.create(
                    organisation=organisation,
                    formation=formation,
                    reference_paiement=reference,
                    intention_de_paiement=intention_de_paiement(session),
                    # Vérifiés plus haut : ce sont ceux du prix ouvert.
                    montant_cents=int(session["amount_total"]),
                    devise=str(session["currency"]).upper()[:3],
                    email=email,
                    # FIGÉ ici, d'après la durée que la formation porte en
                    # cet instant : la changer demain ne déplace la fin
                    # d'aucun accès déjà vendu. Nul pour une durée de zéro
                    # (sans limite). La gérante peut ensuite prolonger depuis
                    # l'administration.
                    acces_jusqu_au=fin_d_acces(
                        timezone.localdate(), formation.duree_d_acces_mois
                    ),
                )
        except IntegrityError:
            # La base a tranché une arrivée simultanée. Deux contraintes
            # peuvent avoir parlé ; on relit pour savoir laquelle.
            gagnant = AchatFormation.objects.filter(reference_paiement=reference).first()
            if gagnant is not None:
                return AchatDeFormation(
                    organisation, compte, formation, gagnant, nouveau=False
                )
            premier = actifs.first()
            if premier is None:
                # Ni l'une ni l'autre : une erreur que l'on ne sait pas lire
                # ne se déguise pas en livraison (règle 1).
                raise
        else:
            _recette_et_panier(organisation, formation, session, reference)
            _log.info(
                "Formation livrée : %s (organisation %s, session %s).",
                formation.slug, organisation.id, abrege,
            )
            return AchatDeFormation(organisation, compte, formation, achat, nouveau=True)

    # L'organisation a DÉJÀ accès à cette formation, par un autre paiement.
    _recette_et_panier(organisation, formation, session, reference)
    _signaler_le_double_paiement(
        organisation=organisation,
        formation=formation,
        premier=premier,
        session=session,
        reference=reference,
    )
    return AchatDeFormation(
        organisation, compte, formation, premier, nouveau=False, en_double=True
    )


def _clore_l_acces_echu(ancien: AchatFormation) -> None:
    """Un RACHAT après échéance : l'ancien achat est clos, le nouveau ouvrira.

    ## Le défaut, trouvé à l'audit du 20/11/2026

    Un achat échu comptait encore comme « détenu ». Racheter une formation
    dont l'accès était terminé tombait donc dans la branche du double
    paiement : l'argent était pris, un incident demandait de le rembourser,
    et l'accès restait fermé.

    ## Pourquoi clore, et ne PAS prolonger l'ancienne ligne

    Chaque paiement doit être porté par SA ligne : c'est par la référence de
    la session que `_deja_traitee` reconnaît un rejeu. Prolonger l'ancien
    achat laisserait le nouveau paiement sans ligne, et son rejeu repasserait
    par toute la livraison. L'ancien achat est donc retiré — avec un motif
    qui dit pourquoi, la ligne reste — et le nouveau naît à côté, avec un
    suivi neuf et sa propre échéance. C'est aussi ce que la contrainte
    d'unicité exige : un seul achat non retiré par organisation et formation.
    """
    ancien.revoque_le = timezone.now()
    ancien.motif_de_revocation = (
        f"Accès échu, racheté le {timezone.localdate().strftime('%d/%m/%Y')}"
    )
    ancien.save(update_fields=["revoque_le", "motif_de_revocation", "updated_at"])
    _log.info(
        "Formation %s rachetée après échéance par l'organisation %s : "
        "l'achat %s est clos.",
        ancien.formation_id, ancien.organisation_id, ancien.id,
    )


def _recette_et_panier(
    organisation: Organisation,
    formation: Formation,
    session: dict[str, Any],
    reference: str,
) -> None:
    """La recette, et le panier soldé — pour tout paiement ENCAISSÉ.

    Y compris un paiement en double : l'argent est entré, la recette doit le
    dire, et son panier ne doit pas passer « abandonné » — la cliente
    relancerait quelqu'un qui a payé deux fois.
    """
    enregistrer_la_recette(
        organisation,
        slug=formation.slug,
        prix_cents=formation.prix_cents,
        session=session,
        reference=reference,
    )
    solder_la_tentative(reference, organisation)


def noter_la_tentative(
    *, session: Any, formation: Formation, email: str = "", organisation: Any = None
) -> None:
    """Enregistre qu'un paiement de formation a été OUVERT, abouti ou non.

    Le pendant de `boutique.noter_la_tentative` : c'est ce qui rend visible,
    dans le suivi des transactions, le panier ouvert puis abandonné — et une
    formation à 1 490 € abandonnée est le panier qui vaut le plus d'être
    relancé.

    Son MONTANT et sa DEVISE sont ceux du moment de l'ouverture : c'est à eux
    que la livraison compare ce que la session a encaissé
    (`achats.exiger_ce_qui_a_ete_ouvert`).

    **Ne lève jamais.** Un défaut de suivi ne doit pas empêcher de payer.
    """
    from organisations.models import ObjetTentative, TentativePaiement  # noqa: PLC0415

    reference = str(getattr(session, "identifiant", "") or "")
    if not reference:
        return
    try:
        # Point de sauvegarde : un échec ici ne doit pas casser la transaction
        # de l'appelant, s'il en a une.
        with transaction.atomic():
            TentativePaiement.objects.get_or_create(
                reference_session=reference,
                defaults={
                    "organisation": organisation,
                    "email": email,
                    "formation": formation,
                    "objet": ObjetTentative.FORMATION,
                    "montant_cents": int(formation.prix_cents or 0),
                    "devise": str(formation.devise or "EUR"),
                },
            )
    except Exception as erreur:  # noqa: BLE001
        # Le TYPE seulement : le message d'une erreur de base cite volontiers
        # la ligne refusée, adresse et référence comprises.
        _log.error(
            "Tentative de formation non enregistrée (%s) : %s",
            reference_abregee(reference), type(erreur).__name__,
        )


def prevenir_l_acheteur(resultat: AchatDeFormation) -> bool:
    """Le courriel qui annonce l'accès, envoyé HORS de la transaction.

    Un envoi à l'intérieur du `atomic` partirait puis serait démenti par un
    retour arrière. L'appelant ne l'envoie que pour un achat `nouveau` : une
    fois par formation achetée, jamais au rejeu ni au paiement en double.
    """
    if resultat.compte is None:
        # Un rejeu, qui n'annonce rien : voir `AchatDeFormation.compte`.
        return False
    return courriels.annoncer_une_formation(
        destinataire=resultat.compte.customer.email,
        formation=resultat.formation.titre,
        lien=identifiants.lien_pour(resultat.compte),
    )
