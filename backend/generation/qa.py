"""Post-génération QA : détection et correction des violations qualité.

Chaque condition de "génération parfaite" est vérifiée indépendamment.
Pour chaque violation détectée, une correction ciblée est appliquée avant
la livraison du document.

Conditions vérifiées (par ordre de priorité) :
  Critiques (bloquent la qualité visuelle) :
    0. empty_content         — chapitre vide ou quasi-vide (retour anticipé)
    1. sentence_cut          — RÈGLE PRIORITAIRE : dernière phrase de prose
                               sans ponctuation terminale. Réparée par ajout
                               déterministe d'un point (sans appel IA).
                               Quels que soient le quota et les tokens
                               alloués, toute phrase commencée doit se
                               terminer par un point.
    2. code_fence            — marqueurs ``` visibles dans le rendu
    3. cut_html_table        — balise <table> non fermée
    4. truncated_in_tag      — contenu se termine dans une balise ouverte
    5. incomplete_pipe_table — dernière ligne de tableau MD incomplète
    6. below_min_length      — chapitre trop court (troncature probable)

  Qualité (dégradent le rendu sans bloquer) :
    7. internal_markers      — jargon pipeline fuité (Étape, Pipeline…)
    8. intermediate_sources  — section Sources dans un chapitre intermédiaire
    9. raw_html_entities     — balises HTML encodées visibles (&lt;table&gt;)
   10. conversational_ai     — tournures IA à bannir (il apparaît que…)
   11. missing_subsections   — numérotation sous-sections non consécutive
   12. abrupt_ending         — dernier paragraphe trop court / préposition
                               pendante → réparation IA (continuation)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple

from .checks_post_rendu import TITRE_EN_GRAS, sans_emphase, sans_fioritures_finales

# ── Constantes de détection ───────────────────────────────────────────────────

_CODE_FENCE_RE = re.compile(r"```")
_TABLE_OPEN_RE = re.compile(r"<table\b", re.IGNORECASE)
_TABLE_CLOSE_RE = re.compile(r"</table>", re.IGNORECASE)

# Détecte les sous-titres numérotés style "### 3.1" ou "## 3.1" ou "**3.1"
_SUBSECTION_HEADING_RE = re.compile(
    r"^(?:#{1,4}\s+|(?:\*\*)?)\d+\.(\d+)(?:\s|\*|\.|:)",
    re.MULTILINE,
)

# Balises de bloc ouvertes sans fermeture → absorbent le contenu suivant
_DANGLING_BLOCK_RE = re.compile(
    r"<(?:td|th|tr|li|p|div|ul|ol|section|thead|tbody|tfoot)\b[^>]*>[^<]*$",
    re.IGNORECASE,
)

# Entités HTML mal encodées visibles dans le texte
_HTML_ENTITY_TAG_RE = re.compile(
    r"&lt;(?:table|tr|td|th|div|ul|ol|li|p)\b",
    re.IGNORECASE,
)

# Tournures IA conversationnelles interdites (Charte EVKHA)
_CONVERSATIONAL_AI_RE = re.compile(
    r"\b(?:il\s+apparaît\s+que|il\s+apparait\s+que|on\s+peut\s+observer\s+que"
    r"|il\s+convient\s+de\s+noter\s+que?|il\s+convient\s+de\s+noter"
    r"|dynamique\s+porteuse)\b",
    re.IGNORECASE,
)

# Fin de contenu abrupte : le dernier paragraphe est trop court ET ne se termine
# pas par une ponctuation de fin de phrase → troncature Claude probable.
_SENTENCE_END_RE = re.compile(r"[.!?»’…]\s*$")

# Phrase de prose se terminant par une lettre (non un chiffre/paren/…) sans
# ponctuation terminale → règle 1 « sentence_cut ».
_TERMINAL_LETTER_RE = re.compile(r"[a-zA-ZÀ-ÿ]\s*$")

# Mots qui ne peuvent PAS terminer une phrase française, même suivis d'un point.
# La règle 1 (sentence_cut) répare une phrase coupée en ajoutant un point ; sur
# une vraie troncature, cette réparation la MASQUE. Constaté en génération réelle
# (job 4c573e40, 24/07/2026) : le chapitre 21 finissait sur « ... redéployée vers
# des tâches à. » — ponctuation valide, troncature bien réelle, aucun détecteur
# déterministe ne la voyait (seul le relecteur Sonnet l'a signalée).
# Uniquement des prépositions/déterminants : on exclut « plus », « moins »,
# « bien », « peu », qui terminent légitimement une phrase.
_HANGING_BEFORE_PERIOD_RE = re.compile(
    r"\b(?:à|a|de|du|des|la|le|les|un|une|en|au|aux|par|pour|sur|avec|dans"
    r"|vers|entre|dont|chez|sous|selon|parmi|et|ou|dès|puis)\s*[.]\s*$",
    re.IGNORECASE,
)

# Mots qui suggèrent une phrase inachevée quand ils sont en toute fin de contenu
_HANGING_WORDS_RE = re.compile(
    r"\b(?:notamment|particulier|tels?\s+que|comme|soit|entre|pour|dont"
    r"|avec|par|sur|ainsi|et|ou|mais|car|donc|or|ni|de|du|la|le|les|une|un"
    r"|des|en|au|aux|qui|que|quand|si|bien|peu|très|plus|moins)\s*$",
    re.IGNORECASE,
)

# Seuils de longueur minimale (mots) par type de section.
# 400 mots pour "chapter" : en-dessous, la troncature est quasi-certaine
# même pour des chapitres analytiques courts.
_MIN_WORDS: dict[str, int] = {
    "opening": 100,
    "chapter": 400,
    "annexe":  200,
    "sources":  30,
}

# Seuils spécifiques par prompt_key (remplacent le seuil générique "chapter").
# Valeurs basées sur le volume de contenu attendu par chapitre.
_MIN_WORDS_BY_KEY: dict[str, int] = {
    # ── EC — clés de CHAPITRE (prompt_key de ChapterGeneration) ─────────────
    # La QA recoit chapter.prompt_key qui est la cle CHAPITRE (ex.
    # "ec.02.classement_qualitatif"), pas les cles de section. Ces entrees
    # couvrent le chapitre fusionne (sections a + b concatenees).
    "ec.01.identification":          1000,  # 11 concurrents × ~120 mots
    "ec.02.classement_qualitatif":   1700,  # 8 directs (~1200) + 3 indirects (~500)
    "ec.03.approfondissement":       2200,  # 8 directs (~1600) + 3 indirects (~600)
    # ── EC — clés de SECTION (pour reference ; non matchees par la QA) ──────
    "ec.02.a.directs":      1200,   # 8 × (3F + 3F + VA) ≈ 1440 mots
    "ec.02.b.indirects":     450,   # 3 × 180 = 540 mots
    "ec.03.a.directs":      1600,   # 8 × 250 = 2000 mots
    "ec.03.b.indirects":     600,   # 3 × 250 = 750 mots
    # ── EM ──────────────────────────────────────────────────────────────────
    "em.01.a.mondial":       500,
    "em.01.b.europeen":      500,
    # Chapitre 2 genere en un seul appel (calcul TAM/SAM/SOM indivisible) :
    # la QA recoit donc la cle CHAPITRE. Seuil = les deux anciens seuils de
    # section additionnes, sinon le chapitre fusionne passerait la QA en
    # ecrivant la moitie du contenu attendu.
    "em.02.marche_national_local": 1000,
    "em.09.douze_chiffres_cles": 600,   # 12 métriques sourcées
    "em.10.a.profil_besoins":    500,
    "em.10.b.comportements":     500,
    "em.10.c.criteres_decision": 500,
    "em.12.risques_plan_gestion": 600,  # risques + plan de mitigation
    "em.14.a.hypotheses":    500,
    "em.14.b.projections":   600,
    "em.14.c.viabilite":     400,
    "em.15.graphiques_tableaux": 300,   # beaucoup de HTML, mots sous-comptés
    "em.18.swot":            400,
    "em.19.a.diagnostic":    500,
    "em.19.b.plan_action":   500,
    # ── BP ──────────────────────────────────────────────────────────────────
    "bp.08.offre_commerciale":    500,
    "bp.10.strategie_commerciale": 500,
    "bp.12.organisation_moyens":   500,
    "bp.14.investissements":       400,
    "bp.16.a.comptes_resultats":   500,
    "bp.16.b.bilan_projection":    500,
    "bp.17.budget_tresorerie":     500,
    # ── STR ──────────────────────────────────────────────────────────────────
    "str.04.forces_structurelles":      500,
    "str.05.contraintes_fragilites":    500,
    "str.07.verticales_strategiques":   500,
    "str.10.architecture_offre":        500,
    "str.13.strategie_visibilite":      500,
    "str.17.feuille_route":             500,
}

_QA_COMPLETION_TOKENS = 1800
# Tokens alloues a la generation des sous-sections manquantes (chaque section
# EC represente ~475 mots / ~640 tokens : 2 sections = ~1280 tokens, marge incluse).
_QA_SUBSECTION_TOKENS = 3000


# ── Types de données ──────────────────────────────────────────────────────────


@dataclass
class ConditionViolation:
    name: str
    severity: str  # "critical" | "quality"
    detail: str


class QAResult(NamedTuple):
    chapter_number: int
    prompt_key: str
    violations_found: list[str]
    fixes_applied: list[str]
    ai_repaired: bool
    passed: bool  # True si aucune violation critique subsiste après corrections


# ── Utilitaires ───────────────────────────────────────────────────────────────


#: Lignes qui ne sont PAS de la prose, et qu'on ne juge donc pas comme telle.
#:
#: **Mesuré sur le dossier réel `c8b4e60a` du 09/08/2026** — une étude d'une
#: cliente, bloquée à la livraison par le gate. Quatre motifs `sentence_cut`,
#: dont TROIS étaient faux :
#:
#:     ch. 3  : « **CRITÈRE DE SÉLECTION BTOB »       → un intitulé en capitales
#:     ch. 8  : « *EVKHA, à partir du socle verrouillé » → une ligne de source
#:     ch. 4  : « ion_cible, panier_moyen, sam, … »   → des identifiants du socle
#:
#: Aucune de ces lignes n'a de ponctuation finale, et aucune n'en réclame : ce
#: ne sont pas des phrases. Le gate a donc retenu un document de vingt-trois
#: chapitres, à 5,26 EUR, pour une faute qui n'existait pas.
#:
#: C'est la règle 2 dans sa forme la plus chère : un contrôle qui compare à une
#: donnée MAL EXTRAITE est pire qu'absent. Ici il ne se contente pas d'un motif
#: faux — il bloque la livraison.
#:
#: `_last_prose_line` écartait déjà les titres Markdown, les tableaux, les
#: puces. Il lui manquait ces trois formes, et elles ont suffi.
#:
#: ## Ce que ce correctif avait laissé passer, et qui est revenu
#:
#: Étude de marché `f0064333` du 17/08/2026 — la même cliente, le même
#: chapitre 3, la MÊME ligne :
#:
#:     sentence_cut: Dernière phrase sans ponctuation finale :
#:     …'**CRITÈRE DE SÉLECTION BTOB'
#:
#: L'expression ci-dessous accepte les astérisques OUVRANTES (`^\**`) et pas
#: les FERMANTES : ancrée sur `$`, elle ne matche donc jamais la ligne
#: complète « **CRITÈRE DE SÉLECTION BTOB** » telle qu'elle est écrite. Le
#: motif du 09/08 avait été relevé APRÈS le passage de `sans_fioritures_finales`,
#: qui avait déjà retiré la queue — on a corrigé sur la trace, pas sur la ligne.
#:
#: C'est la règle 4 dans sa forme la plus exacte : le correctif énumérait un
#: délimiteur et oubliait son symétrique. La réponse n'est donc pas d'ajouter
#: `\**$` — ce serait énumérer encore — mais de RETIRER l'emphase une fois pour
#: toutes avant de juger, de sorte qu'aucun de ces motifs n'ait plus à
#: connaître les astérisques.
_NON_PROSE_RES = (
    # Intitulé en capitales : « CRITÈRE DE SÉLECTION BTOB ».
    # Au moins deux mots capitalisés d'affilée — un sigle isolé dans une phrase
    # (« le CA progresse ») n'en fait pas un titre.
    re.compile(r"^[A-ZÀ-Ý][A-ZÀ-Ý0-9\s'’\-]{6,}$"),
    # Un titre en gras, quelle que soit sa casse. Même règle que
    # `checks_post_rendu`, et c'est SA règle qu'on importe : les deux modules
    # jugeaient « cette ligne est-elle une phrase ? » séparément, et ils
    # n'étaient pas d'accord (règle 5).
    TITRE_EN_GRAS,
    # Ligne de source : le rendu les écrit en italique, elles finissent sans
    # point. « *Source : Insee, 2025* », « *EVKHA, à partir du socle verrouillé* ».
    re.compile(r"^\**\s*(?:sources?\s*[:—-]|.*\bà partir du socle\b)", re.IGNORECASE),
    # Résidu d'un marqueur de graphique : une énumération d'identifiants du
    # socle, en minuscules avec des tirets bas, sans verbe.
    re.compile(r"^[a-z0-9_]+(?:\s*,\s*[a-z0-9_]+){2,}\s*$"),
)


def _est_de_la_prose(ligne: str) -> bool:
    """Cette ligne est-elle une phrase, ou une étiquette ?

    Séparée de `_last_prose_line` pour être testable seule : c'est elle qui a
    bloqué une livraison réelle, et une fonction qu'on ne peut pas interroger
    directement se corrige à l'aveugle.

    Jugée sur la ligne TELLE QU'ÉCRITE **et** sur son texte nu : un titre en
    gras a besoin de ses astérisques pour être reconnu comme tel, un intitulé
    en capitales a besoin qu'on les lui retire. Les deux lectures, plutôt
    qu'une expression par délimiteur — c'est le défaut qui a fait revenir le
    même motif faux deux fois sur le même chapitre (règle 4).
    """
    nu = sans_emphase(ligne)
    return not any(
        motif.match(ligne) or motif.match(nu) for motif in _NON_PROSE_RES
    )


def _last_prose_line(text: str) -> str:
    """Retourne la dernière ligne de prose lisible (≥4 mots, non-titre/tableau/HTML).

    Utilisée par la règle 1 (sentence_cut) pour détecter si la dernière phrase
    de prose se termine sans ponctuation.
    """
    plain = re.sub(r"<[^>]+>", " ", text)
    lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
    for line in reversed(lines):
        if not _est_de_la_prose(line):
            continue
        # Ignorer les titres Markdown, les lignes de tableau, les balises nues,
        # les listes, les délimiteurs de code.
        # « * » et « - » ne sont des puces que suivis d'une espace : un
        # paragraphe ouvrant sur du gras (« **Ce que cela signifie pour X.** »
        # — l'encadré prescrit par le manuel à chaque chapitre) est de la
        # prose. Le sauter faisait remonter, en génération réelle
        # (job 4c573e40, 24/07/2026), une cellule de tableau bien plus haut
        # comme « dernière phrase » et déclenchait un faux sentence_cut.
        if re.match(r"^(?:#|[|<`]|\d+[.)]\s|[-*]\s)", line):
            continue
        if len(line.split()) < 4:
            continue
        return line
    return ""


def _add_terminal_period(content: str) -> str:
    """Insère un point après le dernier mot de prose, avant les balises de fermeture.

    Stratégie : séparer le « corps » (texte) des balises HTML fermantes
    éventuelles en queue, ajouter le point sur le corps, réassembler.
    """
    s = content.rstrip()
    m = re.search(r"((?:\s*</\w+>)+\s*)$", s)
    if m:
        tail = m.group(0)
        core = s[: m.start()].rstrip()
    else:
        tail = ""
        core = s
    if core and not _SENTENCE_END_RE.search(core):
        core += "."
    return core + tail


def _infer_section_kind(prompt_key: str, chapter_number: int) -> str:
    if chapter_number == 0:
        return "opening"
    pk = prompt_key.lower()
    if "sources" in pk:
        return "sources"
    if "annexe" in pk or "annex" in pk:
        return "annexe"
    return "chapter"


def _is_sources_chapter(prompt_key: str, chapter_number: int) -> bool:
    return _infer_section_kind(prompt_key, chapter_number) == "sources"


def _word_count(content: str) -> int:
    """Compte les mots en ignorant les balises HTML et les marqueurs Markdown."""
    text = re.sub(r"<[^>]+>", " ", content)
    text = re.sub(r"[|#*_`]", " ", text)
    return len(text.split())


# ── Détection ────────────────────────────────────────────────────────────────


def detect_violations(
    content: str,
    prompt_key: str,
    chapter_number: int,
) -> list[ConditionViolation]:
    """Retourne la liste complète des violations qualité pour un chapitre."""
    violations: list[ConditionViolation] = []
    stripped = content.strip()

    # 0. Contenu vide
    if not stripped or len(stripped) < 10:
        violations.append(ConditionViolation(
            "empty_content", "critical", "Chapitre vide ou quasi-vide",
        ))
        return violations  # inutile de continuer

    # 1. RÈGLE PRIORITAIRE — phrase sans ponctuation terminale
    # Quels que soient le quota et les tokens alloués, toute phrase commencée
    # doit se terminer par un point. Réparée de façon déterministe (ajout d'un
    # point) sans appel IA.
    # Le gras/italique de fermeture vient APRES le point : on juge le texte,
    # pas le délimiteur (« ... la structure.* » n'est pas une troncature).
    last_prose = sans_fioritures_finales(_last_prose_line(stripped))
    if (
        last_prose
        and not _SENTENCE_END_RE.search(last_prose)
        and _TERMINAL_LETTER_RE.search(last_prose)
    ):
        violations.append(ConditionViolation(
            "sentence_cut",
            "critical",
            f"Dernière phrase sans ponctuation finale : …{last_prose[-80:]!r}",
        ))

    # 2. Code fences
    if _CODE_FENCE_RE.search(content):
        violations.append(ConditionViolation(
            "code_fence", "critical", "Marqueurs ``` présents dans le contenu",
        ))

    # 3. Tables HTML coupées
    open_t = len(_TABLE_OPEN_RE.findall(content))
    close_t = len(_TABLE_CLOSE_RE.findall(content))
    if open_t > close_t:
        violations.append(ConditionViolation(
            "cut_html_table", "critical",
            f"{open_t} <table> ouvertes, {close_t} </table> fermées",
        ))

    # 4. Contenu tronqué dans une balise ouverte
    if _DANGLING_BLOCK_RE.search(stripped):
        violations.append(ConditionViolation(
            "truncated_in_tag", "critical",
            "Contenu se termine à l'intérieur d'une balise HTML ouverte",
        ))

    # 5. Ligne pipe-table incomplète en fin de contenu
    last_line = stripped.split("\n")[-1].strip()
    if re.match(r"^\|[^|]+$", last_line):
        violations.append(ConditionViolation(
            "incomplete_pipe_table", "critical",
            "Dernière ligne de tableau Markdown incomplète",
        ))

    # 6. Longueur insuffisante
    sk = _infer_section_kind(prompt_key, chapter_number)
    min_w = _MIN_WORDS_BY_KEY.get(prompt_key) or _MIN_WORDS.get(sk, 200)
    wc = _word_count(stripped)
    if wc < min_w:
        violations.append(ConditionViolation(
            "below_min_length", "critical",
            f"{wc} mots < minimum {min_w} attendus ({prompt_key!r})",
        ))

    # 7. Marqueurs pipeline internes
    from .rendering import _INTERNAL_LINE_PATTERNS
    for line in content.splitlines():
        if any(p.match(line) for p in _INTERNAL_LINE_PATTERNS):
            violations.append(ConditionViolation(
                "internal_markers", "quality",
                f"Ligne de jargon pipeline détectée : {line.strip()[:60]!r}",
            ))
            break  # un seul exemple suffit à déclencher la correction

    # 8. Section Sources intermédiaire
    if not _is_sources_chapter(prompt_key, chapter_number):
        from .rendering import _SOURCES_BLOCK_PATTERN
        for line in content.splitlines():
            if _SOURCES_BLOCK_PATTERN.match(line):
                violations.append(ConditionViolation(
                    "intermediate_sources", "quality",
                    "Section 'Sources' présente dans un chapitre non-sources",
                ))
                break

    # 9. Entités HTML encodées visibles
    if _HTML_ENTITY_TAG_RE.search(content):
        violations.append(ConditionViolation(
            "raw_html_entities", "quality",
            "Balises HTML encodées visibles (&lt;table&gt; etc.)",
        ))

    # 10. Tournures IA conversationnelles
    if _CONVERSATIONAL_AI_RE.search(content):
        violations.append(ConditionViolation(
            "conversational_ai", "quality",
            "Tournure IA bannie détectée (il apparaît que / dynamique porteuse…)",
        ))

    # 11. Gaps dans la numérotation des sous-sections (ex : 3.1 → 3.6 puis stop)
    sub_numbers = [int(m.group(1)) for m in _SUBSECTION_HEADING_RE.finditer(content)]
    if len(sub_numbers) >= 2:
        expected = set(range(1, max(sub_numbers) + 1))
        missing = sorted(expected - set(sub_numbers))
        if missing:
            violations.append(ConditionViolation(
                "missing_subsections", "critical",
                f"Sous-sections manquantes : numéros {missing} "
                f"(trouvés jusqu'à {max(sub_numbers)})",
            ))

    # 12. Fin abrupte : dernier paragraphe trop court sans ponctuation finale
    # Détecte les coupures mid-phrase (Claude atteint max_tokens silencieusement)
    text_lines = [ln for ln in stripped.splitlines() if ln.strip()]
    if text_lines:
        last_line = text_lines[-1].strip()
        # Reconstruire le dernier paragraphe (lignes consécutives non vides)
        para_lines: list[str] = []
        for line in reversed(text_lines):
            if not line.strip():
                break
            para_lines.insert(0, line)
        last_para_words = len(" ".join(para_lines).split())
        ends_properly = bool(_SENTENCE_END_RE.search(last_line))
        # Le point peut avoir ete ajoute par la reparation de la regle 1 :
        # une preposition suivie d'un point reste une phrase inachevee.
        hangs_on_preposition = bool(
            _HANGING_WORDS_RE.search(last_line)
            or _HANGING_BEFORE_PERIOD_RE.search(last_line)
        )

        if (last_para_words < 15 and not ends_properly) or hangs_on_preposition:
            violations.append(ConditionViolation(
                "abrupt_ending", "critical",
                f"Fin abrupte probable : {last_para_words} mots, "
                f"dernière ligne : {last_line[-80:]!r}",
            ))

    return violations


# ── Réparations règle-métier ──────────────────────────────────────────────────


def repair_rule_based(
    content: str,
    prompt_key: str,
    chapter_number: int,
) -> tuple[str, list[str]]:
    """Applique toutes les corrections automatiques (sans IA).

    Ordre d'application :
    0. Phrase sans ponctuation finale → ajouter un point (sentence_cut)
    1. Marqueurs pipeline → suppression (rendering.strip_internal_markers)
    2. Section Sources intermédiaire → suppression
    3. Substitutions lexicales (anglicismes, tournures IA)
    4. Blocs ```html → désenvelopper le HTML
    5. Autres blocs de code → supprimer
    6. Marqueurs ``` orphelins → supprimer
    7. Entités HTML encodées → décoder
    8. Dernière ligne pipe incomplète → supprimer
    9. Balises HTML orphelines → fermer

    Retourne (contenu corrigé, liste des corrections appliquées).
    """
    from .rendering import (
        apply_lexical_substitutions,
        close_dangling_html_tags,
        strip_incomplete_trailing_tag,
        strip_intermediate_sources,
        strip_internal_markers,
    )

    fixes: list[str] = []
    original = content

    # 0. Phrase sans ponctuation finale → point déterministe (sans IA)
    last_prose = _last_prose_line(content)
    if (
        last_prose
        and not _SENTENCE_END_RE.search(last_prose)
        and _TERMINAL_LETTER_RE.search(last_prose)
    ):
        before = content
        content = _add_terminal_period(content)
        if content != before:
            fixes.append("closed_unfinished_sentence")

    # 1. Marqueurs pipeline
    before = content
    content = strip_internal_markers(content)
    if content != before:
        fixes.append("stripped_internal_markers")

    # 2. Section Sources intermédiaire
    if not _is_sources_chapter(prompt_key, chapter_number):
        before = content
        content = strip_intermediate_sources(content)
        if content != before:
            fixes.append("stripped_intermediate_sources")

    # 3. Substitutions lexicales (anglicismes + tournures IA)
    before = content
    content = apply_lexical_substitutions(content)
    if content != before:
        fixes.append("applied_lexical_substitutions")

    # 4. Désenvelopper les blocs ```html
    def _unwrap_html(m: re.Match[str]) -> str:
        fixes.append("unwrapped_html_fence")
        return m.group(1).strip()

    content = re.sub(r"```html\s*\n(.*?)```", _unwrap_html, content, flags=re.DOTALL)

    # 5. Supprimer les autres blocs de code (python, json, csv…)
    def _drop_fence(m: re.Match[str]) -> str:
        lang = m.group(1) or "code"
        fixes.append(f"dropped_{lang}_fence")
        return ""

    content = re.sub(r"```(\w+)\s*\n.*?```", _drop_fence, content, flags=re.DOTALL)

    # 6. Supprimer les marqueurs ``` orphelins
    orphan_count = len(re.findall(r"^```\w*\s*$", content, re.MULTILINE))
    if orphan_count:
        content = re.sub(r"^```\w*\s*$", "", content, flags=re.MULTILINE)
        fixes.append(f"removed_{orphan_count}_orphan_fences")

    # 7. Décoder les entités HTML encodées visibles
    before = content
    content = re.sub(r"&lt;", "<", content, flags=re.IGNORECASE)
    content = re.sub(r"&gt;", ">", content, flags=re.IGNORECASE)
    if content != before:
        fixes.append("decoded_html_entities")

    # 8. Dernière ligne pipe incomplète
    lines = content.strip().split("\n")
    if lines and re.match(r"^\|[^|]+$", lines[-1].strip()):
        content = "\n".join(lines[:-1]).strip()
        fixes.append("removed_incomplete_pipe_line")

    # 9. Fermer les balises HTML orphelines/tronquées
    before = content
    content = strip_incomplete_trailing_tag(content)
    content = close_dangling_html_tags(content)
    if content != before:
        fixes.append("closed_dangling_html_tags")

    # Compacter les lignes vides excessives produites par les suppressions
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    if content != original and not fixes:
        fixes.append("whitespace_cleanup")

    return content, fixes


# ── Réparation IA ─────────────────────────────────────────────────────────────

_QA_SYSTEM_PROMPT = (
    "Tu es un éditeur expert de documents professionnels EVKHA (études de marché, "
    "études de la concurrence, business plans). "
    "Tu corriges et complètes du contenu de chapitre selon les règles éditoriales EVKHA : "
    "ton professionnel et chaleureux, données chiffrées et sourcées, aucun emoji, "
    "aucun marqueur de pipeline ('Étape', 'Point de contrôle', 'Validation', "
    "'Prompt à utiliser', 'CONTEXTE À REINJECTER'), aucune section 'Sources' "
    "intermédiaire, aucun bloc de code (```). "
    "Tu retournes UNIQUEMENT le contenu corrigé/complété, sans introduction, "
    "sans explication, sans ligne de séparation, sans metadata."
)


def _needs_ai_completion(violations: list[ConditionViolation]) -> bool:
    structural = {"cut_html_table", "truncated_in_tag", "incomplete_pipe_table", "abrupt_ending"}
    return any(v.name in structural for v in violations)


def _needs_ai_expansion(violations: list[ConditionViolation]) -> bool:
    return any(v.name == "below_min_length" for v in violations)


def _needs_subsection_repair(violations: list[ConditionViolation]) -> bool:
    return any(v.name == "missing_subsections" for v in violations)


def _extract_missing_numbers(detail: str) -> list[int]:
    """Extrait les numéros de sous-sections manquantes depuis le detail d'une violation."""
    m = re.search(r"numéros\s+\[([^\]]+)\]", detail)
    if not m:
        return []
    try:
        return sorted(int(x.strip()) for x in m.group(1).split(","))
    except ValueError:
        return []


def _ai_insert_missing_subsections(
    content: str,
    chapter_title: str,
    missing_nums: list[int],
    *,
    client: object,
    project_context: str = "",
) -> tuple[str, int, int]:
    """Génère les sous-sections manquantes et les insère à la bonne position.

    Stratégie d'insertion : cherche la première section APRÈS le gap
    (numéro secondaire = missing_nums[-1] + 1) et insère le contenu juste avant.
    Si aucune section après le gap n'est trouvée, le contenu est ajouté à la fin.
    Retourne (contenu, input_tokens, output_tokens) pour le suivi des coûts §4.
    """
    from integrations.claude import ClaudeClient  # éviter import circulaire

    if not isinstance(client, ClaudeClient) or not missing_nums:
        return content, 0, 0

    sample = content[:2000].strip()
    missing_str = ", ".join(str(n) for n in missing_nums)

    context_block = f"{project_context}\n\n" if project_context else ""
    prompt = (
        f"{context_block}"
        f"Le chapitre « {chapter_title} » est incomplet : "
        f"les sous-sections {missing_str} sont absentes.\n"
        "Génère UNIQUEMENT ces sous-sections manquantes, "
        "dans le même format, style et niveau de détail que les exemples ci-dessous.\n"
        "Appuie-toi STRICTEMENT sur les données du projet fournies en contexte : "
        "aucun contenu générique interchangeable avec un autre projet.\n"
        "Ne reproduis pas les sous-sections déjà présentes dans le contenu.\n"
        "Commence directement par la première sous-section manquante "
        "(ex. ### N.X Nom du concurrent) sans aucune introduction.\n\n"
        f"Extrait du chapitre existant (format de référence) :\n{sample}"
    )

    try:
        result = client.complete(
            system=_QA_SYSTEM_PROMPT,
            prompt=prompt,
            max_tokens=_QA_SUBSECTION_TOKENS,
        )
    except Exception:  # noqa: BLE001
        return content, 0, 0

    new_sections = result.content.strip()
    if not new_sections:
        return content, result.input_tokens, result.output_tokens

    # Insérer avant la première section qui suit le gap
    first_after_gap = missing_nums[-1] + 1
    after_gap_re = re.compile(
        r"(?m)^(#{1,4}\s+\d+\." + str(first_after_gap) + r"(?:\s|\*|\.|:))"
    )
    m = after_gap_re.search(content)
    if m:
        insert_pos = m.start()
        patched = content[:insert_pos] + new_sections + "\n\n" + content[insert_pos:]
        return patched, result.input_tokens, result.output_tokens

    return (
        content.rstrip() + "\n\n" + new_sections,
        result.input_tokens,
        result.output_tokens,
    )


def ai_repair_chapter(
    content: str,
    chapter_title: str,
    section_kind: str,
    violations: list[ConditionViolation],
    *,
    client: object,
    project_context: str = "",
) -> tuple[str, int, int]:
    """Appelle Claude pour compléter ou développer un chapitre problématique.

    - Si troncature structurelle (table coupée, balise ouverte) : génère uniquement
      la suite manquante pour fermer les structures.
    - Si chapitre trop court : développe substantiellement le contenu existant.
    - Si les deux : commence par la complétion, puis l'expansion.

    `project_context` (variables projet + données client) est injecté dans
    chaque prompt de réparation : sans lui, la régénération produisait du
    contenu générique déconnecté du dossier (audit juillet 2026).
    Retourne (contenu, input_tokens, output_tokens) — les tokens des appels
    de réparation sont comptabilisés dans le Cost Engine (§4 cadrage).
    Retourne le contenu d'origine si Claude ne produit rien d'utile.
    """
    from integrations.claude import ClaudeClient  # éviter import circulaire

    total_in = 0
    total_out = 0

    if not isinstance(client, ClaudeClient):
        return content, 0, 0

    context_block = f"{project_context}\n\n" if project_context else ""

    # Réparation prioritaire : sous-sections manquantes (gap dans la numérotation)
    # Traité AVANT completion/expansion car l'insertion change la longueur du chapitre.
    if _needs_subsection_repair(violations):
        for v in violations:
            if v.name == "missing_subsections":
                missing = _extract_missing_numbers(v.detail)
                if missing:
                    patched, sub_in, sub_out = _ai_insert_missing_subsections(
                        content, chapter_title, missing,
                        client=client, project_context=project_context,
                    )
                    total_in += sub_in
                    total_out += sub_out
                    if patched != content:
                        content = patched

    needs_completion = _needs_ai_completion(violations)
    needs_expansion = _needs_ai_expansion(violations)

    if not (needs_completion or needs_expansion):
        return content, total_in, total_out

    min_w = _MIN_WORDS.get(section_kind, 200)
    current_wc = _word_count(content)

    if needs_completion:
        # Complétion structurelle : fermer les balises et terminer les phrases
        prompt = (
            f"{context_block}"
            f"Le chapitre « {chapter_title} » a été tronqué. "
            "Génère UNIQUEMENT la suite manquante pour :\n"
            "— fermer toutes les balises HTML ouvertes (<table>, <tr>, <td>, <ul>, <li>, etc.)\n"
            "— terminer la phrase ou la liste en cours si interrompue\n"
            "— compléter les tableaux avec les données manquantes si un tableau était en cours\n"
            "Utilise UNIQUEMENT les données du projet fournies en contexte, "
            "sans inventer de nouveaux chiffres.\n"
            "Ne répète pas ce qui précède. Commence directement par la continuation.\n\n"
            f"{content.strip()}"
        )
        try:
            result = client.complete(
                system=_QA_SYSTEM_PROMPT,
                prompt=prompt,
                max_tokens=_QA_COMPLETION_TOKENS,
            )
        except Exception:  # noqa: BLE001
            return content, total_in, total_out

        total_in += result.input_tokens
        total_out += result.output_tokens
        completion = result.content.strip()
        if not completion:
            return content, total_in, total_out

        repaired = content.rstrip() + "\n" + completion

        # Si on a aussi besoin d'expansion, vérifier la longueur après complétion
        if needs_expansion and _word_count(repaired) < min_w:
            content = repaired
            needs_expansion = True
        else:
            return repaired, total_in, total_out

    if needs_expansion:
        is_severely_short = current_wc < min_w * 0.3

        if is_severely_short:
            # Trop peu de contenu pour développer : demande un chapitre complet,
            # ancré dans les données réelles du projet (jamais générique).
            prompt = (
                f"{context_block}"
                f"Génère le contenu complet du chapitre « {chapter_title} » "
                f"pour un document professionnel EVKHA (type : {section_kind}). "
                f"Minimum requis : {min_w} mots. "
                "Appuie-toi STRICTEMENT sur les données du projet fournies en "
                "contexte (secteur, pays, chiffres client) : aucun paragraphe "
                "interchangeable avec un autre projet, aucun chiffre inventé. "
                "Données chiffrées, sourcées, concrètes et exploitables. "
                "Ton professionnel et chaleureux. "
                "Structure avec sous-titres et tableaux si pertinent. "
                "Retourne directement le contenu, sans introduction ni conclusion méta."
            )
        else:
            # Développer le contenu existant
            prompt = (
                f"{context_block}"
                f"Ce chapitre « {chapter_title} » est trop court ({current_wc} mots, "
                f"minimum requis : {min_w} mots). "
                "Développe-le substantiellement en conservant le style, "
                "le ton et la structure existants. "
                "Appuie-toi sur les données du projet fournies en contexte ; "
                "n'invente aucun chiffre nouveau. "
                "Ajoute des données chiffrées, des analyses concrètes, des exemples applicables. "
                "Retourne directement le contenu complet et développé :\n\n"
                f"{content.strip()}"
            )

        try:
            result = client.complete(
                system=_QA_SYSTEM_PROMPT,
                prompt=prompt,
                max_tokens=_QA_COMPLETION_TOKENS,
            )
        except Exception:  # noqa: BLE001
            return content, total_in, total_out

        total_in += result.input_tokens
        total_out += result.output_tokens
        expanded = result.content.strip()
        if not expanded:
            return content, total_in, total_out

        if is_severely_short:
            return expanded, total_in, total_out
        else:
            # Vérifier que la réponse est plus longue que le contenu actuel
            if len(expanded) > len(content) * 0.7:
                return expanded, total_in, total_out
            return content.rstrip() + "\n\n" + expanded, total_in, total_out

    return content, total_in, total_out


# ── Point d'entrée principal ───────────────────────────────────────────────────


def run_qa_pass(
    job: object,
    *,
    client: object | None = None,
    ai_repair: bool = True,
) -> list[QAResult]:
    """Passe QA complète sur tous les chapitres DONE du job.

    Séquence pour chaque chapitre :
    1. Détecte les 10 violations qualité
    2. Applique les réparations règle-métier (sans IA) — toujours
    3. Ré-détecte pour voir les violations restantes
    4. Pour les violations critiques restantes : appelle Claude (si ai_repair=True)
    5. Applique une dernière passe de fermeture de balises sur le résultat IA
    6. Sauvegarde en base si le contenu a changé
    7. Évalue si le chapitre est "passé" (aucune violation critique résiduelle)

    Non bloquante : une erreur sur un chapitre ne stoppe pas les autres.
    Retourne un rapport QA par chapitre (pour monitoring / admin django).
    """
    import json
    from decimal import Decimal

    from intake.models import IntakeSubmission
    from integrations.claude import get_claude_client

    from .coherence import client_facts_as_context
    from .cost import current_job_cost_eur, record_additional_cost
    from .models import ChapterStatus, GenerationJob
    from .rendering import close_dangling_html_tags

    assert isinstance(job, GenerationJob)

    if client is None:
        client = get_claude_client()

    # Contexte projet injecte dans chaque prompt de reparation IA : variables
    # du brief + donnees client intangibles. Sans lui, la regeneration d'un
    # chapitre trop court produisait du contenu generique hors-sujet
    # (audit juillet 2026).
    submission = IntakeSubmission.objects.filter(order=job.order).first()
    variables = submission.normalized_variables if submission else {}
    project_context = (
        "CONTEXTE PROJET (a respecter strictement, ne jamais recopier ces "
        "intitules techniques dans la redaction) :\n"
        f"Variables du brief : {json.dumps(variables, ensure_ascii=False, sort_keys=True)}\n"
        f"Donnees client intangibles :\n{client_facts_as_context(job)}"
    )

    # Désactiver la réparation IA si le job a déjà atteint ou dépassé 85% du budget
    # (les appels Claude du QA ne sont pas comptabilisés dans le budget généré,
    # mais ils contribuent au coût réel Anthropic — on les évite si le budget est tendu).
    current_cost = current_job_cost_eur(job)
    if current_cost >= job.budget_eur * Decimal("0.85"):
        ai_repair = False

    GenerationJob.objects.filter(pk=job.pk).update(qa_status="running")

    chapters = job.chapters.filter(status=ChapterStatus.DONE).order_by("chapter_number")
    results: list[QAResult] = []
    any_error = False

    for chapter in chapters:
        try:
            content = chapter.content
            prompt_key = chapter.prompt_key
            chapter_number = chapter.chapter_number
            chapter_title = chapter.chapter_title
            sk = _infer_section_kind(prompt_key, chapter_number)

            # Étape 1 : détection initiale
            violations = detect_violations(content, prompt_key, chapter_number)
            initial_names = [v.name for v in violations]

            if not violations:
                results.append(QAResult(
                    chapter_number=chapter_number,
                    prompt_key=prompt_key,
                    violations_found=[],
                    fixes_applied=[],
                    ai_repaired=False,
                    passed=True,
                ))
                continue

            # Étape 2 : réparations règle-métier
            repaired, fixes = repair_rule_based(content, prompt_key, chapter_number)
            ai_repaired = False

            # Étape 3 : ré-détection après règle-métier
            remaining = detect_violations(repaired, prompt_key, chapter_number)
            critical_remaining = [v for v in remaining if v.severity == "critical"]

            # Étape 4 : réparation IA pour les violations critiques persistantes
            if ai_repair and critical_remaining:
                completed, repair_in, repair_out = ai_repair_chapter(
                    repaired,
                    chapter_title,
                    sk,
                    critical_remaining,
                    client=client,
                    project_context=project_context,
                )
                # §4 cadrage : les appels IA de la QA sont comptabilises dans
                # le Cost Engine (ils etaient invisibles au dashboard).
                if repair_in or repair_out:
                    record_additional_cost(
                        chapter=chapter,
                        input_tokens=repair_in,
                        output_tokens=repair_out,
                    )
                if completed != repaired:
                    # Passe règle-métier supplémentaire sur le résultat IA
                    repaired, extra = repair_rule_based(
                        completed, prompt_key, chapter_number
                    )
                    # Fermeture finale des balises éventuellement ouvertes par l'IA
                    repaired = close_dangling_html_tags(repaired)
                    fixes.extend(extra)
                    ai_repaired = True

            # Étape 5 : sauvegarde si modifié
            # Sanitise em-dashes / en-dashes injectes par une reparation IA
            # eventuelle (Claude en glisse regulierement malgre la consigne).
            from .runner import _strip_ai_tell_dashes  # noqa: PLC0415
            repaired = _strip_ai_tell_dashes(repaired)
            if repaired != content:
                chapter.content = repaired
                chapter.save(update_fields=["content", "updated_at"])

            # Étape 6 : détection finale pour évaluer le résultat
            final_violations = detect_violations(repaired, prompt_key, chapter_number)
            critical_final = [v for v in final_violations if v.severity == "critical"]

            results.append(QAResult(
                chapter_number=chapter_number,
                prompt_key=prompt_key,
                violations_found=initial_names,
                fixes_applied=fixes,
                ai_repaired=ai_repaired,
                passed=len(critical_final) == 0,
            ))

        except Exception:  # noqa: BLE001 — QA non bloquante par chapitre
            any_error = True
            results.append(QAResult(
                chapter_number=getattr(chapter, "chapter_number", -1),
                prompt_key=getattr(chapter, "prompt_key", "unknown"),
                violations_found=["qa_error"],
                fixes_applied=[],
                ai_repaired=False,
                passed=False,
            ))

    # Mise à jour du statut global QA
    all_passed = all(r.passed for r in results)
    qa_status = "passed" if (all_passed and not any_error) else "failed"
    GenerationJob.objects.filter(pk=job.pk).update(qa_status=qa_status)

    return results
