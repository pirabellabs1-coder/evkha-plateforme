from __future__ import annotations

import re
from typing import NamedTuple

# ── Détection ──────────────────────────────────────────────────────────────────

_CODE_FENCE_RE = re.compile(r"```")
_TABLE_OPEN_RE = re.compile(r"<table\b", re.IGNORECASE)
_TABLE_CLOSE_RE = re.compile(r"</table>", re.IGNORECASE)

# Troncature sévère : contenu qui se termine à l'intérieur d'une balise ouverte
_SEVERE_TRUNCATION_RE = re.compile(
    r"<(?:td|th|tr|li|p|div|ul|ol|section)\b[^>]*>[^<]*$",
    re.IGNORECASE,
)

# Ligne de tableau Markdown incomplète en dernière position
_INCOMPLETE_PIPE_LINE_RE = re.compile(r"^\|[^|\n]+$", re.MULTILINE)


class QAResult(NamedTuple):
    chapter_number: int
    prompt_key: str
    issues_found: list[str]
    fixes_applied: list[str]
    ai_repaired: bool


# ── Détection ──────────────────────────────────────────────────────────────────


def detect_issues(content: str) -> list[str]:
    """Retourne la liste des problèmes détectés dans le contenu brut d'un chapitre."""
    issues: list[str] = []

    if _CODE_FENCE_RE.search(content):
        issues.append("code_fence")

    open_t = len(_TABLE_OPEN_RE.findall(content))
    close_t = len(_TABLE_CLOSE_RE.findall(content))
    if open_t > close_t:
        issues.append(f"cut_html_table:{open_t}open/{close_t}close")

    stripped = content.strip()
    if stripped:
        last_line = stripped.split("\n")[-1].strip()
        if re.match(r"^\|[^|]+$", last_line):
            issues.append("incomplete_pipe_table")

    if _SEVERE_TRUNCATION_RE.search(stripped):
        issues.append("truncated_in_tag")

    return issues


def is_severely_truncated(content: str) -> bool:
    """Heuristique : troncature sévère nécessitant une complétion IA."""
    stripped = content.strip()
    if not stripped:
        return False
    open_t = len(_TABLE_OPEN_RE.findall(stripped))
    close_t = len(_TABLE_CLOSE_RE.findall(stripped))
    if open_t > close_t:
        return True
    if _SEVERE_TRUNCATION_RE.search(stripped):
        return True
    return False


# ── Réparation règle-métier ────────────────────────────────────────────────────


def repair_rule_based(content: str) -> tuple[str, list[str]]:
    """Réparations sans IA.

    1. Extrait le HTML des blocs ```html (supprime les marqueurs de fence)
    2. Supprime les autres blocs de code (python, json…)
    3. Retire les marqueurs ``` orphelins
    4. Ferme les balises HTML tronquées/orphelines

    Retourne (contenu corrigé, liste des corrections appliquées).
    """
    from .rendering import close_dangling_html_tags, strip_incomplete_trailing_tag

    fixes: list[str] = []
    original = content

    # 1. Désenvelopper les blocs ```html
    def _unwrap_html(m: re.Match[str]) -> str:
        fixes.append("unwrapped_html_fence")
        return m.group(1).strip()

    content = re.sub(r"```html\s*\n(.*?)```", _unwrap_html, content, flags=re.DOTALL)

    # 2. Supprimer les autres blocs de code
    def _drop_fence(m: re.Match[str]) -> str:
        lang = m.group(1) or "code"
        fixes.append(f"dropped_{lang}_fence")
        return ""

    content = re.sub(r"```(\w*)\s*\n.*?```", _drop_fence, content, flags=re.DOTALL)

    # 3. Supprimer les marqueurs ``` orphelins
    orphans = len(re.findall(r"^```\w*\s*$", content, re.MULTILINE))
    if orphans:
        content = re.sub(r"^```\w*\s*$", "", content, flags=re.MULTILINE)
        fixes.append(f"removed_{orphans}_orphan_fences")

    # 4. Fermer les balises HTML orphelines
    before = content
    content = strip_incomplete_trailing_tag(content)
    content = close_dangling_html_tags(content)
    if content != before:
        fixes.append("closed_dangling_html_tags")

    # Compacter les lignes vides excessives laissées par les suppressions
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    if content != original and not fixes:
        fixes.append("whitespace_cleanup")

    return content, fixes


# ── Réparation IA ─────────────────────────────────────────────────────────────

_QA_SYSTEM_PROMPT = (
    "Tu es un éditeur de documents professionnels spécialisé dans la correction "
    "de contenus partiellement tronqués par une limite technique. "
    "Ta mission : compléter proprement un contenu HTML/Markdown interrompu "
    "sans répéter ce qui est déjà écrit et sans ajouter de nouveau contenu "
    "substantiel. Tu fermes uniquement les structures ouvertes "
    "(<table>, <tr>, <td>, <ul>, <li>, etc.) et tu termines la phrase "
    "ou la liste en cours si elle était incomplète."
)

_QA_MAX_REPAIR_TOKENS = 600


def ai_complete_truncated(content: str, *, client: object) -> str:
    """Appelle Claude pour compléter un contenu sévèrement tronqué (max 600 tokens).

    Limité volontairement : la réparation ne doit fermer des structures,
    pas générer du contenu nouveau. Retourne le contenu d'origine si Claude
    ne produit rien d'utile.
    """
    from integrations.claude import ClaudeClient  # import local pour éviter les cycles

    if not isinstance(client, ClaudeClient):
        return content

    prompt = (
        "Voici du contenu HTML/Markdown tronqué accidentellement :\n\n"
        "---\n"
        f"{content.strip()}\n"
        "---\n\n"
        "Génère UNIQUEMENT la suite manquante pour compléter proprement ce contenu. "
        "Commence directement après le dernier caractère sans répéter le début. "
        "Ferme toutes les balises HTML ouvertes. "
        "Si un tableau était en cours, termine-le avec les données manquantes. "
        "Limite-toi strictement à la complétion nécessaire."
    )
    try:
        result = client.complete(
            system=_QA_SYSTEM_PROMPT,
            prompt=prompt,
            max_tokens=_QA_MAX_REPAIR_TOKENS,
        )
    except Exception:  # noqa: BLE001
        return content

    completion = result.content.strip()
    if not completion:
        return content
    return content.rstrip() + "\n" + completion


# ── Point d'entrée principal ───────────────────────────────────────────────────


def run_qa_pass(
    job: object,
    *,
    client: object | None = None,
    ai_repair: bool = True,
) -> list[QAResult]:
    """Passe QA complète sur tous les chapitres DONE du job.

    Séquence pour chaque chapitre :
    1. Détecte les problèmes (code fence, tables coupées, troncatures)
    2. Applique les réparations règle-métier (sans IA) — toujours
    3. Pour les troncatures sévères : complète avec Claude si ai_repair=True
       et si le client IA est disponible
    4. Sauvegarde le contenu corrigé en base (uniquement si modifié)

    Retourne un rapport QA par chapitre (pour monitoring / admin).
    Non bloquante : une erreur sur un chapitre ne stoppe pas les autres.
    """
    from integrations.claude import get_claude_client

    from .models import ChapterStatus, GenerationJob

    assert isinstance(job, GenerationJob)

    if client is None:
        client = get_claude_client()

    # Mise à jour statut QA
    GenerationJob.objects.filter(pk=job.pk).update(qa_status="running")

    chapters = job.chapters.filter(status=ChapterStatus.DONE).order_by("chapter_number")
    results: list[QAResult] = []
    any_error = False

    for chapter in chapters:
        try:
            content = chapter.content
            issues = detect_issues(content)

            if not issues:
                results.append(
                    QAResult(
                        chapter_number=chapter.chapter_number,
                        prompt_key=chapter.prompt_key,
                        issues_found=[],
                        fixes_applied=[],
                        ai_repaired=False,
                    )
                )
                continue

            # Réparations règle-métier
            repaired, fixes = repair_rule_based(content)
            ai_repaired = False

            # Complétion IA pour troncatures sévères
            if ai_repair and is_severely_truncated(repaired):
                completed = ai_complete_truncated(repaired, client=client)
                if completed != repaired:
                    repaired, extra = repair_rule_based(completed)
                    fixes.extend(extra)
                    ai_repaired = True

            # Sauvegarde si le contenu a changé
            if repaired != content:
                chapter.content = repaired
                chapter.save(update_fields=["content", "updated_at"])

            results.append(
                QAResult(
                    chapter_number=chapter.chapter_number,
                    prompt_key=chapter.prompt_key,
                    issues_found=issues,
                    fixes_applied=fixes,
                    ai_repaired=ai_repaired,
                )
            )

        except Exception:  # noqa: BLE001 - QA non bloquante
            any_error = True
            results.append(
                QAResult(
                    chapter_number=chapter.chapter_number,
                    prompt_key=chapter.prompt_key,
                    issues_found=["qa_error"],
                    fixes_applied=[],
                    ai_repaired=False,
                )
            )

    qa_status = "failed" if any_error else "passed"
    GenerationJob.objects.filter(pk=job.pk).update(qa_status=qa_status)

    return results
