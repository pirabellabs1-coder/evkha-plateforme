from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from .blueprints import SectionKind, chapters_for_deliverable
from .charts import replace_chart_fences
from .internal_labels import callout_alternation, labels_alternation
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
    # "packager" (verbe) et "packagé/e/s" (adjectif) : le remplacement doit
    # s'accorder. Une substitution unique ("claire et structurée") cassait la
    # grammaire ("un produit packagé" -> "un produit claire et structurée").
    # On mappe vers "structurer/structuré" qui s'accorde comme l'original.
    # Ordre : suffixes les plus longs d'abord (sinon "packagé" matche avant
    # "packagée" et laisse un "e" orphelin).
    (re.compile(r"\bpackagées\b", re.IGNORECASE), "structurées"),
    (re.compile(r"\bpackagés\b", re.IGNORECASE), "structurés"),
    (re.compile(r"\bpackagée\b", re.IGNORECASE), "structurée"),
    (re.compile(r"\bpackagé\b", re.IGNORECASE), "structuré"),
    (re.compile(r"\bpackager\b", re.IGNORECASE), "structurer"),
    # Pitch : variantes specifiques + cas general (eviter "presentation de presentation")
    (re.compile(r"\belevator pitch\b", re.IGNORECASE), "présentation courte"),
    (re.compile(r"\bsales pitch\b", re.IGNORECASE), "argumentaire commercial"),
    (re.compile(r"\bpitch deck\b", re.IGNORECASE), "support de présentation"),
    (
        re.compile(r"\bpitch(?!\w)(?!\s+(?:de\s+)?présentation)\b", re.IGNORECASE),
        "présentation",
    ),
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
    # Accords preserves : pluriel -> pluriel (les regex a remplacement unique
    # produisaient des fautes d'accord dans le livrable).
    (re.compile(r"\bpolarisations\b", re.IGNORECASE), "séparations"),
    (re.compile(r"\bpolarisation\b", re.IGNORECASE), "séparation"),
    (
        re.compile(r"\bconsolidation concurrentielle\b", re.IGNORECASE),
        "concentration des concurrents",
    ),
    (re.compile(r"\bconsolidation du marché\b", re.IGNORECASE), "concentration du marché"),
    (re.compile(r"\bnon[- ]discrétionnaires?\b", re.IGNORECASE), "obligatoire"),
    (re.compile(r"\bnon[- ]discretionnaires?\b", re.IGNORECASE), "obligatoire"),
    (re.compile(r"\bancrage éditorial\b", re.IGNORECASE), "appui éditorial"),
    (re.compile(r"\bancrage editorial\b", re.IGNORECASE), "appui éditorial"),
    (
        re.compile(r"\bincarner le positionnement\b", re.IGNORECASE),
        "rendre le positionnement concret",
    ),
    (re.compile(r"\bactionnables\b", re.IGNORECASE), "applicables"),
    (re.compile(r"\bactionnable\b", re.IGNORECASE), "applicable"),
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


# Filet horizontal markdown : une ligne de 3 tirets ou plus, seule.
# Claude en parseme les chapitres (64 sur le BP SYNAPSES) comme separateurs
# decoratifs. Or `---` est EXACTEMENT ce que Gamma lit comme rupture de carte :
# 64 filets + 19 vraies ruptures = 83 cartes, et Gamma refuse au-dela de 60.
# Ils sont retires quand on compose le markdown destine a Gamma, pour que seules
# NOS ruptures comptent. La forme `|---|` des tableaux ne matche pas (pipes).
_RULE_LINE_RE = re.compile(r"^[ \t]*-{3,}[ \t]*$\n?", re.MULTILINE)


@dataclass(frozen=True)
class ClientDocument:
    title: str
    sections: tuple[RenderedSection, ...]

    def to_markdown(self, *, card_breaks: bool = False) -> str:
        """Document complet en markdown.

        `card_breaks` insère un `---` entre les sections. C'est le séparateur
        que Gamma attend avec `cardSplit=inputTextBreaks` : une carte par
        section, découpage imposé par NOUS.

        Sans ces séparateurs, il faut laisser Gamma décider (`cardSplit=auto`)
        — et son défaut est de 10 cartes. Mesuré sur le BP SYNAPSES : 38 752
        mots compressés en 10 cartes, 90 % du document perdu, 5 verticales sur
        10 effacées, dont le self-stockage et l'hébergement de serveurs — soit
        exactement le défaut que la cliente reprochait au pipeline.
        """
        lines = [f"# {self.title}", ""]
        for index, section in enumerate(self.sections):
            if card_breaks and index > 0:
                lines.append("---")
                lines.append("")
            lines.append(f"## {section.number}. {section.title}")
            lines.append("")
            body = section.body.strip()
            if card_breaks:
                body = _RULE_LINE_RE.sub("", body)
            lines.append(body)
            lines.append("")
        return "\n".join(lines).strip() + "\n"


_CALLOUT_MARKER_RE = re.compile(rf"\[\[/?({callout_alternation()})\]\]")

# Intitules techniques du contexte de generation. Ne doivent JAMAIS fuiter
# dans le livrable (brief client juillet 2026 : "en parfaite coherence avec
# les FAITS_VERROUILLES" est apparu tel quel dans un PDF livre).
#
# La liste vit desormais dans `internal_labels.py`, source UNIQUE partagee avec
# les deux niveaux du gate. Elle etait auparavant recopiee ici et deux fois
# dans gate.py : ajouter un label au contexte sans penser aux trois copies
# rouvrait le defaut (constate sur CHIFFRES_A_CITER).
# 1) Occurrence parenthesee : "(FAITS_VERROUILLES)" -> supprimee entierement.
_INTERNAL_LABEL_PAREN_RE = re.compile(
    r"\s*\(\s*(?:" + labels_alternation() + r")\s*\)"
)
# 2) Occurrence nue dans la prose -> remplacee par une designation naturelle.
# L'article precedent eventuel (les/le/la/aux/des/du...) est absorbe pour ne
# pas produire "les les donnees de reference" apres substitution.
_INTERNAL_LABEL_BARE_RE = re.compile(
    r"(?:\b(?:les|le|la|l'|aux|au|des|de|du)\s+)?"
    r"\b(?:" + labels_alternation() + r")\b",
    re.IGNORECASE,
)


def strip_internal_label_tokens(text: str) -> str:
    """Retire les intitules techniques du contexte fuites dans la redaction.

    Deterministe, sans invention : la forme parenthesee est supprimee (elle
    n'apporte rien au lecteur), la forme nue est remplacee par 'les donnees
    de reference du dossier' (designation fidele de ce que le label contient).
    Le gate de livraison re-verifie ensuite qu'aucun label ne subsiste.
    """
    text = _INTERNAL_LABEL_PAREN_RE.sub("", text)
    return _INTERNAL_LABEL_BARE_RE.sub("les données de référence du dossier", text)


def strip_callout_markers(text: str) -> str:
    """Retire les marqueurs [[UNDERSTAND]] etc. colles au texte ou enchaines.

    Utilise en DERNIER recours (apres conversion Markdown -> HTML) pour
    garantir qu'aucun marqueur brut ne fuit dans le livrable client. Ne doit
    PAS etre applique avant _md_to_html : il detruirait les paires bien
    formees que le parser transforme en encadres mentor stylises (regression
    observee : les encadres etaient rendus en simples paragraphes).
    """
    return _CALLOUT_MARKER_RE.sub("", text)


_CALLOUT_MARKER_INLINE_RE = re.compile(
    r"[ \t]*(\[\[/?(?:UNDERSTAND|CONSIDER|ATTENTION|ACTION)\]\])[ \t]*"
)


def normalize_callout_markers(text: str) -> str:
    """Replace chaque marqueur [[...]] sur sa propre ligne.

    Claude colle parfois les marqueurs au texte (``satisfaisant.[[/UNDERSTAND]]``)
    ou les enchaine (``[[/CONSIDER]][[ATTENTION]]``). En les isolant sur leur
    ligne, le parser _md_to_html reconnait les paires bien formees et les rend
    en encadres mentor ; les orphelins residuels sont scrubes apres conversion
    par strip_callout_markers (aucune fuite possible).
    """
    normalized = _CALLOUT_MARKER_INLINE_RE.sub(r"\n\1\n", text)
    return re.sub(r"\n{3,}", "\n\n", normalized)


_DIAMOND_ARTIFACT_RE = re.compile(r"(?:<>){2,}")


def strip_diamond_artifacts(text: str) -> str:
    """Retire les sequences de losanges ``<><><>`` produites par un rendu HTML corrompu."""
    return _DIAMOND_ARTIFACT_RE.sub("", text)


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
        DeliverableType.MARKET_STUDY: "Étude de marché",
        DeliverableType.COMPETITOR_STUDY: "Étude de la concurrence",
        DeliverableType.BUSINESS_PLAN: "Business plan",
        DeliverableType.BUSINESS_STRATEGY: "Stratégie business",
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
    # __text__ → bold ; __isolé__ (séparateur décoratif) → retiré silencieusement
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\w)__(?!\w)", "", text)
    text = re.sub(r"\*(\S.*?\S|\S)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


_HTML_BLOCK_TAGS = re.compile(
    r"^\s*<(?:/?(?:table|thead|tbody|tr|th|td|div|section|figure|caption|ul|ol|li|"
    r"h[1-6]|blockquote|pre|p|hr|br)\b|!--)",
    re.IGNORECASE,
)


def _sanitize_markdown(text: str) -> str:
    """Pré-traitement avant conversion Markdown → HTML.

    Corrige deux cas pathologiques dans les réponses Claude tronquées :
    1. Table pipe précédée par du texte sans ligne vide → le parser ligne-à-ligne
       traite la ligne précédente comme paragraphe et la table comme table,
       mais des librairies markdown externes rateraient la table. On garantit
       \n\n avant chaque première ligne de table pour la robustesse.
    2. Fence ``` orpheline ouverte en fin de texte sans fermeture → le parser
       produirait un bloc de code infini. On ajoute une fermeture implicite.
    """
    # Garantit \n\n avant la PREMIERE ligne de table pipe (sécurité parser).
    # Exclut "|" du caractère précédent pour ne pas scinder les lignes d'une
    # meme table (qui se terminent aussi par "|") en tableaux séparés.
    text = re.sub(r"([^\n|])\n(\|)", r"\1\n\n\2", text)
    # Ferme les fences ``` ouvertes sans fermeture (troncature Claude)
    fence_opens = len(re.findall(r"^```", text, re.MULTILINE))
    fence_closes = len(re.findall(r"^```\s*$", text, re.MULTILINE))
    if fence_opens > fence_closes:
        text = text.rstrip() + "\n```"
    return text


def _md_to_html(text: str) -> str:
    """Convertit le Markdown EVKHA en HTML propre (headings, listes, bold, italic).

    Implémentation légère sans dépendance externe, suffisante pour le contenu
    structuré généré par Claude.
    Supporte :
    - Titres, listes ul/ol, blockquote, hr, paragraphes
    - Tables pipe Markdown (| col | val | …)
    - Blocs HTML bruts émis par les prompts visuels (SWOT, cartographie, charts)
    """
    text = _sanitize_markdown(text)
    lines = text.split("\n")
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # ── Blocs HTML bruts (SWOT, risk matrix, graphiques en HTML) ─────────
        # Passthrough : aucun escape, aucun wrapping <p>.
        if _HTML_BLOCK_TAGS.match(line):
            html_block: list[str] = []
            while i < len(lines) and (
                _HTML_BLOCK_TAGS.match(lines[i]) or (html_block and lines[i].strip())
            ):
                html_block.append(lines[i])
                i += 1
            out.append("\n".join(html_block))
            continue

        # ── Séparateur horizontal ─────────────────────────────────────────────
        if re.match(r"^[-*_]{3,}\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        # ── Titres ───────────────────────────────────────────────────────────
        # (Le tableau markdown pipe est traité plus bas par le parseur complet
        # avec ligne séparateur — cf. "── Table pipe Markdown ──")
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = min(len(m.group(1)) + 1, 4)  # # → h2, ## → h3, ### → h4
            out.append(f"<h{level}>{_md_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # ── Blockquote ───────────────────────────────────────────────────────
        if line.startswith("> "):
            items: list[str] = []
            while i < len(lines) and lines[i].startswith("> "):
                items.append(_md_inline(lines[i][2:]))
                i += 1
            out.append("<blockquote><p>" + "</p><p>".join(items) + "</p></blockquote>")
            continue

        # ── Table pipe Markdown ───────────────────────────────────────────────
        # Détecte : ligne commençant et finissant par | (ou contenant au moins 2 |)
        if re.match(r"^\s*\|", line) and line.count("|") >= 2:
            header_rows: list[str] = []
            body_rows: list[str] = []
            is_header = True
            while i < len(lines) and re.match(r"^\s*\|", lines[i]):
                row = lines[i].strip().strip("|")
                # Ligne séparateur (|---|---|) → marque fin du header
                if re.match(r"^[\s|:\-]+$", row):
                    is_header = False
                    i += 1
                    continue
                cells = [c.strip() for c in row.split("|")]
                if is_header:
                    cell_html = "".join(f"<th>{_md_inline(c)}</th>" for c in cells)
                    header_rows.append(f"<tr>{cell_html}</tr>")
                    is_header = False  # première vraie ligne = header
                else:
                    cell_html = "".join(f"<td>{_md_inline(c)}</td>" for c in cells)
                    body_rows.append(f"<tr>{cell_html}</tr>")
                i += 1
            if header_rows or body_rows:
                # Génère <table><thead>…</thead><tbody>…</tbody></table>.
                # Le chunking sur tableaux longs est délégué à chunk_long_tables()
                # (post-processeur BeautifulSoup) qui couvre aussi les <table>
                # HTML directement émis par Claude dans les prompts visuels.
                header_html = (
                    "<thead>" + "".join(header_rows) + "</thead>" if header_rows else ""
                )
                out.append(
                    "<table>"
                    + header_html
                    + "<tbody>"
                    + "".join(body_rows)
                    + "</tbody></table>"
                )
            continue

        # ── Liste non ordonnée ───────────────────────────────────────────────
        if re.match(r"^[-*]\s", line):
            list_items: list[str] = []
            while i < len(lines) and re.match(r"^[-*]\s", lines[i]):
                list_items.append(f"<li>{_md_inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(list_items) + "</ul>")
            continue

        # ── Liste ordonnée ───────────────────────────────────────────────────
        # QC Evangeline #4 : renumérotation séquentielle. Claude produisait
        # parfois "1. Coach\n1. Web\n1. Livraison...". Le HTML <ol> renumerote
        # automatiquement, mais on nettoie le numero source du contenu du <li>
        # pour ne pas afficher "1. 1. Coach".
        if re.match(r"^\d+[.)]\s", line):
            ol_items: list[str] = []
            while i < len(lines) and re.match(r"^\d+[.)]\s", lines[i]):
                content = re.sub(r"^\d+[.)]\s+", "", lines[i])
                ol_items.append(f"<li>{_md_inline(content)}</li>")
                i += 1
            out.append("<ol>" + "".join(ol_items) + "</ol>")
            continue

        # ── Code fence (```lang ... ```) ─────────────────────────────────────
        # Claude peut envelopper du HTML dans ```html ... ```. On dépouille
        # les marqueurs de fence : les blocs ```html sont passés tels quels
        # (HTML brut déjà structuré), les autres langages sont supprimés
        # silencieusement (JSON, Python, etc. n'ont pas leur place en livrable).
        m_fence = re.match(r"^```(\w*)\s*$", line)
        if m_fence:
            lang = m_fence.group(1).lower()
            i += 1
            fence_lines: list[str] = []
            while i < len(lines) and not re.match(r"^```\s*$", lines[i]):
                fence_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # saute la fence fermante
            if lang in ("html", ""):
                out.append("\n".join(fence_lines))
            # autres langages (python, json…) → supprimés
            continue

        # QC Evangeline #7a : blocs graphiques inline sur une ligne
        # ◆ Ce qu'il faut comprendre : ...  → callout stylé
        # → Ce qu'il faut envisager : ...   → callout action
        # ! Attention : ...                  → callout warning
        callout_match = re.match(r"^\s*([◆→!✓])\s*(.+)$", line)
        if callout_match:
            marker, rest = callout_match.groups()
            kind = {"◆": "understand", "→": "consider", "!": "attention", "✓": "action"}[marker]
            label = {
                "understand": "Ce qu'il faut comprendre",
                "consider": "Ce qu'il faut envisager",
                "attention": "Attention",
                "action": "Action concrète",
            }[kind]
            # Cas "◆ Ce qu'il faut comprendre : contenu" → sépare label et contenu
            body_after = re.sub(
                r"^(?:Ce qu['’]il faut comprendre|Ce qu['’]il faut envisager"
                r"|Attention|Action concr[èe]te)\s*[:\-]\s*",
                "",
                rest,
                flags=re.IGNORECASE,
            )
            out.append(
                f'<div class="callout callout--{kind}">'
                f'<div class="callout__label">{label}</div>'
                f'<div class="callout__body">{_md_inline(body_after)}</div>'
                f'</div>'
            )
            i += 1
            continue

        # Marqueurs parseables [[UNDERSTAND]] ... [[/UNDERSTAND]] (Fix #7b)
        block_open = re.match(r"^\s*\[\[(UNDERSTAND|CONSIDER|ATTENTION|ACTION)\]\]\s*$", line)
        if block_open:
            kind_upper = block_open.group(1)
            kind = kind_upper.lower()
            label = {
                "understand": "Ce qu'il faut comprendre",
                "consider": "Ce qu'il faut envisager",
                "attention": "Attention",
                "action": "Action concrète",
            }[kind]
            i += 1
            block_lines: list[str] = []
            close_re = re.compile(rf"^\s*\[\[/{kind_upper}\]\]\s*$")
            while i < len(lines) and not close_re.match(lines[i]):
                block_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # skip closing marker
            inner_html = _md_to_html("\n".join(block_lines))
            out.append(
                f'<div class="callout callout--{kind}">'
                f'<div class="callout__label">{label}</div>'
                f'<div class="callout__body">{inner_html}</div>'
                f'</div>'
            )
            continue

        # ── Ligne vide ───────────────────────────────────────────────────────
        if not line.strip():
            out.append("")
            i += 1
            continue

        # ── Paragraphe ───────────────────────────────────────────────────────
        out.append(f"<p>{_md_inline(line)}</p>")
        i += 1

    return "\n".join(out)


def _decouper_si_demande(html: str, chunk_tables: bool) -> str:
    """Decoupe les tableaux longs, sauf si le mode reparation l'interdit."""
    return chunk_long_tables(html) if chunk_tables else html


def render_branded_html(
    job: GenerationJob,
    *,
    branding: BrandingContext | None = None,
    chunk_tables: bool = True,
) -> str:
    """Rend le livrable complet en HTML A4 brandé client.

    Utilisé par WeasyPrintPdfClient pour générer le PDF final (D8).
    Le branding est extrait de l'intake Tally (LOGO_URL, COULEUR_PRINCIPALE,
    COULEUR_SECONDAIRE, NOM_ENTREPRISE) avec fallback palette EVKHA.

    `chunk_tables=False` desactive le decoupage des tableaux longs. C'est la
    SEULE etape du rendu qui reecrit la structure du document — donc la seule
    qui peut en perdre. Elle a deja detruit les lignes des tableaux financiers
    (`tbody.decompose()`), et le client a recu `<tbody><></><></></tbody>` a la
    place du compte de resultat.

    Le bug est corrige, mais `documents/services.py` s'en sert comme REPARATION :
    si le controle de sortie detecte une perte, on re-rend sans decoupage et on
    recontrole. Un tableau qui deborde d'une page est moins beau ; un tableau
    ampute est faux. On prefere toujours le moins beau.
    """
    from django.template.loader import render_to_string

    if branding is None:
        branding = extract_branding(job)

    from .visuals import visual_breaks_html_for

    document = render_client_document(job)
    visual_breaks = visual_breaks_html_for(job.deliverable_type)
    sections_ctx = [
        {
            "number": s.number,
            "title": s.title,
            "kind": s.kind,
            # Pipeline HTML : md→html → scrub des marqueurs [[...]] orphelins
            # (les paires bien formées sont déjà rendues en encadrés mentor)
            # → fermeture balises orphelines → chunking tableaux longs
            # (BeautifulSoup). L'ordre est critique : chunk_long_tables doit
            # opérer sur du HTML valide (post close_dangling_html_tags) pour
            # que le parser DOM ne rencontre pas de balises ouvertes.
            "body_html": _decouper_si_demande(
                close_dangling_html_tags(strip_callout_markers(_md_to_html(s.body))),
                chunk_tables,
            ),
            # Idem sur les visual breaks : un <table> non fermé dans un break
            # absorberait tous les chapitres suivants dans WeasyPrint.
            "visual_after_html": _decouper_si_demande(
                close_dangling_html_tags(visual_breaks.get(s.number, "")),
                chunk_tables,
            ),
        }
        for s in document.sections
    ]
    photos = extract_photos(job)

    return render_to_string(
        "generation/document.html",
        {
            "title": document.title,
            "branding": branding,
            "country": _country_for_job(job),  # Mention pays sur page de garde (Bloc 1 Consignes)
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


_HTML_CONTAINER_TAGS: tuple[str, ...] = (
    "style", "script", "table", "thead", "tbody", "tfoot", "tr", "td", "th",
    "div", "section", "figure", "figcaption", "ul", "ol", "li", "blockquote",
    "pre", "span",
)
_HTML_TAG_RE = re.compile(
    r"<\s*(/?)\s*("
    + "|".join(_HTML_CONTAINER_TAGS)
    + r")\b[^>]*?>",
    re.IGNORECASE,
)


_TRAILING_INCOMPLETE_TAG_RE = re.compile(r"<\s*/?\s*[a-zA-Z][^<>]*\Z")


def strip_incomplete_trailing_tag(html: str) -> str:
    """Retire un tag HTML tronque en toute fin de contenu (troncature max_tokens).

    Une troncature qui coupe en plein milieu d'un attribut (ex: un `style="..."`
    coupe a `background:#`) laisse un guillemet jamais referme. Ce cas est pire
    qu'une balise simplement non fermee (gere par close_dangling_html_tags) :
    le tag est incomplet (pas de `>` final), donc invisible pour son parseur
    stack-based. Sans ce nettoyage, le guillemet ouvert fait que le parseur
    HTML5 de WeasyPrint reste en etat "valeur d'attribut" et avale tout le
    contenu suivant, y compris les chapitres suivants, comme du texte
    d'attribut invisible — d'ou des documents qui semblent s'arreter en cours
    de generation alors que tous les chapitres sont bien presents en base.
    """
    match = _TRAILING_INCOMPLETE_TAG_RE.search(html)
    if not match:
        return html
    return html[: match.start()].rstrip()


def close_dangling_html_tags(html: str) -> str:
    """Ferme les balises HTML restees ouvertes en fin de contenu.

    Une reponse Claude tronquee sur max_tokens peut se terminer au milieu d'un
    <table> ou d'un <style> — si on n'ajoute pas les fermetures, le bloc
    "aspire" tous les chapitres suivants au rendu PDF (WeasyPrint reste dans
    la table structurellement, l'utilisateur voit ses chapitres disparaitre).
    Sanitizer stack-based, tolerant : ignore les mismatches, ne touche jamais
    au contenu textuel.
    """
    stack: list[str] = []
    for match in _HTML_TAG_RE.finditer(html):
        is_closing = match.group(1) == "/"
        tag = match.group(2).lower()
        if is_closing:
            for idx in range(len(stack) - 1, -1, -1):
                if stack[idx] == tag:
                    del stack[idx:]
                    break
        else:
            stack.append(tag)
    if not stack:
        return html
    return html + "".join(f"</{t}>" for t in reversed(stack))


_MAX_ROWS_PER_TABLE = 15  # Au-delà : découpage avec saut de page A4


def chunk_long_tables(html_content: str, max_rows: int = _MAX_ROWS_PER_TABLE) -> str:
    """Post-processeur BeautifulSoup : découpe les tableaux longs en sous-blocs A4.

    Opère sur le HTML *après* conversion Markdown → HTML, ce qui garantit que
    toutes les tables sont traitées : tables pipe Markdown ET tables HTML
    directement émises par Claude dans les prompts visuels (financier, SWOT…).

    Principe : si un <tbody> contient plus de `max_rows` lignes, on éclate le
    tableau en N sous-tableaux de max_rows lignes chacun, séparés par un
    <div style="page-break-before:always"> afin que WeasyPrint insère un saut
    de page A4 propre entre chaque morceau. Le <thead> est dupliqué dans chaque
    sous-tableau pour la lisibilité sur la nouvelle page.
    """
    from bs4 import BeautifulSoup  # import paresseux — dépendance optionnelle pdf

    soup = BeautifulSoup(html_content, "html.parser")
    for table in soup.find_all("table"):
        tbody = table.find("tbody")
        if not tbody:
            continue
        rows = tbody.find_all("tr", recursive=False)
        if len(rows) <= max_rows:
            continue

        thead = table.find("thead")
        # bs4 rend les attributs multi-valués (class, rel...) sous forme de
        # liste : ["chapter__body", "wide"]. On les re-sérialise en chaîne,
        # sinon le nouveau <table> hérite d'un attribut invalide et perd son
        # style — le tableau scindé ne ressemblerait plus au tableau d'origine.
        table_attrs: dict[str, str] = {
            key: " ".join(value) if isinstance(value, list) else str(value)
            for key, value in table.attrs.items()
        }

        # DETACHER les lignes AVANT de supprimer le <tbody>.
        #
        # `tbody.decompose()` detruit l'element ET TOUS SES ENFANTS, et libere
        # leur memoire. Or `rows` contient precisement ces enfants : les lignes
        # etaient donc detruites juste avant d'etre recopiees, et le code
        # reinserait des cadavres. Rendu final :
        #     <tbody><></><></><></>...</tbody>
        # C'est LA cause des « tableaux tronques » signales de longue date par
        # la cliente. Le defaut ne frappe que les tableaux de plus de
        # `max_rows` lignes — donc les tableaux financiers, les plus denses et
        # les plus regardes dans un dossier bancaire.
        #
        # `extract()` detache sans detruire : la ligne survit et reste
        # reinserable.
        lignes = [row.extract() for row in rows]
        tbody.decompose()
        new_tbody = soup.new_tag("tbody")
        table.append(new_tbody)
        current_table = table
        current_tbody = new_tbody
        row_count = 0

        for row in lignes:
            if row_count >= max_rows:
                # Saut de page WeasyPrint
                break_div = soup.new_tag(
                    "div", style="page-break-before:always; height:0;"
                )
                current_table.insert_after(break_div)
                # Nouveau tableau identique (mêmes attributs CSS)
                # `attrs=` plutot que `**table_attrs` : le dépaquetage entre en
                # collision avec les parametres nommes de new_tag (namespace,
                # nsprefix, sourceline...), que mypy tente alors de satisfaire
                # avec les valeurs du dict.
                new_table = soup.new_tag("table", attrs=table_attrs)
                if thead:
                    from bs4 import BeautifulSoup as _BS

                    cloned_thead = _BS(str(thead), "html.parser").find("thead")
                    if cloned_thead:
                        new_table.append(cloned_thead)
                current_tbody = soup.new_tag("tbody")
                new_table.append(current_tbody)
                break_div.insert_after(new_table)
                current_table = new_table
                row_count = 0

            current_tbody.append(row)
            row_count += 1

    return str(soup)


def _clean_chapter_body(content: str, kind: str) -> str:
    """Pipeline de nettoyage applique a chaque chapitre client.

    1. Strip jargon pipeline interne (Étape, Point de controle, etc.)
    2. Strip blocs Sources intermediaires (sauf si la section EST Sources)
    3. Substitutions anglicismes + jargon (Bloc 3 Consignes)
    4. Retire un tag HTML tronque en toute fin de contenu (guillemet d'attribut
       jamais referme par une troncature max_tokens)
    5. Ferme les balises HTML orphelines restantes (protection contre les
       troncatures max_tokens qui font disparaitre les chapitres suivants au
       rendu PDF)
    """
    body = strip_internal_markers(content)
    body = strip_internal_label_tokens(body)
    body = normalize_callout_markers(body)
    body = strip_diamond_artifacts(body)
    if kind != SectionKind.SOURCES:
        body = strip_intermediate_sources(body)
    body = apply_lexical_substitutions(body)
    # Remplace les blocs ```chart {...JSON...}``` par du SVG inline avant que
    # le pipeline markdown ne les traite comme du code. Fait ici pour que la
    # section Sources ne soit pas graphifiee et que le nettoyage editorial
    # s'applique aussi au SVG (aucun em-dash n'est produit par le renderer).
    body = replace_chart_fences(body)
    body = strip_incomplete_trailing_tag(body)
    body = close_dangling_html_tags(body)
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
