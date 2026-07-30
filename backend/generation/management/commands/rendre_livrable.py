"""Rend le livrable Word d'un job réel, sans écrire en base (lot 3).

Aucun appel API : le socle et les chapitres sont lus tels qu'ils sont en base.
C'est l'outil de relecture — il montre ce que le client recevrait, et surtout
ce qui n'a PAS pu être rendu.

    python manage.py rendre_livrable <job_id>
    python manage.py rendre_livrable <job_id> --out out/relecture.docx
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from generation.models import GenerationJob
from generation.rendu_word.services import LivrableIncompletError, produire_docx

RACINE = Path(__file__).resolve().parents[4]


class Command(BaseCommand):
    help = "Rend le livrable Word d'un job existant, sans toucher aux artefacts."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("job_id")
        parser.add_argument("--out", default="")

    def handle(self, *args: Any, **options: Any) -> None:
        job = GenerationJob.objects.filter(id=options["job_id"]).first()
        if job is None:
            msg = f"Job introuvable : {options['job_id']}"
            raise CommandError(msg)

        destination = (
            RACINE / str(options["out"]) if options["out"]
            else RACINE / "out" / f"livrable-{job.id}.docx"
        )
        try:
            livrable = produire_docx(job, destination=destination)
        except LivrableIncompletError as erreur:
            raise CommandError(str(erreur)) from erreur

        rapport = livrable.rapport
        poids = livrable.chemin.stat().st_size / 1024
        self.stdout.write(
            self.style.SUCCESS(f"Livrable : {livrable.chemin} ({poids:.0f} ko)")
        )
        self.stdout.write(rapport.resume())

        for conversion in rapport.graphiques_convertis:
            self.stdout.write(self.style.WARNING(f"  converti — {conversion}"))
        for abandon in rapport.graphiques_abandonnes:
            self.stdout.write(self.style.ERROR(f"  abandonné — {abandon}"))
        if rapport.complet:
            self.stdout.write(self.style.SUCCESS("Aucun visuel abandonné."))
