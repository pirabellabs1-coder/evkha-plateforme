"""Post-génération QA : détection et correction des violations qualité.

Chaque condition de "génération parfaite" est vérifiée indépendamment.
Pour chaque violation détectée, une correction ciblée est appliquée avant
la livraison du document.

Conditions vérifiées (par ordre de priorité) :
  Critiques (bloquent la qualité visuelle) :
    1. empty_content         — chapitre vide ou quasi-vide
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
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple

# ── Constantes de détection ───────────────────────────────────────────────────

_CODE_FENCE_RE = re.compile(r"```")
_TABLE_OPEN_RE = re.compile(r"<table\b", re.IGNORECASE)
_TABLE_CLOSE_RE = re.compile(r"</table>", re.IGNORECASE)

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

# Seuils de longueur minimale (mots) par type de section
# Conservateurs : en-dessous, la troncature est quasi-certaine
_MIN_WORDS: dict[str, int] = {
    "opening": 100,
    "chapter": 200,
    "annexe":  100,
    "sources":  30,
}

_QA_COMPLETION_TOKENS = 1800


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

    # 1. Contenu vide
    if not stripped or len(stripped) < 10:
        violations.append(ConditionViolation(
            "empty_content", "critical", "Chapitre vide ou quasi-vide",
        ))
        return violations  # inutile de continuer

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
    min_w = _MIN_WORDS.get(sk, 200)
    wc = _word_count(stripped)
    if wc < min_w:
        violations.append(ConditionViolation(
            "below_min_length", "critical",
            f"{wc} mots < minimum {min_w} attendus (section de type {sk!r})",
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

    return violations


# ── Réparations règle-métier ──────────────────────────────────────────────────


def repair_rule_based(
    content: str,
    prompt_key: str,
    chapter_number: int,
) -> tuple[str, list[str]]:
    """Applique toutes les corrections automatiques (sans IA).

    Ordre d'application :
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
    structural = {"cut_html_table", "truncated_in_tag", "incomplete_pipe_table"}
    return any(v.name in structural for v in violations)


def _needs_ai_expansion(violations: list[ConditionViolation]) -> bool:
    return any(v.name == "below_min_length" for v in violations)


def ai_repair_chapter(
    content: str,
    chapter_title: str,
    section_kind: str,
    violations: list[ConditionViolation],
    *,
    client: object,
) -> str:
    """Appelle Claude pour compléter ou développer un chapitre problématique.

    - Si troncature structurelle (table coupée, balise ouverte) : génère uniquement
      la suite manquante pour fermer les structures.
    - Si chapitre trop court : développe substantiellement le contenu existant.
    - Si les deux : commence par la complétion, puis l'expansion.

    Retourne le contenu d'origine si Claude ne produit rien d'utile.
    """
    from integrations.claude import ClaudeClient  # éviter import circulaire

    if not isinstance(client, ClaudeClient):
        return content

    needs_completion = _needs_ai_completion(violations)
    needs_expansion = _needs_ai_expansion(violations)

    if not (needs_completion or needs_expansion):
        return content

    min_w = _MIN_WORDS.get(section_kind, 200)
    current_wc = _word_count(content)

    if needs_completion:
        # Complétion structurelle : fermer les balises et terminer les phrases
        prompt = (
            f"Le chapitre « {chapter_title} » a été tronqué. "
            "Génère UNIQUEMENT la suite manquante pour :\n"
            "— fermer toutes les balises HTML ouvertes (<table>, <tr>, <td>, <ul>, <li>, etc.)\n"
            "— terminer la phrase ou la liste en cours si interrompue\n"
            "— compléter les tableaux avec les données manquantes si un tableau était en cours\n"
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
            return content

        completion = result.content.strip()
        if not completion:
            return content

        repaired = content.rstrip() + "\n" + completion

        # Si on a aussi besoin d'expansion, vérifier la longueur après complétion
        if needs_expansion and _word_count(repaired) < min_w:
            content = repaired
            needs_expansion = True
        else:
            return repaired

    if needs_expansion:
        is_severely_short = current_wc < min_w * 0.3

        if is_severely_short:
            # Trop peu de contenu pour développer : demande un chapitre complet
            prompt = (
                f"Génère le contenu complet du chapitre « {chapter_title} » "
                f"pour un document professionnel EVKHA (type : {section_kind}). "
                f"Minimum requis : {min_w} mots. "
                "Données chiffrées, sourcées, concrètes et exploitables. "
                "Ton professionnel et chaleureux. "
                "Structure avec sous-titres et tableaux si pertinent. "
                "Retourne directement le contenu, sans introduction ni conclusion méta."
            )
        else:
            # Développer le contenu existant
            prompt = (
                f"Ce chapitre « {chapter_title} » est trop court ({current_wc} mots, "
                f"minimum requis : {min_w} mots). "
                "Développe-le substantiellement en conservant le style, "
                "le ton et la structure existants. "
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
            return content

        expanded = result.content.strip()
        if not expanded:
            return content

        if is_severely_short:
            return expanded
        else:
            # Vérifier que la réponse est plus longue que le contenu actuel
            if len(expanded) > len(content) * 0.7:
                return expanded
            return content.rstrip() + "\n\n" + expanded

    return content


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
    from integrations.claude import get_claude_client

    from .models import ChapterStatus, GenerationJob
    from .rendering import close_dangling_html_tags

    assert isinstance(job, GenerationJob)

    if client is None:
        client = get_claude_client()

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
                completed = ai_repair_chapter(
                    repaired,
                    chapter_title,
                    sk,
                    critical_remaining,
                    client=client,
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
