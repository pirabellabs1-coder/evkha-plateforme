"""Premiere generation REELLE d'un business plan sur le moteur structure.

Accord cliente du 06/08/2026 (« vas y pour les deux generations »). Brief
Joalie, le meme que les generations EM de reference : c'est ce qui rend les
resultats comparables.

Garde-fous, repris des lanceurs precedents :
  - refuse de tourner si EVKHA_USE_STUB_AI est actif (on veut le client reel) ;
  - refuse de tourner si le courriel n'est PAS bouche (aucun envoi automatique
    depuis un environnement de test — CLAUDE.md) ;
  - EVKHA_SOCLE_ENABLED force : sans lui on observe un autre logiciel ;
  - le plafond de depense (3,10 EUR) est tenu par `enforce_budget`, pas ici.

Usage (depuis la racine, venv actif) :
    EVKHA_USE_STUB_AI=false EVKHA_USE_STUB_EMAIL=true EVKHA_SOCLE_ENABLED=true \\
        python backend/scripts/lancer_bp_reel.py [business_plan|business_strategy]

Le .docx est copie dans %TEMP% pour relecture ; rien ne part chez qui que ce soit.
"""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "evkha.settings")
    os.environ["EVKHA_SOCLE_ENABLED"] = "true"
    import django

    django.setup()
    # La console Windows sort en cp1252 : les accents du brief la font
    # tomber. `reconfigure` n'existe que sur un vrai flux texte — sous
    # pytest ou un pipe, stdout peut etre autre chose.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")

    from django.conf import settings

    if getattr(settings, "EVKHA_USE_STUB_AI", True):
        print("ABORT: EVKHA_USE_STUB_AI=true — cette generation doit tourner sur le client reel.")
        return 1
    if not getattr(settings, "EVKHA_USE_STUB_EMAIL", False):
        print("ABORT: EVKHA_USE_STUB_EMAIL doit rester true (aucun envoi automatique).")
        return 1
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ABORT: ANTHROPIC_API_KEY manquante.")
        return 1

    livrable = sys.argv[1] if len(sys.argv) > 1 else "business_plan"
    assert livrable in ("business_plan", "business_strategy"), livrable

    from catalog.models import Offer
    from customers.models import Customer
    from documents.livrable_word import assembler_livrable_word, chaine_word_active
    from generation.models import ChapterStatus, JobStatus
    from generation.runner import run_generation_job
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
    from orders.models import Order, OrderStatus

    # Brief Joalie — identique aux generations EM de reference (9be9a422...).
    variables = {
        "PROJET": "Joalie",
        "SECTEUR": "joaillerie de créateurs",
        "PAYS": "France",
        "ZONE": "Paris",
        "REGION": "Île-de-France",
        "POSITIONNEMENT": "haut de gamme accessible",
        "CIBLE": "clientèle urbaine 30-55 ans sensible à la création",
        "APPORT": "40 000 EUR",
        "BUDGET": "100 000 EUR",
        "LECTEUR_FINAL": "banque et investisseurs",
        "DEVISE": "EUR",
    }

    marque = time.strftime("%d%H%M")
    offre, _ = Offer.objects.get_or_create(
        slug=f"reel-{livrable}",
        defaults={"name": f"Reel {livrable}", "deliverable_type": livrable},
    )
    contact, _ = Customer.objects.get_or_create(
        email="recette@evkha.fr", defaults={"first_name": "Recette"}
    )
    commande = Order.objects.create(
        systeme_order_id=f"reel-{livrable}-{marque}",
        customer=contact,
        offer=offre,
        status=OrderStatus.PROCESSING,
    )
    IntakeSubmission.objects.create(
        order=commande,
        source=IntakeSource.MANUAL,
        status=IntakeStatus.NORMALIZED,
        raw_payload=variables,
        normalized_variables=variables,
    )
    job = bootstrap_generation_job(commande.intake_submission)
    print(f"JOB {job.id}")
    print(f"  type {job.deliverable_type} — {job.chapters.count()} chapitres — "
          f"budget {job.budget_eur} EUR (plafond dur 3,10)")

    debut = time.monotonic()
    try:
        job = run_generation_job(job)
    finally:
        duree = time.monotonic() - debut
        job.refresh_from_db()
        faits = job.chapters.filter(status=ChapterStatus.DONE).count()
        print(f"  statut {job.status} — {faits}/{job.chapters.count()} chapitres "
              f"— {duree/60:.1f} min — cout {job.total_cost_eur} EUR")

    if job.status != JobStatus.DONE:
        print("GENERATION INCOMPLETE — voir incidents.")
        return 2

    assert chaine_word_active(job), "chaine Word inactive sur un job structure ?"
    livrable_word = assembler_livrable_word(job)
    controle = livrable_word.controle
    print(f"  controles : {controle.resume() if controle else 'ABSENTS'}")
    print(f"  livrable : {livrable_word.livrable}")

    rapport = livrable_word.rapport
    for attribut in ("rendus", "convertis", "abandonnes", "figures"):
        valeur = getattr(rapport, attribut, None)
        if valeur is not None:
            print(f"  rapport.{attribut} : {valeur}")

    # Copie locale pour relecture.
    from django.core.files.storage import default_storage

    if livrable_word.docx and livrable_word.docx.storage_key:
        source = Path(default_storage.path(livrable_word.docx.storage_key))
        cible = Path(tempfile.gettempdir()) / f"{livrable}_{job.id.hex[:8]}.docx"
        shutil.copy(source, cible)
        print(f"  DOCX : {cible} ({source.stat().st_size} octets)")

    print("TERMINE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
