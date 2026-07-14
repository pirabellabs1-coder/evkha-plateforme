"""Gate de livraison — Brique 3 du brief client (juillet 2026).

Couche de relecture automatique exécutée APRÈS la passe QA et AVANT toute
livraison. Contrairement à la QA (qui corrige ce qu'elle peut et trace le
reste), le gate est BLOQUANT : si un seul check critique échoue, le document
ne part pas chez le client. La livraison ne peut alors être déclenchée que
manuellement depuis le dashboard admin (décision humaine assumée).

Les quatre checks (brief client, verbatim) :
1. Contamination pipeline — aucun token interne (FAITS_VERROUILLES,
   VARIABLES_PROJET, marqueurs [[...]], placeholders) dans le texte final.
2. Cohérence chiffrée — les nombres clés extraits du document sont comparés
   à l'état chiffré verrouillé du brief client, tolérance zéro.
3. Complétude verticales — chaque verticale d'activité listée dans le brief
   doit apparaître dans le livrable.
4. Troncature — aucun chapitre ne se termine en pleine phrase ou dans une
   structure HTML ouverte.

Le gate travaille sur le contenu NETTOYÉ (ce que le client verra réellement),
pas sur le contenu brut : un token neutralisé par le Rendering Engine n'est
pas une fuite.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .models import ChapterStatus, FactProvenance, GenerationJob
from .rendering import RenderedSection, render_client_document

# ── Check 1 : contamination pipeline ─────────────────────────────────────────
# Tokens interdits dans le texte final (brief client : "grep des tokens
# interdits... Si un seul apparaît → rejet").
_FORBIDDEN_TOKEN_RE = re.compile(
    r"\b(?:FAITS_VERROUILLES|VARIABLES_PROJET|DONNEES_CLIENT"
    r"|REPERES_DEJA_ENONCES|RESUME_OPERATIONNEL(?:_PRECEDENT)?"
    r"|FICHE_SECTORIELLE|CHAPITRE_CIBLE|CHAPITRE_PARENT"
    r"|SECTIONS_PRECEDENTES|PROMPT_KEY|SECTION_A_GENERER"
    r"|CONSIGNE_DU_CHAPITRE|DATE_DU_JOUR|CONTEXTE_ETUDE_PRECEDENTE"
    r"|TODO|PLACEHOLDER|XXX)\b"
    r"|\[\[/?(?:UNDERSTAND|CONSIDER|ATTENTION|ACTION)\]\]"
    r"|\{\{\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\}\}"
)

# ── Check 2 : cohérence chiffrée vs état client ──────────────────────────────
# Chaque clé de fait client est associée aux motifs qui repèrent sa valeur
# dans le texte généré. Tolérance zéro : toute valeur extraite qui ne
# correspond à aucun nombre du fait client est bloquante.
_CLIENT_FACT_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "investissement_total": (
        re.compile(
            r"investissement\s+(?:total|initial|global|de\s+d[ée]part)\s*"
            r"(?:de\s+|estim[ée]\s+[àa]\s+|s'[ée]l[èe]ve\s+[àa]\s+|:\s*)?"
            r"(\d[\d\s ]*(?:[.,]\d+)?)\s*(?:€|euros?|EUR|k€|M€)",
            re.IGNORECASE,
        ),
    ),
    "emprunt": (
        re.compile(
            r"(?:emprunt|pr[êe]t\s+bancaire)\s*"
            r"(?:de\s+|d'un\s+montant\s+de\s+|:\s*)?"
            r"(\d[\d\s ]*(?:[.,]\d+)?)\s*(?:€|euros?|EUR|k€|M€)",
            re.IGNORECASE,
        ),
    ),
    "apport": (
        re.compile(
            r"apport\s+(?:personnel|propre|en\s+capital)?\s*"
            r"(?:de\s+|:\s*)?"
            r"(\d[\d\s ]*(?:[.,]\d+)?)\s*(?:€|euros?|EUR|k€|M€)",
            re.IGNORECASE,
        ),
    ),
    "taux_occupation": (
        re.compile(
            r"taux\s+d['e]?occupation\s*"
            r"(?:de\s+|cible\s+de\s+|moyen\s+de\s+|:\s*|atteint\s+|est\s+de\s+)?"
            r"(\d+(?:[.,]\d+)?)\s*%",
            re.IGNORECASE,
        ),
    ),
    "seuil_rentabilite": (
        re.compile(
            r"seuil\s+de\s+rentabilit[ée]\s*"
            r"(?:se\s+situe\s+[àa]\s+|est\s+de\s+|:\s*|de\s+|atteint\s+[àa]\s+)?"
            r"(\d[\d\s ]*(?:[.,]\d+)?)\s*(?:€|euros?|EUR)",
            re.IGNORECASE,
        ),
    ),
    "resultat_net_previsionnel": (
        re.compile(
            r"r[ée]sultat\s+net\s*(?:pr[ée]visionnel|projet[ée]|attendu|d[e']?ann[ée]e\s*\d)?\s*"
            r"(?:de\s+|:\s*|est\s+de\s+|atteint\s+)?"
            r"(-?\d[\d\s ]*(?:[.,]\d+)?)\s*(?:€|euros?|EUR|k€)",
            re.IGNORECASE,
        ),
    ),
    "ebe_previsionnel": (
        re.compile(
            r"(?:EBE|exc[ée]dent\s+brut\s+d['e]?exploitation)\s*"
            r"(?:pr[ée]visionnel|projet[ée]|d[e']?ann[ée]e\s*\d)?\s*"
            r"(?:de\s+|:\s*|est\s+de\s+|atteint\s+)?"
            r"(-?\d[\d\s ]*(?:[.,]\d+)?)\s*(?:€|euros?|EUR|k€)",
            re.IGNORECASE,
        ),
    ),
}

# Nombres "libres" uniquement : un chiffre colle a une lettre ("An1", "M4")
# est un indice d'annee/mois, pas une valeur du previsionnel.
_NUMBER_RE = re.compile(r"(?<![A-Za-z\d])-?\d[\d\s ]*(?:[.,]\d+)?")

# ── Check 4 : troncature ─────────────────────────────────────────────────────
# Violations QA considérées comme des troncatures bloquantes si elles
# subsistent après la passe QA (le document partirait incomplet).
_BLOCKING_TRUNCATION = frozenset(
    {"empty_content", "sentence_cut", "cut_html_table", "truncated_in_tag", "abrupt_ending"}
)


@dataclass(frozen=True)
class GateFailure:
    check: str  # "contamination" | "coherence_chiffree" | "verticales" | "troncature"
    detail: str
    chapter_number: int | None = None


@dataclass(frozen=True)
class GateReport:
    passed: bool
    failures: tuple[GateFailure, ...] = field(default_factory=tuple)

    def as_details(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "failures": [
                {
                    "check": f.check,
                    "chapitre": f.chapter_number,
                    "detail": f.detail,
                }
                for f in self.failures
            ],
        }


def _strip_accents_lower(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn"
    )


def _parse_number(raw: str) -> float | None:
    try:
        return float(raw.replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _client_numbers(value: str) -> list[float]:
    """Extrait tous les nombres d'une valeur de fait client.

    Une valeur client peut être multiple ("55 % An1 → 85 % An5") : dans ce
    cas, les valeurs du document sont acceptées si elles tombent DANS la
    fourchette [min, max] des nombres du brief (années intermédiaires).
    """
    numbers = []
    for m in _NUMBER_RE.finditer(value):
        parsed = _parse_number(m.group(0))
        if parsed is not None:
            numbers.append(parsed)
    return numbers


def _check_contamination(sections: tuple[RenderedSection, ...]) -> list[GateFailure]:
    """Scanne le HTML RENDU de chaque section (ce que le client voit).

    Le corps markdown contient legitimement des paires [[UNDERSTAND]]...
    [[/UNDERSTAND]] que le convertisseur transforme en encadres mentor : le
    check doit donc operer APRES conversion + scrub (meme pipeline que
    render_branded_html), sinon chaque document avec encadres serait bloque.
    """
    from .rendering import _md_to_html, strip_callout_markers  # noqa: PLC0415

    failures: list[GateFailure] = []
    for section in sections:
        rendered = strip_callout_markers(_md_to_html(section.body))
        match = _FORBIDDEN_TOKEN_RE.search(rendered)
        if match:
            failures.append(GateFailure(
                check="contamination",
                chapter_number=section.number,
                detail=f"Token interne dans le texte final : {match.group(0)!r}",
            ))
    return failures


def _check_numeric_coherence(
    job: GenerationJob, sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Tolérance zéro entre les chiffres du document et l'état client.

    Pour chaque fait client numérique, toutes les occurrences repérées dans
    le document doivent correspondre à un nombre du brief (exactement, ou
    dans la fourchette si le brief donne une trajectoire multi-années).
    """
    failures: list[GateFailure] = []
    client_facts = {
        fact.key: fact.value
        for fact in job.coherence_facts.filter(
            is_locked=True, provenance=FactProvenance.CLIENT
        )
    }

    for key, patterns in _CLIENT_FACT_PATTERNS.items():
        client_value = client_facts.get(key, "")
        expected = _client_numbers(client_value)
        if not expected:
            continue  # pas de donnée client structurée pour cette clé
        lo, hi = min(expected), max(expected)
        for section in sections:
            for pattern in patterns:
                for m in pattern.finditer(section.body):
                    found = _parse_number(m.group(1))
                    if found is None:
                        continue
                    exact = any(found == e for e in expected)
                    in_range = lo <= found <= hi
                    if not (exact or (len(expected) > 1 and in_range)):
                        failures.append(GateFailure(
                            check="coherence_chiffree",
                            chapter_number=section.number,
                            detail=(
                                f"{key} : document dit {m.group(1).strip()!r}, "
                                f"brief client dit {client_value!r}"
                            ),
                        ))
    return failures


def _check_verticales(
    job: GenerationJob, sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Chaque verticale d'activité du brief doit apparaître dans le livrable."""
    fact = job.coherence_facts.filter(
        is_locked=True, provenance=FactProvenance.CLIENT, key="verticales"
    ).first()
    if fact is None or not fact.value.strip():
        return []

    verticales = [v.strip() for v in re.split(r"[/,;]|\n", fact.value) if v.strip()]
    if not verticales:
        return []

    full_text = _strip_accents_lower("\n".join(s.body for s in sections))
    failures: list[GateFailure] = []
    for verticale in verticales:
        needle = _strip_accents_lower(verticale)
        if needle and needle not in full_text:
            failures.append(GateFailure(
                check="verticales",
                detail=(
                    f"Verticale du brief absente du livrable : {verticale!r}. "
                    "Le remplacement silencieux d'une activité client par un "
                    "modèle générique est interdit."
                ),
            ))
    return failures


def _check_truncation(sections: tuple[RenderedSection, ...]) -> list[GateFailure]:
    from .qa import detect_violations  # import local : éviter le cycle qa->gate

    failures: list[GateFailure] = []
    for section in sections:
        violations = detect_violations(section.body, prompt_key="", chapter_number=section.number)
        for v in violations:
            if v.name in _BLOCKING_TRUNCATION:
                failures.append(GateFailure(
                    check="troncature",
                    chapter_number=section.number,
                    detail=f"{v.name}: {v.detail}",
                ))
    return failures


def run_delivery_gate(job: GenerationJob) -> GateReport:
    """Exécute les quatre checks bloquants sur le document tel que livré.

    Lecture seule : aucune écriture en base. L'appelant (tasks.py) décide
    des effets (statut BLOCKED, incident, blocage de l'email).
    """
    if not job.chapters.filter(status=ChapterStatus.DONE).exists():
        return GateReport(
            passed=False,
            failures=(GateFailure(check="troncature", detail="Aucun chapitre généré."),),
        )

    document = render_client_document(job)
    sections = document.sections

    failures: list[GateFailure] = []
    failures.extend(_check_contamination(sections))
    failures.extend(_check_numeric_coherence(job, sections))
    failures.extend(_check_verticales(job, sections))
    failures.extend(_check_truncation(sections))

    return GateReport(passed=not failures, failures=tuple(failures))
