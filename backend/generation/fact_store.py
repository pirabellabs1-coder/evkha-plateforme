"""Mémoire persistante inter-runs (Option 1 — fact store JSON).

Après chaque génération ayant passé le gate, les faits de marché validés
(CHIFFRES_FONDATIONS) sont exportés dans un fichier JSON nommé d'après le
couple secteur/pays. Avant la génération du chapitre 1, ce fichier est relu
et injecté comme FAITS_REFERENCES dans le contexte — Claude dispose ainsi de
chiffres de marché validés par un run humainement accepté, sans repartir de
zéro.

Répertoire de stockage : EVKHA_FACT_STORE_DIR dans settings/env
(défaut : <BASE_DIR>/fact_store/).
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.conf import settings

if TYPE_CHECKING:
    # Import réservé aux annotations : `from __future__ import annotations` les
    # laisse sous forme de chaînes, donc rien n'est chargé à l'exécution et
    # aucun cycle ne se referme. L'annotation citait `GenerationJob` sans que le
    # nom existe nulle part, et un `type: ignore[name-defined]` faisait taire le
    # symptôme — ce que le dépôt interdit explicitement.
    from .models import GenerationJob

logger = logging.getLogger(__name__)

_FACT_STORE_DIR = Path(
    getattr(settings, "EVKHA_FACT_STORE_DIR", None)
    or (Path(settings.BASE_DIR) / "fact_store")
)

# Clés CoherenceFact à conserver (MARKET_SIZE + GROWTH_RATE)
_FACT_KEYS: frozenset[str] = frozenset({
    "taille_marche_mondial",
    "taille_marche_continental",
    "taille_marche_national",
    "taille_marche_local",
    "taille_marche",
    "tcac",
    "tcac_mondial",
    "tcac_continental",
    "tcac_national",
    "tam",
    "tam_mondial",
    "tam_continental",
    "tam_national",
    "sam",
    "sam_mondial",
    "sam_continental",
    "sam_national",
    "som",
    "som_mondial",
    "som_continental",
    "som_national",
})

# Clés VARIABLES_PROJET pour identifier le secteur et le pays
_SECTEUR_KEY = "SECTEUR"
_PAYS_KEY = "PAYS"


def _slug(text: str) -> str:
    """Normalise un texte en slug ASCII lowercase utilisable comme nom de fichier."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")[:80]


def _store_path(secteur: str, pays: str) -> Path:
    return _FACT_STORE_DIR / f"{_slug(secteur)}_{_slug(pays)}.json"


def export_facts(job: GenerationJob) -> None:
    """Exporte les faits validés du job vers le fact store JSON.

    Appelé après que le gate de livraison ait passé. En cas d'erreur, log
    uniquement — ne bloque jamais la livraison.
    """
    from intake.models import IntakeSubmission  # noqa: PLC0415

    submission = IntakeSubmission.objects.filter(order=job.order).first()
    if not submission:
        return

    variables: dict[str, Any] = submission.normalized_variables or {}
    secteur = str(variables.get(_SECTEUR_KEY, "")).strip()
    pays = str(variables.get(_PAYS_KEY, "")).strip()
    if not secteur or not pays:
        logger.warning(
            "fact_store: SECTEUR ou PAYS absent du brief — export ignoré (job %s)",
            job.id,
        )
        return

    facts: dict[str, str] = {}
    for fact in job.coherence_facts.filter(key__in=_FACT_KEYS):
        if fact.value:
            facts[fact.key] = str(fact.value)

    if not facts:
        logger.info("fact_store: aucun fait de marché à exporter (job %s)", job.id)
        return

    payload: dict[str, Any] = {
        "secteur": secteur,
        "pays": pays,
        "last_updated": date.today().isoformat(),
        "source_job_id": str(job.id),
        "facts": facts,
    }

    try:
        _FACT_STORE_DIR.mkdir(parents=True, exist_ok=True)
        path = _store_path(secteur, pays)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(
            "fact_store: %d faits exportés → %s (job %s)", len(facts), path.name, job.id
        )
    except OSError:
        logger.exception("fact_store: écriture échouée pour le job %s", job.id)


def load_facts_block(variables: dict[str, Any]) -> str | None:
    """Retourne le bloc FAITS_REFERENCES prêt à être injecté dans le contexte.

    Retourne None si aucun fichier ne correspond au secteur/pays du brief,
    ou si le fichier est vide/corrompu.
    """
    secteur = str(variables.get(_SECTEUR_KEY, "")).strip()
    pays = str(variables.get(_PAYS_KEY, "")).strip()
    if not secteur or not pays:
        return None

    path = _store_path(secteur, pays)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("fact_store: lecture échouée pour %s", path)
        return None

    facts: dict[str, str] = payload.get("facts", {})
    if not facts:
        return None

    source_info = (
        f"run {payload.get('source_job_id', '?')} — {payload.get('last_updated', '?')}"
    )
    lines = [
        f"Repères issus d'une étude précédente validée ({source_info}).",
        "Ces valeurs sont des POINTS DE DÉPART : vérifie-les, actualise-les si",
        "les données récentes divergent, mais ne les ignore pas sans raison.",
        "",
        "| Clé | Valeur |",
        "|---|---|",
    ]
    for key, value in facts.items():
        lines.append(f"| {key} | {value} |")

    return "\n".join(lines)
