"""La pompe : ce qui fait partir les courriels de la lettre, minute par minute.

Une tâche périodique (`lettre.pomper`, chaque minute) fait tout, dans cet
ordre :

1. les courriels de CONFIRMATION d'inscription en attente ;
2. les lettres PROGRAMMÉES dont l'heure est venue passent « en cours », avec
   une ligne `Envoi` par inscrit du moment ;
3. les AUTOMATISATIONS mettent en file les étapes dont le délai est échu ;
4. les envois en file partent, un à un, dans un budget de temps borné ;
5. les lettres sans plus rien en file sont closes.

## Pourquoi une pompe, et pas une tâche par lettre

Un déploiement redémarre les ouvriers et tue la tâche en cours. Une tâche
« envoie 800 courriels » mourrait au 312e sans que personne ne la reprenne.
La pompe, elle, repart à la minute suivante là où l'état en base dit qu'il
faut repartir — et chaque passage est court.

## Jamais deux fois le même courriel

Un envoi est PRIS par une mise à jour conditionnelle (`a_envoyer` →
`en_cours`) : si deux pompes se chevauchent, une seule l'obtient. Un envoi
resté `en_cours` au-delà de `INTERRUPTION` (ouvrier tué pendant l'appel au
prestataire) passe en échec SANS être renvoyé : on ne sait pas s'il est
parti, et un doublon est pire qu'un manque signalé.
"""
from __future__ import annotations

import logging
import time
import urllib.error
from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.utils import timezone

from audience.models import Contact, Demande, Origine, inscrits_q
from integrations.brevo import get_transactional_email_client

from . import gabarit
from .models import (
    Automatisation,
    Declencheur,
    Envoi,
    Etape,
    Lettre,
    StatutEnvoi,
    StatutLettre,
)

_log = logging.getLogger(__name__)

#: Entre deux courriels. Resend accepte deux requêtes par seconde.
CADENCE_S = 0.6
#: Un passage de pompe ne dépasse pas ce temps : la suivante prend le relais.
BUDGET_S = 45.0
INTERRUPTION = timedelta(minutes=15)


class Ralenti(Exception):
    """Le prestataire demande d'attendre (HTTP 429) : on reprendra plus tard."""


def _envoyer(
    adresse: str, objet: str, html: str, lien_sortie: str | None
) -> str:
    entetes: dict[str, str] = {}
    if lien_sortie:
        # RFC 8058 : le bouton « Se désinscrire » des messageries poste
        # directement sur ce lien, que la vue publique accepte en POST.
        entetes = {
            "List-Unsubscribe": f"<{lien_sortie}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    try:
        resultat = get_transactional_email_client().send_delivery_email(
            recipient_email=adresse,
            subject=objet,
            html_body=html,
            attachments=(),
            headers=entetes or None,
            # Une copie cachée par abonné inonderait la boîte de la gérante.
            copie_cachee=False,
        )
    except urllib.error.HTTPError as erreur:
        if erreur.code == 429:
            raise Ralenti from erreur
        raise
    return resultat.provider_message_id


# --- 1. Confirmations -------------------------------------------------------


def _passager(erreur: Exception) -> bool:
    """Une panne qui passera : saturation, coupure réseau, erreur 5xx."""
    if isinstance(erreur, Ralenti):
        return True
    if isinstance(erreur, urllib.error.HTTPError):
        return erreur.code >= 500
    return isinstance(erreur, (urllib.error.URLError, TimeoutError, ConnectionError))


def envoyer_les_confirmations(*, pause_s: float = CADENCE_S) -> int:
    """Un courriel par demande d'inscription en attente, et un seul.

    La demande est PRISE avant l'appel (mise à jour conditionnelle), pour
    qu'une pompe qui chevauche l'autre ne l'envoie pas deux fois. Si l'envoi
    échoue pour une raison passagère (prestataire saturé, coupure), la prise
    est rendue : la confirmation repartira au passage suivant. Un refus
    définitif (adresse rejetée) reste noté, pour ne pas réessayer chaque
    minute une adresse qui n'existe pas.
    """
    en_attente = (
        Contact.objects.filter(confirmation_demandee_le__isnull=False)
        .filter(
            Q(confirmation_envoyee_le__isnull=True)
            | Q(confirmation_envoyee_le__lt=F("confirmation_demandee_le"))
        )
        .exclude(inscrits_q())
    )
    parties = 0
    for contact in en_attente:
        envoyee = contact.confirmation_envoyee_le
        maintenant = timezone.now()
        pris = Contact.objects.filter(pk=contact.pk, confirmation_envoyee_le=envoyee).update(
            confirmation_envoyee_le=maintenant, updated_at=maintenant
        )
        if not pris:
            continue
        try:
            objet, html = gabarit.courriel_de_confirmation(contact)
            _envoyer(contact.email, objet, html, None)
        except Exception as erreur:  # noqa: BLE001 — une adresse ne bloque pas les autres
            _log.warning("Confirmation non envoyée à un contact %s", contact.pk, exc_info=True)
            if _passager(erreur):
                Contact.objects.filter(pk=contact.pk).update(confirmation_envoyee_le=envoyee)
                if isinstance(erreur, Ralenti):
                    break
            continue
        Contact.objects.filter(pk=contact.pk).update(
            confirmations_sans_reponse=F("confirmations_sans_reponse") + 1
        )
        parties += 1
        if pause_s:
            time.sleep(pause_s)
    return parties


#: Une demande jamais confirmée n'est pas gardée : au-delà, l'adresse — saisie
#: peut-être par un tiers — disparaît, si elle n'a rien demandé d'autre.
CONSERVATION_SANS_CONFIRMATION = timedelta(days=30)


def purger_les_demandes_sans_reponse(maintenant: datetime) -> int:
    """RGPD (minimisation, art. 5) : les adresses qui n'ont demandé QUE la
    lettre et n'ont jamais confirmé sont effacées après 30 jours."""
    supprimes, _ = (
        Contact.objects.filter(
            lettre_le__isnull=True,
            confirmation_demandee_le__lt=maintenant - CONSERVATION_SANS_CONFIRMATION,
        )
        .exclude(demandes__origine__in=[Origine.CHECKLIST, Origine.LEXIQUE])
        .delete()
    )
    return supprimes


# --- 2. Lettres -------------------------------------------------------------


def lancer(lettre: Lettre) -> int:
    """La lettre part : une ligne d'envoi par inscrit, maintenant.

    Rend le nombre de destinataires. Une lettre déjà lancée, envoyée ou
    annulée n'est pas relancée (0).
    """
    with transaction.atomic():
        verrou = Lettre.objects.select_for_update().get(pk=lettre.pk)
        if verrou.statut not in (StatutLettre.BROUILLON, StatutLettre.PROGRAMMEE):
            return 0
        contacts = list(Contact.objects.filter(inscrits_q()).values_list("pk", flat=True))
        Envoi.objects.bulk_create(
            [Envoi(lettre=verrou, contact_id=pk) for pk in contacts],
            ignore_conflicts=True,
        )
        verrou.statut = StatutLettre.EN_COURS
        verrou.lancee_le = timezone.now()
        verrou.save(update_fields=["statut", "lancee_le", "updated_at"])
    return len(contacts)


def lancer_les_lettres_dues(maintenant: datetime) -> int:
    dues = Lettre.objects.filter(
        statut=StatutLettre.PROGRAMMEE, programmee_pour__lte=maintenant
    )
    lancees = 0
    for lettre in dues:
        lancer(lettre)
        lancees += 1
    return lancees


def clore_les_lettres(maintenant: datetime) -> int:
    closes = 0
    for lettre in Lettre.objects.filter(statut=StatutLettre.EN_COURS):
        if lettre.envois.filter(
            statut__in=[StatutEnvoi.A_ENVOYER, StatutEnvoi.EN_COURS]
        ).exists():
            continue
        # Sous condition : une annulation arrivée entre-temps ne doit pas être
        # recouverte par « envoyée ».
        closes += Lettre.objects.filter(pk=lettre.pk, statut=StatutLettre.EN_COURS).update(
            statut=StatutLettre.ENVOYEE, terminee_le=maintenant, updated_at=maintenant
        )
    return closes


# --- 3. Automatisations -----------------------------------------------------


def _evenements(automatisation: Automatisation, etape: Etape, maintenant: datetime) -> list[Any]:
    """Les contacts dont l'événement est survenu depuis l'activation, et dont
    le délai de l'étape est échu."""
    if automatisation.active_depuis is None:
        return []
    # Ni avant l'activation, ni avant la création de l'ÉTAPE : un message
    # ajouté à une suite active depuis trois mois ne part pas d'un coup à
    # toutes les personnes arrivées entre-temps.
    depuis = max(automatisation.active_depuis, etape.created_at)
    seuil = maintenant - timedelta(days=etape.delai_jours)
    inscrits = Contact.objects.filter(inscrits_q())
    if automatisation.declencheur == Declencheur.INSCRIPTION:
        # Les abonnés AJOUTÉS par la gérante (une liste reprise d'ailleurs)
        # ne sont pas de nouveaux inscrits : leur souhaiter la bienvenue à
        # tous d'un coup, le jour de l'import, serait un envoi massif surprise.
        # Seulement si c'est l'ajout qui a posé l'inscription ACTUELLE : une
        # personne importée, partie, puis revenue d'elle-même par le site est
        # une vraie nouvelle inscrite.
        ajoutee = Demande.objects.filter(
            contact=OuterRef("pk"), origine=Origine.AJOUT, created_at__gte=OuterRef("lettre_le")
        )
        cibles = inscrits.filter(lettre_le__gte=depuis, lettre_le__lte=seuil).exclude(
            Exists(ajoutee)
        )
    else:
        # Un téléchargement ne déclenche la suite que s'il est fait APRÈS la
        # confirmation : une demande anonyme au nom d'un abonné (n'importe qui
        # peut saisir son adresse) ne lui vaut pas une série de messages.
        demandes = Demande.objects.filter(
            origine=automatisation.declencheur,
            created_at__gte=depuis,
            created_at__lte=seuil,
        ).filter(created_at__gte=F("contact__lettre_le")).values("contact_id")
        cibles = inscrits.filter(pk__in=demandes)
    deja = Envoi.objects.filter(etape=etape).values("contact_id")
    return list(cibles.exclude(pk__in=deja).values_list("pk", flat=True))


def mettre_en_file_les_automatisations(maintenant: datetime) -> int:
    ajoutes = 0
    for automatisation in Automatisation.objects.filter(active=True).prefetch_related("etapes"):
        for etape in automatisation.etapes.all():
            contacts = _evenements(automatisation, etape, maintenant)
            Envoi.objects.bulk_create(
                [Envoi(etape=etape, contact_id=pk) for pk in contacts],
                ignore_conflicts=True,
            )
            ajoutes += len(contacts)
    return ajoutes


# --- 4. Envois --------------------------------------------------------------


def marquer_les_interrompus(maintenant: datetime) -> int:
    return Envoi.objects.filter(
        statut=StatutEnvoi.EN_COURS, pris_le__lt=maintenant - INTERRUPTION
    ).update(
        statut=StatutEnvoi.ECHEC,
        erreur="Envoi interrompu : non renvoyé, pour ne pas risquer un doublon.",
        updated_at=maintenant,
    )


def _contenu(envoi: Envoi) -> tuple[str, str, str]:
    source = envoi.lettre if envoi.lettre_id else envoi.etape
    assert source is not None  # garanti par la contrainte `une_seule_source`
    return source.objet, source.apercu, source.corps_html


def envoyer_un(envoi: Envoi) -> str:
    """Envoie un message en file. Rend le statut final."""
    maintenant = timezone.now()
    pris = Envoi.objects.filter(pk=envoi.pk, statut=StatutEnvoi.A_ENVOYER).update(
        statut=StatutEnvoi.EN_COURS, pris_le=maintenant, updated_at=maintenant
    )
    if not pris:
        return "deja_pris"
    contact = envoi.contact
    contact.refresh_from_db()
    # Une automatisation mise en pause (ou une lettre annulée) entre la mise
    # en file et le départ ne doit plus rien envoyer.
    suspendu = (
        envoi.etape_id is not None
        and not Automatisation.objects.filter(etapes=envoi.etape_id, active=True).exists()
    ) or (
        envoi.lettre_id is not None
        and Lettre.objects.filter(pk=envoi.lettre_id, statut=StatutLettre.ANNULEE).exists()
    )
    if suspendu or not contact.inscrit_a_la_lettre:
        Envoi.objects.filter(pk=envoi.pk).update(
            statut=StatutEnvoi.IGNORE, updated_at=timezone.now()
        )
        return StatutEnvoi.IGNORE
    try:
        objet, apercu, corps = _contenu(envoi)
        lien = gabarit.lien_de_desinscription(contact)
        html = gabarit.enrober(objet=objet, apercu=apercu, corps_html=corps, lien_sortie=lien)
        message_id = _envoyer(contact.email, objet, html, lien)
    except Ralenti:
        Envoi.objects.filter(pk=envoi.pk).update(
            statut=StatutEnvoi.A_ENVOYER, pris_le=None, updated_at=timezone.now()
        )
        raise
    except Exception as erreur:  # noqa: BLE001 — l'échec est noté, la file continue
        _log.warning("Envoi %s en échec", envoi.pk, exc_info=True)
        Envoi.objects.filter(pk=envoi.pk).update(
            statut=StatutEnvoi.ECHEC,
            erreur=f"{type(erreur).__name__}: {erreur}"[:300],
            updated_at=timezone.now(),
        )
        return StatutEnvoi.ECHEC
    Envoi.objects.filter(pk=envoi.pk).update(
        statut=StatutEnvoi.ENVOYE,
        message_id=message_id[:200],
        envoye_le=timezone.now(),
        updated_at=timezone.now(),
    )
    return StatutEnvoi.ENVOYE


def pomper(*, pause_s: float = CADENCE_S, budget_s: float = BUDGET_S) -> dict[str, int]:
    """Un passage complet. Rend ce qu'il a fait, pour les journaux."""
    debut = time.monotonic()
    maintenant = timezone.now()
    bilan = {
        "confirmations": envoyer_les_confirmations(pause_s=pause_s),
        "purges": purger_les_demandes_sans_reponse(maintenant),
        "interrompus": marquer_les_interrompus(maintenant),
        "lettres_lancees": lancer_les_lettres_dues(maintenant),
        "etapes_en_file": mettre_en_file_les_automatisations(maintenant),
        "envoyes": 0,
        "echecs": 0,
        "ignores": 0,
    }
    file = Envoi.objects.filter(statut=StatutEnvoi.A_ENVOYER).select_related("contact")
    for envoi in file.iterator():
        if time.monotonic() - debut > budget_s:
            break
        try:
            statut = envoyer_un(envoi)
        except Ralenti:
            _log.info("Prestataire de courriel saturé : reprise au prochain passage")
            break
        if statut == StatutEnvoi.ENVOYE:
            bilan["envoyes"] += 1
        elif statut == StatutEnvoi.ECHEC:
            bilan["echecs"] += 1
        elif statut == StatutEnvoi.IGNORE:
            bilan["ignores"] += 1
        if pause_s:
            time.sleep(pause_s)
    bilan["lettres_closes"] = clore_les_lettres(timezone.now())
    return bilan


def envoyer_un_essai(*, objet: str, apercu: str, corps_html: str, adresse: str) -> str:
    """Un exemplaire à une adresse choisie par la gérante, hors liste."""
    html = gabarit.enrober(
        objet=objet, apercu=apercu, corps_html=corps_html, lien_sortie=None
    )
    return _envoyer(adresse, f"[Essai] {objet}", html, None)
