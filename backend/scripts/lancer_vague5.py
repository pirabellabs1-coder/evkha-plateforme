"""Lanceur de test reel - pipeline vague 5 (branche feat/vague5-sonnet-pipeline-complet).

Clone le brief WAOME (submission du job 49953f14) - l'etude EM sur laquelle les
generations vague 3 et 4 ont echoue ou ete coupees - et le fait passer par le
pipeline vague 5 complet :
  - 21 chapitres EM (blueprint manuel Evangeline juillet 2026)
  - CHECKs Sonnet 4.6 (INITIAL + blocs A-J + FINAL)
  - advisor sur blocs A, F, G, I, J
  - few-shot Findrax (tache #13, stable segment)
  - code execution ch. 2 (TAM/SAM/SOM)
  - fiche enrichie apres chaque CHECK
  - registre chiffres-fondations (SS5, p.6)
  - gate + boucle correction (max 2 rounds)
  - rendu HTML + PDF WeasyPrint

Usage (depuis backend/) :
    ANTHROPIC_API_KEY=sk-... EVKHA_USE_STUB_AI=false EVKHA_USE_STUB_EMAIL=true \\
    EVKHA_USE_STUB_PDF=false \\
        python scripts/lancer_vague5.py

Le livrable NE PART PAS chez Evangeline (EVKHA_USE_STUB_EMAIL=true obligatoire).
Le PDF est ecrit dans %TEMP%/vague5/<job_id>.pdf.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


# Job WAOME v1 (premier test reel, brief original) - variables source.
# Si introuvable dans la DB, tombe sur la derniere IntakeSubmission MARKET_STUDY.
_JOB_SOURCE_PREFIX = "49953f14"


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "evkha.settings")
    import django
    django.setup()

    from django.conf import settings

    if getattr(settings, "EVKHA_USE_STUB_AI", True):
        print("ABORT: EVKHA_USE_STUB_AI=true - cette relance doit tourner sur le client reel.")
        return 1
    if not getattr(settings, "EVKHA_USE_STUB_EMAIL", False):
        print("ABORT: EVKHA_USE_STUB_EMAIL doit rester true (pas d'envoi automatique).")
        return 1
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ABORT: ANTHROPIC_API_KEY manquante dans l'environnement.")
        return 1

    pdf_reel = not getattr(settings, "EVKHA_USE_STUB_PDF", True)
    if not pdf_reel:
        print("[INFO] EVKHA_USE_STUB_PDF=true - le PDF genere sera un stub (pas WeasyPrint).")
        print("       Pour le vrai PDF : ajouter EVKHA_USE_STUB_PDF=false a la commande.")

    from catalog.models import DeliverableType
    from customers.models import Customer
    from generation.correction import run_correction_loop
    from generation.gate import run_delivery_gate
    from generation.models import GenerationJob
    from generation.rendering import render_branded_html
    from generation.runner import run_generation_job
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from integrations.claude import get_claude_client
    from integrations.pdf import get_pdf_client
    from orders.models import Order

    # 1. Recuperation des variables du brief WAOME
    source_sub = None
    try:
        job_src = GenerationJob.objects.get(id__startswith=_JOB_SOURCE_PREFIX)
        source_sub = IntakeSubmission.objects.filter(order_id=job_src.order_id).first()
    except GenerationJob.DoesNotExist:
        pass

    if source_sub is None:
        source_sub = (
            IntakeSubmission.objects
            .filter(
                status=IntakeStatus.NORMALIZED,
                order__offer__deliverable_type=DeliverableType.MARKET_STUDY,
            )
            .order_by("-created_at")
            .first()
        )

    if source_sub is None:
        print("ABORT: aucune submission MARKET_STUDY disponible dans la DB.")
        return 1

    variables = dict(source_sub.normalized_variables)
    nom = variables.get("NOM_ENTREPRISE") or variables.get("NOM_PROJET") or "(inconnu)"
    print(f"[1/8] Brief source : job={getattr(source_sub.order, 'id', '?')} "
          f"- projet: {nom} - {len(variables)} variables")

    # 2. Nouvel order + submission dedies au test vague 5
    offer = source_sub.order.offer
    customer, _ = Customer.objects.get_or_create(
        email="vague5-test@evkha.local",
        defaults={"first_name": "VAGUE5", "last_name": "test"},
    )
    order = Order.objects.create(
        systeme_order_id=f"vague5_{int(time.time())}",
        customer=customer,
        offer=offer,
    )
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables=variables,
    )
    print(f"[2/8] Order cree : {order.id} | submission : {submission.id}")

    # 3. Bootstrap job
    job = bootstrap_generation_job(submission)
    print(f"[3/8] Job : {job.id} ({job.deliverable_type}) - {job.chapters.count()} chapitres")

    # 4. Generation
    print("[4/8] Generation en cours (claude-sonnet-4-6, client reel)...")
    t0 = time.time()
    client = get_claude_client()
    print(f"       Client : {type(client).__name__}")
    try:
        run_generation_job(job, client=client)
    except Exception as exc:  # noqa: BLE001
        print(f"[4/8] ECHEC run_generation_job : {type(exc).__name__}: {exc}")
        job.refresh_from_db()
        print(f"       Statut : {job.status}")
        return 1

    dt = time.time() - t0
    job.refresh_from_db()
    done = job.chapters.filter(status="done").count()
    total = job.chapters.count()
    print(f"[4/8] Termine en {dt/60:.1f} min - {done}/{total} chapitres DONE "
          f"- cout : {job.total_cost_eur} EUR")

    # 5. Gate initial
    print("[5/8] Gate initial...")
    report0 = run_delivery_gate(job)
    print(f"       Passed : {report0.passed} ({len(report0.failures)} failures)")

    # 6. Boucle de correction
    report = report0
    if not report0.passed:
        print("[6/8] Boucle de correction (max 2 rounds)...")
        t_corr = time.time()
        try:
            report = run_correction_loop(job, client=client, max_rounds=2)
        except Exception as exc:  # noqa: BLE001
            print(f"       Boucle KO : {type(exc).__name__}: {exc}")
            report = report0
        dt_corr = time.time() - t_corr
        job.refresh_from_db()
        print(f"       Boucle terminee en {dt_corr/60:.1f} min - "
              f"cout total : {job.total_cost_eur} EUR")
        print(f"       Gate final passed : {report.passed} ({len(report.failures)} failures)")
    else:
        print("[6/8] Gate initial passe - pas de correction necessaire.")

    if not report.passed:
        by_check: dict[str, list[str]] = {}
        for f in report.failures:
            by_check.setdefault(f.check, []).append(
                f"[ch.{f.chapter_number}] {f.detail[:200]}"
            )
        print("       Failures par controle :")
        for check, items in by_check.items():
            print(f"         * {check} ({len(items)}) :")
            for item in items[:5]:
                print(f"             - {item}")
            if len(items) > 5:
                print(f"             ... et {len(items) - 5} de plus.")

    # 7. Rendu HTML + PDF
    scratch = Path(os.environ.get("TEMP", r"C:\Users\tobid\AppData\Local\Temp")) / "vague5"
    scratch.mkdir(parents=True, exist_ok=True)

    print("[7/8] Rendu HTML + PDF...")
    try:
        html = render_branded_html(job)
        pdf_client = get_pdf_client()
        from generation.rendering import _document_title
        title = _document_title(job)
        result = pdf_client.generate(title=title, html=html)

        # Copie locale dans scratch pour relecture directe.
        html_local = scratch / f"vague5_{job.id}.html"
        pdf_local = scratch / f"vague5_{job.id}.pdf"
        html_local.write_text(html, encoding="utf-8")
        pdf_local.write_bytes(result.pdf_bytes)

        print(f"       HTML : {html_local}")
        print(f"       PDF  : {pdf_local}  ({result.page_count} pages)")
        if result.pdf_download_url and not result.pdf_download_url.startswith("https://pdf.evkha.local"):
            print(f"       URL  : {result.pdf_download_url}")
    except Exception as exc:  # noqa: BLE001
        print(f"[7/8] Rendu KO : {type(exc).__name__}: {exc}")
        print("       Le corpus markdown reste disponible a l'etape 8.")

    # 8. Dump corpus markdown (filet de securite)
    dump_path = scratch / f"vague5_{job.id}.md"
    with dump_path.open("w", encoding="utf-8") as f:
        f.write(f"# VAGUE 5 - job {job.id}\n\n")
        f.write(f"Brief : {nom} | Statut : {job.status} | Gate : {report.passed} "
                f"| Cout : {job.total_cost_eur} EUR\n\n")
        f.write("---\n\n")
        for ch in job.chapters.order_by("chapter_number"):
            f.write(f"\n\n## Chapitre {ch.chapter_number} - {ch.chapter_title}\n\n")
            f.write(ch.content or "*(vide)*")
    print(f"[8/8] Corpus markdown : {dump_path}")

    return 0 if report.passed else 2


if __name__ == "__main__":
    sys.exit(main())
