from __future__ import annotations

import re
from typing import Any

from .models import CoherenceFact, FactKind, GenerationJob

# Detection des chiffres cles dans le contenu genere (§5 cadrage : aucun chiffre
# contradictoire entre chapitres). Premiere mention -> verrou ; mention ulterieure
# differente -> CoherenceConflictError -> incident.
_TCAC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"TCAC\s*(?:de\s+|d['e]?\s+|:\s*)?(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE),
    re.compile(
        r"taux de croissance annuel moyen\s*(?:de\s+|:\s*)?(\d+(?:[.,]\d+)?)\s*%",
        re.IGNORECASE,
    ),
)
_MARKET_SIZE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"march[ée]\s+(?:mondial|global|national|local|regional|europe|europ[ée]en|africain)?\s*"
        r"(?:de\s+|estim[ée]\s+a\s+|atteint\s+|p[èe]se\s+|repr[ée]sente\s+)"
        r"(\d+(?:[.,]\d+)?)\s*(milliards?|mds?|millions?|m€|md€|mds?€|mfcfa)",
        re.IGNORECASE,
    ),
)

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

    # BP specifiques : forme juridique et capital verrouilles pour coherence
    # des projections financieres (meme statut du chap. 2 au chap. 10).
    forme = str(variables.get("FORME_JURIDIQUE", "")).strip()
    if forme:
        upsert_locked_fact(job=job, kind=FactKind.ASSUMPTION, key="forme_juridique", value=forme)

    capital = str(variables.get("CAPITAL_INITIAL", "")).strip()
    if capital:
        upsert_locked_fact(
            job=job, kind=FactKind.ASSUMPTION, key="capital_initial", value=capital
        )


def locked_facts_as_context(job: GenerationJob) -> str:
    facts = job.coherence_facts.filter(is_locked=True).order_by("kind", "key")
    if not facts:
        return "Aucun fait verrouille pour le moment."
    return "\n".join(f"- {fact.kind}:{fact.key} = {fact.value}" for fact in facts)


def extract_and_lock_chiffres_cles(job: GenerationJob, chapter_number: int, content: str) -> None:
    """Detecte TCAC et taille de marche dans le contenu d'un chapitre et les verrouille.

    Si une valeur differente est detectee plus tard, upsert_locked_fact leve
    CoherenceConflictError -> le runner ouvre un incident. Premiere mention
    suffit a fixer la valeur de reference pour le reste du livrable.
    """
    text = content or ""
    for pattern in _TCAC_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1).replace(",", ".") + "%"
            try:
                upsert_locked_fact(
                    job=job,
                    kind=FactKind.GROWTH_RATE,
                    key="tcac",
                    value=value,
                    source_chapter_number=chapter_number,
                )
            except CoherenceConflictError:
                # Le runner attrape cette exception et ouvre un incident HIGH.
                raise
            break

    for pattern in _MARKET_SIZE_PATTERNS:
        match = pattern.search(text)
        if match:
            value = f"{match.group(1)} {match.group(2)}".strip()
            try:
                upsert_locked_fact(
                    job=job,
                    kind=FactKind.MARKET_SIZE,
                    key="taille_marche",
                    value=value,
                    source_chapter_number=chapter_number,
                )
            except CoherenceConflictError:
                raise
            break
