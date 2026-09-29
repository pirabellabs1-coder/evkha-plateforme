"""Le suivi client montre chaque chapitre annoncé, avec son étape en direct.

29/09/2026 : une seule étape « Rédaction des chapitres » pendant une
demi-heure. Le suivi expose désormais la liste des chapitres ANNONCÉS (la
Fiche projet exclue, décision D9) avec l'étape que pose la production.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import ChapterStatus, GenerationJob
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order
from organisations import suivi

pytestmark = pytest.mark.django_db

ANNONCES = {
    DeliverableType.MARKET_STUDY: 22,
    DeliverableType.COMPETITOR_STUDY: 9,
    DeliverableType.BUSINESS_PLAN: 21,
    DeliverableType.BUSINESS_STRATEGY: 20,
}


def _dossier(livrable: str) -> GenerationJob:
    offre = Offer.objects.create(name=livrable, slug=f"o-{livrable}", deliverable_type=livrable)
    client = Customer.objects.create(email=f"{livrable}@exemple.fr")
    commande = Order.objects.create(systeme_order_id=f"c-{livrable}", customer=client, offer=offre)
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "x", "PAYS": "France", "ZONE": "Paris", "PROJET": "T"},
    )
    return bootstrap_generation_job(soumission)


@pytest.mark.parametrize(("livrable", "annonce"), list(ANNONCES.items()))
def test_autant_de_lignes_que_de_chapitres_annonces(livrable: str, annonce: int) -> None:
    chapitres = suivi.en_dict(_dossier(livrable))["chapitres"]
    assert len(chapitres) == annonce
    assert chapitres[0]["numero"] == 1, "la Fiche projet (0) n'est pas un chapitre annoncé"


def test_l_etape_posee_par_la_production_est_lue_telle_quelle() -> None:
    job = _dossier(DeliverableType.BUSINESS_PLAN)
    job.chapters.filter(chapter_number=1).update(
        status=ChapterStatus.DONE, etape="valide", retry_count=1
    )
    job.chapters.filter(chapter_number=2).update(status=ChapterStatus.RUNNING, etape="verification")
    lignes = {c["numero"]: c for c in suivi.en_dict(job)["chapitres"]}
    assert lignes[1]["etape"] == "valide" and lignes[1]["ajuste"] is True
    assert lignes[2]["etape"] == "verification"
    assert lignes[3]["etape"] == ""


def test_un_chapitre_de_l_ancien_chemin_se_lit_sans_echec() -> None:
    """Sans étape posée : terminé = validé, en cours ou repris = en rédaction."""
    job = _dossier(DeliverableType.BUSINESS_PLAN)
    job.chapters.filter(chapter_number=1).update(status=ChapterStatus.DONE)
    job.chapters.filter(chapter_number=2).update(status=ChapterStatus.FAILED)
    lignes = {c["numero"]: c for c in suivi.en_dict(job)["chapitres"]}
    assert lignes[1]["etape"] == "valide"
    assert lignes[2]["etape"] == "redaction"


def test_un_dossier_arrete_se_dit_en_pause_et_un_chapitre_fini_valide() -> None:
    """Revue du 29/09/2026 : « rédaction en cours » restait figé sur un dossier arrêté."""
    from generation.models import JobStatus

    job = _dossier(DeliverableType.BUSINESS_PLAN)
    job.chapters.filter(chapter_number=1).update(status=ChapterStatus.DONE, etape="verification")
    job.chapters.filter(chapter_number=2).update(status=ChapterStatus.FAILED, etape="redaction")
    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.FAILED)
    job.refresh_from_db()
    lignes = {c["numero"]: c for c in suivi.en_dict(job)["chapitres"]}
    assert lignes[1]["etape"] == "valide"
    assert lignes[2]["etape"] == "pause"

