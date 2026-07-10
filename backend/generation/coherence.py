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


# Seuil de tolerance relative pour les valeurs numeriques : en-deca,
# on considere que les deux valeurs sont dans le meme ordre de grandeur
# (ex: 8.4% vs 9.0% = 7% d'ecart -> ignore). Au-dela, conflict reel
# (ex: 8.4% vs 13% = 35% d'ecart -> incident MEDIUM, pas d'arret).
_NUMERIC_CONFLICT_TOLERANCE = 0.20


def _numeric_gap(a: str, b: str) -> float | None:
    """Retourne l'ecart relatif entre deux valeurs numeriques (apres strip %).
    Retourne None si l'une des valeurs n'est pas numerique.
    """
    try:
        va = float(a.rstrip("% ").replace(",", "."))
        vb = float(b.rstrip("% ").replace(",", "."))
        denom = max(abs(va), abs(vb))
        if denom == 0:
            return 0.0
        return abs(va - vb) / denom
    except (ValueError, AttributeError):
        return None


def upsert_locked_fact(
    *,
    job: GenerationJob,
    kind: FactKind,
    key: str,
    value: str,
    source_chapter_number: int | None = None,
) -> CoherenceFact:
    """Verrouille un fait. En cas de conflit :
    - Ecart numerique < 20% : ignore silencieusement (meme ordre de grandeur).
    - Ecart >= 20% ou valeurs non numeriques : incident MEDIUM, generation continue.
    N'arrete JAMAIS la generation — un conflit de chiffre est une imperfection
    de contenu, pas une erreur systeme.

    Les valeurs client (SECTEUR, ZONE, FORME_JURIDIQUE...) sont du texte libre
    sans limite cote formulaire Tally. Tronquees a la longueur du champ pour
    ne jamais faire planter le job sur un DataError Postgres — un fait de
    coherence legerement tronque vaut mieux qu'un job qui ne demarre jamais.
    """
    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    max_len = CoherenceFact._meta.get_field("value").max_length
    if max_len is not None and len(value) > max_len:
        value = value[:max_len]

    existing = CoherenceFact.objects.filter(job=job, kind=kind, key=key).first()
    if existing and existing.is_locked and existing.value != value:
        gap = _numeric_gap(existing.value, value)
        if gap is not None and gap < _NUMERIC_CONFLICT_TOLERANCE:
            # Meme ordre de grandeur — pas de conflit significatif.
            return existing

        # Conflit reel : alerter l'admin mais NE PAS stopper la generation.
        OperationalIncident.objects.get_or_create(
            title=f"Incoh. donnee {kind}:{key} job {job.id}",
            defaults={
                "severity": IncidentSeverity.MEDIUM,
                "job": job,
                "order": job.order,
                "details": {
                    "valeur_verrouillee": existing.value,
                    "valeur_conflictuelle": value,
                    "chapitre": source_chapter_number,
                    "ecart_relatif": f"{gap:.0%}" if gap is not None else "non-numerique",
                },
            },
        )
        # Garde la valeur verrouilee — la premiere mention fait foi.
        return existing

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

    Premiere mention fixe la valeur de reference ; les mentions ulterieures
    differentes creent un incident MEDIUM mais ne stoppent pas la generation.
    """
    text = content or ""
    for pattern in _TCAC_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1).replace(",", ".") + "%"
            upsert_locked_fact(
                job=job,
                kind=FactKind.GROWTH_RATE,
                key="tcac",
                value=value,
                source_chapter_number=chapter_number,
            )
            break

    for pattern in _MARKET_SIZE_PATTERNS:
        match = pattern.search(text)
        if match:
            value = f"{match.group(1)} {match.group(2)}".strip()
            upsert_locked_fact(
                job=job,
                kind=FactKind.MARKET_SIZE,
                key="taille_marche",
                value=value,
                source_chapter_number=chapter_number,
            )
            break
