"""Rend un livrable de démonstration depuis une fixture JSON (lot 0).

Aucun appel API : le contenu vient du fichier. C'est l'outil de la boucle de
validation visuelle.

    python manage.py render_demo --fixture fixtures/etude_demo.json --out out/demo.docx
    python manage.py render_demo --creer-fixture   # (re)génère la fixture
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand

from generation.rendu_word.depuis_json import rendre_depuis_fichier
from generation.rendu_word.fixture import construire_fixture
from generation.rendu_word.secteurs import profil_du_secteur

RACINE = Path(__file__).resolve().parents[4]


class Command(BaseCommand):
    help = "Génère un livrable Word de démonstration depuis une fixture JSON."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--fixture", default="fixtures/etude_demo.json")
        parser.add_argument("--out", default="out/demo.docx")
        parser.add_argument(
            "--creer-fixture",
            action="store_true",
            help="(Re)génère la fixture avant le rendu.",
        )
        parser.add_argument("--chapitres", type=int, default=22)
        parser.add_argument(
            "--secteur",
            default="joaillerie",
            help=(
                "Secteur d'activité du client. Détermine les types de "
                "graphiques retenus (voir generation/rendu_word/secteurs.py)."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        fixture = RACINE / str(options["fixture"])
        sortie = RACINE / str(options["out"])

        if options["creer_fixture"] or not fixture.is_file():
            secteur = str(options["secteur"])
            etude = construire_fixture(
                nombre_chapitres=int(options["chapitres"]), secteur=secteur
            )
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_text(
                json.dumps(etude, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            blocs = sum(len(c["blocs"]) for c in etude["chapitres"])
            profil = profil_du_secteur(secteur)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Fixture écrite : {fixture} "
                    f"({len(etude['chapitres'])} chapitres, {blocs} blocs, "
                    f"profil « {profil.libelle} »)"
                )
            )

        chemin = rendre_depuis_fichier(fixture, sortie)
        poids = chemin.stat().st_size / 1024
        self.stdout.write(self.style.SUCCESS(f"Livrable écrit : {chemin} ({poids:.0f} ko)"))
