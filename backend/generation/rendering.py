from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from .blueprints import SectionKind, chapters_for_deliverable
from .models import ChapterStatus, GenerationJob

# Marqueurs de pipeline interne a retirer du livrable client (Rendering Engine).
# La couche interne ne doit jamais fuiter cote client (regle d'or : separation
# interne -> client).
_INTERNAL_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:✅\s*)?Etape\b.*$", re.IGNORECASE),
    re.compile(r"^\s*(?:✅\s*)?Étape\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Point de controle\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Point de contrôle\b.*$", re.IGNORECASE),
    re.compile(r"^\s*(?:✅\s*)?V[ée]rification\b.*:?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:✅\s*)?Prompt [àa] utiliser\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Elements attendus\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Éléments attendus\b.*$", re.IGNORECASE),
)

_SECTION_ORDER: dict[str, int] = {
    SectionKind.OPENING: 0,
    SectionKind.CHAPTER: 1,
    SectionKind.ANNEXE: 2,
    SectionKind.SOURCES: 3,
}


@dataclass(frozen=True)
class RenderedSection:
    number: int
    title: str
    kind: str
    body: str


@dataclass(frozen=True)
class ClientDocument:
    title: str
    sections: tuple[RenderedSection, ...]

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", ""]
        for section in self.sections:
            lines.append(f"## {section.number}. {section.title}")
            lines.append("")
            lines.append(section.body.strip())
            lines.append("")
        return "\n".join(lines).strip() + "\n"


def strip_internal_markers(text: str) -> str:
    """Retire les lignes de jargon pipeline ; conserve le contenu redactionnel."""
    kept: list[str] = []
    for line in text.splitlines():
        if any(pattern.match(line) for pattern in _INTERNAL_LINE_PATTERNS):
            continue
        kept.append(line)
    cleaned = "\n".join(kept)
    # Compacte les lignes vides multiples laissees par les suppressions.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _document_title(job: GenerationJob) -> str:
    from catalog.models import DeliverableType

    labels: dict[str, str] = {
        DeliverableType.MARKET_STUDY: "Etude de marche",
        DeliverableType.COMPETITOR_STUDY: "Etude de la concurrence",
        DeliverableType.BUSINESS_PLAN: "Business plan",
        DeliverableType.BUSINESS_STRATEGY: "Strategie business",
    }
    return labels.get(job.deliverable_type, "Livrable EVKHA")


# ── Branding ──────────────────────────────────────────────────────────────────

_EVKHA_PRIMARY = "#2C3333"    # slate profond
_EVKHA_SECONDARY = "#A27B5C"  # argile chaud

_MOIS_FR: dict[int, str] = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}


@dataclass(frozen=True)
class BrandingContext:
    """Variables de branding client extraites de l'intake Tally.

    Fallback automatique sur la palette EVKHA si une variable est absente.
    """

    logo_url: str
    color_primary: str
    color_secondary: str
    company_name: str


def extract_branding(job: GenerationJob) -> BrandingContext:
    """Lit les variables de branding dans l'intake associé au job.

    Variables Tally concernées : LOGO_URL, COULEUR_PRINCIPALE,
    COULEUR_SECONDAIRE, NOM_ENTREPRISE.
    Toutes sont optionnelles ; la palette EVKHA est utilisée par défaut.
    """
    variables: dict[str, str] = {}
    try:
        submission = job.order.intake_submission
        raw = submission.normalized_variables
        if isinstance(raw, dict):
            variables = {k: str(v) for k, v in raw.items() if v}
    except Exception:  # noqa: BLE001 – intake optionnel
        pass

    return BrandingContext(
        logo_url=variables.get("LOGO_URL", ""),
        color_primary=variables.get("COULEUR_PRINCIPALE", _EVKHA_PRIMARY),
        color_secondary=variables.get("COULEUR_SECONDAIRE", _EVKHA_SECONDARY),
        company_name=variables.get("NOM_ENTREPRISE", ""),
    )


def _fr_date(dt: datetime) -> str:
    return f"{dt.day:02d} {_MOIS_FR[dt.month]} {dt.year}"


# ── Markdown → HTML (sans dépendance externe) ─────────────────────────────────


def _md_inline(text: str) -> str:
    """Inline Markdown : escape HTML, puis bold / italic / code."""
    from html import escape as _escape

    text = _escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(\S.*?\S|\S)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _md_to_html(text: str) -> str:
    """Convertit le Markdown EVKHA en HTML propre (headings, listes, bold, italic).

    Implémentation légère sans dépendance externe, suffisante pour le contenu
    structuré généré par Claude.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Séparateur horizontal
        if re.match(r"^[-*_]{3,}\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        # Titres
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = min(len(m.group(1)) + 1, 4)  # # → h2, ## → h3, ### → h4
            out.append(f"<h{level}>{_md_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # Blockquote
        if line.startswith("> "):
            items: list[str] = []
            while i < len(lines) and lines[i].startswith("> "):
                items.append(_md_inline(lines[i][2:]))
                i += 1
            out.append("<blockquote><p>" + "</p><p>".join(items) + "</p></blockquote>")
            continue

        # Liste non ordonnée
        if re.match(r"^[-*]\s", line):
            list_items: list[str] = []
            while i < len(lines) and re.match(r"^[-*]\s", lines[i]):
                list_items.append(f"<li>{_md_inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(list_items) + "</ul>")
            continue

        # Liste ordonnée
        if re.match(r"^\d+[.)]\s", line):
            ol_items: list[str] = []
            while i < len(lines) and re.match(r"^\d+[.)]\s", lines[i]):
                content = re.sub(r"^\d+[.)]\s", "", lines[i])
                ol_items.append(f"<li>{_md_inline(content)}</li>")
                i += 1
            out.append("<ol>" + "".join(ol_items) + "</ol>")
            continue

        # Ligne vide
        if not line.strip():
            out.append("")
            i += 1
            continue

        # Paragraphe
        out.append(f"<p>{_md_inline(line)}</p>")
        i += 1

    return "\n".join(out)


def render_branded_html(job: GenerationJob, *, branding: BrandingContext | None = None) -> str:
    """Rend le livrable complet en HTML A4 brandé client.

    Utilisé par WeasyPrintPdfClient pour générer le PDF final (D8).
    Le branding est extrait de l'intake Tally (LOGO_URL, COULEUR_PRINCIPALE,
    COULEUR_SECONDAIRE, NOM_ENTREPRISE) avec fallback palette EVKHA.
    """
    from django.template.loader import render_to_string

    if branding is None:
        branding = extract_branding(job)

    document = render_client_document(job)
    sections_ctx = [
        {
            "number": s.number,
            "title": s.title,
            "body_html": _md_to_html(s.body),
        }
        for s in document.sections
    ]

    return render_to_string(
        "generation/document.html",
        {
            "title": document.title,
            "branding": branding,
            "sections": sections_ctx,
            "generated_on": _fr_date(timezone.now()),
        },
    )


def render_client_document(job: GenerationJob) -> ClientDocument:
    """Assemble les chapitres DONE en document client, ordre methode EVKHA."""
    blueprints = chapters_for_deliverable(job.deliverable_type)
    kinds = {bp.prompt_key: bp.section_kind for bp in blueprints}

    done = job.chapters.filter(status=ChapterStatus.DONE)
    sections: list[RenderedSection] = []
    for chapter in done:
        kind = kinds.get(chapter.prompt_key, SectionKind.CHAPTER)
        sections.append(
            RenderedSection(
                number=chapter.chapter_number,
                title=chapter.chapter_title,
                kind=kind,
                body=strip_internal_markers(chapter.content),
            )
        )

    sections.sort(key=lambda s: (_SECTION_ORDER.get(s.kind, 1), s.number))
    return ClientDocument(title=_document_title(job), sections=tuple(sections))
