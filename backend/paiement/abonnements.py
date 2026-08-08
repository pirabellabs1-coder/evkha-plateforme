"""Traduit un evenement de paiement Stripe en souscription EVKHA.

## Le probleme central de ce fichier : ne pas doter deux fois

`services.souscrire` cree un NOUVEL abonnement a chaque appel et resilie le
precedent. C'est le bon comportement pour un changement de formule, et c'est un
piege ici : l'idempotence des credits repose sur la cle
`f"{abonnement_id}:{periode}"` (`credits.reference_de_dotation`). Deux appels a
`souscrire` produisent deux identifiants d'abonnement, donc deux cles
differentes, donc **deux dotations pour un seul paiement**.

La deduplication par identifiant d'evenement (`record_webhook_event`) ne suffit
pas a l'empecher : elle protege du rejeu du MEME evenement, pas de deux
evenements differents qui disent la meme chose. Or Stripe en envoie justement
deux pour une premiere souscription — `checkout.session.completed` et
`invoice.paid` — sans garantir leur ordre d'arrivee.

D'ou `assurer_abonnement`, seul chemin de creation : il refuse de recreer un
abonnement deja rattache au meme abonnement Stripe. Les deux evenements y
passent, dans n'importe quel ordre, et le second ne fait rien.

## Ce que ce module ne fait pas

Il ne suspend personne sur un prelevement refuse. Stripe retente pendant
plusieurs jours avant d'abandonner ; couper l'acces au premier refus punirait
une carte momentanement declinee. L'echec ouvre un incident — quelqu'un doit le
savoir — et c'est la resiliation prononcee par Stripe qui ferme l'acces.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from django.db import transaction

from monitoring.models import IncidentSeverity, OperationalIncident
from organisations import services
from organisations.models import (
    AbonnementOrganisation,
    Formule,
    Organisation,
    StatutAbonnement,
)

_log = logging.getLogger(__name__)


class EvenementInexploitable(ValueError):
    """L'evenement est authentique mais on ne sait pas quoi en faire.

    Distinct d'une signature invalide, qui est un refus. Ici Stripe a bien
    parle, mais il manque de quoi agir : une organisation introuvable, une
    formule supprimee. Cela ne doit pas faire echouer la reponse HTTP — Stripe
    retenterait indefiniment un evenement qui ne passera jamais — mais cela doit
    laisser une trace que quelqu'un lit.
    """


def _metadonnees(objet: dict[str, Any]) -> dict[str, str]:
    brut = objet.get("metadata") or {}
    return {str(cle): str(valeur) for cle, valeur in brut.items()}


def _organisation(identifiant: str) -> Organisation:
    try:
        cle = UUID(str(identifiant))
    except (ValueError, AttributeError, TypeError) as exc:
        raise EvenementInexploitable(
            f"Identifiant d'organisation illisible : {identifiant!r}"
        ) from exc
    organisation = Organisation.objects.filter(id=cle).first()
    if organisation is None:
        raise EvenementInexploitable(
            f"Aucune organisation {identifiant} : paiement recu pour un compte "
            "qui n'existe pas (ou plus)."
        )
    return organisation


def _formule(code: str) -> Formule:
    formule = Formule.objects.filter(code=str(code)).first()
    if formule is None:
        raise EvenementInexploitable(
            f"Aucune formule « {code} » : paiement recu pour une offre retiree "
            "du catalogue."
        )
    return formule


def _incident(titre: str, gravite: str, **details: Any) -> None:
    OperationalIncident.objects.create(
        title=titre, severity=gravite, details={k: str(v) for k, v in details.items()}
    )


@transaction.atomic
def assurer_abonnement(
    *, organisation_id: str, formule_code: str, reference_stripe: str
) -> tuple[AbonnementOrganisation, bool]:
    """Rend l'abonnement correspondant a cet abonnement Stripe, en le creant au besoin.

    Retourne `(abonnement, cree)`. C'est le SEUL endroit qui appelle
    `services.souscrire` depuis un paiement : concentrer la creation en un point
    est ce qui rend la garde ci-dessous efficace. Un second appelant qui
    souscrirait « juste ici, c'est plus simple » rouvrirait la double dotation.

    `select_for_update` sur l'organisation, et pas seulement une lecture : deux
    evenements Stripe peuvent arriver en parallele sur deux processus gunicorn.
    Sans le verrou, les deux liraient « aucun abonnement » avant que l'un des
    deux n'ecrive, et tous deux doteraient.
    """
    organisation = _organisation(organisation_id)
    Organisation.objects.select_for_update().filter(pk=organisation.pk).first()

    reference = str(reference_stripe or "").strip()
    if not reference:
        raise EvenementInexploitable(
            "Evenement de paiement sans identifiant d'abonnement Stripe : "
            "impossible de garantir qu'il ne sera pas rejoue."
        )

    existant = AbonnementOrganisation.objects.filter(
        organisation=organisation,
        reference_paiement=reference,
        statut=StatutAbonnement.ACTIF,
    ).select_related("formule").first()
    if existant is not None:
        return existant, False

    formule = _formule(formule_code)
    abonnement = services.souscrire(organisation, formule)
    abonnement.reference_paiement = reference
    abonnement.save(update_fields=["reference_paiement", "updated_at"])

    _log.info(
        "Abonnement ouvert par paiement : organisation=%s formule=%s stripe=%s",
        organisation.id, formule.code, reference,
    )
    return abonnement, True


def _identite(objet: dict[str, Any], abonnement_stripe: str) -> tuple[str, str]:
    """Retrouve (organisation, formule) dans un objet Stripe.

    Les metadonnees d'abord — c'est nous qui les avons posees, sur la session ET
    sur l'abonnement Stripe, donc elles suivent les factures des mois suivants.
    A defaut, l'abonnement EVKHA deja rattache : une facture de renouvellement
    peut arriver depuis un abonnement cree avant que ces metadonnees n'existent.
    """
    meta = _metadonnees(objet)
    organisation_id = meta.get("organisation_id", "") or str(
        objet.get("client_reference_id") or ""
    )
    formule_code = meta.get("formule_code", "")
    if organisation_id and formule_code:
        return organisation_id, formule_code

    connu = AbonnementOrganisation.objects.filter(
        reference_paiement=abonnement_stripe
    ).select_related("organisation", "formule").order_by("-created_at").first()
    if connu is not None:
        return str(connu.organisation_id), connu.formule.code

    raise EvenementInexploitable(
        "Evenement de paiement sans organisation identifiable : ni metadonnees "
        f"ni abonnement connu pour {abonnement_stripe!r}."
    )


def _abonnement_stripe_de_la_facture(facture: dict[str, Any]) -> str:
    """L'identifiant d'abonnement porte par une facture.

    Stripe l'expose tantot comme une chaine, tantot comme l'objet complet selon
    l'expansion demandee et la version d'API du point de terminaison. Lire les
    deux formes coute trois lignes ; ne lire que la premiere donne un webhook
    qui marche en recette et se tait en production.
    """
    brut = facture.get("subscription")
    if isinstance(brut, dict):
        return str(brut.get("id") or "")
    if brut:
        return str(brut)
    # Stripe 2025+ deplace le lien dans les lignes de facture.
    for ligne in (facture.get("lines") or {}).get("data") or []:
        parent = (ligne or {}).get("parent") or {}
        details = parent.get("subscription_item_details") or {}
        if details.get("subscription"):
            return str(details["subscription"])
    return ""


def sur_session_terminee(session: dict[str, Any]) -> str:
    """`checkout.session.completed` — la personne vient de payer.

    On ne se fie pas a `payment_status` seul : une session en mode abonnement
    peut se terminer sans encaissement immediat (essai gratuit). C'est
    `status == "complete"` qui dit que Stripe considere la souscription faite.
    """
    if str(session.get("status") or "") != "complete":
        return "session non terminee, ignoree"

    _marquer_la_tentative_payee(str(session.get("id") or ""))

    # Un achat de credits passe par le MEME evenement qu'une souscription. Sans
    # cet aiguillage, il serait traite comme un abonnement : `_identite` ne
    # trouverait aucun abonnement Stripe, ouvrirait un incident, et le client
    # aurait paye sans rien recevoir.
    if str((session.get("metadata") or {}).get("achat") or "") == "credits":
        return _crediter_l_achat(session)

    abonnement_stripe = str(session.get("subscription") or "")
    organisation_id, formule_code = _identite(session, abonnement_stripe)
    _, cree = assurer_abonnement(
        organisation_id=organisation_id,
        formule_code=formule_code,
        reference_stripe=abonnement_stripe,
    )
    return "abonnement ouvert" if cree else "abonnement deja ouvert"


def _marquer_la_tentative_payee(reference: str) -> None:
    """Ferme la tentative ouverte a l'entree du paiement.

    Sans cela, une souscription reussie resterait affichee comme panier
    abandonne dans l'administration — et la cliente relancerait un client qui a
    deja paye. Un suivi qui se trompe est pire qu'un suivi absent (regle 2).

    Ne leve jamais : le versement des credits ne doit pas dependre de la bonne
    tenue d'un tableau de bord.
    """
    if not reference:
        return
    try:
        from django.utils import timezone  # noqa: PLC0415

        from organisations.models import (  # noqa: PLC0415
            EtatTentative,
            TentativePaiement,
        )

        TentativePaiement.objects.filter(reference_session=reference).update(
            etat=EtatTentative.PAYEE, payee_le=timezone.now()
        )
    except Exception:  # noqa: BLE001
        _log.exception("Tentative de paiement non marquee payee (%s)", reference)


def _crediter_l_achat(session: dict[str, Any]) -> str:
    """Verse les credits supplementaires payes a l'unite.

    La quantite vient des METADONNEES, pas du montant : la relire par division
    serait une occasion de se tromper d'un credit le jour ou une remise ou un
    arrondi s'en mele.

    Le type `ACHAT` n'est pas cosmetique. `credits.ENTREES_PERENNES` le
    distingue de la dotation mensuelle : ces credits-la NE PERIMENT PAS. Les
    verser en `DOTATION` les ferait expirer a la fin du mois — le client aurait
    paye 59 EUR pour un credit qui disparait le 31.

    La reference de session sert de garde : Stripe rejoue ses evenements
    pendant trois jours, et un second versement doublerait les credits d'un
    paiement unique. Le journal des webhooks assure deja cette idempotence, mais
    les deux verrous ne jugent pas sur la meme evidence (regle 9).
    """
    from organisations import credits as credits_service  # noqa: PLC0415
    from organisations.models import MouvementCredit, TypeMouvement  # noqa: PLC0415

    metadonnees = session.get("metadata") or {}
    reference = str(session.get("id") or "").strip()
    organisation_id = str(
        metadonnees.get("organisation_id") or session.get("client_reference_id") or ""
    ).strip()

    try:
        quantite = int(metadonnees.get("quantite") or 0)
    except (TypeError, ValueError):
        quantite = 0

    if not organisation_id or quantite <= 0:
        _incident(
            "Achat de credits inexploitable",
            IncidentSeverity.HIGH,
            session=reference,
            motif=(
                "Paiement de credits sans organisation ou sans quantite "
                f"lisible : organisation={organisation_id!r}, "
                f"quantite={metadonnees.get('quantite')!r}."
            ),
        )
        return "achat de credits inexploitable"

    if reference and MouvementCredit.objects.filter(reference=reference).exists():
        return "achat deja credite"

    organisation = Organisation.objects.filter(id=organisation_id).first()
    if organisation is None:
        _incident(
            "Achat de credits sans organisation connue",
            IncidentSeverity.HIGH,
            session=reference,
            motif=f"Organisation {organisation_id} introuvable.",
        )
        return "organisation inconnue"

    credits_service.crediter(
        organisation,
        quantite,
        motif=f"Achat de {quantite} credit(s) supplementaire(s)",
        type_mouvement=TypeMouvement.ACHAT,
        reference=reference,
        auteur="stripe",
    )
    return f"{quantite} credits achetes"


def sur_facture_payee(facture: dict[str, Any]) -> str:
    """`invoice.paid` — premiere echeance ou renouvellement mensuel.

    La premiere facture arrive en meme temps que la session terminee, sans
    ordre garanti. Les deux passent donc par `assurer_abonnement`, et seule
    celle qui n'a rien cree applique une echeance — que
    `services.appliquer_echeance` ignorera de toute facon si la periode est deja
    dotee. Deux verrous pour la meme faute : ils ne coutent rien et ne jugent
    pas sur la meme evidence (regle 9).
    """
    abonnement_stripe = _abonnement_stripe_de_la_facture(facture)
    if not abonnement_stripe:
        return "facture hors abonnement, ignoree"

    organisation_id, formule_code = _identite(facture, abonnement_stripe)
    abonnement, cree = assurer_abonnement(
        organisation_id=organisation_id,
        formule_code=formule_code,
        reference_stripe=abonnement_stripe,
    )
    if cree:
        _enregistrer_l_encaissement(facture, abonnement)
        return "abonnement ouvert"

    _enregistrer_l_encaissement(facture, abonnement)
    ajoutes = services.appliquer_echeance(abonnement)
    return f"echeance appliquee ({ajoutes} credits)" if ajoutes else "periode deja dotee"


def _enregistrer_l_encaissement(facture: dict[str, Any], abonnement: Any) -> None:
    """Garde la trace de ce qui est REELLEMENT rentre.

    Le tableau de bord ne savait afficher qu'un revenu contractuel — la somme
    des abonnements actifs — faute de quoi que ce soit d'encaisse a montrer.
    Cette ligne est la seule source d'un chiffre d'affaires realise.

    `get_or_create` sur la reference de facture, et une contrainte d'unicite en
    base derriere : Stripe rejoue ses evenements pendant trois jours en cas
    d'erreur, et compter deux fois un meme paiement gonflerait la recette sans
    que rien ne le signale. Deux verrous pour la meme faute, qui ne jugent pas
    sur la meme evidence (regle 9).

    Ne leve jamais : un defaut de comptabilite ne doit pas empecher un client
    d'etre dote de ses credits. L'echec ouvre un incident, il ne se tait pas.
    """
    reference = str(facture.get("id") or "").strip()
    montant = int(facture.get("amount_paid") or 0)
    if not reference or montant <= 0:
        return

    from django.utils import timezone  # noqa: PLC0415

    from organisations.models import Encaissement  # noqa: PLC0415

    transitions = facture.get("status_transitions") or {}
    horodatage = transitions.get("paid_at") or facture.get("created")
    paye_le = (
        datetime.fromtimestamp(int(horodatage), tz=UTC)
        if horodatage
        else timezone.now()
    )

    try:
        Encaissement.objects.get_or_create(
            reference_facture=reference,
            defaults={
                "organisation": abonnement.organisation,
                "formule_code": getattr(abonnement.formule, "code", ""),
                "montant_cents": montant,
                "devise": str(facture.get("currency") or "eur").upper()[:3],
                "reference_abonnement": _abonnement_stripe_de_la_facture(facture),
                "paye_le": paye_le,
            },
        )
    except Exception as erreur:  # noqa: BLE001
        _incident(
            "Encaissement non enregistre",
            IncidentSeverity.MEDIUM,
            facture=reference,
            montant_cents=montant,
            motif=f"{type(erreur).__name__} : {erreur}",
        )


def sur_abonnement_supprime(abonnement_stripe: dict[str, Any]) -> str:
    """`customer.subscription.deleted` — Stripe a mis fin a l'abonnement.

    Fin d'engagement voulue par le client, ou echec de prelevement que Stripe a
    fini par abandonner : dans les deux cas l'argent ne rentre plus, donc la
    dotation mensuelle doit s'arreter. `services.resilier` suffit pour cela —
    la tache `appliquer_echeances` ne regarde que les abonnements ACTIF.

    Le solde deja acquis n'est pas efface ici. Il expirera a la bascule de
    periode par le chemin normal (`tasks._expirer_les_reserves_resiliees`), et
    les credits ACHETES survivent, comme partout ailleurs.
    """
    reference = str(abonnement_stripe.get("id") or "")
    concerne = AbonnementOrganisation.objects.filter(
        reference_paiement=reference, statut=StatutAbonnement.ACTIF
    ).select_related("organisation").first()
    if concerne is None:
        return "aucun abonnement actif pour cette reference, ignore"

    services.resilier(concerne.organisation, motif="Resiliation prononcee par Stripe.")
    _log.info("Abonnement resilie par Stripe : %s", reference)
    return "abonnement resilie"


def sur_prelevement_refuse(facture: dict[str, Any]) -> str:
    """`invoice.payment_failed` — on ouvre un incident, on ne coupe rien.

    Couper au premier refus punirait une carte momentanement declinee, alors que
    Stripe va retenter plusieurs jours. Mais se taire ferait decouvrir la perte
    d'un abonne au moment ou il se plaint. L'incident est le juste milieu : la
    supervision le voit, l'acces reste ouvert, et c'est la resiliation
    prononcee par Stripe qui tranchera.
    """
    reference = _abonnement_stripe_de_la_facture(facture)
    _incident(
        "Prelevement Stripe refuse",
        IncidentSeverity.MEDIUM,
        abonnement_stripe=reference,
        facture=facture.get("id") or "",
        montant_du=facture.get("amount_due") or 0,
        tentative=facture.get("attempt_count") or 0,
    )
    return "incident ouvert"


def sur_abonnement_modifie(abonnement_stripe: dict[str, Any]) -> str:
    """`customer.subscription.updated` — Stripe est l'autorite sur ces deux etats.

    Il ne dote RIEN, et c'est deliberement etroit : cet evenement part a chaque
    changement de carte, chaque relance, chaque modification de metadonnee. Le
    traiter largement suffirait a crediter a chaque fois.

    Il recopie deux choses, et rien d'autre :

    - `cancel_at_period_end`, parce qu'une resiliation peut etre prononcee
      AILLEURS QUE CHEZ NOUS — depuis le tableau de bord Stripe, ou par Stripe
      lui-meme apres une serie d'impayes. Sans cet evenement, notre ecran
      continuerait d'annoncer « se reconduit chaque mois » a quelqu'un dont le
      prelevement est deja arrete ;
    - le terme de la periode, qui bouge a chaque echeance et dont nous n'avons
      aucun moyen de deduire la valeur.
    """
    reference = str(abonnement_stripe.get("id") or "")
    concerne = AbonnementOrganisation.objects.filter(
        reference_paiement=reference, statut=StatutAbonnement.ACTIF
    ).first()
    if concerne is None:
        return "aucun abonnement actif pour cette reference, ignore"

    arrete = bool(abonnement_stripe.get("cancel_at_period_end"))
    concerne.renouvellement_actif = not arrete

    champs = ["renouvellement_actif", "updated_at"]
    fin = _fin_de_periode(abonnement_stripe)
    if fin is not None:
        concerne.fin_de_periode_le = fin
        champs.insert(1, "fin_de_periode_le")
    concerne.save(update_fields=champs)

    return "renouvellement arrete" if arrete else "renouvellement actif"


def _fin_de_periode(abonnement_stripe: dict[str, Any]) -> datetime | None:
    """Le terme de la periode en cours, ou None si Stripe ne le donne pas.

    None et non « maintenant » : une date inventee serait affichee au client
    comme la date jusqu'a laquelle il garde son acces (regle 1 — on n'ecrit pas
    une valeur qu'on n'a pas).

    Stripe l'expose au niveau de l'abonnement dans les versions anciennes, et au
    niveau de la ligne de facturation depuis 2025.
    """
    horodatage = abonnement_stripe.get("current_period_end")
    if not horodatage:
        for ligne in (abonnement_stripe.get("items") or {}).get("data") or []:
            if ligne.get("current_period_end"):
                horodatage = ligne["current_period_end"]
                break
    if not horodatage:
        return None
    try:
        return datetime.fromtimestamp(int(horodatage), tz=UTC)
    except (ValueError, OSError, TypeError):
        return None


#: Evenements traites, et eux seuls. Une liste fermee plutot qu'un `else` qui
#: tenterait sa chance : Stripe en envoie des dizaines par defaut, et un
#: traitement approximatif de `customer.subscription.updated` suffirait a doter
#: a chaque changement de carte bancaire.
_TRAITEMENTS = {
    "checkout.session.completed": sur_session_terminee,
    "invoice.paid": sur_facture_payee,
    "invoice.payment_failed": sur_prelevement_refuse,
    "customer.subscription.updated": sur_abonnement_modifie,
    "customer.subscription.deleted": sur_abonnement_supprime,
}


def traiter(evenement: dict[str, Any]) -> str:
    """Aiguille un evenement Stripe verifie. Retourne un verdict pour le journal."""
    type_evenement = str(evenement.get("type") or "")
    traitement = _TRAITEMENTS.get(type_evenement)
    if traitement is None:
        return f"type « {type_evenement} » non traite"

    objet = ((evenement.get("data") or {}).get("object")) or {}
    if not isinstance(objet, dict):
        raise EvenementInexploitable(
            f"Evenement {type_evenement} sans objet exploitable."
        )
    return traitement(objet)
