"""Réduit la charge des événements Stripe DÉJÀ enregistrés.

Depuis le 20/11/2026, `paiement.vues.charge_a_conserver` n'écrit plus en base
qu'une liste blanche de ce qu'un événement de paiement porte. Les lignes
antérieures gardaient l'événement entier : l'identifiant de session complet,
le nom, l'adresse de courriel et l'adresse postale de l'acheteur, lisibles
dans l'administration et dans les sauvegardes.

**Irréversible, et voulu** (accord de la cliente du 20/11/2026) : ce qui est
retiré ne se retrouve pas. Rien ne relit cette charge pour traiter un
paiement — le prestataire renvoie ses événements —, elle ne sert qu'à
comprendre après coup, et la charge réduite y suffit.

**Ne fait jamais échouer le démarrage.** `migrate` est dans la chaîne de
démarrage du conteneur : une ligne illisible est laissée telle quelle et
comptée, pas levée. `dashboard/system/` dit ensuite combien il en reste
(`webhooks_stripe_non_expurges`).
"""
from __future__ import annotations

from typing import Any

from django.db import migrations


def expurger(apps: Any, schema_editor: Any) -> None:
    # La MÊME fonction que celle qui écrit les nouveaux événements : deux
    # écritures de la liste blanche finiraient par ne plus garder la même
    # chose (règle 5). Lue par le module, pour qu'un test puisse la remplacer.
    from paiement import vues  # noqa: PLC0415

    WebhookEvent = apps.get_model("integrations", "WebhookEvent")  # noqa: N806
    faites = laissees = 0
    lignes = WebhookEvent.objects.filter(provider="stripe").values_list(
        "pk", "raw_payload", "error_message"
    )
    for cle, charge, message in lignes.iterator(chunk_size=200):
        try:
            if isinstance(charge, dict) and charge.get("expurge") is True:
                continue
            reduite = vues.charge_a_conserver(charge if isinstance(charge, dict) else {})
            # `update`, pas `save` : la date de modification sert à reconnaître
            # un traitement perdu, elle ne doit pas bouger.
            WebhookEvent.objects.filter(pk=cle).update(
                raw_payload=reduite, error_message=vues.sans_secrets(message or "")
            )
            faites += 1
        except Exception:  # noqa: BLE001 — voir « ne fait jamais échouer »
            laissees += 1
    if faites or laissees:
        print(  # noqa: T201 — lu dans le journal du déploiement
            f"\n  Charges Stripe expurgées : {faites} ; laissées : {laissees}."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0007_alter_externalcredentialref_provider_and_more"),
    ]

    operations = [migrations.RunPython(expurger, migrations.RunPython.noop)]
