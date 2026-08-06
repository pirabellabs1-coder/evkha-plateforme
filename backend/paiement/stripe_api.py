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
            success_url=_adresse_de_retour("/espace?paiement=ok"),
            cancel_url=_adresse_de_retour("/espace?paiement=abandon"),
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
