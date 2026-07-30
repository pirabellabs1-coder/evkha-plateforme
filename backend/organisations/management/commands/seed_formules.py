"""Crée ou met à jour les formules d'abonnement EVKHA (lot 4).

Valeurs relevées sur https://www.evkha.fr/ (page « Partenariats PRO et
abonnements »). Elles sont ici pour amorcer une base vide, **pas** pour faire
autorité : le cahier des charges exige qu'une formule se crée et se modifie
depuis l'administration, sans déploiement. Une modification faite en admin ne
doit donc jamais être écrasée par cette commande — d'où `--forcer`, qui n'est
pas le comportement par défaut.

    python manage.py seed_formules
    python manage.py seed_formules --forcer   # réaligne sur les valeurs du site
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from organisations.models import Formule, ReportCredits

#: (code, libellé, cible commerciale, crédits/mois, prix mensuel en centimes,
#:  prix du crédit supplémentaire en centimes)
FORMULES: tuple[tuple[str, str, str, int, int, int], ...] = (
    ("solo", "Solo", "Coach · Freelance", 2, 12_900, 5_900),
    ("pro", "Pro", "Agence · Cabinet", 3, 18_900, 5_500),
    ("pro-plus", "Pro Plus", "Agence avec volume", 5, 24_900, 4_500),
    ("structure", "Structure", "Incubateur · Association · Réseau", 10, 42_900, 3_900),
)


class Command(BaseCommand):
    help = "Crée les quatre formules d'abonnement EVKHA."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--forcer",
            action="store_true",
            help=(
                "Réécrit les formules existantes. Sans ce drapeau, une formule "
                "déjà en base est laissée telle quelle : elle a pu être ajustée "
                "en administration, et l'écraser en silence effacerait ce "
                "réglage."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        forcer = bool(options["forcer"])
        crees, majs, laissees = 0, 0, 0

        for code, libelle, cible, credits_mois, prix, prix_credit in FORMULES:
            valeurs = {
                "libelle": libelle,
                "credits_par_echeance": credits_mois,
                "prix_mensuel_cents": prix,
                "devise": "EUR",
                # Décision de la cliente : les crédits non consommés ne se
                # reportent pas d'un mois sur l'autre.
                "report_credits": ReportCredits.AUCUN,
                "plafond_report": 0,
                "regenerations_offertes": 1,
                "active": True,
            }
            formule = Formule.objects.filter(code=code).first()
            if formule is None:
                Formule.objects.create(code=code, **valeurs)
                crees += 1
                etat = "créée"
            elif forcer:
                for champ, valeur in valeurs.items():
                    setattr(formule, champ, valeur)
                formule.save()
                majs += 1
                etat = "mise à jour"
            else:
                laissees += 1
                etat = "inchangée"

            euros = prix / 100
            par_livrable = euros / credits_mois
            self.stdout.write(
                f"{libelle:10} {cible:36} {credits_mois:2} crédits · "
                f"{euros:6.2f} €/mois · {par_livrable:5.2f} €/livrable · "
                f"crédit sup. {prix_credit / 100:5.2f} €  [{etat}]"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{crees} créée(s), {majs} mise(s) à jour, {laissees} inchangée(s)."
            )
        )
        if laissees and not forcer:
            self.stdout.write(
                "Utiliser --forcer pour réaligner les formules existantes sur "
                "les valeurs du site."
            )
