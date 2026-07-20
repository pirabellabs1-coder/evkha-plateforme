"""Active Gamma sur toutes les offres, existantes comprises.

Gamma est le moteur de mise en page privilegie du projet (cf.
`delivery/services.py:ensure_gamma_artifacts`, ou WeasyPrint n'est que le
repli). Mais `gamma_enabled` valait False par defaut depuis la migration
initiale, `seed_offers` ne le renseignait pas, et aucune migration ne l'a
jamais bascule. Consequence : Gamma n'a jamais tourne sur un seul dossier,
pas meme en production. Le code etait ecrit, teste, branche, et dormant.

Changer le defaut ne suffit pas : il ne s'applique qu'aux offres CREEES
ensuite. Les offres deja en base (les 8 du catalogue) resteraient a False et
continueraient a livrer du WeasyPrint. D'ou la mise a jour des lignes
existantes ci-dessous.
"""
from django.db import migrations, models


def activer_gamma(apps, schema_editor):
    Offer = apps.get_model("catalog", "Offer")
    Offer.objects.update(gamma_enabled=True)


def desactiver_gamma(apps, schema_editor):
    """Retour arriere : on remet le comportement d'avant (Gamma inactif)."""
    Offer = apps.get_model("catalog", "Offer")
    Offer.objects.update(gamma_enabled=False)


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0003_offer_systeme_product_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='offer',
            name='gamma_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(activer_gamma, desactiver_gamma),
    ]
