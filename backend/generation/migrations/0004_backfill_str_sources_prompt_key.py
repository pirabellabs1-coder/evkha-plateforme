"""Backfill : renomme str.18.sources → str.19.sources dans les ChapterGeneration existants.

Contexte : le commit 3b6166c a inseré str.18.annexe_brief dans BUSINESS_STRATEGY_CHAPTERS,
décalant l'ancien chapitre Sources de chapter_number=18 → 19. Les jobs bootstrappés avant
ce commit conservent prompt_key='str.18.sources' en base, ce qui provoque un fallback sur
l'instruction générique et un rendu incorrect du chapitre Sources (SectionKind.CHAPTER au
lieu de SOURCES). Cette migration corrige l'existant.
"""
from __future__ import annotations

from django.db import migrations


def backfill_str_sources_prompt_key(apps: object, schema_editor: object) -> None:
    ChapterGeneration = apps.get_model("generation", "ChapterGeneration")  # noqa: N806
    ChapterGeneration.objects.filter(prompt_key="str.18.sources").update(
        prompt_key="str.19.sources"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("generation", "0003_alter_coherencefact_kind"),
    ]

    operations = [
        migrations.RunPython(
            backfill_str_sources_prompt_key,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
