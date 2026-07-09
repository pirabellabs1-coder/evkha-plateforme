from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("generation", "0007_generationjob_qa_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="generationjob",
            name="phase0_plan",
            field=models.TextField(blank=True),
        ),
    ]
