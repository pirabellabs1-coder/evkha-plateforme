from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="company_name",
            field=models.CharField(blank=True, max_length=160),
            preserve_default=True,
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to="customers.customer",
                    ),
                ),
                (
                    "tier",
                    models.CharField(
                        choices=[
                            ("solo", "Solo"),
                            ("pro", "Pro"),
                            ("pro_plus", "Pro Plus"),
                            ("structure", "Structure"),
                        ],
                        default="solo",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Actif"),
                            ("cancelled", "Annule"),
                            ("expired", "Expire"),
                        ],
                        default="active",
                        max_length=12,
                    ),
                ),
                (
                    "systeme_subscription_id",
                    models.CharField(max_length=160, unique=True),
                ),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
