"""Conservation des livrables : douze mois (décision de l'utilisateur, 29/09/2026).

Les offres encore à l'ancienne valeur par défaut (7 jours) passent à 365. Une
offre réglée à la main sur une autre durée garde la sienne : c'est un choix
commercial, pas un reste.
"""

from django.db import migrations, models


def douze_mois(apps, schema_editor):
    Offer = apps.get_model("catalog", "Offer")
    Offer.objects.filter(retention_days=7).update(retention_days=365)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0011_remove_produitboutique_extrait_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="offer",
            name="retention_days",
            field=models.PositiveSmallIntegerField(default=365),
        ),
        migrations.RunPython(douze_mois, migrations.RunPython.noop),
    ]
