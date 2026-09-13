"""Les trois nombres qui disent si l'entraînement des prompts a servi.

    python manage.py mesurer_livrable <job_id>
    python manage.py mesurer_livrable <job_id> <job_id> ...

Le comptage lui-même vit dans `generation/mesure.py`, partagé avec la vue du
tableau de bord : les dossiers du client sont en production, et une mesure
qu'on ne peut prendre que sur sa propre machine ne sert à rien. Deux compteurs
qui ne s'accorderaient pas seraient pires qu'un seul (règle 5).

Cette commande n'ajoute que l'affichage — et le droit de désigner un dossier
par son préfixe.
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from generation.console import console_en_utf8
from generation.mesure import Mesure, mesurer
from generation.models import GenerationJob


def _resoudre(reference: str) -> GenerationJob:
    """Un dossier par son UUID complet — ou par son PRÉFIXE.

    On ne lit jamais un dossier autrement que par ses huit premiers caractères
    (journaux, écrans, incidents, conversations). Exiger l'UUID entier ferait
    de cette commande un outil qu'on n'ouvre pas.

    Un préfixe ambigu est une erreur, pas un choix silencieux : rendre la
    mesure du mauvais dossier serait pire que ne rien rendre (règle 2).
    """
    candidats = list(GenerationJob.objects.filter(id__startswith=reference)[:5])
    if len(candidats) == 1:
        return candidats[0]
    if not candidats:
        raise CommandError(f"Dossier introuvable : {reference}")
    trouves = ", ".join(str(j.id)[:12] for j in candidats)
    raise CommandError(f"Préfixe ambigu « {reference} » : {trouves}")


class Command(BaseCommand):
    help = "Compte figures, sources sans adresse et chiffres hors socle d'un livrable."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("job_ids", nargs="+")

    def handle(self, *args: Any, **options: Any) -> None:
        console_en_utf8()
        for job_id in options["job_ids"]:
            job = _resoudre(job_id)
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n═══ {str(job.id)[:8]} — {job.deliverable_type}"
            ))
            self._afficher(mesurer(job))

    def _afficher(self, mesure: Mesure) -> None:
        if mesure.echec:
            # Ne pas pouvoir rendre EST la mesure : on le dit, on ne rend pas
            # des zéros qui passeraient pour un document parfait.
            self.stdout.write(self.style.ERROR(f"  rendu impossible : {mesure.echec}"))
            return

        part = mesure.part_des_figures
        self.stdout.write(
            f"  FIGURES   {mesure.figures_obtenues}/{mesure.figures_demandees} "
            f"demandées par le modèle et obtenues "
            f"({'—' if part is None else f'{part} %'}) · "
            f"{mesure.figures_completees} ajoutées par complétion · "
            f"{mesure.figures_reparees} réparées · "
            f"{mesure.figures_en_tableau} repliées en tableau · "
            f"{mesure.figures_perdues} perdues"
        )

        sources = mesure.sources
        if sources is None:
            self.stdout.write(self.style.WARNING(
                "  SOURCES   chapitre Sources INTROUVABLE — rien à mesurer"
            ))
        else:
            self.stdout.write(
                f"  SOURCES   {sources.exterieures} extérieures dont "
                f"{sources.sans_adresse} SANS adresse utilisable · "
                f"{sources.du_client} venant du client"
            )
        self.stdout.write(
            f"            {mesure.adresses_collectees} adresse(s) rapportée(s) "
            "par la recherche web — ce que le modèle pouvait citer"
        )

        self.stdout.write(f"  CHIFFRES  {len(mesure.chiffres_hors_socle)} hors socle")
        for detail in mesure.chiffres_hors_socle[:5]:
            self.stdout.write(f"            · {detail[:110]}")
        self.stdout.write(f"  RESTE     {mesure.autres_anomalies} autres anomalies relevées")
