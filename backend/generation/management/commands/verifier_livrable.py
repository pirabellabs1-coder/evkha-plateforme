"""Passe de vérification sur un livrable déjà produit (lot 4).

Aucun appel API, aucune écriture en base par défaut : la commande lit le
fichier et dit ce qu'elle y voit.

    python manage.py verifier_livrable <job_id>
    python manage.py verifier_livrable <job_id> --fichier out/relecture.docx
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from generation.models import GenerationJob
from generation.verification.rapport import Gravite
from generation.verification.services import verifier_livrable

RACINE = Path(__file__).resolve().parents[4]

_STYLE = {
    Gravite.BLOQUANTE: "ERROR",
    Gravite.AVERTISSEMENT: "WARNING",
    Gravite.INFORMATION: "NOTICE",
}


class Command(BaseCommand):
    help = "Vérifie le livrable Word d'un job et affiche le rapport de contrôle."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("job_id")
        parser.add_argument(
            "--fichier", default="",
            help="Chemin du .docx à vérifier. Par défaut, celui du job dans MEDIA_ROOT.",
        )
        parser.add_argument(
            "--incident", action="store_true",
            help="Ouvre un incident si le livrable est bloqué (désactivé par défaut).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        job = GenerationJob.objects.filter(id=options["job_id"]).first()
        if job is None:
            msg = f"Job introuvable : {options['job_id']}"
            raise CommandError(msg)

        if options["fichier"]:
            chemin = RACINE / str(options["fichier"])
        else:
            from django.conf import settings  # noqa: PLC0415

            chemin = (
                Path(str(getattr(settings, "MEDIA_ROOT", "") or "media"))
                / "livrables" / f"{job.id}.docx"
            )

        try:
            rapport = verifier_livrable(
                job, chemin, ouvrir_incident=bool(options["incident"])
            )
        except FileNotFoundError as erreur:
            raise CommandError(str(erreur)) from erreur

        self.stdout.write(f"Fichier  : {chemin}")
        self.stdout.write(f"Mesures  : {rapport.mesures}")
        self.stdout.write(rapport.resume())

        for anomalie in rapport.anomalies:
            style = getattr(self.style, _STYLE[anomalie.gravite])
            self.stdout.write(
                style(f"  [{anomalie.gravite}] {anomalie.controle} — {anomalie.detail}")
            )
            if anomalie.extrait:
                self.stdout.write(f"        … {anomalie.extrait}")

        if rapport.livrable:
            self.stdout.write(self.style.SUCCESS("Livrable : OUI"))
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"Livrable : NON — {len(rapport.bloquantes)} anomalie(s) bloquante(s)."
                )
            )
