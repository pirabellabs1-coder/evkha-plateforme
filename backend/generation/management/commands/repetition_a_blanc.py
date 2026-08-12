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

import sys
from typing import Any

from django.core.management.base import BaseCommand

from catalog.models import DeliverableType
from generation.repetition import jouer_a_blanc


def _console_en_utf8() -> None:
    """La sortie de cette commande ne doit pas dépendre de la console.

    ## Le défaut mesuré

    12/08/2026 : lancée depuis un terminal Windows, la commande s'arrête sur
    `UnicodeEncodeError: 'charmap' codec can't encode characters` — sur la
    ligne de séparation `═══` et sur les accents de « passé ». Rien à voir
    avec la chaîne testée : c'est le rapport qui ne s'imprime pas, et la
    commande sort en erreur sans avoir rien dit.

    Cette commande est OBLIGATOIRE avant tout déploiement (CLAUDE.md). Une
    étape obligatoire qui plante sur la console standard finit par être
    contournée, puis oubliée — c'est exactement l'histoire de Gamma dans ce
    dépôt : intégré, testé, branché, et jamais exécuté.

    On reconfigure donc la sortie plutôt que d'appauvrir le rapport : un
    tableau lisible vaut mieux qu'un tableau qui passe partout.
    """
    for flux in (sys.stdout, sys.stderr):
        reconfigurer = getattr(flux, "reconfigure", None)
        if reconfigurer is not None:
            try:
                reconfigurer(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                # Flux capturé par un test ou redirigé : il n'y a rien à
                # reconfigurer, et ce n'est pas une raison d'échouer.
                pass


class Command(BaseCommand):
    help = "Joue la chaîne des 4 livrables sur la doublure et signale tout défaut interne."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--livrable",
            choices=list(DeliverableType.values),
            help="Un seul livrable au lieu des quatre.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        _console_en_utf8()
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
