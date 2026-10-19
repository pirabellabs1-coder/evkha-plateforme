"""Traduction d'un événement Brevo en `Evenement` de prospection.

Brevo appelle notre webhook à chaque étape d'un e-mail (délivré, ouvert, cliqué,
rebond, désinscription, plainte). On relie l'événement au `Message` par son
`provider_message_id`, et on en trace un `Evenement` — la source unique des
métriques (une seule vérité : aucun compteur stocké à part).

Fonction pure et défensive : un événement inconnu, un message introuvable ou un
horodatage illisible ne lèvent pas — ils rendent `None` ou retombent sur l'heure
courante. Un webhook qui plante se retrace sans fin ; on préfère ignorer
proprement ce qu'on ne sait pas lire.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from django.utils import timezone as dj_timezone

from . import services
from .models import Evenement, Message, TypeEvenement

#: Événement Brevo (champ `event`) -> notre type. Plusieurs libellés Brevo
#: retombent sur le même type (un rebond dur ou mou, un blocage : tous REBOND).
_CORRESPONDANCE: dict[str, str] = {
    "delivered": TypeEvenement.DELIVRE,
    "opened": TypeEvenement.OUVERT,
    "unique_opened": TypeEvenement.OUVERT,
    "proxy_open": TypeEvenement.OUVERT,
    "click": TypeEvenement.CLIQUE,
    "unsubscribed": TypeEvenement.DESINSCRIT,
    "list_unsubscribe": TypeEvenement.DESINSCRIT,
    "hard_bounce": TypeEvenement.REBOND,
    "soft_bounce": TypeEvenement.REBOND,
    "blocked": TypeEvenement.REBOND,
    "invalid_email": TypeEvenement.REBOND,
    "deferred": TypeEvenement.REBOND,
    "error": TypeEvenement.REBOND,
    "spam": TypeEvenement.PLAINTE,
    "complaint": TypeEvenement.PLAINTE,
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
    type, horodatage) ne crée pas de doublon. Une désinscription déclenche
    l'opt-out du prospect (et annule ses messages en file).
    """
    if not isinstance(payload, dict):
        return None
    type_evt = _CORRESPONDANCE.get(str(payload.get("event", "")).strip().lower())
    if type_evt is None:
        return None
    identifiant = _identifiant_message(payload)
    if not identifiant:
        return None
    message = (
        Message.objects.select_related("prospect")
        .filter(provider_message_id=identifiant)
        .first()
    )
    if message is None:
        return None

    evenement, _ = Evenement.objects.get_or_create(
        message=message,
        type=type_evt,
        horodatage=_horodatage(payload),
        defaults={"charge": payload},
    )
    if type_evt == TypeEvenement.DESINSCRIT and not message.prospect.consentement_retire:
        services.desinscrire(message.prospect)
    return evenement
