"""Remet droits les lots qui portent une heure d'envoi ET un statut d'échec.

## Le défaut, mesuré

Étude de concurrence `c7c6ba96`, 17/08/2026. L'e-mail part à 13:29:30 et
`sent_at` est écrit. Quatre-vingts secondes plus tard une seconde tentative de
livraison rejoue la vérification, échoue, et réécrit le lot en FAILED — sans
toucher à `sent_at`, qui n'est pas dans les `defaults` du chemin d'échec.

Le tableau de bord affiche donc « non envoyé » sur un dossier que la cliente a
reçu dans sa boîte. Un dossier qui ment sur son propre état est pire qu'un
dossier en échec : on ne sait plus lequel croire.

Le code ne peut plus produire cet état — le chemin d'échec vérifie désormais
qu'aucun lot SENT n'existe avant d'écrire FAILED. Restent les lignes déjà
écrites, qu'aucun correctif ne repasse.

## Pourquoi une migration, et pas une correction à la main

Une ligne corrigée à la main répare l'instance ; le dépôt a appris quatre fois
que c'est la CLASSE qu'il faut viser (règle 4). Tout lot horodaté et pourtant
en échec est dans le même cas, et il n'y a qu'une lecture possible : l'envoi a
eu lieu, `sent_at` en est la trace, et c'est le statut qui a été écrasé après
coup.

Aucun e-mail n'est envoyé. Cette migration ne fait que rendre à ces lignes
l'état qu'elles décrivent déjà.

## Le retour en arrière

Il n'y en a pas — `reverse` est un no-op assumé. Réécrire FAILED sur ces lots
recréerait exactement le mensonge qu'on corrige, et rien ne permettrait de
distinguer les lignes réparées ici de celles légitimement envoyées.
"""
from __future__ import annotations

from django.db import migrations


def _un_envoi_horodate_est_un_envoi(apps, schema_editor) -> None:
    DeliveryBatch = apps.get_model("delivery", "DeliveryBatch")
    remis_droits = DeliveryBatch.objects.filter(
        status="failed", sent_at__isnull=False
    ).update(status="sent", error_message="")
    if remis_droits:
        print(  # noqa: T201 — visible dans le journal de deploiement
            f"  {remis_droits} lot(s) de livraison horodate(s) mais marque(s) "
            "en echec : statut remis a « envoye »."
        )


def _pas_de_retour_en_arriere(apps, schema_editor) -> None:
    """Volontairement vide : voir le module."""


class Migration(migrations.Migration):

    dependencies = [
        ("delivery", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            _un_envoi_horodate_est_un_envoi, _pas_de_retour_en_arriere
        ),
    ]
