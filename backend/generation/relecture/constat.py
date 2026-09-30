"""Un constat de relecture, et le registre des contrôles qui les produisent."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..memoire.etude import MemoireEtude
    from .document import Document


@dataclass(frozen=True)
class Constat:
    """Une erreur trouvée dans le texte, que le lecteur peut retrouver (règle 2)."""

    #: La classe d'erreur (« formule », « comptage », « fuite »…).
    classe: str
    #: Où la lire : « 9.3 », « ch. 16 », « p. 26 ».
    section: str
    #: Le passage exact, tel qu'écrit.
    extrait: str
    #: Ce qui ne va pas, et ce qu'il faut écrire à la place.
    detail: str
    #: Grave : fait reprendre le chapitre avant rendu. Sinon : signalé seulement.
    grave: bool = True

    def motif(self) -> str:
        """La consigne de reprise transmise au rédacteur."""
        return f"[{self.classe}] {self.section} — « {self.extrait} » : {self.detail}"


@dataclass(frozen=True)
class Reference:
    """Ce contre quoi le texte se juge."""

    memoire: MemoireEtude | None = None
    #: Type de livrable (`business_plan`…) : certaines règles lui sont propres.
    livrable: str = ""
    #: Contrôles réservés au document ENTIER (mise en page, sources) : sur un
    #: chapitre seul, ils n'ont pas de quoi juger.
    document_entier: bool = False
    extra: dict[str, object] = field(default_factory=dict)


Controle = Callable[["Document", Reference], list[Constat]]


def controles() -> tuple[Controle, ...]:
    """Tous les contrôles, dans l'ordre des classes d'erreurs."""
    from . import (  # noqa: PLC0415 — registre chargé à l'usage
        coherence,
        comptages,
        formules,
        fuites,
        mise_en_page,
        periodes,
        sensibilite,
        sources,
        tableaux,
    )

    return (
        periodes.controler,
        coherence.controler,
        formules.controler,
        tableaux.controler,
        comptages.controler,
        fuites.controler,
        sources.controler,
        mise_en_page.controler,
        sensibilite.controler,
    )


def relire(document: Document, reference: Reference) -> list[Constat]:
    """Chaque contrôle sur le document ; aucun ne peut en faire tomber un autre."""
    import logging  # noqa: PLC0415

    constats: list[Constat] = []
    for controle in controles():
        try:
            constats.extend(controle(document, reference))
        except Exception:  # noqa: BLE001 — un contrôle en panne ne tait pas les autres
            logging.getLogger(__name__).exception(
                "Contrôle de relecture en panne : %s", getattr(controle, "__module__", controle)
            )
    vus: set[tuple[str, str, str]] = set()
    uniques: list[Constat] = []
    for constat in constats:
        cle = (constat.classe, constat.section, constat.extrait)
        if cle not in vus:
            vus.add(cle)
            uniques.append(constat)
    return uniques
