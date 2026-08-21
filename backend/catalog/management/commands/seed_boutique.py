"""python manage.py seed_boutique

Cree les neuf etudes du catalogue `evkha.fr/etude-achat-immediat`, avec leur
titre et leur prix, PRETES A RECEVOIR LEUR FICHIER.

Elles sont creees HORS LIGNE, et c'est le point : un produit sans fichier
encaisserait sans rien remettre. La cliente depose le document depuis
l'administration, puis met l'etude en ligne — le controle vit dans
`ProduitBoutique.est_publiable`, et le refus nomme ce qui manque.

Relancer la commande ne touche pas aux produits deja crees : elle ne remplit
que les fiches absentes.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from catalog.models import ProduitBoutique

#: (slug, titre, theme). Le prix est commun — 89 EUR — et modifiable ensuite
#: produit par produit depuis l'administration.
ETUDES: list[tuple[str, str, str]] = [
    ("marche-chatbot-2026", "Le marché des chatbots en 2026", "Tech"),
    ("marche-foodtrucks-2026", "Le marché des foodtrucks en 2026", "Restauration"),
    (
        "marche-agences-nettoyage-2026",
        "Le marché des agences de nettoyage en 2026",
        "Services",
    ),
    (
        "marche-conciergeries-airbnb-2026",
        "Le marché des conciergeries Airbnb en 2026",
        "Services",
    ),
    (
        "marche-services-domicile-2026",
        "Le marché des services à domicile en 2026",
        "Services",
    ),
    ("marche-micro-creches-2026", "Le marché des micro-crèches en 2026", "Petite enfance"),
    (
        "marche-bien-etre-2026",
        "Le marché des centres de bien-être et du bien-vieillir en 2026",
        "Bien-être",
    ),
    (
        "marche-ecommerce-animaux-2026",
        "Le marché du e-commerce pour animaux en 2026",
        "Commerce",
    ),
    (
        "entreprises-moins-5000-euros-2026",
        "20 entreprises à créer avec moins de 5 000 € en 2026",
        "Création",
    ),
]

PRIX_CENTS = 8900


class Command(BaseCommand):
    help = "Cree les fiches des etudes du catalogue, hors ligne."

    def handle(self, *args: object, **options: object) -> None:
        creees = existantes = 0

        for rang, (slug, titre, theme) in enumerate(ETUDES):
            _, cree = ProduitBoutique.objects.get_or_create(
                slug=slug,
                defaults={
                    "titre": titre,
                    "theme": theme,
                    "prix_cents": PRIX_CENTS,
                    "rang": rang,
                    # HORS LIGNE tant que le fichier n'est pas depose : la
                    # fiche existe, la vente non.
                    "en_ligne": False,
                },
            )
            if cree:
                creees += 1
                self.stdout.write(self.style.SUCCESS(f"  [CRÉÉ]  {slug}"))
            else:
                existantes += 1
                self.stdout.write(f"  [OK]    {slug}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{creees} fiches créées, {existantes} déjà présentes.\n"
                "Déposez le fichier de chaque étude depuis l'administration, "
                "puis mettez-la en ligne."
            )
        )
