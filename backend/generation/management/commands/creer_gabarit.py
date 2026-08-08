"""Fabrique le gabarit Word à partir de la mise en page du document de référence.

À exécuter UNE fois, puis à versionner. Ensuite le gabarit se modifie dans
Word, plus par le code : « le code remplit le gabarit, il ne le recrée pas ».
Relancer cette commande écrase donc les retouches faites dans Word — elle
refuse de le faire sans `--ecraser`.

Ce que le gabarit porte : la mise en page, les styles nommés, l'en-tête et le
pied de page. Ce qu'il ne porte PAS : les couleurs du client, appliquées à la
génération (cf. `generation/rendu_word/palette.py`), puisqu'elles changent à
chaque étude.

Mesures reprises de « Etude_de_marche_Joalie_EVKHA_2026_v4.docx » :
A4, marges 2 cm sauf 1,7 cm en bas, en-tête à 0,7 cm, corps Aptos 10 pt,
titres Georgia 18 pt, sous-titres Aptos 13 pt.

    python manage.py creer_gabarit
    python manage.py creer_gabarit --ecraser
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from generation.rendu_word.gabarit import CHEMIN_GABARITS, construire_gabarit


class Command(BaseCommand):
    help = "Génère le gabarit Word des livrables (structure et styles nommés)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--ecraser",
            action="store_true",
            help="Écrase un gabarit existant, y compris s'il a été retouché dans Word.",
        )
        parser.add_argument(
            "--nom",
            default="livrable_evkha.docx",
            help="Nom du fichier produit dans gabarits/.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        destination = CHEMIN_GABARITS / str(options["nom"])

        if destination.exists() and not options["ecraser"]:
            msg = (
                f"{destination} existe déjà. Le régénérer écraserait les "
                "retouches faites dans Word. Utiliser --ecraser pour forcer."
            )
            raise CommandError(msg)

        chemin = construire_gabarit(destination)
        self.stdout.write(self.style.SUCCESS(f"Gabarit écrit : {chemin}"))
        self.stdout.write(
            "Il est maintenant modifiable dans Word : polices, tailles, marges, "
            "en-tête et pied de page. Les couleurs, elles, viennent du formulaire client."
        )
