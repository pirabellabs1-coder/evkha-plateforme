from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    """Phase 7 — ajoute SYSTEME_SUB aux choices provider (commandes vs abonnements)."""

    dependencies = [
        ("integrations", "0003_alter_webhookevent_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="externalcredentialref",
            name="provider",
            field=models.CharField(
                choices=[
                    ("anthropic", "Anthropic Claude"),
                    ("google", "Google Docs / Drive"),
                    ("gamma", "Gamma"),
                    ("brevo", "Brevo"),
                    ("systeme", "Systeme.io (commandes)"),
                    ("systeme_sub", "Systeme.io (abonnements)"),
                    ("tally", "Tally"),
                    ("n8n", "n8n"),
                ],
                max_length=24,
            ),
        ),
        migrations.AlterField(
            model_name="webhookevent",
            name="provider",
            field=models.CharField(
                choices=[
                    ("anthropic", "Anthropic Claude"),
                    ("google", "Google Docs / Drive"),
                    ("gamma", "Gamma"),
                    ("brevo", "Brevo"),
                    ("systeme", "Systeme.io (commandes)"),
                    ("systeme_sub", "Systeme.io (abonnements)"),
                    ("tally", "Tally"),
                    ("n8n", "n8n"),
                ],
                max_length=24,
            ),
        ),
    ]
