"""Relit un PDF rendu avec les contrôles de relecture, et dit ce qu'ils trouvent.

    python manage.py relire_un_pdf tests/fixtures/eclore_v2.pdf \\
        --reference tests/fixtures/eclore_v2_reference.json \\
        --attendus tests/fixtures/eclore_v2_attendus.json

Sans `--attendus`, liste les constats ; avec, imprime le rapport de régression
« détectées / attendues ». Lecture seule : rien n'est écrit, aucun appel au
modèle.
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from generation.relecture import Reference, document_du_pdf, relire
from generation.relecture.regression import (
    charger_la_reference,
    charger_les_attendus,
    evaluer,
    rapport,
)


class Command(BaseCommand):
    help = "Relit un PDF rendu avec les contrôles de relecture (lecture seule)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("pdf")
        parser.add_argument("--reference", default="")
        parser.add_argument("--attendus", default="")

    def handle(self, *args: Any, **options: Any) -> None:
        reference = (
            charger_la_reference(options["reference"]) if options["reference"]
            else Reference(document_entier=True)
        )
        constats = relire(document_du_pdf(options["pdf"]), reference)
        if options["attendus"]:
            resultats = evaluer(constats, charger_les_attendus(options["attendus"]))
            self.stdout.write(rapport(resultats, constats))
            return
        for constat in constats:
            self.stdout.write(constat.motif())
        self.stdout.write(f"\n{len(constats)} constat(s).")
