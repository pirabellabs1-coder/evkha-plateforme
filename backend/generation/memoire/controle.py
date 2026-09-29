"""Le contrôle d'UN chapitre contre la mémoire de l'étude — avant qu'il soit validé.

## Pourquoi ici, et pas à la fin

29/09/2026, business plan ÉCLORE : la relecture finale arrivait après les
vingt-deux chapitres, relisait tout d'un coup sans référence complète, et une
erreur du chapitre 1 avait déjà été recopiée par les vingt suivants. Le
contrôle se fait désormais chapitre par chapitre, contre la mémoire : un
chapitre n'est validé qu'une fois ses chiffres, ses décisions et ses repères
conformes — ou ajustés.

## Ce que ce module fait

1. `appliquer_les_reperes` remplace les `{{identifiant}}` d'un chapitre par
   leurs valeurs, dans toutes ses chaînes, et dit lesquels sont inconnus ;
2. `controler_le_chapitre` rend les MOTIFS qui le font reprendre : repère
   inconnu, chiffre écrit en clair qui n'est ni un fait ni une réponse du
   client, TVA « par choix » quand la règle l'impose, compte de concurrents
   différent de la base, « taux » exprimé en euros ;
3. `replis_de_derniere_tentative` : à la dernière tentative, ce qui ne peut
   pas partir est retiré (la phrase qui porte un repère inconnu) — le chapitre
   est TOUJOURS validé, l'étude ne s'arrête jamais.

Tout est déterministe, sans appel au modèle : ces contrôles ne coûtent rien.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .etude import MemoireEtude
from .faits import Fait
from .reperes import REPERE, remplacer_les_reperes

_ESP = "[ \u00a0\u202f]"
#: Un nombre écrit en français, avec son unité éventuelle.
_NOMBRE = re.compile(
    rf"(?<![\w.,{{])([+\-−]?\d{{1,3}}(?:{_ESP}\d{{3}})+(?:,\d+)?|[+\-−]?\d+(?:,\d+)?)"
    rf"(?:{_ESP}?(%|k€|M€|Md€|€))?"
)
_MULT = {"k€": 1e3, "M€": 1e6, "Md€": 1e9}
_PHRASE = re.compile(r"[^.!?\n]+[.!?]?")


@dataclass
class Controle:
    """Le verdict sur un chapitre : les motifs de reprise, et ce qui a été vu."""

    motifs: list[str] = field(default_factory=list)
    reperes_utilises: list[str] = field(default_factory=list)
    reperes_inconnus: list[str] = field(default_factory=list)
    #: Ce que le contrôle a examiné — jamais « rien à signaler » sans dire quoi
    #: (règle 1 : un contrôle qui n'a rien comparé n'est pas un succès).
    verifie: list[str] = field(default_factory=list)


# ── Repères ──────────────────────────────────────────────────────────────────


def _parcourir(valeur: Any, transformer: Any) -> Any:
    if isinstance(valeur, str):
        return transformer(valeur)
    if isinstance(valeur, list):
        return [_parcourir(v, transformer) for v in valeur]
    if isinstance(valeur, dict):
        return {k: _parcourir(v, transformer) for k, v in valeur.items()}
    return valeur


def _chaines(valeur: Any) -> Iterable[str]:
    if isinstance(valeur, str):
        yield valeur
    elif isinstance(valeur, list):
        for v in valeur:
            yield from _chaines(v)
    elif isinstance(valeur, dict):
        for v in valeur.values():
            yield from _chaines(v)


def appliquer_les_reperes(
    payload: Any, faits: Mapping[str, Fait]
) -> tuple[Any, list[str], list[str]]:
    """Le chapitre avec ses repères remplacés ; les repères utilisés ; les inconnus."""
    utilises: list[str] = []
    inconnus: list[str] = []

    def _remplacer(texte: str) -> str:
        rendu = remplacer_les_reperes(texte, faits)
        utilises.extend(rendu.utilises)
        inconnus.extend(rendu.inconnus)
        return rendu.texte

    return _parcourir(payload, _remplacer), utilises, inconnus


# ── Chiffres écrits en clair ─────────────────────────────────────────────────


def _valeur(brut: str, unite: str | None) -> float:
    nombre = float(re.sub(_ESP, "", brut).replace(",", ".").replace("−", "-"))
    return nombre * _MULT.get(unite or "", 1.0)


def nombres_du_texte(texte: str) -> list[tuple[str, float, str | None]]:
    """Les nombres d'un texte : (écriture, valeur en unité de base, unité)."""
    trouves = []
    for m in _NOMBRE.finditer(texte or ""):
        try:
            trouves.append((m.group(0).strip(), _valeur(m.group(1), m.group(2)), m.group(2)))
        except ValueError:
            continue
    return trouves


def _en_liste_blanche(ecriture: str, valeur: float, unite: str | None, contexte: str) -> bool:
    """Années, numéros, petits compteurs de langue courante : pas des chiffres du projet."""
    if unite is None and valeur.is_integer():
        if 1990 <= valeur <= 2040 or 0 <= valeur <= 12:
            return True
    return bool(re.search(r"(?i)(chapitre|section|annexe|étape|phase|page)\s*$", contexte))


def _proche(valeur: float, references: Iterable[float]) -> bool:
    for ref in references:
        if ref == valeur or (ref and abs(valeur - ref) <= max(abs(ref) * 0.005, 0.5)):
            return True
    return False


def _valeurs_des_faits(faits: Mapping[str, Fait]) -> list[float]:
    from generation.socle.schema import valeur_en_unites_de_base  # noqa: PLC0415

    valeurs: list[float] = []
    for fait in faits.values():
        base = valeur_en_unites_de_base(fait.valeur, fait.unite)
        valeurs.append(base[0] if base else fait.valeur)
    return valeurs


# ── Le contrôle ──────────────────────────────────────────────────────────────

_TVA_CHOIX = re.compile(
    r"(?i)(TVA[^.]{0,90}\b(par choix|choisie?|optionnel\w*|en option|volontaire\w*|opt(e|er|é))\b"
    r"|\b(par choix|opte|opter|optant)\b[^.]{0,60}\bTVA\b)"
)
_COMPTE_CONCURRENTS = re.compile(r"\b(\d{1,3})\s+(concurrents?|acteurs?)\b", re.IGNORECASE)
#: « l'étude » n'attribue rien : ce peut être la nôtre. Seul un possessif, un
#: « recensait » ou un « selon » dit que le compte vient du client.
_ATTRIBUE_AU_CLIENT = re.compile(
    r"(?i)\b(votre|son|sa|leur|ses|leurs)\s+(propre\s+)?"
    r"(étude|analyse|recensement|document|travail)|\brecens\w*|\bselon (le|la|les|son|sa)\b"
)
_TAUX_EN_EUROS = re.compile(r"(?i)\btaux\b[^.%]{0,50}?\d[\d \u00a0\u202f,]*\s?€")


def controler_le_chapitre(
    payload: Any, memoire: MemoireEtude, nombres_du_client: Iterable[float] = (),
) -> Controle:
    """Les motifs qui empêchent de valider ce chapitre en l'état.

    `payload` est le chapitre TEL QUE LE MODÈLE L'A ÉCRIT (repères non
    remplacés) : un nombre écrit en clair s'y distingue d'un repère.
    """
    controle = Controle()
    brut = "\n".join(_chaines(payload))
    references = _valeurs_des_faits(memoire.faits)
    du_client = list(nombres_du_client)

    _, controle.reperes_utilises, controle.reperes_inconnus = appliquer_les_reperes(
        payload, memoire.faits
    )
    controle.verifie.append(f"{len(controle.reperes_utilises)} repère(s) cités")
    for inconnu in sorted(set(controle.reperes_inconnus)):
        controle.motifs.append(
            f"Repère inconnu {{{{{inconnu}}}}} : il n'existe pas dans la mémoire de "
            "l'étude. Utilise un identifiant de la liste, ou retire la phrase."
        )

    libres: list[str] = []
    sans_reperes = REPERE.sub(" ", brut)
    nombres = nombres_du_texte(sans_reperes)
    controle.verifie.append(f"{len(nombres)} nombre(s) écrits en clair examinés")
    for ecriture, valeur, unite in nombres:
        debut = sans_reperes.find(ecriture)
        contexte = sans_reperes[max(0, debut - 14):debut]
        if _en_liste_blanche(ecriture, valeur, unite, contexte):
            continue
        if _proche(valeur, references) or _proche(valeur, du_client):
            continue
        libres.append(ecriture)
    for ecriture in sorted(set(libres)):
        controle.motifs.append(
            f"Chiffre écrit en clair « {ecriture} » : ni un fait de la mémoire ni une "
            "réponse du client — c'est un calcul ou une invention. Cite le repère du fait "
            "voulu ({{…}}), ou retire le chiffre."
        )

    obligatoire = [
        d for d in memoire.decisions if d.sujet == "regime_tva" and "obligatoire" in d.valeur
    ]
    controle.verifie.append("régime de TVA confronté aux règles")
    if obligatoire and _TVA_CHOIX.search(brut):
        annees = ", ".join(str(d.annee) for d in obligatoire)
        controle.motifs.append(
            f"La TVA est présentée comme un choix alors qu'elle est OBLIGATOIRE ({annees}) : "
            "le chiffre d'affaires dépasse le seuil de franchise. Écris qu'elle s'applique, "
            "jamais qu'elle est choisie."
        )

    base = next((d for d in memoire.decisions if d.sujet == "concurrents"), None)
    controle.verifie.append("comptes de concurrents confrontés à la base")
    if base is not None:
        admis = {int(n) for n in re.findall(r"\d+", base.valeur)}
        for phrase in _PHRASE.findall(brut):
            for m in _COMPTE_CONCURRENTS.finditer(phrase):
                if int(m.group(1)) not in admis and not _ATTRIBUE_AU_CLIENT.search(phrase):
                    controle.motifs.append(
                        f"« {m.group(0)} » contredit la base ({base.valeur}). Un autre "
                        "compte trouvé dans un document du client s'attribue au client."
                    )

    controle.verifie.append("unités des taux")
    for m in _TAUX_EN_EUROS.finditer(brut):
        controle.motifs.append(
            f"« {m.group(0).strip()} » : un taux s'exprime en %, jamais en euros. "
            "Un montant par personne est un montant, pas un taux."
        )
    return controle


def replis_de_derniere_tentative(payload: Any, faits: Mapping[str, Fait]) -> Any:
    """Niveau 3 : retire les phrases qui portent encore un repère inconnu.

    Une phrase dont le chiffre n'existe pas ne peut pas partir avec un trou ni
    avec `{{…}}` imprimé : on la retire. Le reste du chapitre est gardé — c'est
    la garantie qu'un chapitre est toujours validé.
    """

    def _nettoyer(texte: str) -> str:
        if not REPERE.search(texte):
            return texte
        gardees = []
        for phrase in _PHRASE.findall(texte):
            inconnus = [i for i in REPERE.findall(phrase) if i not in faits]
            if not inconnus:
                gardees.append(phrase)
        return "".join(gardees).strip()

    return _parcourir(payload, _nettoyer)
