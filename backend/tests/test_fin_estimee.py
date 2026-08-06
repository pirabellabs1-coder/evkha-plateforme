"""Dans combien de temps l'etude sera-t-elle prete ? Ou rien du tout.

Demande de la cliente : « montrer les etapes avec une duree d'estimation de la
fin ». Le suivi n'affichait qu'une fourchette FIXE, `DUREE_MINUTES = (20, 45)`,
identique pour tout le monde et pour toujours — elle ne mesure rien.

## Ce que ces tests refusent

Une estimation inventee. Le module le dit deja en toutes lettres : « une
estimation fausse est pire que pas d'estimation » (regle 1). Les trois refus
verrouilles ici :

- pas de mesure possible -> `None`, et l'interface se rabat sur la fourchette,
  presentee comme une fourchette ;
- une extrapolation faite trop tot -> refusee. Une regle de trois sur 3 %
  d'avancement multiplie par trente-trois la moindre irregularite de demarrage,
  et le demarrage EST irregulier ;
- un temps restant negatif -> jamais. Une etude en retard sur sa propre
  estimation dit « bientot », pas « il y a trois minutes ».
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import (
    ChapterGeneration,
    ChapterStatus,
    GenerationJob,
    JobStatus,
)
from orders.models import Order, OrderStatus
from organisations import suivi

pytestmark = pytest.mark.django_db


def _offre() -> Offer:
    offre, _ = Offer.objects.get_or_create(
        slug="em",
        defaults={"name": "Etude de marche", "deliverable_type": DeliverableType.MARKET_STUDY},
    )
    return offre


def creer_job(
    *,
    statut: str = JobStatus.RUNNING,
    demarre_il_y_a: timedelta | None = None,
    chapitres: int = 0,
    faits: int = 0,
    type_livrable: str = DeliverableType.MARKET_STUDY,
) -> GenerationJob:
    contact = Customer.objects.create(email=f"c{GenerationJob.objects.count()}@exemple.fr")
    commande = Order.objects.create(
        customer=contact, offer=_offre(),
        systeme_order_id=f"cmd-{GenerationJob.objects.count()}",
        status=OrderStatus.PROCESSING,
    )
    job = GenerationJob.objects.create(
        order=commande, deliverable_type=type_livrable, status=statut,
    )
    if demarre_il_y_a is not None:
        job.started_at = timezone.now() - demarre_il_y_a
        job.save(update_fields=["started_at"])
    for numero in range(chapitres):
        ChapterGeneration.objects.create(
            job=job, chapter_number=numero + 1,
            status=ChapterStatus.DONE if numero < faits else ChapterStatus.PENDING,
        )
    return job


# ── On se tait plutot que de mentir ──────────────────────────────────────────


def test_une_etude_terminee_n_a_pas_de_temps_restant() -> None:
    job = creer_job(statut=JobStatus.DONE, demarre_il_y_a=timedelta(hours=1))
    assert suivi.fin_estimee(job) is None


def test_sans_date_de_demarrage_on_n_estime_rien() -> None:
    """Il n'y a rien a comparer : on le dit en ne disant rien (regle 1)."""
    job = creer_job(demarre_il_y_a=None, chapitres=20, faits=10)
    assert suivi.fin_estimee(job) is None


def test_on_refuse_d_extrapoler_sur_un_avancement_minuscule() -> None:
    """3 % d'avancement multiplie par trente-trois l'irregularite du demarrage.

    Sans ce plancher, une etude de vingt minutes annoncerait « 4 heures » a
    quelqu'un qui vient de commander.
    """
    job = creer_job(demarre_il_y_a=timedelta(minutes=5), chapitres=30, faits=1)

    assert suivi.progression(job) < suivi.PROGRESSION_MINIMALE_POUR_ESTIMER
    assert suivi.fin_estimee(job) is None


def test_on_refuse_d_extrapoler_sur_quelques_secondes() -> None:
    """Une mesure de rythme faite en dix secondes n'a rien mesure."""
    job = creer_job(demarre_il_y_a=timedelta(seconds=10), chapitres=10, faits=5)

    assert suivi.fin_estimee(job) is None


# ── Quand on peut mesurer, on mesure ─────────────────────────────────────────


def test_l_estimation_se_fonde_d_abord_sur_l_etude_elle_meme() -> None:
    """La seule source qui tienne compte d'une journee ou l'API repond lentement.

    Vingt minutes ecoulees pour la moitie du travail : il en reste environ
    vingt. On verifie l'ordre de grandeur, pas la minute — le rapport depend de
    la ponderation de `progression`, qui a le droit de bouger.
    """
    job = creer_job(demarre_il_y_a=timedelta(minutes=20), chapitres=10, faits=5)

    estimation = suivi.fin_estimee(job)

    assert estimation is not None
    assert estimation["fondee_sur"] == "cette_etude"
    assert 5 <= estimation["minutes_restantes"] <= 90


def test_le_temps_restant_n_est_jamais_negatif() -> None:
    """Une etude en retard sur son estimation dit « bientot », pas un negatif."""
    job = creer_job(demarre_il_y_a=timedelta(hours=6), chapitres=10, faits=9)

    estimation = suivi.fin_estimee(job)

    assert estimation is not None
    assert estimation["minutes_restantes"] >= 1


def test_au_demarrage_on_se_fonde_sur_les_etudes_passees() -> None:
    """Rien a extrapoler encore, mais l'historique du meme type sait deja.

    Il faut au moins trois etudes : une mediane sur deux valeurs n'est pas une
    mediane, c'est une moyenne de deux accidents.
    """
    for _ in range(4):
        passe = creer_job(statut=JobStatus.DONE, demarre_il_y_a=timedelta(hours=2))
        assert passe.started_at is not None
        passe.completed_at = passe.started_at + timedelta(minutes=30)
        passe.save(update_fields=["completed_at"])

    job = creer_job(demarre_il_y_a=timedelta(minutes=4), chapitres=20, faits=0)

    estimation = suivi.fin_estimee(job)

    assert estimation is not None
    assert estimation["fondee_sur"] == "etudes_passees"
    # 30 minutes de mediane moins 4 ecoulees.
    assert 20 <= estimation["minutes_restantes"] <= 32


def test_deux_etudes_passees_ne_suffisent_pas() -> None:
    """CONTRE-EPREUVE du seuil : en dessous de trois, on se tait."""
    for _ in range(2):
        passe = creer_job(statut=JobStatus.DONE, demarre_il_y_a=timedelta(hours=2))
        assert passe.started_at is not None
        passe.completed_at = passe.started_at + timedelta(minutes=30)
        passe.save(update_fields=["completed_at"])

    job = creer_job(demarre_il_y_a=timedelta(minutes=4), chapitres=20, faits=0)

    assert suivi.fin_estimee(job) is None


def test_l_historique_d_un_autre_type_de_livrable_ne_sert_pas() -> None:
    """Un business plan et une etude de marche n'ont ni le meme nombre de
    chapitres ni la meme recherche. Les melanger donnerait une estimation juste
    en moyenne et fausse pour chacun.
    """
    for _ in range(5):
        passe = creer_job(
            statut=JobStatus.DONE, demarre_il_y_a=timedelta(hours=2),
            type_livrable=DeliverableType.BUSINESS_PLAN,
        )
        assert passe.started_at is not None
        passe.completed_at = passe.started_at + timedelta(minutes=30)
        passe.save(update_fields=["completed_at"])

    job = creer_job(
        demarre_il_y_a=timedelta(minutes=4), chapitres=20, faits=0,
        type_livrable=DeliverableType.MARKET_STUDY,
    )

    assert suivi.fin_estimee(job) is None


# ── Ce que l'interface reçoit ────────────────────────────────────────────────


def test_le_suivi_expose_l_estimation_et_garde_la_fourchette() -> None:
    """Les deux coexistent, et ne disent pas la meme chose.

    `fin_estimee` est une MESURE ; `duree_estimee_minutes` est une fourchette
    large qui ne pretend pas en etre une. L'interface affiche la premiere quand
    elle existe, et se rabat sur la seconde en la presentant comme telle.
    """
    job = creer_job(demarre_il_y_a=timedelta(minutes=20), chapitres=10, faits=5)

    charge = suivi.en_dict(job)

    assert charge["fin_estimee"] is not None
    assert charge["fin_estimee"]["echeance"]
    assert charge["duree_estimee_minutes"] == list(suivi.DUREE_MINUTES)
