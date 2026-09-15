"""Le chapitre des sources exige l'adresse de chaque source extérieure.

## Le défaut mesuré

Génération test du 15/09/2026, stratégie `cd639627` (reprise de `f8a29b66`) :
la recherche avait collecté 35 adresses, et le chapitre « Sources et
méthodologie » a listé sept sources extérieures sans une seule adresse —
« Institut Leges, taille du marché français de la legaltech, 2026 ». Le gate :
« 0 URL vérifiable pour 7 sources extérieures ». Le business plan de preuve du
même jour, sous la MÊME consigne, avait gardé ses adresses.

La consigne des trois livrables disait « Nom - URL si disponible » : elle
laissait l'adresse au choix du rédacteur, et le contrôle, lui, l'exige.

## Pourquoi un test de classe

Il lit TOUS les fichiers de prompt d'un chapitre de sources, tels qu'ils
partent : un livrable ajouté, ou une consigne réécrite, est vérifié sans que
personne y pense (règle 4).
"""
from __future__ import annotations

from generation.chapitres.configuration import RACINE_PROMPTS
from generation.chapitres.fichiers_prompts import _BANDEAU


def _prompts_des_sources() -> dict[str, str]:
    fichiers = {
        f"{f.parent.name}/{f.name}": f.read_text(encoding="utf-8")
        for f in sorted(RACINE_PROMPTS.rglob("chapitre_*.md"))
    }
    sources = {
        nom: _BANDEAU.sub("", texte)
        for nom, texte in fichiers.items()
        if "Sources et méthodologie" in texte.split("-->", 1)[0]
    }
    assert len(sources) >= 4, f"chapitres de sources introuvables : {sorted(sources)}"
    return sources


def test_aucune_consigne_de_sources_ne_rend_l_adresse_facultative() -> None:
    fautes = {
        nom: texte for nom, texte in _prompts_des_sources().items() if "si disponible" in texte
    }
    assert fautes == {}


def test_la_consigne_des_livrables_courts_exige_l_adresse_recopiee() -> None:
    for nom, texte in _prompts_des_sources().items():
        if nom.startswith("etude_marche/"):
            continue  # le manuel porte sa propre exigence : « liens complets, fonctionnels »
        assert "adresse web, recopiée telle quelle" in texte, nom
        assert "ne figure PAS dans cette liste" in texte, nom
