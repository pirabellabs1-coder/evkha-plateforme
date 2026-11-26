"""Double consentement : un jeton par contact, et la demande en attente.

Le jeton est posé en trois temps. Un `AddField` unique avec `default=uuid4`
calcule le défaut UNE fois pour toutes les lignes existantes : deux contacts
déjà en base recevraient le même jeton, et la contrainte d'unicité ferait
échouer la migration en production.
"""
import uuid

from django.db import migrations, models


def _poser_les_jetons(apps, schema_editor):  # type: ignore[no-untyped-def]
    Contact = apps.get_model("audience", "Contact")
    for contact in Contact.objects.filter(jeton__isnull=True).iterator():
        contact.jeton = uuid.uuid4()
        contact.save(update_fields=["jeton"])


class Migration(migrations.Migration):
    dependencies = [
        ("audience", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="contact",
            name="jeton",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(_poser_les_jetons, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="contact",
            name="jeton",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="contact",
            name="confirmation_demandee_le",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contact",
            name="confirmation_envoyee_le",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contact",
            name="confirmations_sans_reponse",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
