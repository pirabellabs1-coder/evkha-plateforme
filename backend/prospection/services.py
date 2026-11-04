"""Les actes de la prospection — dont l'invariant « rien ne part sans validation ».

Toute la sûreté de ce sous-système tient en un point : un `Message` ne quitte
le système que s'il a été VALIDÉ par un humain, et jamais vers un prospect
désinscrit. `envoyer_message` est le SEUL chemin d'envoi, et il refuse tout le
reste. Un test rejoue un brouillon contre lui : il doit lever.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.db import transaction
from django.urls import reverse
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


def lien_de_desinscription(prospect: Prospect) -> str:
    """L'URL ABSOLUE de désinscription du prospect, bâtie sur `EVKHA_BASE_URL`.

    Jeton opaque, aucune donnée personnelle dans l'URL (règle de confidentialité).
    """
    base = str(getattr(settings, "EVKHA_BASE_URL", "")).rstrip("/")
    chemin = reverse("prospection-desinscription", kwargs={"jeton": prospect.jeton_desinscription})
    return f"{base}{chemin}"


def _corps_pour_envoi(message: Message) -> str:
    """L'e-mail complet, mis en page, à l'envoi seulement.

    On ne touche PAS au brouillon validé : le corps rédigé par l'agent est
    enrobé dans le gabarit de marque EVKHA (en-tête, cadre, pied) au moment de
    partir, et le lien de désinscription — dépendant du jeton et de l'URL de
    base — y est injecté. Tout e-mail de prospection doit porter une sortie
    facile (prospection B2B : opt-out obligatoire).
    """
    from .gabarit_email import enrober  # noqa: PLC0415

    return enrober(message.objet, message.corps, lien_de_desinscription(message.prospect))


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
    prospect = message.prospect
    # La désinscription d'abord : elle annule aussi les messages en file, et le
    # message relu avant envoi dirait sinon « annulé » sans dire pourquoi.
    if prospect.consentement_retire or prospect.statut == StatutProspect.DESINSCRIT:
        return "le prospect s'est désinscrit : plus aucun message ne lui est envoyé"
    if message.statut not in ETATS_ENVOYABLES:
        return (
            f"message en état « {message.statut} » : seul un message validé par un humain "
            "peut être envoyé"
        )
    if not prospect.email:
        return "le prospect n'a pas d'adresse e-mail"
    if prospect.statut == StatutProspect.EXCLU:
        return "le prospect est exclu de la prospection"
    # Une relance ne part qu'après ce qui la précède (04/11/2026) : sinon le
    # prospect pouvait recevoir « je reviens vers vous » avant le premier mail.
    from .file import place  # noqa: PLC0415 — `file` importe les modèles

    sa_place = place(message)
    if not sa_place.pret:
        if sa_place.disponible_le is None:
            return (
                f"{sa_place.libelle.lower()} : le message de l'étape précédente "
                "n'est pas encore envoyé"
            )
        return (
            f"{sa_place.libelle.lower()} : son délai court jusqu'au "
            f"{timezone.localtime(sa_place.disponible_le):%d/%m/%Y %H:%M}"
        )
    return None


def envoyer_message(
    message: Message, *, client: TransactionalEmailClient | None = None,
) -> Message:
    """Envoie un message VALIDÉ, via Brevo. SEUL chemin d'envoi du sous-système.

    Refuse — en levant `EnvoiRefuseError`, jamais en envoyant quand même — tout
    message non validé, annulé, déjà parti, ou dont le prospect s'est
    désinscrit. L'envoi marque le message ENVOYÉ et trace un événement.

    Le message est VERROUILLÉ et RELU avant d'être jugé (relecture du
    04/11/2026). L'objet reçu peut dater du début d'un envoi par lot : jugé tel
    quel, il laissait partir la relance d'un prospect désinscrit entre-temps,
    et deux clics concurrents envoyaient deux fois le même message. Le verrou
    tient jusqu'à l'écriture d'ENVOYÉ : le second appel attend, puis trouve le
    message parti et refuse.
    """
    from integrations.brevo import get_transactional_email_client  # noqa: PLC0415

    erreur_fournisseur: Exception | None = None
    with transaction.atomic():
        frais = (
            Message.objects.select_for_update()
            .select_related("prospect", "sequence")
            .get(pk=message.pk)
        )
        refus = _raison_de_refus(frais)
        if refus is not None:
            raise EnvoiRefuseError(refus)

        client = client or get_transactional_email_client()
        try:
            resultat = client.send_delivery_email(
                recipient_email=frais.prospect.email,
                subject=frais.objet,
                html_body=_corps_pour_envoi(frais),
                attachments=(),
            )
        except Exception as erreur:  # noqa: BLE001 — un échec d'envoi se trace, ne se masque pas
            # Écrit DANS la transaction, levé APRÈS : lever ici annulerait la
            # trace de l'échec avec le reste.
            frais.statut = StatutMessage.ECHOUE
            frais.error_message = f"{type(erreur).__name__}: {erreur}"[:500]
            frais.save(update_fields=["statut", "error_message", "updated_at"])
            erreur_fournisseur = erreur
        else:
            frais.statut = StatutMessage.ENVOYE
            frais.envoye_le = timezone.now()
            frais.provider_message_id = resultat.provider_message_id
            frais.error_message = ""
            frais.save(update_fields=[
                "statut", "envoye_le", "provider_message_id", "error_message", "updated_at",
            ])
            Evenement.objects.create(
                message=frais, type=TypeEvenement.ENVOYE, horodatage=frais.envoye_le,
                charge={"provider_message_id": resultat.provider_message_id},
            )
            prospect = frais.prospect
            if prospect.statut in (StatutProspect.NOUVEAU, StatutProspect.QUALIFIE):
                prospect.statut = StatutProspect.CONTACTE
            elif prospect.statut == StatutProspect.CONTACTE and frais.sequence_id:
                prospect.statut = StatutProspect.EN_RELANCE
            prospect.save(update_fields=["statut", "updated_at"])

    # L'appelant garde son objet : on lui rend l'état écrit en base.
    for champ in ("statut", "envoye_le", "provider_message_id", "error_message"):
        setattr(message, champ, getattr(frais, champ))
    if erreur_fournisseur is not None:
        msg = f"envoi refusé par le fournisseur : {erreur_fournisseur}"
        raise EnvoiRefuseError(msg) from erreur_fournisseur
    return message


#: Un lot d'envoi tient dans une requête HTTP : gunicorn la coupe à 120 s, et
#: un worker tué entre l'appel Brevo et l'écriture d'ENVOYÉ laisse un message
#: parti mais encore VALIDÉ — renvoyé au lot suivant. Cinquante envois à
#: quelques centaines de millisecondes restent loin de la coupure.
ENVOI_PAR_LOT_MAX = 50


def valider_par_lot(messages: list[Message], *, par: str) -> tuple[int, list[str]]:
    """Valide d'un coup des brouillons PRÊTS. Rend (validés, refus nommés).

    Chaque message passe par `valider_message` : la règle reste la sienne, le
    lot n'en invente pas une seconde (règle 5). Un brouillon pas encore prêt
    — relance dont l'étape d'avant n'est pas partie — n'est pas validé.
    """
    from .file import places  # noqa: PLC0415

    leurs_places = places(messages)
    valides, refus = 0, []
    for message in messages:
        if message.statut != StatutMessage.BROUILLON:
            continue
        if not leurs_places[str(message.id)].pret:
            refus.append(f"{message.objet} : pas encore à son tour")
            continue
        try:
            valider_message(message, par=par)
        except EnvoiRefuseError as erreur:
            refus.append(f"{message.objet} : {erreur}")
            continue
        valides += 1
    return valides, refus


def envoyer_par_lot(
    messages: list[Message], *, client: TransactionalEmailClient | None = None,
) -> tuple[int, list[str]]:
    """Envoie d'un coup des messages VALIDÉS, chacun par `envoyer_message`.

    Le seul chemin d'envoi reste `envoyer_message` : ses refus — brouillon,
    désinscrit, relance pas encore à son tour — valent pour chaque message du
    lot. Un échec n'arrête pas les autres ; il est nommé.
    """
    from .file import places  # noqa: PLC0415

    # Les places sont FIGÉES avant la boucle : jugées message par message, une
    # relance validée partait dans le même lot que son premier mail, quelques
    # secondes après lui, dès que le premier passait devant elle.
    leurs_places = places(messages)
    envoyes, refus = 0, []
    if len(messages) > ENVOI_PAR_LOT_MAX:
        refus.append(
            f"{len(messages) - ENVOI_PAR_LOT_MAX} message(s) au-delà du lot de "
            f"{ENVOI_PAR_LOT_MAX} : relancez l'envoi pour les suivants"
        )
    for message in messages[:ENVOI_PAR_LOT_MAX]:
        if not leurs_places[str(message.id)].pret:
            refus.append(f"{message.objet} : pas encore à son tour")
            continue
        try:
            envoyer_message(message, client=client)
        except EnvoiRefuseError as erreur:
            refus.append(f"{message.objet} : {erreur}")
            continue
        envoyes += 1
    return envoyes, refus


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
