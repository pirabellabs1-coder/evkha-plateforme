from __future__ import annotations

from typing import Any

from .models import CoherenceFact, FactKind, GenerationJob

# Devise officielle par pays (cle de coherence transverse a tous les chapitres).
# Table volontairement minimale et extensible ; defaut prudent sinon.
_COUNTRY_CURRENCY: dict[str, str] = {
    "benin": "XOF",
    "cote d'ivoire": "XOF",
    "cote d ivoire": "XOF",
    "senegal": "XOF",
    "togo": "XOF",
    "burkina faso": "XOF",
    "mali": "XOF",
    "niger": "XOF",
    "cameroun": "XAF",
    "gabon": "XAF",
    "france": "EUR",
    "belgique": "EUR",
    "allemagne": "EUR",
    "espagne": "EUR",
    "maroc": "MAD",
    "tunisie": "TND",
    "canada": "CAD",
    "suisse": "CHF",
    "nigeria": "NGN",
    "ghana": "GHS",
}


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


def seed_locked_facts_from_variables(
    job: GenerationJob,
    variables: dict[str, Any],
) -> None:
    """Verrouille les faits deduits des variables de cadrage (devise, secteur, zone).

    Idempotent : meme valeur -> pas de conflit. Source = donnees client figees,
    donc base fiable du Coherence Engine pour tous les chapitres suivants.
    """
    sector = str(variables.get("SECTEUR", "")).strip()
    if sector:
        upsert_locked_fact(job=job, kind=FactKind.ASSUMPTION, key="secteur", value=sector)

    zone = str(variables.get("ZONE", "")).strip()
    if zone:
        upsert_locked_fact(job=job, kind=FactKind.ASSUMPTION, key="zone", value=zone)

    country = str(variables.get("PAYS", "")).strip()
    if country:
        currency = _COUNTRY_CURRENCY.get(country.lower())
        if currency:
            upsert_locked_fact(job=job, kind=FactKind.CURRENCY, key="currency", value=currency)


def locked_facts_as_context(job: GenerationJob) -> str:
    facts = job.coherence_facts.filter(is_locked=True).order_by("kind", "key")
    if not facts:
        return "Aucun fait verrouille pour le moment."
    return "\n".join(f"- {fact.kind}:{fact.key} = {fact.value}" for fact in facts)
