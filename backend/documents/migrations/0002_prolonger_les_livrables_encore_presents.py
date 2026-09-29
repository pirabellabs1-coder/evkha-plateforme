"""Les livrables encore présents sur le disque prennent la conservation de douze mois.

Leur échéance a été inscrite à la production, à sept jours. Sans ce passage,
la purge horaire aurait supprimé dans la semaine des documents que la nouvelle
règle garde un an. On ne fait que PROLONGER : une échéance déjà plus lointaine
reste la sienne. Les fichiers déjà supprimés ne reviennent pas — ils n'existent
plus sur le disque.

Les liens de l'espace client sont signés à chaque lecture pour le temps qui
reste au fichier (`organisations.suivi._lien_frais`) : prolonger l'échéance
suffit à les rendre valables.
"""

from datetime import timedelta

from django.db import migrations

#: Figé ici, comme toute valeur de migration : la règle vit dans
#: `evkha/retention.py`, et une migration rejouée demain doit faire la même
#: chose qu'aujourd'hui.
DOUZE_MOIS = timedelta(days=365)


def prolonger(apps, schema_editor):
    DocumentArtifact = apps.get_model("documents", "DocumentArtifact")
    for artefact in DocumentArtifact.objects.filter(
        status="ready", expires_at__isnull=False
    ).only("id", "created_at", "expires_at"):
        echeance = artefact.created_at + DOUZE_MOIS
        if artefact.expires_at < echeance:
            DocumentArtifact.objects.filter(pk=artefact.pk).update(expires_at=echeance)


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(prolonger, migrations.RunPython.noop),
    ]
