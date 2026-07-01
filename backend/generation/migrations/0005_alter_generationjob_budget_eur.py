from __future__ import annotations

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("generation", "0004_backfill_str_sources_prompt_key"),
    ]

    operations = [
        migrations.AlterField(
            model_name="generationjob",
            name="budget_eur",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("5.0000"),
                max_digits=8,
            ),
        ),
    ]
