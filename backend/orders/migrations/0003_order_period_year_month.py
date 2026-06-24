from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_order_parent_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="period_year_month",
            field=models.CharField(blank=True, db_index=True, max_length=7),
        ),
    ]
