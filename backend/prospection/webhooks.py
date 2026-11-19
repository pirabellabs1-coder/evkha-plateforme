"""Traduction d'un événement Brevo en `Evenement` de prospection.

Brevo appelle notre webhook à chaque étape d'un e-mail (délivré, ouvert, cliqué,
rebond, désinscription, plainte). On relie l'événement au `Message` par son
`provider_message_id`, et on en trace un `Evenement` — la source unique des
métriques (une seule vérité : aucun compteur stocké à part).

Fonction pure et défensive : un événement inconnu, un message introuvable ou un
horodatage illisible ne lèvent pas — ils rendent `None` ou retombent sur l'heure
courante. Un webhook qui plante se retrace sans fin ; on préfère ignorer
proprement ce qu'on ne sait pas lire.

## Tracer n'est pas agir (audit du 19/11/2026)

Seule la désinscription déclenchait une action. Une PLAINTE était tracée et les
relances continuaient vers quelqu'un qui venait de nous signaler comme
indésirable ; un REBOND DÉFINITIF aussi, vers une boîte qui n'existe pas. Et
les simples RETARDS (`deferred`, `soft_bounce`, `email.delivery_delayed`)
étaient rangés en REBOND : ils gonflaient le compteur des rebonds.

Chaque libellé du fournisseur porte donc DEUX choses : le type tracé, et
l'effet sur la suite (`_Effet`). Le type seul ne suffit pas — un `blocked`
Brevo est un non-remis (REBOND au compteur) dont la cause peut être chez
l'expéditeur : il ne prouve rien sur l'adresse et ne l'interdit pas.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from django.utils import timezone as dj_timezone

from . import services
from .models import Evenement, Message, MotifInterdiction, TypeEvenement


class _Effet(Enum):
    """Ce qu'un événement change à la suite de la séquence, au-delà de sa trace."""

    AUCUN = "aucun"
    #: La personne ne veut plus de nos messages : opposition, attachée à l'adresse.
    DESINSCRIPTION = "desinscription"
    #: Signalement comme indésirable : vaut opposition, même traitement.
    PLAINTE = "plainte"
    #: L'adresse n'existe pas : file annulée, adresse refusée à l'envoi.
    ADRESSE_INVALIDE = "adresse_invalide"


#: Événement Brevo (champ `event`) -> (notre type, son effet).
#:
#: Trois familles de non-remise, qu'il ne faut pas confondre :
#: - `hard_bounce`, `invalid_email` : la boîte n'existe pas — rebond DÉFINITIF ;
#: - `soft_bounce`, `deferred` : remise RETARDÉE, le fournisseur réessaie — ni
#:   rebond au compteur, ni blocage ;
#: - `blocked`, `error` : non remis, cause indéterminée (liste de blocage du
#:   compte, expéditeur non autorisé, panne) — compté en rebond, SANS interdire
#:   l'adresse : une panne côté expéditeur invaliderait sinon tout le fichier.
_CORRESPONDANCE: dict[str, tuple[str, _Effet]] = {
    "delivered": (TypeEvenement.DELIVRE, _Effet.AUCUN),
    "opened": (TypeEvenement.OUVERT, _Effet.AUCUN),
    "unique_opened": (TypeEvenement.OUVERT, _Effet.AUCUN),
    "proxy_open": (TypeEvenement.OUVERT, _Effet.AUCUN),
    "click": (TypeEvenement.CLIQUE, _Effet.AUCUN),
    "unsubscribed": (TypeEvenement.DESINSCRIT, _Effet.DESINSCRIPTION),
    "list_unsubscribe": (TypeEvenement.DESINSCRIT, _Effet.DESINSCRIPTION),
    "hard_bounce": (TypeEvenement.REBOND, _Effet.ADRESSE_INVALIDE),
    "invalid_email": (TypeEvenement.REBOND, _Effet.ADRESSE_INVALIDE),
    "blocked": (TypeEvenement.REBOND, _Effet.AUCUN),
    "error": (TypeEvenement.REBOND, _Effet.AUCUN),
    "soft_bounce": (TypeEvenement.RETARD, _Effet.AUCUN),
    "deferred": (TypeEvenement.RETARD, _Effet.AUCUN),
    "spam": (TypeEvenement.PLAINTE, _Effet.PLAINTE),
    "complaint": (TypeEvenement.PLAINTE, _Effet.PLAINTE),
}


def _identifiant_message(payload: dict[str, Any]) -> str:
    """L'identifiant du message tel que Brevo le renvoie (clé selon les versions)."""
    for cle in ("message-id", "messageId", "message_id"):
        valeur = payload.get(cle)
        if valeur:
            return str(valeur).strip().strip("<>")
    return ""


def _horodatage(payload: dict[str, Any]) -> datetime:
    """L'heure de l'événement Brevo, ou l'heure courante si elle est illisible."""
    brut = payload.get("ts_event") or payload.get("ts") or payload.get("date")
    if isinstance(brut, (int, float)):
        try:
            return datetime.fromtimestamp(float(brut), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return dj_timezone.now()
    if isinstance(brut, str) and brut:
        try:
            dt = datetime.fromisoformat(brut.replace("Z", "+00:00"))
        except ValueError:
            return dj_timezone.now()
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return dj_timezone.now()


def enregistrer_evenement_brevo(payload: dict[str, Any]) -> Evenement | None:
    """Trace l'événement Brevo sur le bon message. Rend l'`Evenement`, ou None.

    None quand l'événement n'est pas suivi (ex. `request`) ou que le message est
    introuvable — jamais une exception. Idempotent : le même événement (message,
    type, horodatage) ne crée pas de doublon. Une désinscription ou une plainte
    déclenche l'opt-out de l'adresse ; un rebond définitif l'invalide.
    """
    if not isinstance(payload, dict):
        return None
    correspondance = _CORRESPONDANCE.get(str(payload.get("event", "")).strip().lower())
    if correspondance is None:
        return None
    type_evt, effet = correspondance
    return _tracer_sur_message(
        _identifiant_message(payload), type_evt, _horodatage(payload), payload, effet
    )


def _tracer_sur_message(
    identifiant: str,
    type_evt: str,
    horodatage: Any,
    charge: dict[str, Any],
    effet: _Effet = _Effet.AUCUN,
) -> Evenement | None:
    """Pose l'événement sur le message désigné par son id fournisseur, ou None.

    Partagé par Brevo et Resend : les deux relient par `provider_message_id` et
    tracent un `Evenement` idempotent, puis appliquent son EFFET. L'effet est
    rejoué même si l'événement était déjà tracé : les services sont
    idempotents, et un webhook rejoué après une panne à mi-chemin doit finir
    le travail, pas le croire fait.
    """
    if not identifiant:
        return None
    # L'identifiant est cherché sous ses DEUX écritures. Brevo le rend entre
    # chevrons à l'envoi (« <…@smtp-relay…> »), et c'est ainsi qu'il est
    # enregistré ; son webhook, lui, est lu sans chevrons. Cherché sous une
    # seule forme, aucun événement Brevo ne retrouvait son message : plainte,
    # désinscription et rebond rendaient `None` en silence (relecture du
    # 19/11/2026). Resend, fournisseur par défaut, n'en met pas.
    nu = identifiant.strip().strip("<>")
    message = (
        Message.objects.select_related("prospect")
        .filter(provider_message_id__in=(nu, f"<{nu}>"))
        .first()
    )
    if message is None:
        return None
    evenement, _ = Evenement.objects.get_or_create(
        message=message,
        type=type_evt,
        horodatage=horodatage,
        defaults={"charge": charge},
    )
    _appliquer(effet, message)
    return evenement


def _appliquer(effet: _Effet, message: Message) -> None:
    """L'effet d'un événement sur la suite : opposition, ou adresse invalidée."""
    if effet is _Effet.DESINSCRIPTION:
        services.desinscrire(message.prospect)
    elif effet is _Effet.PLAINTE:
        services.desinscrire(message.prospect, motif=MotifInterdiction.PLAINTE)
    elif effet is _Effet.ADRESSE_INVALIDE:
        # L'adresse où CE message est parti, pas celle que la fiche porte
        # aujourd'hui : une fiche corrigée depuis ne doit pas voir sa bonne
        # adresse frappée par le rebond de l'ancienne. Les messages d'avant
        # l'audit n'ont pas cette trace : on retombe sur la fiche.
        services.invalider_adresse(message.destinataire or message.prospect.email)


#: Type d'événement Resend (champ `type`, préfixé `email.`) -> (notre type, effet).
#: `email.bounced` n'y figure pas : son effet dépend de la charge, voir
#: `_rebond_resend`.
_CORRESPONDANCE_RESEND: dict[str, tuple[str, _Effet]] = {
    "email.delivered": (TypeEvenement.DELIVRE, _Effet.AUCUN),
    "email.opened": (TypeEvenement.OUVERT, _Effet.AUCUN),
    "email.clicked": (TypeEvenement.CLIQUE, _Effet.AUCUN),
    "email.delivery_delayed": (TypeEvenement.RETARD, _Effet.AUCUN),
    "email.complained": (TypeEvenement.PLAINTE, _Effet.PLAINTE),
}


def _rebond_resend(donnee: object) -> tuple[str, _Effet]:
    """Classe un `email.bounced` Resend selon `data.bounce.type`.

    Resend range sous le même événement le rejet permanent et le rejet
    transitoire, et les distingue dans la charge : « Permanent », « Transient »,
    « Undetermined ». Un rejet transitoire est un RETARD. Un rejet indéterminé
    est compté sans interdire l'adresse — on ne condamne pas une adresse sur un
    doute. Sans précision (charges anciennes), `email.bounced` est par
    définition un rejet permanent du serveur destinataire.
    """
    nature = ""
    if isinstance(donnee, dict):
        rebond = donnee.get("bounce")
        if isinstance(rebond, dict):
            nature = str(rebond.get("type") or "").strip().lower()
    if nature == "transient":
        return TypeEvenement.RETARD, _Effet.AUCUN
    if nature == "undetermined":
        return TypeEvenement.REBOND, _Effet.AUCUN
    return TypeEvenement.REBOND, _Effet.ADRESSE_INVALIDE


def enregistrer_evenement_resend(payload: dict[str, Any]) -> Evenement | None:
    """Trace un événement Resend sur le bon message. Rend l'`Evenement`, ou None.

    Resend enveloppe tout sous `{"type": "email.opened", "data": {"email_id": …}}`.
    Même contrat défensif que Brevo : inconnu ou introuvable rendent None, jamais
    une exception. Resend n'émet pas d'événement de désinscription — celle-ci
    passe par notre lien public.
    """
    if not isinstance(payload, dict):
        return None
    donnee = payload.get("data")
    nom = str(payload.get("type", "")).strip().lower()
    if nom == "email.bounced":
        correspondance: tuple[str, _Effet] | None = _rebond_resend(donnee)
    else:
        correspondance = _CORRESPONDANCE_RESEND.get(nom)
    if correspondance is None:
        return None
    type_evt, effet = correspondance
    identifiant = ""
    if isinstance(donnee, dict):
        identifiant = str(donnee.get("email_id") or donnee.get("id") or "").strip()
    horodatage = _horodatage({"date": payload.get("created_at", "")})
    return _tracer_sur_message(identifiant, type_evt, horodatage, payload, effet)
