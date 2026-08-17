"""Un dossier qui ecrit ne se declare plus « en attente ».

## Le defaut mesure

Business plan `256e63d8`, 17/08/2026. La ligne porte `status=pending` et
`started_at=None` pendant que la generation ecrit ses chapitres : constate a
1/22 pour 0,05 EUR, puis a 17/22 pour 2,24 EUR. La cliente lit dans son espace
« votre etude est dans la file de production, elle demarre dans quelques
instants » — sous une liste d'etapes qui montre, elle, les chapitres en cours.
Deux avis sur le meme ecran (regle 5), et c'est le plus visible qui ment.

## Pourquoi la ligne peut mentir

Le statut n'etait ecrit qu'UNE fois, au lancement. `relaunch_generation_job`
est le seul code qui reecrit `pending` avec `started_at` vide, et il le fait
sans egard pour une tache en train de produire.

## Ce que ce mensonge coutait, au-dela de l'affichage

`duree_sans_progression` et `reset_stuck_generation_jobs` ne regardent QUE les
dossiers `running`. Un dossier bloque dans cet etat etait invisible aux DEUX
gardiens — exactement le silence qui a laisse une cliente attendre
soixante-seize minutes le 09/08/2026, dans une autre variante.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from generation.models import ChapterStatus, JobStatus
from generation.services import duree_sans_progression
from organisations.suivi import message_client

# `production_engagee` et `reaffirmer_en_cours` sont importees DANS les tests
# qui s'en servent, et non ici : importees en tete, leur absence ferait echouer
# la COLLECTE du module sur le code d'avant, et les tests de comportement —
# ceux qui prouvent vraiment quelque chose — ne tourneraient jamais (regle 6).


def _dossier(slug: str, *, statut=JobStatus.PENDING, cout="0.0000"):
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(
        name="Business plan", slug=slug,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email=f"{slug}@test.local")
    commande = Order.objects.create(
        systeme_order_id=slug, customer=client, offer=offer,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        status=statut,
        total_cost_eur=Decimal(cout),
    )
    for numero in range(1, 4):
        ChapterGeneration.objects.create(
            job=job, chapter_number=numero, chapter_title=f"Ch {numero}",
            prompt_key=f"bp.0{numero}", status=ChapterStatus.PENDING,
        )
    return job


@pytest.mark.django_db
def test_un_chapitre_ecrit_suffit_a_dire_que_le_dossier_produit() -> None:
    from generation.services import production_engagee

    job = _dossier("produit-chapitre")
    assert not production_engagee(job)

    chapitre = job.chapters.first()
    chapitre.status = ChapterStatus.DONE
    chapitre.save(update_fields=["status"])
    assert production_engagee(job)


@pytest.mark.django_db
def test_un_centime_depense_suffit_aussi() -> None:
    """Le socle se paie AVANT le premier chapitre : 0,05 EUR et 0 chapitre."""
    from generation.services import production_engagee

    job = _dossier("produit-cout", cout="0.0500")
    assert production_engagee(job)


@pytest.mark.django_db
def test_la_cliente_ne_lit_plus_que_son_etude_va_demarrer() -> None:
    """Le message EXACT qui etait faux a l'ecran.

    Echoue sur le code d'avant : `message_client` lisait `job.status` seul.
    """
    job = _dossier("message-en-attente", cout="2.2400")
    phrase = message_client(job)
    assert "démarre dans quelques instants" not in phrase, phrase
    assert phrase == MESSAGES_EN_COURS


@pytest.mark.django_db
def test_un_dossier_qui_attend_vraiment_le_dit_toujours() -> None:
    """Contre-epreuve : une etude en file, qui n'a RIEN produit, attend.

    Lui annoncer « en cours de production » serait le meme mensonge, retourne.
    """
    job = _dossier("message-vraie-attente")
    assert "démarre dans quelques instants" in message_client(job)


@pytest.mark.django_db
def test_le_gardien_voit_un_dossier_en_attente_qui_a_produit() -> None:
    """Echoue sur le code d'avant : `None` des que le statut n'est pas running.

    Un dossier orphelin dans cet etat n'etait vu par aucun gardien.
    """
    job = _dossier("gardien-orphelin", cout="2.2400")
    chapitre = job.chapters.first()
    chapitre.status = ChapterStatus.DONE
    chapitre.save(update_fields=["status"])
    job.chapters.update(updated_at=timezone.now() - timedelta(minutes=45))

    silence = duree_sans_progression(job)
    assert silence is not None
    assert silence > timedelta(minutes=40)


@pytest.mark.django_db
def test_un_dossier_simplement_en_file_n_est_pas_declare_interrompu() -> None:
    """Contre-epreuve : ne pas offrir « relancer » sur une etude qui attend.

    Le relancer ferait tourner deux generations sur le meme dossier.
    """
    assert duree_sans_progression(_dossier("gardien-en-file")) is None


@pytest.mark.django_db
def test_un_dossier_termine_n_a_pas_de_duree_sans_progression() -> None:
    """Contre-epreuve : la question ne se pose pas pour un dossier fini."""
    job = _dossier("gardien-termine", statut=JobStatus.DONE, cout="5.0000")
    assert duree_sans_progression(job) is None


@pytest.mark.django_db
def test_la_generation_retablit_une_ligne_reecrite_sous_elle() -> None:
    """Ce que le runner fait entre deux chapitres.

    Echoue sur le code d'avant : rien ne rétablissait le statut apres le
    lancement, donc la ligne restait fausse jusqu'a la fin de la generation.
    """
    from generation.services import reaffirmer_en_cours

    job = _dossier("retablit-statut", cout="0.0500")
    assert reaffirmer_en_cours(job) is True

    job.refresh_from_db()
    assert job.status == JobStatus.RUNNING
    assert job.started_at is not None

    # Idempotent : une ligne deja juste n'est pas reecrite a chaque chapitre.
    assert reaffirmer_en_cours(job) is False


@pytest.mark.django_db
def test_une_annulation_n_est_jamais_ecrasee() -> None:
    """Contre-epreuve : l'annulation est une DECISION, pas un etat perime."""
    from generation.services import reaffirmer_en_cours

    job = _dossier("retablit-annule", statut=JobStatus.CANCELLED, cout="0.0500")
    assert reaffirmer_en_cours(job) is False
    job.refresh_from_db()
    assert job.status == JobStatus.CANCELLED


#: Le message attendu, lu depuis la source pour ne pas le recopier (regle 5).
def _message_en_cours() -> str:
    from organisations.suivi import MESSAGES

    return MESSAGES[JobStatus.RUNNING]


MESSAGES_EN_COURS = _message_en_cours()
