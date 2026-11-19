"""Les commandes dont le dossier existe déjà quittent « en attente de formulaire ».

Audit du 19/11/2026. Cinquante et une commandes de production affichaient cet
état avec un document produit : des reprises et des saisies manuelles de la
console, créées « en attente » puis mises en génération dans la même requête.
Seule la livraison faisait avancer l'état, et une reprise « sans envoi » ne
livre jamais.

`generation.services._sortir_la_commande_de_l_attente` corrige désormais le
défaut à la création du dossier. Cette migration remet d'accord les commandes
DÉJÀ là — sans elle, le compteur du tableau de bord continuerait de dire que
cinquante et une personnes n'ont pas rempli leur questionnaire.

Une seule mise à jour, conditionnelle : seules les commandes encore « reçue »
ou « en attente » ET qui portent un dossier changent. Une commande livrée,
échouée ou annulée garde son état. Rejouable sans effet. Le retour arrière ne
fait rien : l'état d'avant était faux, il n'y a rien à rétablir.

Les états sont écrits en clair, à dessein : une migration fige le jour où elle
a été écrite et ne dépend pas du code vivant.
"""
from django.db import migrations


def sortir_de_l_attente(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    GenerationJob = apps.get_model("generation", "GenerationJob")
    Order.objects.filter(
        status__in=("received", "waiting_intake"),
        pk__in=GenerationJob.objects.values("order_id"),
    ).update(status="processing")


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_projets_par_client"),
        ("generation", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sortir_de_l_attente, migrations.RunPython.noop),
    ]
