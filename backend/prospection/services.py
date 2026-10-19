"""Les actes de la prospection — dont l'invariant « rien ne part sans validation ».

Toute la sûreté de ce sous-système tient en un point : un `Message` ne quitte
le système que s'il a été VALIDÉ par un humain, et jamais vers un prospect
désinscrit. `envoyer_message` est le SEUL chemin d'envoi, et il refuse tout le
reste. Un test rejoue un brouillon contre lui : il doit lever.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from .models import (
    ETATS_ENVOYABLES,
    Evenement,
    Message,
    Prospect,
    StatutMessage,
    StatutProspect,
    TypeEvenement,
)

if TYPE_CHECKING:
    from integrations.brevo import TransactionalEmailClient


class EnvoiRefuseError(RuntimeError):
    """L'envoi est refusé. Le message dit pourquoi, pour l'humain et le journal."""


def valider_message(message: Message, *, par: str) -> Message:
    """Un humain valide le message : il PEUT désormais partir. Rien ne part ici.

    La validation est un acte horodaté et nominatif (`par`) : c'est elle, et
    elle seule, qui autorisera `envoyer_message`. Un message déjà envoyé ou
    annulé ne se « revalide » pas.
    """
    if message.statut in (StatutMessage.ENVOYE, StatutMessage.ANNULE):
        msg = f"Un message {message.statut} ne se valide pas."
        raise EnvoiRefuseError(msg)
    if not (par or "").strip():
        msg = "Une validation sans auteur n'en est pas une : elle doit être nominative."
        raise EnvoiRefuseError(msg)
    message.statut = StatutMessage.VALIDE
    message.valide_par = par.strip()
    message.valide_le = timezone.now()
    message.error_message = ""
    message.save(update_fields=["statut", "valide_par", "valide_le", "error_message", "updated_at"])
    return message


def annuler_message(message: Message) -> Message:
    """Retire un message de la file : il ne partira pas."""
    if message.statut == StatutMessage.ENVOYE:
        msg = "Un message déjà envoyé ne s'annule pas."
        raise EnvoiRefuseError(msg)
    message.statut = StatutMessage.ANNULE
    message.save(update_fields=["statut", "updated_at"])
    return message


def _raison_de_refus(message: Message) -> str | None:
    """Pourquoi ce message ne peut PAS partir, ou None s'il le peut."""
    if message.statut not in ETATS_ENVOYABLES:
        return (
            f"message en état « {message.statut} » : seul un message validé par un humain "
            "peut être envoyé"
        )
    prospect = message.prospect
    if not prospect.email:
        return "le prospect n'a pas d'adresse e-mail"
    if prospect.consentement_retire or prospect.statut == StatutProspect.DESINSCRIT:
        return "le prospect s'est désinscrit : plus aucun message ne lui est envoyé"
    if prospect.statut == StatutProspect.EXCLU:
        return "le prospect est exclu de la prospection"
    return None


def envoyer_message(
    message: Message, *, client: TransactionalEmailClient | None = None,
) -> Message:
    """Envoie un message VALIDÉ, via Brevo. SEUL chemin d'envoi du sous-système.

    Refuse — en levant `EnvoiRefuseError`, jamais en envoyant quand même — tout
    message non validé, annulé, déjà parti, ou dont le prospect s'est
    désinscrit. L'envoi marque le message ENVOYÉ et trace un événement.
    """
    refus = _raison_de_refus(message)
    if refus is not None:
        raise EnvoiRefuseError(refus)

    from integrations.brevo import get_transactional_email_client  # noqa: PLC0415

    client = client or get_transactional_email_client()
    try:
        resultat = client.send_delivery_email(
            recipient_email=message.prospect.email,
            subject=message.objet,
            html_body=message.corps,
            attachments=(),
        )
    except Exception as erreur:  # noqa: BLE001 — un échec d'envoi se trace, ne se masque pas
        message.statut = StatutMessage.ECHOUE
        message.error_message = f"{type(erreur).__name__}: {erreur}"[:500]
        message.save(update_fields=["statut", "error_message", "updated_at"])
        raise EnvoiRefuseError(f"envoi refusé par le fournisseur : {erreur}") from erreur

    with transaction.atomic():
        message.statut = StatutMessage.ENVOYE
        message.envoye_le = timezone.now()
        message.provider_message_id = resultat.provider_message_id
        message.error_message = ""
        message.save(update_fields=[
            "statut", "envoye_le", "provider_message_id", "error_message", "updated_at",
        ])
        Evenement.objects.create(
            message=message, type=TypeEvenement.ENVOYE, horodatage=message.envoye_le,
            charge={"provider_message_id": resultat.provider_message_id},
        )
        prospect = message.prospect
        if prospect.statut in (StatutProspect.NOUVEAU, StatutProspect.QUALIFIE):
            prospect.statut = StatutProspect.CONTACTE
        elif prospect.statut == StatutProspect.CONTACTE and message.sequence_id:
            prospect.statut = StatutProspect.EN_RELANCE
        prospect.save(update_fields=["statut", "updated_at"])
    return message


def desinscrire(prospect: Prospect) -> Prospect:
    """Un prospect se désinscrit : opt-out définitif, plus aucun envoi.

    Les messages encore en file (brouillon, validé, programmé) sont annulés :
    la désinscription prime sur toute validation déjà donnée.
    """
    with transaction.atomic():
        prospect.consentement_retire = True
        prospect.desinscrit_le = timezone.now()
        prospect.statut = StatutProspect.DESINSCRIT
        prospect.save(update_fields=[
            "consentement_retire", "desinscrit_le", "statut", "updated_at",
        ])
        prospect.messages.exclude(
            statut__in=(StatutMessage.ENVOYE, StatutMessage.ANNULE)
        ).update(statut=StatutMessage.ANNULE)
    return prospect
