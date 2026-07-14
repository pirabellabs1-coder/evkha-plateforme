"""Validation post-generation des chapitres (QC Evangeline #3).

Detecte les defauts de rendu que la generation elle-meme peut produire
silencieusement : tableaux vides, troncatures, placeholders qui fuient,
substitutions ratees. Retourne une liste de ChapterValidationIssue.

Le runner utilise ces issues pour decider d'un retry (1x) puis, si toujours
KO, marque le chapitre FAILED et ouvre un incident.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


class ValidationSeverity:
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ChapterValidationIssue:
    code: str
    severity: str
    message: str


# --- Detecteurs -------------------------------------------------------------

# Un tableau markdown est considere vide si toutes ses lignes de donnees
# ne contiennent que des tirets/em-dashes/espaces/pipes.
_TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_EMPTY_CELL = re.compile(r"^[\s—–\-]*$")


def detect_empty_tables(content: str) -> list[ChapterValidationIssue]:
    """Detecte les tableaux markdown dont TOUTES les cellules de donnees sont vides.

    Un vrai tableau a au moins une ligne de donnees non-vide sous l'entete
    (l'entete + la separation `|---|` ne comptent pas).
    """
    issues: list[ChapterValidationIssue] = []
    lines = content.splitlines()
    i = 0
    table_index = 0
    while i < len(lines):
        if not _TABLE_LINE.match(lines[i]):
            i += 1
            continue
        # Debut d'un tableau : accumule les lignes consecutives commencant par |
        start = i
        while i < len(lines) and _TABLE_LINE.match(lines[i]):
            i += 1
        block = lines[start:i]
        if len(block) < 3:
            continue  # pas un vrai tableau (header + separator + >=1 data)
        table_index += 1
        # Ligne 0 = header, ligne 1 = separator, le reste = data
        data_rows = block[2:]
        has_content = False
        for row in data_rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if any(cell and not _EMPTY_CELL.match(cell) for cell in cells):
                has_content = True
                break
        if not has_content:
            issues.append(
                ChapterValidationIssue(
                    code="empty_table",
                    severity=ValidationSeverity.ERROR,
                    message=f"Tableau {table_index} vide (aucune donnee dans les lignes).",
                )
            )
    return issues


# Une troncature typique : le texte se termine sur un marqueur inacheve.
_TRUNCATION_TAIL = re.compile(
    r"(?:\*\*\s*$)"           # gras non ferme
    r"|(?::\s*$)"             # deux-points sans suite
    r"|(?:\|\s*$)"            # tableau coupe
    r"|(?:^\s*\|[^\n|]*$)",   # ligne de tableau incomplete en fin de doc
    re.MULTILINE,
)


def detect_truncation(content: str) -> list[ChapterValidationIssue]:
    """Detecte une fin de chapitre coupee (fin sur '**', ':', '|', phrase inachevee)."""
    stripped = content.rstrip()
    if not stripped:
        return [
            ChapterValidationIssue(
                code="empty_content",
                severity=ValidationSeverity.ERROR,
                message="Chapitre vide.",
            )
        ]
    # Retire le bloc Sources qui a une structure legitime differente.
    body = re.split(r"\n\s*sources\b", stripped, maxsplit=1, flags=re.IGNORECASE)[0].rstrip()
    if not body:
        return []
    tail = body[-40:]
    if _TRUNCATION_TAIL.search(tail):
        return [
            ChapterValidationIssue(
                code="truncated",
                severity=ValidationSeverity.ERROR,
                message=f"Chapitre tronque (fin brute: '{tail[-20:]!r}').",
            )
        ]
    # Fin sur une phrase inachevee : dernier caractere ni ponctuation ni chiffre.
    last = body.rstrip()[-1] if body.strip() else ""
    if last and last not in ".!?)]}»\"":
        # Tolere si la derniere ligne est un titre markdown
        last_line = body.splitlines()[-1].lstrip()
        if not last_line.startswith("#") and not last_line.startswith("-"):
            return [
                ChapterValidationIssue(
                    code="unfinished_sentence",
                    severity=ValidationSeverity.WARNING,
                    message=f"Chapitre finit sans ponctuation ('...{last_line[-30:]}').",
                )
            ]
    return []


# Placeholders et substitutions ratees observees sur les documents Evangeline.
_PLACEHOLDER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "leaked_prompt_snippet",
        re.compile(r"'préparer une offre claire'|«\s*préparer une offre claire\s*»", re.IGNORECASE),
    ),
    (
        "leaked_prompt_snippet",
        re.compile(r"souscrit à un ['\"]préparer", re.IGNORECASE),
    ),
    (
        "botched_substitution",
        re.compile(
            r"\b(?:le|un|au|du|ce)\s+clients?\s+prioritaires?\b(?!\s+(?:sont|constituent))",
            re.IGNORECASE,
        ),
    ),
    (
        "unresolved_template_variable",
        re.compile(r"\[(?:SECTEUR|PAYS|ZONE|PROJET|VARIABLE|TODO|PLACEHOLDER)\]"),
    ),
    (
        "unresolved_curly_placeholder",
        re.compile(r"\{\{\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\}\}"),
    ),
    (
        "leaked_callout_marker",
        re.compile(r"\[\[/?(UNDERSTAND|CONSIDER|ATTENTION)\]\]"),
    ),
    (
        "diamond_artifact",
        re.compile(r"(?:<>){2,}"),
    ),
)


def detect_placeholder_leaks(content: str) -> list[ChapterValidationIssue]:
    issues: list[ChapterValidationIssue] = []
    seen: set[tuple[str, str]] = set()
    for code, pattern in _PLACEHOLDER_PATTERNS:
        match = pattern.search(content)
        if match and (code, match.group(0)) not in seen:
            seen.add((code, match.group(0)))
            issues.append(
                ChapterValidationIssue(
                    code=code,
                    severity=ValidationSeverity.ERROR,
                    message=f"Fuite detectee: {match.group(0)!r}.",
                )
            )
    return issues


# Concatenations sans espace typiques d'un rendu casse.
_CONCAT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:net|de|la|le|se|au|du)"
        r"(?:entre|p[eé]riode|tr[eé]sorerie|renforcent)\b",
        re.IGNORECASE,
    ),
)


def detect_concatenation_bugs(content: str) -> list[ChapterValidationIssue]:
    issues: list[ChapterValidationIssue] = []
    for pattern in _CONCAT_PATTERNS:
        for match in pattern.finditer(content):
            issues.append(
                ChapterValidationIssue(
                    code="missing_space",
                    severity=ValidationSeverity.WARNING,
                    message=f"Concatenation sans espace: {match.group(0)!r}.",
                )
            )
    return issues


def validate_chapter_content(content: str) -> list[ChapterValidationIssue]:
    """Point d'entree : execute toutes les detections et rend la liste combinee."""
    issues: list[ChapterValidationIssue] = []
    issues.extend(detect_empty_tables(content))
    issues.extend(detect_truncation(content))
    issues.extend(detect_placeholder_leaks(content))
    issues.extend(detect_concatenation_bugs(content))
    return issues


def has_blocking_issues(issues: list[ChapterValidationIssue]) -> bool:
    return any(issue.severity == ValidationSeverity.ERROR for issue in issues)


def format_issues_for_retry(issues: list[ChapterValidationIssue]) -> str:
    """Formate les issues en instruction correctrice pour un retry."""
    lines = [f"- {issue.code}: {issue.message}" for issue in issues]
    return (
        "La generation precedente a produit des defauts a corriger IMPERATIVEMENT :\n"
        + "\n".join(lines)
        + "\n\nRegle : remplis les tableaux avec de vraies donnees, ne laisse aucun "
        "placeholder, termine chaque phrase, et n'utilise jamais 'préparer une offre "
        "claire' litteralement."
    )
