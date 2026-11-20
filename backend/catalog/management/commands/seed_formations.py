"""python manage.py seed_formations

Crée les fiches des trois formations vendues sur le site, avec leur titre, leur
prix et leur durée.

SANS lien d'achat : les pages de paiement de l'ancien site, que ce tableau
recopiait, n'existent plus. Une formation se paie par Stripe sur la plateforme
(décision de la cliente du 20/11/2026), et une fiche qui porterait encore
l'ancienne adresse enverrait l'acheteur sur une page morte.

Elles sont créées HORS LIGNE : c'est la cliente qui les publie, après les avoir
relues depuis l'administration.

Elles sont créées SANS MODULE, et ce n'est pas un oubli : la liste des modules
n'existe nulle part ailleurs que dans l'outil externe où les formations sont
hébergées. En inventer une ici publierait un programme que personne n'a écrit.
La cliente la saisit.

Relancer la commande ne modifie JAMAIS une formation existante — ni son prix,
ni son titre, ni son état : elle ne crée que les fiches absentes, et dit
lesquelles elle a créées et lesquelles elle a laissées.
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from catalog import formations as regles
from catalog.models import Formation

#: slug, titre, prix en centimes, heures de cours, heures de coaching. Valeurs
#: relevées sur le site au 19/11/2026 ; une fois la fiche créée, c'est
#: l'administration qui fait foi, plus ce tableau.
FORMATIONS: list[tuple[str, str, int, int, int]] = [
    (
        "creer-son-entreprise",
        "Créer son entreprise de A à Z",
        149_000,
        18,
        2,
    ),
    (
        "creer-sa-micro-entreprise",
        "Créer sa micro-entreprise de A à Z",
        149_000,
        18,
        2,
    ),
    (
        "methode-pop",
        "Méthode P.O.P",
        85_000,
        7,
        0,
    ),
]


class Command(BaseCommand):
    help = "Crée les fiches des trois formations, hors ligne et sans module."

    def handle(self, *args: Any, **options: Any) -> None:
        creees: list[str] = []
        laissees: list[str] = []

        for rang, (slug, titre, prix, heures, coaching) in enumerate(FORMATIONS):
            if Formation.objects.filter(slug=slug).exists():
                laissees.append(slug)
                self.stdout.write(f"  [LAISSÉE]  {slug}")
                continue

            formation = Formation(
                slug=slug,
                titre=titre,
                prix_cents=prix,
                duree_heures=heures,
                heures_de_coaching=coaching,
                rang=rang,
                en_ligne=False,
            )
            # Les mêmes règles que l'administration : ce tableau n'a aucun
            # passe-droit, et une valeur mal recopiée échoue ICI plutôt que
            # sur la page publique.
            regles.verifier_formation(formation)
            formation.save()
            creees.append(slug)
            self.stdout.write(self.style.SUCCESS(f"  [CRÉÉE]    {slug}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{len(creees)} formation(s) créée(s), {len(laissees)} déjà "
                "présente(s) et laissée(s) telle(s) quelle(s).\n"
                "Saisissez les modules et leurs leçons depuis l'administration, "
                "puis mettez chaque formation en ligne après relecture."
            )
        )
