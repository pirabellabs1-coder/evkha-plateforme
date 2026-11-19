"""Reprise : les oppositions DÉJÀ enregistrées entrent dans la table par adresse.

Audit du 19/11/2026. Jusqu'ici une désinscription ne vivait que sur la fiche
(`Prospect.consentement_retire`). La table `AdresseInterdite` (migration 0006)
naît vide : sans cette reprise, un cabinet désinscrit AVANT le déploiement
serait encore recréé contactable par la campagne suivante — le défaut même que
la table corrige, pour toutes les oppositions déjà reçues.

Strictement additive : on INSÈRE dans la table neuve, aucune fiche n'est
modifiée ni supprimée. Rejouable sans doublon (`ignore_conflicts` sur la clé
unique). Le retour arrière ne retire rien : une opposition ne s'oublie pas.

La normalisation est RECOPIÉE ici, à dessein : une migration fige l'état du
jour où elle a été écrite et ne doit pas dépendre du code vivant
(`models.normaliser_adresse`), qui peut changer après elle.
"""
from django.db import migrations
from django.db.models import Q


def _cle(adresse):
    return "".join(str(adresse or "").split()).lower()


def reprendre_les_oppositions(apps, schema_editor):
    Prospect = apps.get_model("prospection", "Prospect")
    AdresseInterdite = apps.get_model("prospection", "AdresseInterdite")
    opposes = (
        Prospect.objects.filter(Q(consentement_retire=True) | Q(statut="desinscrit"))
        .exclude(email="")
        .values_list("email", flat=True)
    )
    cles = {_cle(email) for email in opposes.iterator()} - {""}
    AdresseInterdite.objects.bulk_create(
        [AdresseInterdite(adresse=cle, motif="desinscription") for cle in sorted(cles)],
        ignore_conflicts=True,
    )

    # Les PLAINTES déjà reçues, elles aussi (relecture du 19/11/2026). Le
    # webhook les traçait depuis le début, sans aucun effet : la fiche restait
    # contactable et sa relance validée serait partie au prochain envoi. Une
    # plainte est une opposition, au même titre qu'une désinscription.
    #
    # L'adresse est celle de la fiche du message : aucune route ne permettait
    # de la corriger avant cette série de migrations, c'est donc bien celle où
    # le message est parti. Les rebonds d'avant ne sont PAS repris : rangés
    # sous un seul type, un retard de remise ne s'y distingue pas d'une adresse
    # morte, et interdire sur un doute fermerait des adresses valides.
    Evenement = apps.get_model("prospection", "Evenement")
    plaintes = (
        Evenement.objects.filter(type="plainte")
        .exclude(message__prospect__email="")
        .values_list("message__prospect__email", flat=True)
    )
    plaignants = {_cle(email) for email in plaintes.iterator()} - {""} - cles
    AdresseInterdite.objects.bulk_create(
        [AdresseInterdite(adresse=cle, motif="plainte") for cle in sorted(plaignants)],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("prospection", "0006_adresses_interdites_et_retards"),
    ]

    operations = [
        migrations.RunPython(reprendre_les_oppositions, migrations.RunPython.noop),
    ]
