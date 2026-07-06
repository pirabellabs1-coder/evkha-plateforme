from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("generation", "0006_alter_generationjob_budget_eur"),
    ]

    operations = [
        migrations.AddField(
            model_name="generationjob",
            name="qa_status",
            field=models.CharField(
                choices=[
                    ("pending", "En attente"),
                    ("running", "En cours"),
                    ("passed", "Validé"),
                    ("failed", "Echec partiel"),
                ],
                default="pending",
                help_text="Statut de la passe QA post-génération (correction automatique des chapitres).",
                max_length=16,
            ),
        ),
    ]
