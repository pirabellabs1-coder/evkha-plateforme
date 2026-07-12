from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_offer_b2b_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="offer",
            name="systeme_product_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
