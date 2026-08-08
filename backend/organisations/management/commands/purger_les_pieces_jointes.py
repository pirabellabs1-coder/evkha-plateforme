"""Purge les documents déposés par les clients — ou dit seulement ce qu'elle ferait.

    python manage.py purger_les_pieces_jointes --simulation   # ne touche à rien
    python manage.py purger_les_pieces_jointes                # supprime

La purge tourne toutes les heures via Celery beat
(`organisations.purger_les_pieces_jointes`). Cette commande existe pour le
moment où on la met en service : lire ce que la PREMIÈRE exécution emportera,
sur la vraie base, avant de la laisser mordre.

C'est la règle 7. Les tests de ce lot tournent sur des doublures et sur SQLite ;
ils ne disent rien du volume de production, où les fichiers sont les bilans de
clients de nos abonnés et où la suppression ne se rattrape pas. Le seul contrôle
qui vaille est un relevé sur les vraies données.

`--simulation` est un mode d'affichage, pas un mode d'exécution : il emprunte la
même requête que la purge (`purge._expirees`). Un essai qui sélectionnerait
autrement rassurerait sur un ensemble différent de celui qu'on supprime ensuite.
"""
from __future__ import annotations

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from organisations.purge import purger_les_pieces_jointes


class Command(BaseCommand):
    help = (
        "Supprime les pièces jointes déposées arrivées à échéance. "
        "Avec --simulation, n'efface rien et affiche ce qui partirait."
    )

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--simulation",
            action="store_true",
            help="Ne supprime rien : compte et énumère seulement.",
        )
        parser.add_argument(
            "--detail",
            action="store_true",
            help="Énumère chaque fichier. Implicite avec --simulation.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        simulation: bool = options["simulation"]
        detail: bool = options["detail"] or simulation

        rapport = purger_les_pieces_jointes(simulation=simulation)

        if simulation:
            self.stdout.write(
                self.style.WARNING("SIMULATION — ni la base ni le disque ne sont touchés.")
            )

        # Zéro se DIT. Une commande muette laisse croire qu'elle a échoué, ou
        # qu'elle n'a pas tourné — et c'est ce silence qui a permis à Gamma de
        # ne jamais s'exécuter pendant des semaines (règle 8).
        if not rapport.compte:
            self.stdout.write(
                f"Aucun document déposé n'a atteint son échéance "
                f"(dépôts antérieurs au {rapport.echeance:%Y-%m-%d}). Rien à faire."
            )
            return

        if detail:
            for depot in rapport.depots:
                self.stdout.write(f"  {depot}")

        self.stdout.write(self.style.SUCCESS(rapport.resume()))

        if rapport.fichiers_deja_absents:
            # Dit, jamais tu : ces lignes sont le reste d'une suppression qui
            # n'avait pas libéré le volume, ou d'un volume recréé. Les taire
            # ferait passer un écart pour un état normal (règle 1).
            self.stdout.write(
                self.style.WARNING(
                    "Des fichiers manquaient déjà sur le volume : la ligne part, "
                    "l'espace annoncé ne sera pas rendu."
                )
            )
