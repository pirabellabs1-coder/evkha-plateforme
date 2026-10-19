"""Ajoute le jeton de désinscription public à Prospect.

Un défaut appelable sur un champ unique n'attribue qu'UNE valeur à toutes les
lignes existantes — donc une collision dès qu'il y en a plus d'une. On procède
en trois temps (patron documenté Django) pour que la migration tienne aussi
sur une base déjà peuplée, pas seulement sur une base vierge :
ajout sans contrainte → une valeur distincte par ligne → passage en unique.
"""
from __future__ import annotations

import uuid

from django.db import migrations, models


def _attribuer_les_jetons(apps, schema_editor):
    Prospect = apps.get_model("prospection", "Prospect")
    for prospect in Prospect.objects.all().iterator():
        prospect.jeton_desinscription = uuid.uuid4()
        prospect.save(update_fields=["jeton_desinscription"])


class Migration(migrations.Migration):

    dependencies = [
        ("prospection", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="prospect",
            name="jeton_desinscription",
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(_attribuer_les_jetons, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="prospect",
            name="jeton_desinscription",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
