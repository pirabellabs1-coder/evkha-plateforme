"""Exporte les prompts du code Python vers des fichiers versionnés.

Migration mécanique et réversible : le contenu de `prompt_library.py` est
recopié VERBATIM dans `prompts/<document>/chapitre_NN.md`, avec un en-tête
documentant l'origine et les variables disponibles.

À exécuter une fois, puis à versionner. Ensuite, les prompts se modifient
dans les fichiers, plus dans le code.

    python manage.py exporter_prompts             # écrit les fichiers
    python manage.py exporter_prompts --verifier  # contrôle sans rien écrire
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from generation.chapitres.configuration import types_declares
from generation.chapitres.fichiers_prompts import nom_fichier
from generation.prompt_library import prompt_instruction

_EN_TETE = """<!--
Prompt du chapitre {numero} — {libelle}
Clé historique : {cle}

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{{{ nom }}}}) :
  {{{{ secteur }}}}   {{{{ pays }}}}   {{{{ zone }}}}   {{{{ projet }}}}
  {{{{ titre_chapitre }}}}   {{{{ numero_chapitre }}}}   {{{{ cible_mots }}}}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

"""


class Command(BaseCommand):
    help = "Exporte les prompts du code vers prompts/<document>/chapitre_NN.md"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--verifier",
            action="store_true",
            help="N'écrit rien ; signale les fichiers manquants ou divergents.",
        )
        parser.add_argument(
            "--document",
            default="",
            help="Limite l'export à un code de document (ex. market_study).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        verifier: bool = options["verifier"]
        filtre: str = options["document"]

        ecrits = 0
        divergents: list[str] = []
        manquants: list[str] = []

        for document in types_declares():
            if filtre and document.code != filtre:
                continue

            dossier = document.chemin_prompts
            if not verifier:
                dossier.mkdir(parents=True, exist_ok=True)

            for blueprint in document.chapitres():
                corps = prompt_instruction(blueprint.prompt_key)
                contenu = _EN_TETE.format(
                    numero=blueprint.number,
                    libelle=blueprint.title,
                    cle=blueprint.prompt_key,
                ) + corps.rstrip() + "\n"

                fichier = dossier / nom_fichier(blueprint.number)

                if verifier:
                    if not fichier.is_file():
                        manquants.append(str(fichier))
                    elif fichier.read_text(encoding="utf-8") != contenu:
                        divergents.append(str(fichier))
                    continue

                fichier.write_text(contenu, encoding="utf-8")
                ecrits += 1

        if verifier:
            for chemin in manquants:
                self.stdout.write(self.style.ERROR(f"manquant  : {chemin}"))
            for chemin in divergents:
                self.stdout.write(self.style.WARNING(f"divergent : {chemin}"))
            if manquants:
                msg = f"{len(manquants)} prompt(s) manquant(s)."
                raise CommandError(msg)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Tous les prompts sont présents. {len(divergents)} divergence(s) "
                    "— normal si un prompt a été édité dans son fichier."
                )
            )
            return

        self.stdout.write(self.style.SUCCESS(f"{ecrits} prompt(s) exporté(s)."))
