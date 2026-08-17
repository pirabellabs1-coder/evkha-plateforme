"""python manage.py verifier_gate <job_id> [--json]

Rejoue le gate de livraison (Brique 3) sur un job DÉJÀ généré, en LECTURE
SEULE : aucune régénération, aucun appel IA, aucun email, aucune écriture en
base. Sert à la QC d'Evangeline pour recontrôler n'importe quel dossier
(passé, échoué, bloqué) sans brûler de budget API.

Sortie : le verdict global (LIVRABLE / BLOQUÉ) puis le détail de chaque
échec (check, chapitre, raison). Code de sortie 0 si le gate passe, 1 sinon
— utilisable dans un script.

Exemples :
    python manage.py verifier_gate 3f2c...            # rapport lisible
    python manage.py verifier_gate 3f2c... --json     # rapport machine
"""
from __future__ import annotations

import json
from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from generation.gate import run_delivery_gate
from generation.models import GenerationJob


class Command(BaseCommand):
    help = "Rejoue le gate de livraison sur un job existant (lecture seule)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("job_id", type=str, help="UUID du GenerationJob à vérifier.")
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Sortie JSON brute (pour scripts).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        job_id = options["job_id"]
        try:
            job = GenerationJob.objects.select_related("order").get(id=job_id)
        except GenerationJob.DoesNotExist as exc:
            raise CommandError(f"Aucun job avec l'id {job_id!r}.") from exc
        except (ValueError, ValidationError) as exc:  # id UUID mal formé
            raise CommandError(f"Id de job invalide : {job_id!r}.") from exc

        report = run_delivery_gate(job)

        if options["as_json"]:
            payload = {
                "job_id": str(job.id),
                "deliverable_type": job.deliverable_type,
                "qa_status": job.qa_status,
                **report.as_details(),
            }
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            if not report.passed:
                raise SystemExit(1)
            return

        self.stdout.write("")
        self.stdout.write(f"Job        : {job.id}")
        self.stdout.write(f"Livrable   : {job.deliverable_type}")
        self.stdout.write(f"qa_status  : {job.qa_status}")
        self.stdout.write("")

        if report.passed:
            self.stdout.write(self.style.SUCCESS("GATE OK — le document peut être livré."))
            return

        self.stdout.write(
            self.style.ERROR(
                f"GATE BLOQUÉ — {len(report.failures)} problème(s). "
                "Le document NE DOIT PAS partir en l'état."
            )
        )
        self.stdout.write("")
        # Regroupe par type de check pour une lecture QC rapide.
        by_check: dict[str, list[str]] = {}
        for failure in report.failures:
            chap = f"ch. {failure.chapter_number}" if failure.chapter_number is not None else "—"
            by_check.setdefault(failure.check, []).append(f"[{chap}] {failure.detail}")

        labels = {
            "contamination": "Contamination pipeline (token interne dans le texte)",
            "coherence_chiffree": "Incohérence chiffrée vs brief client",
            "reference_client_illisible": (
                "Le brief ne donne aucun montant : rien à comparer (action "
                "humaine, pas une réécriture)"
            ),
            "verticales": "Verticale d'activité manquante",
            "troncature": "Chapitre tronqué / incomplet",
        }
        for check, items in by_check.items():
            self.stdout.write(self.style.WARNING(f"• {labels.get(check, check)} ({len(items)}) :"))
            for item in items:
                self.stdout.write(f"    - {item}")
            self.stdout.write("")

        raise SystemExit(1)
