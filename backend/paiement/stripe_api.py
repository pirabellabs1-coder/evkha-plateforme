"""Le seul endroit qui parle a Stripe, et qui refuse de le faire sans cle.

La cle n'est jamais lue ailleurs. Elle n'est pas non plus posee sur le module
`stripe` global (`stripe.api_key = ...`) : cette affectation est un etat
partage par tout le processus, qui survit a un test, traverse une requete, et
rend impossible de dire en lisant un appel avec quelle cle il part. Elle est
donc passee explicitement a chaque appel.
"""
from __future__ import annotations

import logging
from typing import Any

import stripe
from django.conf import settings

from organisations.models import Formule, Organisation

_log = logging.getLogger(__name__)


class PaiementIndisponible(RuntimeError):
    """Stripe n'est pas configure, ou refuse la demande.

    Volontairement une seule exception pour les deux cas. L'appelant n'a rien
    de different a faire : dans les deux cas il ne peut pas encaisser, et dans
    les deux cas la personne en face doit lire une phrase qui ne parle ni de
    cle d'API ni de code HTTP.
    """


def cle_secrete() -> str:
    """La cle, ou une erreur. Jamais une chaine vide rendue silencieusement.

    Regle 1 : un controle qui n'a rien a comparer echoue bruyamment. Rendre
    `""` ici aurait laisse partir un appel Stripe anonyme, dont l'echec se
    serait manifeste trois couches plus loin sous une forme incomprehensible.
    """
    cle = str(getattr(settings, "STRIPE_SECRET_KEY", "") or "")
    if not cle:
        raise PaiementIndisponible(
            "Le paiement n'est pas encore configuré sur cette plateforme."
        )
    return cle


def secret_de_signature() -> str:
    """Le secret du point de terminaison, ou une erreur.

    Meme raisonnement, avec une consequence plus grave : sans lui on ne peut
    pas distinguer un evenement venu de Stripe d'un POST fabrique. Voir
    `vues.webhook`, qui refuse plutot que de faire confiance.
    """
    secret = str(getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "")
    if not secret:
        raise PaiementIndisponible(
            "La vérification des événements de paiement n'est pas configurée."
        )
    return secret


def configure() -> bool:
    """Stripe est-il utilisable ? Pour l'affichage seulement.

    Ne sert jamais a autoriser quoi que ce soit — seulement a dire a
    l'interface s'il faut proposer un bouton de paiement ou une explication.
    """
    return bool(
        str(getattr(settings, "STRIPE_SECRET_KEY", "") or "")
        and str(getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "")
    )


def _adresse_de_retour(chemin: str) -> str:
    """Une URL absolue vers l'espace client, batie sur EVKHA_APP_URL.

    Le meme reglage sert deja aux liens d'invitation et de mot de passe
    (`organisations/identifiants.py`). En introduire un second pour Stripe
    aurait cree deux adresses du meme site, qui divergent le jour d'un
    changement de domaine (regle 5).
    """
    base = str(getattr(settings, "EVKHA_APP_URL", "") or "").rstrip("/")
    if not base:
        raise PaiementIndisponible(
            "L'adresse de l'espace client n'est pas configurée."
        )
    return f"{base}{chemin}"


def creer_session_de_paiement(
    organisation: Organisation, formule: Formule, *, email: str
) -> str:
    """Ouvre une session Checkout et rend l'adresse ou envoyer la personne.

    `mode="subscription"` et non `payment` : c'est Stripe qui portera ensuite
    le prelevement mensuel, ses echecs et ses relances. Reconduire nous-memes
    un abonnement mensuel reviendrait a reecrire une facturation recurrente,
    et a en heriter les cas tordus (carte expiree, contestation, proratisation
    d'un changement de formule en cours de mois).

    L'identifiant de l'organisation voyage a DEUX endroits, et ce n'est pas
    une redondance inutile :

    - `client_reference_id` sur la session, lu a `checkout.session.completed` ;
    - `subscription_data.metadata`, qui se retrouve sur l'abonnement Stripe
      lui-meme, donc sur CHAQUE facture mensuelle ulterieure.

    Sans le second, la premiere echeance saurait a qui doter, et aucune des
    suivantes : un evenement `invoice.paid` du mois prochain n'a pas de
    session Checkout derriere lui.
    """
    tarif = str(formule.reference_paiement or "").strip()
    if not tarif:
        raise PaiementIndisponible(
            f"La formule « {formule.libelle} » n'a pas encore de tarif Stripe. "
            "Renseignez sa référence de paiement en administration."
        )

    # L'adresse est OMISE quand on ne l'a pas, jamais envoyee a vide : Stripe
    # attend une adresse valable, et `customer_email=None` n'est pas la meme
    # chose que « ne pas preciser ». C'est aussi ce que dit son typage, qui
    # refuse `str | None` — le contourner par un `type: ignore` aurait cache un
    # appel que Stripe rejette.
    facultatifs: dict[str, Any] = {}
    if email:
        facultatifs["customer_email"] = email

    try:
        session: Any = stripe.checkout.Session.create(
            api_key=cle_secrete(),
            mode="subscription",
            line_items=[{"price": tarif, "quantity": 1}],
            client_reference_id=str(organisation.id),
            # `?paiement=ok` n'est PAS une preuve de paiement : c'est le
            # navigateur qui revient, et n'importe qui peut taper cette adresse.
            # L'interface s'en sert seulement pour savoir qu'il faut attendre le
            # webhook, jamais pour ouvrir l'espace (voir `vues_espace.moi`).
            success_url=_adresse_de_retour("/espace/souscription?paiement=ok"),
            cancel_url=_adresse_de_retour("/espace/souscription?paiement=abandon"),
            subscription_data={
                "metadata": {
                    "organisation_id": str(organisation.id),
                    "formule_code": formule.code,
                },
            },
            metadata={
                "organisation_id": str(organisation.id),
                "formule_code": formule.code,
            },
            **facultatifs,
        )
    except stripe.StripeError as exc:
        # Le message de Stripe part dans le journal, jamais a l'ecran : il cite
        # volontiers l'identifiant du tarif et le mode de la cle.
        _log.error(
            "Stripe a refuse la creation de session (organisation=%s, formule=%s) : %s",
            organisation.id, formule.code, exc,
        )
        raise PaiementIndisponible(
            "Le paiement est momentanément indisponible. Réessayez dans "
            "quelques minutes."
        ) from exc

    adresse = str(session.get("url") or "")
    if not adresse:
        raise PaiementIndisponible(
            "Le paiement est momentanément indisponible. Réessayez dans "
            "quelques minutes."
        )
    return adresse


def creer_paiement_de_credits(
    *,
    organisation: Any,
    formule: Any,
    quantite: int,
    email: str = "",
) -> str:
    """Ouvre un paiement PONCTUEL pour des credits supplementaires.

    `mode="payment"` et non `subscription` : c'est un achat unique, pas un
    engagement. Le confondre avec l'abonnement creerait un second prelevement
    mensuel a cote du premier — le client paierait deux fois par mois pour
    avoir achete des credits une fois.

    Le montant est transmis A LA VOLEE (`price_data`) plutot que par un tarif
    Stripe preenregistre. Un tarif par formule ferait quatre produits de plus a
    creer et a tenir a jour, et le prix du credit supplementaire vit deja dans
    la formule, en administration : le dupliquer chez Stripe ferait deux
    verites pour un meme tarif (regle 5), et celle de Stripe gagnerait sans que
    personne ne l'ait decide.

    La QUANTITE voyage dans les metadonnees. La relire depuis le montant paye
    serait une division, donc une occasion de se tromper d'un credit le jour
    ou une remise ou un arrondi s'en mele.
    """
    prix_unitaire = int(getattr(formule, "prix_credit_supplementaire_cents", 0) or 0)
    if prix_unitaire <= 0:
        raise PaiementIndisponible(
            f"La formule « {formule.libelle} » ne propose pas de credit "
            "supplementaire. Renseignez son tarif en administration."
        )

    facultatifs: dict[str, Any] = {}
    if email:
        facultatifs["customer_email"] = email

    libelle = (
        f"{quantite} credit supplementaire"
        if quantite == 1
        else f"{quantite} credits supplementaires"
    )

    try:
        session: Any = stripe.checkout.Session.create(
            api_key=cle_secrete(),
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": str(getattr(formule, "devise", "EUR") or "EUR").lower(),
                    "unit_amount": prix_unitaire,
                    "product_data": {"name": f"EVKHA — {libelle}"},
                },
                "quantity": quantite,
            }],
            client_reference_id=str(organisation.id),
            success_url=_adresse_de_retour("/espace/credits?achat=ok"),
            cancel_url=_adresse_de_retour("/espace/credits?achat=abandon"),
            metadata={
                "organisation_id": str(organisation.id),
                "formule_code": formule.code,
                # Ce qui distingue cet achat d'une souscription au webhook.
                "achat": "credits",
                "quantite": str(quantite),
            },
            **facultatifs,
        )
    except stripe.StripeError as exc:
        _log.error(
            "Stripe a refuse l'achat de credits (organisation=%s, quantite=%s) : %s",
            organisation.id, quantite, exc,
        )
        raise PaiementIndisponible(
            "Le paiement est momentanément indisponible. Réessayez dans "
            "quelques minutes."
        ) from exc

    adresse = str(session.get("url") or "")
    if not adresse:
        raise PaiementIndisponible(
            "Le paiement est momentanément indisponible. Réessayez dans "
            "quelques minutes."
        )
    return adresse


def arreter_le_renouvellement(reference_stripe: str) -> str:
    """Demande à Stripe de ne plus reconduire cet abonnement.

    **`cancel_at_period_end` et non une résiliation immédiate.** Le mois en
    cours est payé : le couper à l'instant du clic reprendrait ce que le client
    vient de régler. Il garde donc son accès et ses crédits jusqu'au terme, et
    rien n'est prélevé ensuite.

    C'est aussi ce qui rend le geste réversible sans repasser par une carte —
    voir `reprendre_le_renouvellement`. Une annulation sèche
    (`Subscription.cancel`) obligerait à ressaisir un moyen de paiement pour
    revenir, ce qui transforme une hésitation en départ définitif.

    Retourne la date de fin, en texte ISO, ou une chaîne vide si Stripe ne la
    donne pas — l'appelant l'affiche, il ne s'en sert pas pour décider.
    """
    try:
        abonnement: Any = stripe.Subscription.modify(
            reference_stripe, api_key=cle_secrete(), cancel_at_period_end=True
        )
    except stripe.StripeError as exc:
        _log.error("Stripe refuse l'arret du renouvellement %s : %s", reference_stripe, exc)
        raise PaiementIndisponible(
            "L'arrêt de l'abonnement n'a pas pu être enregistré. Réessayez dans "
            "quelques minutes ; rien n'a été modifié."
        ) from exc
    return _fin_de_periode(abonnement)


def reprendre_le_renouvellement(reference_stripe: str) -> None:
    """Annule l'arrêt : l'abonnement se reconduira de nouveau.

    Tant que le terme n'est pas atteint, revenir sur sa décision ne doit rien
    coûter — ni un nouveau paiement, ni une nouvelle saisie de carte.
    """
    try:
        stripe.Subscription.modify(
            reference_stripe, api_key=cle_secrete(), cancel_at_period_end=False
        )
    except stripe.StripeError as exc:
        _log.error("Stripe refuse la reprise de %s : %s", reference_stripe, exc)
        raise PaiementIndisponible(
            "La reprise de l'abonnement n'a pas pu être enregistrée. Réessayez "
            "dans quelques minutes."
        ) from exc


def changer_de_formule(reference_stripe: str, formule: Formule) -> None:
    """Bascule un abonnement Stripe sur le tarif d'une autre formule.

    `proration_behavior="create_prorations"` : Stripe calcule lui-même ce qui
    reste dû ou ce qui est rendu sur le mois en cours. Écrire ce calcul ici en
    donnerait deux versions — la sienne, qui facture, et la nôtre, qui affiche
    (règle 5).

    On modifie la LIGNE existante au lieu d'en ajouter une : ajouter reviendrait
    à facturer les deux formules ensemble, ce qui est précisément le défaut
    qu'un abonné remarque sur son relevé et pas sur notre écran.
    """
    tarif = str(formule.reference_paiement or "").strip()
    if not tarif:
        raise PaiementIndisponible(
            f"La formule « {formule.libelle} » n'a pas encore de tarif Stripe. "
            "Renseignez sa référence de paiement en administration."
        )
    try:
        actuel: Any = stripe.Subscription.retrieve(
            reference_stripe, api_key=cle_secrete()
        )
        lignes = (actuel.get("items") or {}).get("data") or []
        if not lignes:
            raise PaiementIndisponible(
                "Cet abonnement n'a aucune ligne de facturation chez Stripe."
            )
        stripe.Subscription.modify(
            reference_stripe,
            api_key=cle_secrete(),
            items=[{"id": lignes[0]["id"], "price": tarif}],
            proration_behavior="create_prorations",
        )
    except stripe.StripeError as exc:
        _log.error(
            "Stripe refuse le changement de formule %s -> %s : %s",
            reference_stripe, formule.code, exc,
        )
        raise PaiementIndisponible(
            "Le changement de formule n'a pas pu être enregistré. Réessayez "
            "dans quelques minutes ; votre formule actuelle est inchangée."
        ) from exc


def _fin_de_periode(abonnement: dict[str, Any]) -> str:
    """La fin de la période en cours, en ISO, depuis un abonnement Stripe.

    Stripe l'expose au niveau de l'abonnement dans les versions anciennes, et
    au niveau de la ligne de facturation depuis 2025. Lire les deux coûte cinq
    lignes ; n'en lire qu'une donne une date vide en production et une date
    juste en recette.
    """
    from datetime import UTC, datetime

    horodatage = abonnement.get("current_period_end")
    if not horodatage:
        for ligne in (abonnement.get("items") or {}).get("data") or []:
            if ligne.get("current_period_end"):
                horodatage = ligne["current_period_end"]
                break
    if not horodatage:
        return ""
    return datetime.fromtimestamp(int(horodatage), tz=UTC).isoformat()
