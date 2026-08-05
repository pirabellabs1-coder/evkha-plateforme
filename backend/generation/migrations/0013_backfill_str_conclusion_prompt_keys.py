"""Backfill : décale les clés de prompt STR après l'insertion de la conclusion.

Contexte : `str.18.conclusion` est inséré dans BUSINESS_STRATEGY_CHAPTERS, ce qui
décale l'annexe de 18 → 19 et les sources de 19 → 20. Les jobs bootstrappés avant
ce commit conservent en base `prompt_key='str.18.annexe_brief'` et
`prompt_key='str.19.sources'`.

Sans ce backfill, `prompt_instruction` ne trouve plus ces clés — et elle ne lève
JAMAIS sur une clé inconnue : elle rend une consigne générique d'une ligne. Le
chapitre serait donc écrit sans consigne, et le livrable aurait l'air complet
(règle 1). C'est exactement le défaut que la migration 0004 a déjà corrigé une
fois, pour le même livrable et pour la même raison.

L'ORDRE des deux renommages est porteur : sources (19 → 20) d'abord, annexe
(18 → 19) ensuite. Dans l'autre sens, l'annexe devenue 19 serait reprise par le
second passage et finirait en 20, écrasant les sources.
"""
from __future__ import annotations

from django.db import migrations


def decaler_cles_apres_conclusion(apps: object, schema_editor: object) -> None:
    ChapterGeneration = apps.get_model("generation", "ChapterGeneration")  # noqa: N806
    # Sources d'abord : voir la note d'ordre dans le docstring.
    ChapterGeneration.objects.filter(prompt_key="str.19.sources").update(
        prompt_key="str.20.sources"
    )
    ChapterGeneration.objects.filter(prompt_key="str.18.annexe_brief").update(
        prompt_key="str.19.annexe_brief"
    )


def rétablir_cles_avant_conclusion(apps: object, schema_editor: object) -> None:
    ChapterGeneration = apps.get_model("generation", "ChapterGeneration")  # noqa: N806
    # Ordre inverse, pour la même raison de télescopage.
    ChapterGeneration.objects.filter(prompt_key="str.19.annexe_brief").update(
        prompt_key="str.18.annexe_brief"
    )
    ChapterGeneration.objects.filter(prompt_key="str.20.sources").update(
        prompt_key="str.19.sources"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("generation", "0012_chaptergeneration_payload_alter_generationjob_status"),
    ]

    operations = [
        migrations.RunPython(
            decaler_cles_apres_conclusion,
            reverse_code=rétablir_cles_avant_conclusion,
        ),
    ]
