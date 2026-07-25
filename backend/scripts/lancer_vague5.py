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

Usage (depuis backend/) :
    ANTHROPIC_API_KEY=sk-... EVKHA_USE_STUB_AI=false EVKHA_USE_STUB_EMAIL=true \\
        python scripts/lancer_vague5.py

Le livrable NE PART PAS chez Evangeline (EVKHA_USE_STUB_EMAIL=true obligatoire).
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

    from catalog.models import DeliverableType
    from customers.models import Customer
    from generation.correction import run_correction_loop
    from generation.gate import run_delivery_gate
    from generation.models import GenerationJob
    from generation.runner import run_generation_job
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from integrations.claude import get_claude_client
    from orders.models import Order

    # 1. Recuperation des variables du brief WAOME
    source_sub = None
    try:
        job_src = GenerationJob.objects.get(id__startswith=_JOB_SOURCE_PREFIX)
        source_sub = IntakeSubmission.objects.filter(order_id=job_src.order_id).first()
    except GenerationJob.DoesNotExist:
        pass

    if source_sub is None:
        # Fallback : derniere submission MARKET_STUDY normalisee disponible.
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
    print(f"[1/7] Brief source : job={getattr(source_sub.order, 'id', '?')} "
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
    print(f"[2/7] Order cree : {order.id} | submission : {submission.id}")

    # 3. Bootstrap job
    job = bootstrap_generation_job(submission)
    print(f"[3/7] Job : {job.id} ({job.deliverable_type}) - {job.chapters.count()} chapitres")

    # 4. Generation
    print("[4/7] Generation en cours (claude-sonnet-4-6, client reel)...")
    t0 = time.time()
    client = get_claude_client()
    print(f"       Client : {type(client).__name__}")
    try:
        run_generation_job(job, client=client)
    except Exception as exc:  # noqa: BLE001
        print(f"[4/7] ECHEC run_generation_job : {type(exc).__name__}: {exc}")
        job.refresh_from_db()
        print(f"       Statut : {job.status}")
        return 1

    dt = time.time() - t0
    job.refresh_from_db()
    done = job.chapters.filter(status="done").count()
    total = job.chapters.count()
    print(f"[4/7] Termine en {dt/60:.1f} min - {done}/{total} chapitres DONE "
          f"- cout : {job.total_cost_eur} EUR")

    # 5. Gate initial
    print("[5/7] Gate initial...")
    report0 = run_delivery_gate(job)
    print(f"       Passed : {report0.passed} ({len(report0.failures)} failures)")

    # 6. Boucle de correction
    report = report0
    if not report0.passed:
        print("[6/7] Boucle de correction (max 2 rounds)...")
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
        print("[6/7] Gate initial passe - pas de correction necessaire.")

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

    # 7. Dump corpus markdown
    scratch = Path(os.environ.get("TEMP", r"C:\Users\tobid\AppData\Local\Temp")) / "vague5"
    scratch.mkdir(parents=True, exist_ok=True)
    dump_path = scratch / f"vague5_{job.id}.md"
    with dump_path.open("w", encoding="utf-8") as f:
        f.write(f"# VAGUE 5 - job {job.id}\n\n")
        f.write(f"Brief : {nom} | Statut : {job.status} | Gate : {report.passed} "
                f"| Cout : {job.total_cost_eur} EUR\n\n")
        f.write("---\n\n")
        for ch in job.chapters.order_by("chapter_number"):
            f.write(f"\n\n## Chapitre {ch.chapter_number} - {ch.chapter_title}\n\n")
            f.write(ch.content or "*(vide)*")
    print(f"[7/7] Corpus : {dump_path}")

    return 0 if report.passed else 2


if __name__ == "__main__":
    sys.exit(main())
