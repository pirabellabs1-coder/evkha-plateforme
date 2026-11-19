"""Les actes de la prospection — dont l'invariant « rien ne part sans validation ».

Toute la sûreté de ce sous-système tient en un point : un `Message` ne quitte
le système que s'il a été VALIDÉ par un humain, et jamais vers un prospect
désinscrit. `envoyer_message` est le SEUL chemin d'envoi, et il refuse tout le
reste. Un test rejoue un brouillon contre lui : il doit lever.

Depuis l'audit du 19/11/2026, « à qui peut-on écrire ? » n'a plus qu'une
réponse, ici : `motif_de_non_contact`. L'envoi, la rédaction et l'écran la
lisent tous — une opposition, un rebond définitif, une réponse reçue ou une
exclusion arrêtent la séquence au même endroit (règle 5).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import transaction
from django.db.models.functions import Lower, Trim
from django.urls import reverse
from django.utils import timezone

from .models import (
    ETATS_ENVOYABLES,
    MOTIFS_D_OPPOSITION,
    AdresseInterdite,
    Evenement,
    Message,
    MotifInterdiction,
    Prospect,
    StatutMessage,
    StatutProspect,
    TypeEvenement,
    normaliser_adresse,
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


class ClassementRefuseError(RuntimeError):
    """Le prospect ne peut pas prendre ce statut. Le message dit pourquoi."""


#: Les états d'où un message n'est PAS encore parti et peut encore être retiré
#: de la file. Tout sauf ENVOYÉ (parti) et ANNULÉ (déjà retiré) : une seule
#: définition pour la désinscription, le rebond et le classement (règle 5).
_ETATS_FINIS = (StatutMessage.ENVOYE, StatutMessage.ANNULE)


# ── Les adresses auxquelles on n'écrit plus ──────────────────────────────────


def interdictions(adresses: Iterable[object]) -> dict[str, str]:
    """Le motif d'interdiction de celles de ces adresses qui sont interdites.

    Clé : l'adresse NORMALISÉE. Une seule requête pour tout le lot — l'écran
    liste jusqu'à 500 fiches, on ne les interroge pas une à une.
    """
    cles = {normaliser_adresse(a) for a in adresses} - {""}
    if not cles:
        return {}
    return dict(
        AdresseInterdite.objects.filter(adresse__in=cles).values_list("adresse", "motif")
    )


def interdire_adresse(adresse: object, motif: str) -> AdresseInterdite | None:
    """Inscrit l'adresse à la table d'opposition. Idempotent ; None si elle est vide.

    Une opposition (désinscription, plainte) PRIME sur un rebond déjà inscrit :
    elle est définitive et attachée à la personne. L'inverse ne rétrograde
    jamais — un rebond sur une adresse opposée ne fait pas oublier l'opposition.
    """
    cle = normaliser_adresse(adresse)
    if not cle:
        return None
    interdite, creee = AdresseInterdite.objects.get_or_create(
        adresse=cle, defaults={"motif": motif}
    )
    if not creee and motif in MOTIFS_D_OPPOSITION and not interdite.est_une_opposition:
        interdite.motif = motif
        interdite.save(update_fields=["motif", "updated_at"])
    return interdite


def _fiches_a_ces_adresses(cles: set[str]) -> list[Prospect]:
    """Toutes les fiches dont l'adresse est l'une de celles-ci, toutes campagnes.

    Comparaison sur `Lower(Trim(email))` : les adresses écrites depuis l'audit
    du 19/11/2026 sont normalisées, mais les fiches d'avant portent ce que le
    formulaire ou le modèle avait rendu (majuscules, espace en bout).
    """
    if not cles:
        return []
    ids = list(
        Prospect.objects.annotate(cle_adresse=Lower(Trim("email")))
        .filter(cle_adresse__in=cles)
        .values_list("pk", flat=True)
    )
    return list(Prospect.objects.filter(pk__in=ids))


def _annuler_la_file(prospects: Iterable[Prospect]) -> int:
    """Annule tout message PAS ENCORE PARTI de ces fiches. Rend leur nombre."""
    ids = [p.pk for p in prospects]
    if not ids:
        return 0
    return Message.objects.filter(prospect_id__in=ids).exclude(
        statut__in=_ETATS_FINIS
    ).update(statut=StatutMessage.ANNULE, updated_at=timezone.now())


def _adresses_ecrites(prospect: Prospect) -> set[str]:
    """L'adresse de la fiche ET celles où ses messages sont réellement partis.

    Une fiche se corrige : le lien de désinscription d'un e-mail parti à
    l'ancienne adresse doit opposer CETTE adresse-là aussi.
    """
    adresses = {normaliser_adresse(prospect.email)}
    adresses.update(
        normaliser_adresse(d)
        for d in prospect.messages.exclude(destinataire="").values_list(
            "destinataire", flat=True
        )
    )
    return adresses - {""}


def _motif_d_arret(prospect: Prospect, interdites: Mapping[str, str]) -> str | None:
    """Ce qui ARRÊTE la séquence de ce prospect, ou None. Ne juge pas l'adresse vide."""
    motif = interdites.get(normaliser_adresse(prospect.email))
    if prospect.consentement_retire or prospect.statut == StatutProspect.DESINSCRIT:
        return "le prospect s'est désinscrit : plus aucun message ne lui est envoyé"
    if motif == MotifInterdiction.DESINSCRIPTION:
        return (
            f"l'adresse {prospect.email} s'est désinscrite (opposition enregistrée "
            "sur une autre fiche) : plus aucun message ne lui est envoyé"
        )
    if motif == MotifInterdiction.PLAINTE:
        return (
            f"l'adresse {prospect.email} a signalé nos messages comme indésirables "
            "(plainte) : plus aucun message ne lui est envoyé"
        )
    if motif == MotifInterdiction.REBOND_DEFINITIF:
        return (
            f"l'adresse {prospect.email} a été rejetée définitivement (rebond) : "
            "corrigez l'adresse de la fiche avant tout envoi"
        )
    if prospect.statut == StatutProspect.A_REPONDU:
        return "le prospect a répondu : sa séquence de relances est arrêtée"
    if prospect.statut == StatutProspect.CONVERTI:
        return "le prospect est converti : la prospection est terminée pour lui"
    if prospect.statut == StatutProspect.EXCLU:
        return "le prospect est exclu de la prospection"
    return None


_SANS_ADRESSE = "le prospect n'a pas d'adresse e-mail"


def motif_de_non_contact(
    prospect: Prospect, *, interdites: Mapping[str, str] | None = None
) -> str | None:
    """Pourquoi on ne peut PAS écrire à ce prospect, ou None si on le peut.

    LA définition de « contactable » (règle 5) : `_raison_de_refus` (l'envoi),
    `agents.rediger_les_messages` (ne pas payer une rédaction qui ne partira
    pas) et l'écran (`contactable`) la lisent tous.

    `interdites` : le résultat d'`interdictions` quand l'appelant juge un lot ;
    absent, la table est interrogée pour cette seule adresse.
    """
    if interdites is None:
        interdites = interdictions([prospect.email])
    arret = _motif_d_arret(prospect, interdites)
    if arret is not None:
        return arret
    if not normaliser_adresse(prospect.email):
        return _SANS_ADRESSE
    return None


def heriter_de_l_opposition(prospect: Prospect) -> bool:
    """Marque d'emblée une fiche dont l'adresse est DÉJÀ opposée. Rend True si marquée.

    Appelé à la création (agent ou saisie) et à la correction d'une adresse :
    la fiche naît désinscrite au lieu de naître contactable (audit du
    19/11/2026 — la campagne B recréait le cabinet désinscrit dans la A).
    Un rebond définitif ne marque pas la fiche : l'adresse est refusée à
    l'envoi, et se corrige.
    """
    if prospect.consentement_retire:
        return False
    motif = interdictions([prospect.email]).get(normaliser_adresse(prospect.email))
    if motif not in MOTIFS_D_OPPOSITION:
        return False
    with transaction.atomic():
        prospect.consentement_retire = True
        prospect.desinscrit_le = timezone.now()
        prospect.statut = StatutProspect.DESINSCRIT
        prospect.save(update_fields=[
            "consentement_retire", "desinscrit_le", "statut", "updated_at",
        ])
        _annuler_la_file([prospect])
    return True


# ── Valider, annuler, remettre en brouillon ──────────────────────────────────


def valider_message(message: Message, *, par: str) -> Message:
    """Un humain valide le message : il PEUT désormais partir. Rien ne part ici.

    La validation est un acte horodaté et nominatif (`par`) : c'est elle, et
    elle seule, qui autorisera `envoyer_message`. Un message déjà envoyé ou
    annulé ne se « revalide » pas. Un message EN ÉCHEC, si : c'est la sortie
    de l'impasse après un refus du fournisseur (« Revalider » à l'écran).
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


def remettre_en_brouillon(message: Message) -> Message:
    """Ramène un message EN ÉCHEC ou VALIDÉ à l'état de brouillon, pour le retoucher.

    Audit du 19/11/2026 : un envoi refusé par le fournisseur laissait le
    message `echoue`, que rien ne permettait de modifier (seul un brouillon
    s'édite). La validation est RETIRÉE avec l'état : un texte retouché doit
    être relu et validé de nouveau — c'est l'invariant du sous-système. Le
    motif de l'échec reste lisible tant que le message n'est pas revalidé.
    """
    if message.statut not in (StatutMessage.ECHOUE, StatutMessage.VALIDE):
        msg = (
            f"Un message {message.statut} ne se remet pas en brouillon : seul un "
            "message en échec ou validé y revient."
        )
        raise EnvoiRefuseError(msg)
    message.statut = StatutMessage.BROUILLON
    message.valide_par = ""
    message.valide_le = None
    message.save(update_fields=["statut", "valide_par", "valide_le", "updated_at"])
    return message


def _raison_de_refus(message: Message) -> str | None:
    """Pourquoi ce message ne peut PAS partir, ou None s'il le peut."""
    prospect = message.prospect
    # Ce qui arrête la séquence d'abord — désinscription, plainte, rebond
    # définitif, réponse reçue, conversion, exclusion : chacun annule aussi les
    # messages en file, et le message relu avant envoi dirait sinon « annulé »
    # sans dire pourquoi. L'adresse est jugée sur la TABLE, pas sur la seule
    # fiche (audit du 19/11/2026) : l'opposition suit l'adresse.
    interdites = interdictions([prospect.email])
    arret = _motif_d_arret(prospect, interdites)
    if arret is not None:
        return arret
    if message.statut not in ETATS_ENVOYABLES:
        return (
            f"message en état « {message.statut} » : seul un message validé par un humain "
            "peut être envoyé"
        )
    if not normaliser_adresse(prospect.email):
        return _SANS_ADRESSE
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
        # `of=("self",)` : le verrou porte sur la SEULE ligne du message.
        # Audit du 19/11/2026 — `Message.sequence` est nullable, donc joint en
        # LEFT OUTER JOIN par `select_related`, et PostgreSQL refuse `FOR
        # UPDATE` sur le côté nullable d'une jointure externe
        # (`NotSupportedError`). SQLite ignore la clause : toute la suite
        # passait, et la production rendait 500 sur « Envoyer » comme sur
        # « Tout envoyer » — aucun envoi ne pouvait aboutir.
        frais = (
            Message.objects.select_for_update(of=("self",))
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
            # L'adresse où le message est réellement parti : c'est ELLE qu'un
            # rebond ou une plainte frappera, même si la fiche est corrigée
            # entre-temps.
            frais.destinataire = normaliser_adresse(frais.prospect.email)
            frais.save(update_fields=[
                "statut", "envoye_le", "provider_message_id", "error_message",
                "destinataire", "updated_at",
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
    for champ in ("statut", "envoye_le", "provider_message_id", "error_message", "destinataire"):
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


# ── Ce qui arrête une séquence : opposition, rebond définitif, classement ────


def desinscrire(
    prospect: Prospect, *, motif: str = MotifInterdiction.DESINSCRIPTION
) -> Prospect:
    """Un prospect s'oppose : opt-out définitif, plus aucun envoi — À CETTE ADRESSE.

    L'opposition suit l'adresse, pas la fiche (audit du 19/11/2026) : elle est
    inscrite à `AdresseInterdite`, et TOUTES les fiches de même adresse, toutes
    campagnes confondues, sont marquées et voient leur file annulée. Une fiche
    créée plus tard à cette adresse naîtra désinscrite
    (`heriter_de_l_opposition`), et `_raison_de_refus` refuse l'adresse quelle
    que soit la fiche.

    `motif` : une PLAINTE (signalement comme indésirable) vaut opposition, avec
    le même traitement ; seule la trace diffère.

    Les messages encore en file (brouillon, validé, programmé, en échec) sont
    annulés : la désinscription prime sur toute validation déjà donnée.
    """
    if motif not in MOTIFS_D_OPPOSITION:
        msg = f"« {motif} » n'est pas une opposition : voir `invalider_adresse`."
        raise ValueError(msg)
    with transaction.atomic():
        maintenant = timezone.now()
        adresses = _adresses_ecrites(prospect)
        for adresse in adresses:
            interdire_adresse(adresse, motif)

        prospect.consentement_retire = True
        # La date de la PREMIÈRE opposition fait foi : une seconde visite du
        # lien ne la déplace pas.
        prospect.desinscrit_le = prospect.desinscrit_le or maintenant
        prospect.statut = StatutProspect.DESINSCRIT
        prospect.save(update_fields=[
            "consentement_retire", "desinscrit_le", "statut", "updated_at",
        ])

        homonymes = [f for f in _fiches_a_ces_adresses(adresses) if f.pk != prospect.pk]
        Prospect.objects.filter(
            pk__in=[f.pk for f in homonymes], consentement_retire=False
        ).update(
            consentement_retire=True,
            desinscrit_le=maintenant,
            statut=StatutProspect.DESINSCRIT,
            updated_at=maintenant,
        )
        _annuler_la_file([prospect, *homonymes])
    return prospect


def invalider_adresse(adresse: object) -> int:
    """Un REBOND DÉFINITIF : l'adresse n'existe pas. Rend le nombre de messages annulés.

    Audit du 19/11/2026 : un rebond était tracé, puis rien — les relances
    continuaient de partir vers une boîte qui n'existe pas, ce qui abîme la
    réputation de l'expéditeur. L'adresse est inscrite à `AdresseInterdite`
    (`_raison_de_refus` la refuse, avec son motif), et la file de toute fiche
    qui la porte est annulée.

    La FICHE n'est pas désinscrite : personne ne s'est opposé. Corriger son
    adresse (`PUT prospects/<id>/`) lève l'interdiction, qui est attachée à
    l'adresse morte et non à l'organisation.
    """
    cle = normaliser_adresse(adresse)
    if not cle:
        return 0
    with transaction.atomic():
        interdire_adresse(cle, MotifInterdiction.REBOND_DEFINITIF)
        return _annuler_la_file(_fiches_a_ces_adresses({cle}))


#: Les statuts qui ARRÊTENT la séquence quand un humain les pose : la file
#: non partie est annulée. Les mêmes que `_motif_d_arret` refuse à l'envoi.
_STATUTS_QUI_ARRETENT = frozenset(
    {StatutProspect.A_REPONDU, StatutProspect.CONVERTI, StatutProspect.EXCLU}
)


def classer_prospect(prospect: Prospect, statut: str) -> Prospect:
    """Classe un prospect selon ce qu'il devient — et ARRÊTE ses relances s'il le faut.

    Audit du 19/11/2026 : « A répondu », « Converti », « Exclu » ne changeaient
    que le statut. Les relances déjà rédigées restaient en file et partaient
    vers quelqu'un qui avait répondu ; et le taux de réponse valait toujours 0,
    parce que les métriques comptent `TypeEvenement.REPONDU` et que rien ne
    l'écrivait.

    - RÉPONDU, CONVERTI, EXCLU : les messages non partis de sa file sont annulés.
    - RÉPONDU : l'événement REPONDU est tracé sur son dernier message envoyé
      (une fois par prospect), source du taux de réponse.
    - DÉSINSCRIT : passe par `desinscrire` (l'opposition suit l'adresse).
    - Un prospect désinscrit ne se reclasse pas : l'opposition est définitive.
    """
    if statut not in StatutProspect.values:
        msg = f"Statut inconnu : « {statut} »."
        raise ClassementRefuseError(msg)
    if statut == StatutProspect.DESINSCRIT:
        return desinscrire(prospect)
    if prospect.consentement_retire or prospect.statut == StatutProspect.DESINSCRIT:
        msg = "Un prospect désinscrit ne se reclasse pas : son opposition est définitive."
        raise ClassementRefuseError(msg)
    with transaction.atomic():
        prospect.statut = statut
        prospect.save(update_fields=["statut", "updated_at"])
        if statut in _STATUTS_QUI_ARRETENT:
            _annuler_la_file([prospect])
        if statut == StatutProspect.A_REPONDU:
            _tracer_la_reponse(prospect)
    return prospect


def _tracer_la_reponse(prospect: Prospect) -> Evenement | None:
    """Trace REPONDU sur le dernier message ENVOYÉ du prospect, une seule fois.

    None s'il n'a reçu aucun message : une réponse à rien ne se rapporte à
    aucun envoi, et le taux de réponse se compte sur les messages envoyés.
    """
    deja = Evenement.objects.filter(
        message__prospect=prospect, type=TypeEvenement.REPONDU
    ).first()
    if deja is not None:
        return deja
    dernier = (
        prospect.messages.filter(statut=StatutMessage.ENVOYE)
        .order_by("-envoye_le", "-created_at")
        .first()
    )
    if dernier is None:
        return None
    return Evenement.objects.create(
        message=dernier,
        type=TypeEvenement.REPONDU,
        horodatage=timezone.now(),
        charge={"source": "classement manuel"},
    )
