from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from .blueprints import SectionKind, chapters_for_deliverable
from .models import ChapterStatus, GenerationJob

# Marqueurs de pipeline interne a retirer du livrable client (Rendering Engine).
# La couche interne ne doit jamais fuiter cote client (regle d'or : separation
# interne -> client). Inclut les "phrases meta" du Bloc 1 des Consignes EVKHA.
_INTERNAL_LINE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:✅\s*)?Etape\b.*$", re.IGNORECASE),
    re.compile(r"^\s*(?:✅\s*)?Étape\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Point de controle\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Point de contrôle\b.*$", re.IGNORECASE),
    re.compile(r"^\s*(?:✅\s*)?V[ée]rification\b.*:?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:✅\s*)?Validation\b.*:?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:✅\s*)?Prompt [àa] utiliser\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Elements attendus\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Éléments attendus\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Cas\s*\d+\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Livrable\s+automatis[ée]\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Methodologie\s+EVKHA\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Méthodologie\s+EVKHA\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Pipeline\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Version\s+CSV\b.*$", re.IGNORECASE),
    re.compile(r"^\s*CONTEXTE\s+[AÀ]\s+R[EÉ]INJECTER\b.*$", re.IGNORECASE),
    re.compile(r"^\s*La liste ci-dessous\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Cette lecture pr[ée]pare\b.*$", re.IGNORECASE),
    re.compile(r"^\s*L['e]objectif est de\b.*$", re.IGNORECASE),
    re.compile(r"^\s*Tableau\s+de\s+conformit[ée]\b.*$", re.IGNORECASE),
)

# Substitutions lexicales (Bloc 3 Consignes EVKHA) : anglicismes + jargon
# rapport. Appliquees en post-traitement avec word boundaries pour preserver
# les mots metier (ASN, ANDPC, DPC, Qualiopi, MERM, IBODE...).
_LEXICAL_SUBSTITUTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Anglicismes consulting
    (re.compile(r"\bblended learning\b", re.IGNORECASE), "format mixte (e-learning + présentiel)"),
    (re.compile(r"\bblended\b", re.IGNORECASE), "format mixte"),
    (re.compile(r"\bmicro[- ]learning\b", re.IGNORECASE), "formats courts"),
    (re.compile(r"\bself[- ]paced\b", re.IGNORECASE), "à son rythme"),
    (re.compile(r"\bpain[- ]points?\b", re.IGNORECASE), "vraies difficultés"),
    (re.compile(r"\bpackager?\b", re.IGNORECASE), "préparer une offre claire"),
    (re.compile(r"\bpackagée?s?\b", re.IGNORECASE), "claire et structurée"),
    (re.compile(r"\bpitch\b", re.IGNORECASE), "présentation"),
    (re.compile(r"\bticket moyen\b", re.IGNORECASE), "prix moyen par client"),
    (re.compile(r"\bonboarding\b", re.IGNORECASE), "accueil des nouveaux"),
    (re.compile(r"\bcœur de cible\b", re.IGNORECASE), "clients prioritaires"),
    (re.compile(r"\bcoeur de cible\b", re.IGNORECASE), "clients prioritaires"),
    # Jargon de rapport
    (re.compile(r"\bsolvabilisations?\b", re.IGNORECASE), "financements"),
    (re.compile(r"\bsolvabiliser\b", re.IGNORECASE), "financer"),
    (re.compile(r"\brécurrence des revenus\b", re.IGNORECASE), "revenus qui se renouvellent"),
    (re.compile(r"\brecurrence des revenus\b", re.IGNORECASE), "revenus qui se renouvellent"),
    (re.compile(r"\bla récurrence\b", re.IGNORECASE), "le caractère récurrent"),
    (re.compile(r"\bla recurrence\b", re.IGNORECASE), "le caractère récurrent"),
    (re.compile(r"\bdynamique porteuse\b", re.IGNORECASE), "tendance favorable"),
    (re.compile(r"\btendance structurelle\b", re.IGNORECASE), "tendance de fond"),
    (re.compile(r"\bpolarisations?\b", re.IGNORECASE), "séparation"),
    (re.compile(r"\bconsolidation concurrentielle\b", re.IGNORECASE), "concentration des concurrents"),
    (re.compile(r"\bconsolidation du marché\b", re.IGNORECASE), "concentration du marché"),
    (re.compile(r"\bnon[- ]discrétionnaires?\b", re.IGNORECASE), "obligatoire"),
    (re.compile(r"\bnon[- ]discretionnaires?\b", re.IGNORECASE), "obligatoire"),
    (re.compile(r"\bancrage éditorial\b", re.IGNORECASE), "appui éditorial"),
    (re.compile(r"\bancrage editorial\b", re.IGNORECASE), "appui éditorial"),
    (re.compile(r"\bincarner le positionnement\b", re.IGNORECASE), "rendre le positionnement concret"),
    (re.compile(r"\bactionnables?\b", re.IGNORECASE), "applicable"),
    (re.compile(r"\bvitesse de captation\b", re.IGNORECASE), "vitesse de conquête"),
    # Tournures evitees (debut de phrase)
    (re.compile(r"\bIl apparaît que\b"), "On constate que"),
    (re.compile(r"\bIl apparait que\b"), "On constate que"),
    (re.compile(r"\bOn peut observer que\b"), "On voit que"),
    (re.compile(r"\bIl convient de noter que\b"), "À noter :"),
    (re.compile(r"\bIl convient de noter\b"), "À noter"),
)

# Sources intermediaires (Bloc 1 Consignes : "Une seule section Sources en
# toute fin"). On strip toute section Sources interne aux chapitres.
_SOURCES_BLOCK_PATTERN = re.compile(
    r"^\s*(?:#{1,4}\s*)?Sources?\s*(?:[:—-].*)?$", re.IGNORECASE
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


def strip_intermediate_sources(text: str) -> str:
    """Retire les blocs 'Sources' intermediaires (Bloc 1 Consignes : section unique en fin).

    Detecte une ligne de type '# Sources', 'Sources :', '## Sources' et supprime
    la ligne + toutes les lignes suivantes jusqu'au prochain titre ou ligne vide
    doublee. Reserve aux chapitres NON sources.
    """
    lines = text.splitlines()
    out: list[str] = []
    skip = False
    for i, line in enumerate(lines):
        if _SOURCES_BLOCK_PATTERN.match(line):
            skip = True
            continue
        if skip:
            # Sortir du skip si on rencontre un titre Markdown ou une autre section
            if re.match(r"^\s*#{1,4}\s+\S+", line):
                skip = False
                out.append(line)
            elif not line.strip() and i + 1 < len(lines) and not lines[i + 1].strip():
                skip = False
            # sinon : continuer a ignorer
            continue
        out.append(line)
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def apply_lexical_substitutions(text: str) -> str:
    """Applique les substitutions anglicismes + jargon (Bloc 3 Consignes EVKHA).

    Les mots metier (ASN, ANDPC, DPC, Qualiopi, MERM, IBODE...) sont preserves
    car aucune substitution ne les cible (word boundaries strictes sur les
    termes a remplacer).
    """
    result = text
    for pattern, replacement in _LEXICAL_SUBSTITUTIONS:
        result = pattern.sub(replacement, result)
    return result


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
# Palette OFFICIELLE EVKHA (Bloc 6 Consignes mai 2026) — couleurs validees
# par Evangeline. Ne pas modifier sans accord ecrit.
_EVKHA_PRIMARY        = "#1A1A1A"   # Noir profond (titres + texte structurant)
_EVKHA_SECONDARY      = "#C9A227"   # Or (accents, filets, encadres cles)
_EVKHA_SECONDARY_ALT  = "#E4C65B"   # Or clair (variations secondaires)
_EVKHA_GRAY           = "#5A5A5A"   # Gris (legendes, italiques)
_EVKHA_CREAM          = "#FBF8EF"   # Creme (fonds encadres + lignes alternees)
_EVKHA_CREAM_DARK     = "#EFEAD8"   # Creme foncee (lignes tableau)

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


def extract_photos(job: GenerationJob) -> list[str]:
    """Photos illustratives du client pour le Business Plan (§14 cadrage).

    Retourne 0 a 3 URLs (PHOTO_1, PHOTO_2, PHOTO_3) ; seulement pour les BP.
    """
    from catalog.models import DeliverableType

    if job.deliverable_type != DeliverableType.BUSINESS_PLAN:
        return []

    try:
        submission = job.order.intake_submission
        raw = submission.normalized_variables
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(raw, dict):
        return []
    photos = [str(raw.get(k, "")).strip() for k in ("PHOTO_1", "PHOTO_2", "PHOTO_3")]
    return [p for p in photos if p]


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
            "kind": s.kind,
            "body_html": _md_to_html(s.body),
        }
        for s in document.sections
    ]
    photos = extract_photos(job)

    return render_to_string(
        "generation/document.html",
        {
            "title": document.title,
            "branding": branding,
            "sections": sections_ctx,
            "photos": photos,
            "generated_on": _fr_date(timezone.now()),
            "evkha_primary":       _EVKHA_PRIMARY,
            "evkha_secondary":     _EVKHA_SECONDARY,
            "evkha_secondary_alt": _EVKHA_SECONDARY_ALT,
            "evkha_gray":          _EVKHA_GRAY,
            "evkha_cream":         _EVKHA_CREAM,
            "evkha_cream_dark":    _EVKHA_CREAM_DARK,
            # Mention obligatoire en cloture absolue (Bloc 5 Consignes)
            "closing_mention":     "Fin de l'étude",
        },
    )


def _country_for_job(job: GenerationJob) -> str:
    try:
        submission = job.order.intake_submission
        return str(submission.normalized_variables.get("PAYS", "")).strip()
    except Exception:  # noqa: BLE001
        return ""


def _title_override(prompt_key: str, country: str, default: str) -> str:
    """Adapte le titre selon la zone geographique (§7 cadrage).

    Aujourd'hui : chapitre 1 EM (mondial + zone macro pertinente).
    """
    from .geography import chapter_title_em_01

    if prompt_key == "em.01.marche_mondial_europeen" and country:
        return chapter_title_em_01(country)
    return default


def _clean_chapter_body(content: str, kind: str) -> str:
    """Pipeline de nettoyage applique a chaque chapitre client.

    1. Strip jargon pipeline interne (Étape, Point de controle, etc.)
    2. Strip blocs Sources intermediaires (sauf si la section EST Sources)
    3. Substitutions anglicismes + jargon (Bloc 3 Consignes)
    """
    body = strip_internal_markers(content)
    if kind != SectionKind.SOURCES:
        body = strip_intermediate_sources(body)
    body = apply_lexical_substitutions(body)
    return body


def render_client_document(job: GenerationJob) -> ClientDocument:
    """Assemble les chapitres DONE en document client, ordre methode EVKHA.

    Applique l'adaptation geographique automatique (§7) et le pipeline de
    nettoyage editorial (Consignes mai 2026).
    """
    blueprints = chapters_for_deliverable(job.deliverable_type)
    kinds = {bp.prompt_key: bp.section_kind for bp in blueprints}
    country = _country_for_job(job)

    done = job.chapters.filter(status=ChapterStatus.DONE)
    sections: list[RenderedSection] = []
    for chapter in done:
        kind = kinds.get(chapter.prompt_key, SectionKind.CHAPTER)
        title = _title_override(chapter.prompt_key, country, chapter.chapter_title)
        sections.append(
            RenderedSection(
                number=chapter.chapter_number,
                title=title,
                kind=kind,
                body=_clean_chapter_body(chapter.content, kind),
            )
        )

    sections.sort(key=lambda s: (_SECTION_ORDER.get(s.kind, 1), s.number))
    return ClientDocument(title=_document_title(job), sections=tuple(sections))
