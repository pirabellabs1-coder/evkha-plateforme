"""Relance WAOME EM avec la refonte post-feedback Evangeline.

Clone la submission du job WAOME v1 (49953f14) avec les MEMES variables
normalisees, cree un nouvel order + submission + job, execute la
generation avec le client Claude reel, puis rapporte le gate report.

Usage (depuis backend/):
    python scripts/lancer_waome_v2.py

Contrainte SaaS : EVKHA_USE_STUB_EMAIL=true doit rester actif — le
livrable ne partira PAS automatiquement chez Evangeline. On decidera
manuellement de le lui envoyer apres relecture.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "evkha.settings")
    import django
    django.setup()

    from django.conf import settings

    # Verrous critiques.
    if getattr(settings, "EVKHA_USE_STUB_AI", True):
        print("ABORT: EVKHA_USE_STUB_AI=true, cette relance doit tourner sur le client reel.")
        return 1
    if not getattr(settings, "EVKHA_USE_STUB_EMAIL", False):
        print("ABORT: EVKHA_USE_STUB_EMAIL doit rester true (pas d'envoi automatique).")
        return 1
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ABORT: ANTHROPIC_API_KEY manquante dans l'environnement.")
        return 1

    from customers.models import Customer
    from generation.correction import run_correction_loop
    from generation.gate import run_delivery_gate
    from generation.models import GenerationJob
    from generation.runner import run_generation_job
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from integrations.claude import get_claude_client
    from orders.models import Order

    # 1. Recup vars WAOME v1.
    job_v1 = GenerationJob.objects.get(id__startswith="49953f14")
    sub_v1 = IntakeSubmission.objects.filter(order_id=job_v1.order_id).first()
    if sub_v1 is None:
        print("ABORT: submission WAOME v1 introuvable.")
        return 1
    variables = dict(sub_v1.normalized_variables)
    print(
        f"[step 1] Variables recuperees ({len(variables)} keys) "
        f"— projet: {variables.get('NOM_ENTREPRISE')}"
    )

    # 2. Nouvel order + submission dedies a la relance.
    offer = job_v1.order.offer
    customer, _ = Customer.objects.get_or_create(
        email="waome-v2@evkha.local",
        defaults={"first_name": "WAOME", "last_name": "v2 (relance)"},
    )
    order = Order.objects.create(
        systeme_order_id=f"waome_v2_{int(time.time())}",
        customer=customer,
        offer=offer,
    )
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables=variables,
    )
    print(f"[step 2] Order/submission crees : order={order.id}, submission={submission.id}")

    # 3. Bootstrap du job (le seed des locked_facts est fait par run_generation_job).
    job = bootstrap_generation_job(submission)
    print(f"[step 3] Job cree : {job.id} ({job.deliverable_type})")
    print(f"         {job.chapters.count()} chapitres a generer.")

    # 4. Lance la generation avec le client reel.
    print("[step 4] Generation en cours (client Anthropic reel)...")
    t0 = time.time()
    client = get_claude_client()
    print(f"         Client actif : {type(client).__name__}")
    try:
        run_generation_job(job, client=client)
    except Exception as exc:  # noqa: BLE001
        print(f"[step 4] ECHEC pendant run_generation_job : {type(exc).__name__}: {exc}")
        job.refresh_from_db()
        print(f"         Statut job final : {job.status}")
        return 1

    dt = time.time() - t0
    job.refresh_from_db()
    print(f"[step 4] Generation terminee en {dt/60:.1f} min. Statut : {job.status}")
    print(f"         Cout total : {job.total_cost_eur} EUR")

    # 5. Gate initial.
    print("[step 5] Passage du gate initial...")
    report_initial = run_delivery_gate(job)
    print(f"         Gate initial passed : {report_initial.passed} "
          f"({len(report_initial.failures)} failures)")

    # 6. Boucle de correction si necessaire.
    if not report_initial.passed:
        print("[step 6] Boucle de correction (regenere les chapitres fautifs)...")
        t_corr = time.time()
        try:
            report = run_correction_loop(job, client=client, max_rounds=2)
        except Exception as exc:  # noqa: BLE001
            print(f"         Boucle KO : {type(exc).__name__}: {exc}")
            report = report_initial
        dt_corr = time.time() - t_corr
        job.refresh_from_db()
        print(f"         Boucle terminee en {dt_corr/60:.1f} min. "
              f"Cout total : {job.total_cost_eur} EUR")
        print(f"         Gate final passed : {report.passed} "
              f"({len(report.failures)} failures)")
    else:
        report = report_initial

    if not report.passed:
        by_check: dict[str, list[str]] = {}
        for f in report.failures:
            by_check.setdefault(f.check, []).append(
                f"[ch. {f.chapter_number}] {f.detail[:200]}"
            )
        for check, items in by_check.items():
            print(f"    * {check} ({len(items)}) :")
            for item in items[:5]:
                print(f"        - {item}")
            if len(items) > 5:
                print(f"        ... et {len(items) - 5} de plus.")

    # 7. Dump corpus markdown pour relecture.
    scratch = Path(os.environ.get(
        "TEMP",
        r"C:\Users\tobid\AppData\Local\Temp",
    )) / "waome_v2"
    scratch.mkdir(parents=True, exist_ok=True)
    dump = scratch / f"waome_v2_{job.id}.md"
    with dump.open("w", encoding="utf-8") as f:
        f.write(f"# WAOME v2 — job {job.id}\n\n")
        f.write(f"Statut : {job.status} — gate passed : {report.passed}\n\n")
        for ch in job.chapters.order_by("chapter_number"):
            f.write(f"\n\n## Chapitre {ch.chapter_number} — {ch.chapter_title}\n\n")
            f.write(ch.content or "(vide)")
    print(f"[step 7] Corpus assemble : {dump}")

    return 0 if report.passed else 2


if __name__ == "__main__":
    sys.exit(main())
