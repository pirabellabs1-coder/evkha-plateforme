"""Reprise WAOME v4 apres crash reseau au chapitre 21.

Le runner exclut deja les chapitres DONE (runner.py:267), donc rappeler
run_generation_job sur le meme job reprend depuis le premier chapitre
non-DONE. On evite ainsi de repayer les 21 chapitres deja generes.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


JOB_ID_PREFIX = "45e0809c"  # WAOME v4 crashe au ch. 21


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "evkha.settings")
    import django
    django.setup()

    from generation.correction import run_correction_loop
    from generation.gate import run_delivery_gate
    from generation.models import ChapterStatus, JobStatus, GenerationJob
    from generation.rendering import render_branded_html
    from generation.runner import run_generation_job
    from integrations.claude import get_claude_client

    job = GenerationJob.objects.get(id__startswith=JOB_ID_PREFIX)
    n_done = job.chapters.filter(status=ChapterStatus.DONE).count()
    n_total = job.chapters.count()
    print(f"[step 1] Job {job.id} — {n_done}/{n_total} chapitres deja DONE")

    # Remettre le job en statut RUNNING pour que le runner accepte de repartir.
    job.status = JobStatus.RUNNING
    job.error_message = ""
    job.save(update_fields=["status", "error_message"])

    print("[step 2] Reprise generation (chapitres non-DONE uniquement)...")
    t0 = time.time()
    client = get_claude_client()
    try:
        run_generation_job(job, client=client)
    except Exception as exc:  # noqa: BLE001
        print(f"[step 2] ECHEC : {type(exc).__name__}: {exc}")
        job.refresh_from_db()
        print(f"         Statut : {job.status}")
        return 1
    dt = time.time() - t0
    job.refresh_from_db()
    print(f"[step 2] Reprise terminee en {dt/60:.1f} min. Statut : {job.status}")
    print(f"         Cout total cumule : {job.total_cost_eur} EUR")

    # Gate + boucle correction.
    print("[step 3] Gate initial...")
    report0 = run_delivery_gate(job)
    print(f"         Passed : {report0.passed} ({len(report0.failures)} failures)")

    if not report0.passed:
        print("[step 4] Boucle de correction (max 2 rounds)...")
        t_c = time.time()
        report = run_correction_loop(job, client=client, max_rounds=2)
        job.refresh_from_db()
        print(f"         Terminee en {(time.time()-t_c)/60:.1f} min. Cout : {job.total_cost_eur} EUR")
        print(f"         Gate final : {report.passed} ({len(report.failures)} failures)")
    else:
        report = report0

    # Rapport final defauts.
    if not report.passed:
        by_check: dict[str, list[str]] = {}
        for f in report.failures:
            by_check.setdefault(f.check, []).append(
                f"[ch. {f.chapter_number}] {f.detail[:180]}"
            )
        for check, items in by_check.items():
            print(f"    * {check} ({len(items)}) :")
            for item in items[:3]:
                print(f"        - {item}")
            if len(items) > 3:
                print(f"        ... et {len(items) - 3} de plus.")

    # Dump HTML + MD.
    livrables = Path(r"C:\Users\tobid\Downloads\EVKHA\livrables_test")
    livrables.mkdir(parents=True, exist_ok=True)
    short = str(job.id)[:8]

    html = render_branded_html(job)
    html_path = livrables / f"WAOME_v4_{short}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"[step 5] HTML : {html_path} ({html_path.stat().st_size/1024:.1f} KB)")

    md_path = livrables / f"WAOME_v4_{short}.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# WAOME v4 - job {job.id}\n\nStatut : {job.status} — passed : {report.passed}\n\n")
        for ch in job.chapters.order_by("chapter_number"):
            f.write(f"\n\n## Chapitre {ch.chapter_number} — {ch.chapter_title}\n\n")
            f.write(ch.content or "(vide)")
    print(f"         MD  : {md_path} ({md_path.stat().st_size/1024:.1f} KB)")

    return 0 if report.passed else 2


if __name__ == "__main__":
    sys.exit(main())
