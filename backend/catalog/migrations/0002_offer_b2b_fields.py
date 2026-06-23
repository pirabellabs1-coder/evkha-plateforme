from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="offer",
            name="deliverable_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("market_study", "Etude de marche"),
                    ("competitor_study", "Etude de concurrence"),
                    ("business_plan", "Business plan"),
                    ("business_strategy", "Strategie business"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="offer",
            name="credits_per_month",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="offer",
            name="is_subscription",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="offer",
            name="is_extra_credit",
            field=models.BooleanField(default=False),
        ),
    ]
