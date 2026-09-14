"""Un prompt ne fait pas écrire au modèle ce que le contrôle du méta-discours punit.

## Le défaut mesuré

Corpus du 14/09/2026 : deux stratégies (`f7f2fad9`, `f8a29b66`) portent au
chapitre 1 l'intertitre « CE QUE CE CHAPITRE CHANGE », que `meta_discours`
bloque au gate — le lecteur ne doit jamais apprendre qu'un texte a été rédigé
ou révisé. Le prompt de ce chapitre demandait : « Bloc court de recul : ce que
ce document change dans la façon de décider ». Le modèle a repris la tournure,
en remplaçant « document » par « chapitre ». La consigne ordonnait ce que le
contrôle refuse (règle 5).

## Pourquoi le test lit les contrôles eux-mêmes

Il applique `meta_discours.trouver` — la liste qui FAIT FOI — à chaque fiche,
après avoir remplacé « document » par « chapitre » : c'est exactement la
reformulation que le modèle a faite. Un motif ajouté au contrôle sera vérifié
ici sans que personne ait à y penser.
"""
from __future__ import annotations

import re
from pathlib import Path

from generation.meta_discours import trouver


def _fiches() -> list[Path]:
    from generation.chapitres.fichiers_prompts import rendre_prompt

    dossier = Path(rendre_prompt.__code__.co_filename).parents[3] / "prompts"
    return sorted(dossier.rglob("chapitre_*.md"))


def test_aucune_fiche_ne_dicte_une_tournure_de_meta_discours() -> None:
    fautives: list[str] = []
    for fiche in _fiches():
        corps = re.sub(r"<!--.*?-->", "", fiche.read_text(encoding="utf-8"), flags=re.DOTALL)
        for variante in (corps, re.sub(r"(?i)\bdocument\b", "chapitre", corps)):
            for extrait in trouver(variante):
                fautives.append(f"{fiche.parent.name}/{fiche.name} : « {extrait} »")
    assert sorted(set(fautives)) == []


def test_le_controle_reconnait_bien_la_tournure_du_corpus() -> None:
    """CONTRE-ÉPREUVE : le test n'est pas vert parce que `trouver` ne voit rien."""
    assert trouver("CE QUE CE CHAPITRE CHANGE")
