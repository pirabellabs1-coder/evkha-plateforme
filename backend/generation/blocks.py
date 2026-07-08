"""Modèles Pydantic v2 pour la génération structurée (mode JSON strict).

Architecture hybride : les chapitres purement textuels/tabulaires peuvent être
générés via Tool Calling Anthropic → Pydantic valide la structure → Python génère
le HTML. Les chapitres visuels (SVG, tableaux financiers avec colspan/rowspan)
continuent en Markdown libre analysé par _md_to_html().

Avantage clé : un JSON tronqué (accolades manquantes) lève immédiatement une
ValidationError Pydantic, ce qui déclenche un retry ciblé dans le runner plutôt
qu'une livraison silencieuse d'un contenu cassé.

Activation : opt-in par chapitre. Passer LIVRER_CHAPITRE_TOOL dans l'appel
Anthropic, puis valider la réponse avec ChapterPayload.model_validate(tool_input).
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# ── Blocs atomiques ──────────────────────────────────────────────────────────


class TextBlock(BaseModel):
    """Paragraphe ou suite de paragraphes (inline markdown bold/italic autorisé)."""

    type: Literal["text"] = "text"
    content: str = Field(..., min_length=1, description="Texte sans Markdown structurel.")


class StandardTableBlock(BaseModel):
    """Tableau de données structurées — Python génère le HTML via render_blocks_to_html.

    Avantage : impossible d'avoir une balise <table> orpheline ou une ligne
    à cheval entre deux pages (chunk_long_tables s'en charge en aval).
    """

    type: Literal["standard_table"] = "standard_table"
    headers: list[str] = Field(..., min_length=1)
    rows: list[list[str]] = Field(..., min_length=1)


class ComplexHTMLBlock(BaseModel):
    """HTML natif pour structures complexes (colspan/rowspan, tableaux financiers, SWOT).

    close_dangling_html_tags() + chunk_long_tables() sont appliqués automatiquement
    au rendu. Ce type est réservé aux chapitres visuels qui ont besoin d'un markup
    HTML précis que StandardTableBlock ne peut pas représenter.
    """

    type: Literal["complex_html"] = "complex_html"
    html_content: str = Field(..., min_length=1)


class SVGChartBlock(BaseModel):
    """Graphique vectoriel SVG — rendu direct dans le PDF WeasyPrint."""

    type: Literal["svg_chart"] = "svg_chart"
    svg_code: str = Field(
        ...,
        min_length=1,
        description="Code SVG complet valide (<svg>...</svg>) pour rendu vectoriel.",
    )


# Union discriminée — Pydantic résout le type via le champ `type`
BlockType = Annotated[
    TextBlock | StandardTableBlock | ComplexHTMLBlock | SVGChartBlock,
    Field(discriminator="type"),
]


# ── Document structuré ────────────────────────────────────────────────────────


class ChapterPayload(BaseModel):
    """Réponse validée d'un appel en mode JSON strict.

    Si Claude tronque sa sortie, le JSON sera invalide → ValidationError
    immédiate → le runner peut retry ou logger l'incident MEDIUM.
    """

    chapter_id: str
    blocks: list[BlockType] = Field(..., min_length=1)

    def to_markdown(self) -> str:
        """Convertit les blocs en Markdown pour stockage en DB (compat pipeline existant)."""
        parts: list[str] = []
        for block in self.blocks:
            if isinstance(block, TextBlock):
                parts.append(block.content)
            elif isinstance(block, StandardTableBlock):
                parts.append(_standard_table_to_markdown(block))
            elif isinstance(block, ComplexHTMLBlock):
                parts.append(block.html_content)
            elif isinstance(block, SVGChartBlock):
                parts.append(block.svg_code)
        return "\n\n".join(parts)


def _standard_table_to_markdown(block: StandardTableBlock) -> str:
    sep = " | ".join("---" for _ in block.headers)
    header_line = " | ".join(block.headers)
    body_lines = "\n".join("| " + " | ".join(row) + " |" for row in block.rows)
    return f"| {header_line} |\n| {sep} |\n{body_lines}"


# ── Renderer HTML depuis blocs typés ─────────────────────────────────────────


def render_blocks_to_html(payload: ChapterPayload) -> str:
    """Génère le HTML final depuis les blocs validés Pydantic.

    Appelé à la place de _md_to_html() pour les chapitres en mode JSON strict.
    Les mêmes post-processeurs (close_dangling_html_tags, chunk_long_tables)
    sont appliqués ensuite par render_branded_html().
    """
    html_elements: list[str] = []
    for block in payload.blocks:
        if isinstance(block, TextBlock):
            # Inline markdown (bold, italic) préservé — pas de Markdown structurel
            html_elements.append(f"<p>{block.content}</p>")
        elif isinstance(block, StandardTableBlock):
            html_elements.append(_standard_table_to_html(block))
        elif isinstance(block, ComplexHTMLBlock):
            html_elements.append(block.html_content)
        elif isinstance(block, SVGChartBlock):
            html_elements.append(f"<div class='svg-container'>{block.svg_code}</div>")
    return "\n".join(html_elements)


def _standard_table_to_html(block: StandardTableBlock) -> str:
    header_html = "".join(f"<th>{h}</th>" for h in block.headers)
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in block.rows
    )
    return (
        "<table>"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table>"
    )


# ── Schéma Anthropic Tool Use ─────────────────────────────────────────────────

LIVRER_CHAPITRE_TOOL: dict = {
    "name": "livrer_chapitre",
    "description": (
        "Livre le contenu structuré du chapitre sous forme de blocs typés. "
        "Utilise ce tool pour toute ta réponse. Ne produis aucun texte en dehors de ce tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "chapter_id": {"type": "string"},
            "blocks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "oneOf": [
                        {
                            "type": "object",
                            "properties": {
                                "type": {"const": "text"},
                                "content": {"type": "string", "minLength": 1},
                            },
                            "required": ["type", "content"],
                        },
                        {
                            "type": "object",
                            "properties": {
                                "type": {"const": "standard_table"},
                                "headers": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "minItems": 1,
                                },
                                "rows": {
                                    "type": "array",
                                    "items": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "minItems": 1,
                                },
                            },
                            "required": ["type", "headers", "rows"],
                        },
                        {
                            "type": "object",
                            "properties": {
                                "type": {"const": "complex_html"},
                                "html_content": {"type": "string", "minLength": 1},
                            },
                            "required": ["type", "html_content"],
                        },
                        {
                            "type": "object",
                            "properties": {
                                "type": {"const": "svg_chart"},
                                "svg_code": {"type": "string", "minLength": 1},
                            },
                            "required": ["type", "svg_code"],
                        },
                    ]
                },
            },
        },
        "required": ["chapter_id", "blocks"],
    },
}
