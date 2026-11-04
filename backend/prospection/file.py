"""L'ordre de la file de validation : quel message, à quelle étape, et quand.

## Le défaut

Retour de l'utilisateur, 04/11/2026 : dans « À valider », « on ne sait pas
quel est le premier message, ni le second, ni le troisième ». L'agent rédige
d'un coup le premier e-mail ET toutes ses relances (`agents._creer_les_messages`),
et la file les montrait pêle-mêle, triés par date de création — identique pour
les cinq messages d'un même prospect. Rien ne disait l'étape, rien n'empêchait
de valider une relance avant que le premier mail soit parti.

## La règle

Un message est PRÊT quand :

- c'est un premier message, et qu'aucun autre premier message de ce prospect
  n'est déjà parti — on n'écrit pas deux fois « je me présente » ;
- ou c'est une relance, un message de l'étape précédente du même prospect est
  ENVOYÉ, et le délai de son étape est écoulé (`Sequence.delai_jours`, ou
  `DELAI_RELANCE_PAR_DEFAUT_JOURS` sans séquence).

Une relance dont l'étape précédente n'a plus aucun message vivant est
ROMPUE : elle ne partira jamais seule, et on le dit au lieu de la compter
parmi celles qui « attendent leur tour ».

La file de validation ne montre que ce qui est prêt. Les relances restent
rédigées d'avance — un seul appel au modèle, cohérent d'une étape à l'autre —
mais elles n'apparaissent qu'à leur tour. `services.envoyer_message` applique
la même règle : c'est l'invariant, pas un filtre d'écran.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone

from .models import Message, StatutMessage

#: Délai d'une relance sans étape de séquence pour le fixer. Zéro laissait la
#: relance partir dans la seconde qui suit le premier mail (relecture du
#: 04/11/2026) ; trois jours est le délai que les campagnes utilisent.
DELAI_RELANCE_PAR_DEFAUT_JOURS = 3


@dataclass(frozen=True)
class Place:
    """La place d'un message dans la séquence de son prospect."""

    etape: int
    pret: bool
    #: À partir de quand il pourra partir ; None tant que l'étape d'avant n'est
    #: pas envoyée (ou ne le sera jamais).
    disponible_le: datetime | None
    #: L'étape d'avant n'a plus aucun message vivant : il ne partira jamais.
    rompue: bool = False

    @property
    def libelle(self) -> str:
        return "Premier message" if self.etape == 0 else f"Relance {self.etape}"


def _cle(message: Message) -> tuple[datetime, str]:
    return (message.created_at, str(message.id))


def _etapes(messages: list[Message]) -> dict[str, int]:
    """L'étape de chaque message d'UN prospect.

    Dans l'ordre : l'étape écrite par l'agent (`Message.etape`), celle de la
    séquence, et seulement pour les messages hérités qui n'ont ni l'une ni
    l'autre, leur rang parmi les messages VIVANTS de même condition — un
    message annulé ne décale pas les suivants.
    """
    etapes: dict[str, int] = {}
    sans_rien = sorted(
        (
            m for m in messages
            if m.etape is None and m.sequence_id is None and m.statut != StatutMessage.ANNULE
        ),
        key=_cle,
    )
    for rang, message in enumerate(sans_rien):
        etapes[str(message.id)] = rang
    for message in messages:
        if message.etape is not None:
            etapes[str(message.id)] = message.etape
        elif message.sequence_id is not None and message.sequence is not None:
            etapes[str(message.id)] = message.sequence.ordre
        else:
            etapes.setdefault(str(message.id), 0)
    return etapes


def _delai(message: Message) -> timedelta:
    if message.sequence is not None:
        return timedelta(days=message.sequence.delai_jours)
    return timedelta(days=DELAI_RELANCE_PAR_DEFAUT_JOURS)


def _places_d_un_prospect(
    messages: list[Message], maintenant: datetime
) -> dict[str, Place]:
    etapes = _etapes(messages)
    vivants: dict[int, list[Message]] = {}
    envoyes: dict[int, list[Message]] = {}
    for message in messages:
        etape = etapes[str(message.id)]
        if message.statut != StatutMessage.ANNULE:
            vivants.setdefault(etape, []).append(message)
        if message.statut == StatutMessage.ENVOYE and message.envoye_le is not None:
            envoyes.setdefault(etape, []).append(message)

    places: dict[str, Place] = {}
    for message in messages:
        etape = etapes[str(message.id)]
        if message.statut == StatutMessage.ENVOYE:
            places[str(message.id)] = Place(etape, False, message.envoye_le)
            continue
        if etape == 0:
            deja_parti = any(m.pk != message.pk for m in envoyes.get(0, []))
            places[str(message.id)] = Place(0, not deja_parti, message.created_at)
            continue
        partis = envoyes.get(etape - 1, [])
        if not partis:
            rompue = not vivants.get(etape - 1)
            places[str(message.id)] = Place(etape, False, None, rompue=rompue)
            continue
        dernier_envoi = max(m.envoye_le for m in partis if m.envoye_le is not None)
        disponible = dernier_envoi + _delai(message)
        places[str(message.id)] = Place(etape, disponible <= maintenant, disponible)
    return places


def places(
    messages: Iterable[Message], *, maintenant: datetime | None = None
) -> dict[str, Place]:
    """La place de chacun de ces messages, lue sur TOUTE la séquence de leur prospect.

    Juger une relance sur les seuls messages affichés serait juger sur une
    évidence tronquée (règle 9) : son premier mail, déjà envoyé, n'est plus dans
    la liste « à valider ». On relit donc chaque prospect en entier.
    """
    maintenant = maintenant or timezone.now()
    prospects = {m.prospect_id for m in messages}
    tous = list(
        Message.objects.filter(prospect_id__in=prospects).select_related("sequence")
    )
    par_prospect: dict[object, list[Message]] = {}
    for message in tous:
        par_prospect.setdefault(message.prospect_id, []).append(message)
    resultat: dict[str, Place] = {}
    for liste in par_prospect.values():
        resultat.update(_places_d_un_prospect(liste, maintenant))
    return resultat


def place(message: Message, *, maintenant: datetime | None = None) -> Place:
    return places([message], maintenant=maintenant)[str(message.id)]
