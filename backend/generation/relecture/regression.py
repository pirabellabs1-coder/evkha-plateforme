"""Régression sur un document réel : chaque erreur attendue doit être DÉTECTÉE.

30/09/2026 — le business plan ÉCLORE `28a257bf` sert de référence
(`tests/fixtures/eclore_v2.pdf`). Le PDF, la mémoire de référence et la liste
des erreurs attendues portent des données de cliente : ils ne sont JAMAIS
versionnés (`.gitignore` : `tests/fixtures/eclore_*`). Le test versionné se
saute proprement quand ils manquent ; la commande `relire_un_pdf` imprime le
rapport « détectées / attendues ».
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constat import Constat, Reference


@dataclass(frozen=True)
class Attendu:
    classe: str
    sections: tuple[str, ...]
    cherche: str
    exemple: str


@dataclass(frozen=True)
class Resultat:
    attendu: Attendu
    trouve: Constat | None


def charger_les_attendus(chemin: str | Path) -> list[Attendu]:
    return [
        Attendu(
            classe=a["classe"], sections=tuple(a["sections"]), cherche=a["cherche"],
            exemple=a.get("exemple", ""),
        )
        for a in json.loads(Path(chemin).read_text(encoding="utf-8"))
    ]


def charger_la_reference(chemin: str | Path) -> Reference:
    """La mémoire de l'étude reconstruite comme en production : socle, puis faits et décisions."""
    from ..memoire.etude import MemoireEtude  # noqa: PLC0415
    from ..socle.schema import Socle  # noqa: PLC0415

    brut: dict[str, Any] = json.loads(Path(chemin).read_text(encoding="utf-8"))
    socle = Socle.model_validate(brut["socle"])
    livrable = str(brut.get("livrable") or "")
    memoire = MemoireEtude.construire(socle, brut.get("variables") or {}, livrable)
    return Reference(memoire=memoire, livrable=livrable, document_entier=True)


def evaluer(constats: list[Constat], attendus: list[Attendu]) -> list[Resultat]:
    """Un attendu est détecté par un constat de sa classe, dans une de ses sections."""
    resultats: list[Resultat] = []
    for attendu in attendus:
        trouve = next(
            (
                c for c in constats
                if c.classe == attendu.classe and c.section in attendu.sections
                and re.search(attendu.cherche, f"{c.extrait} {c.detail}")
            ),
            None,
        )
        resultats.append(Resultat(attendu, trouve))
    return resultats


def rapport(resultats: list[Resultat], constats: list[Constat]) -> str:
    detectes = sum(1 for r in resultats if r.trouve)
    lignes = [
        f"RÉGRESSION — {detectes} erreurs détectées sur {len(resultats)} attendues",
        "",
    ]
    for r in resultats:
        etat = "DÉTECTÉ " if r.trouve else "MANQUÉ  "
        lignes.append(f"{etat} [{r.attendu.classe}] {r.attendu.exemple}")
        if r.trouve:
            lignes.append(f"          → {r.trouve.section} : {r.trouve.detail[:150]}")
    en_plus = [
        c for c in constats
        if not any(r.trouve is c for r in resultats)
    ]
    lignes += ["", f"Autres constats sur le document : {len(en_plus)}"]
    par_classe: dict[str, int] = {}
    for c in en_plus:
        par_classe[c.classe] = par_classe.get(c.classe, 0) + 1
    lignes += [f"  {classe} : {n}" for classe, n in sorted(par_classe.items())]
    return "\n".join(lignes)
