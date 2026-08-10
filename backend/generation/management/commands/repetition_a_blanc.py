"""python manage.py repetition_a_blanc [--livrable TYPE]

Joue la chaîne entière — socle, chapitres, gate — sur la doublure, pour les
quatre livrables. Zéro appel d'API, zéro centime, zéro email.

Code de sortie 0 si aucun DÉFAUT INTERNE (chapitre refusé, chaîne
interrompue) ; 1 sinon. Les échecs de gate portant sur le contenu de la
doublure sont affichés pour information, pas comptés.

Obligatoire avant tout déploiement — voir CLAUDE.md. Trois des cinq défauts
payés le 10/08/2026 auraient été attrapés ici, gratuitement.
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from catalog.models import DeliverableType
from generation.repetition import jouer_a_blanc


class Command(BaseCommand):
    help = "Joue la chaîne des 4 livrables sur la doublure et signale tout défaut interne."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--livrable",
            choices=list(DeliverableType.values),
            help="Un seul livrable au lieu des quatre.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        livrables = (
            [options["livrable"]] if options["livrable"] else list(DeliverableType.values)
        )

        defauts = 0
        for livrable in livrables:
            rapport = jouer_a_blanc(livrable)
            etat = "SAIN" if rapport.saine else "DÉFAUT INTERNE"
            self.stdout.write(
                f"\n═══ {livrable} — {etat} — chapitres "
                f"{rapport.chapitres_ok}/{rapport.chapitres_total} — gate "
                f"{'passé' if rapport.gate_passe else 'bloqué'}"
            )
            for defaut in rapport.defauts_internes:
                defauts += 1
                self.stdout.write(self.style.ERROR(f"  INTERNE  {defaut}"))
            for echec in rapport.gate_echecs:
                self.stdout.write(f"  gate     {echec}")

        if defauts:
            self.stdout.write(self.style.ERROR(f"\n{defauts} défaut(s) interne(s)."))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("\nAucun défaut interne : la chaîne tient."))
