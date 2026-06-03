from __future__ import annotations

import re
from dataclasses import dataclass

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
