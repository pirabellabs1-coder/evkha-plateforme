from __future__ import annotations

from .models import CoherenceFact, FactKind, GenerationJob


class CoherenceConflictError(ValueError):
    pass


def upsert_locked_fact(
    *,
    job: GenerationJob,
    kind: FactKind,
    key: str,
    value: str,
    source_chapter_number: int | None = None,
) -> CoherenceFact:
    existing = CoherenceFact.objects.filter(job=job, kind=kind, key=key).first()
    if existing and existing.is_locked and existing.value != value:
        msg = f"Coherence conflict for {kind}:{key} ({existing.value} != {value})"
        raise CoherenceConflictError(msg)

    fact, _created = CoherenceFact.objects.update_or_create(
        job=job,
        kind=kind,
        key=key,
        defaults={
            "value": value,
            "source_chapter_number": source_chapter_number,
            "is_locked": True,
        },
    )
    return fact


def locked_facts_as_context(job: GenerationJob) -> str:
    facts = job.coherence_facts.filter(is_locked=True).order_by("kind", "key")
    if not facts:
        return "Aucun fait verrouille pour le moment."
    return "\n".join(f"- {fact.kind}:{fact.key} = {fact.value}" for fact in facts)
