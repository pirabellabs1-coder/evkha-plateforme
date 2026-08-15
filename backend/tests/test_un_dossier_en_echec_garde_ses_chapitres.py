"""Vingt-et-un chapitres ecrits ne se perdent pas parce que le vingt-deuxieme echoue.

Demande de la cliente, 13/08/2026 : « il faut que les documents qui ont ete en
echec soient utilisables aussi ».

Le cas est reel et il s'est produit deux fois le meme jour : une etude
concurrentielle arretee a 9 chapitres sur 10, un business plan a 21 sur 22.
Le tableau de bord affichait un statut rouge et n'offrait rien a telecharger,
alors que l'essentiel du travail etait ecrit, controle et PAYE.

L'assemblage ne coute RIEN au modele : c'est de la mise en page sur du texte
deja produit. Il n'y avait donc aucun arbitrage a faire — le seul choix etait
entre « disponible » et « perdu ».
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest


def _dossier_partiel(chapitres_ecrits: int):  # type: ignore[no-untyped-def]
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
    from orders.models import Order

    offre = Offer.objects.create(
        name="EC", slug=f"test-echec-{chapitres_ecrits}",
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
    )
    client = Customer.objects.create(email=f"echec{chapitres_ecrits}@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-echec-{chapitres_ecrits}", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
        budget_eur=Decimal("4.50"),
    )
    for numero in range(chapitres_ecrits):
        ChapterGeneration.objects.create(
            job=job, chapter_number=numero, chapter_title=f"Chapitre {numero}",
            prompt_key=f"ec.{numero:02d}", status=ChapterStatus.DONE,
            content="Un contenu de chapitre suffisamment long pour etre assemble.",
        )
    return job


@pytest.mark.django_db
def test_un_dossier_en_echec_assemble_ce_qui_est_ecrit() -> None:
    """LE point de la cliente : neuf chapitres sur dix ne se jettent pas."""
    from generation.tasks import _assembler_ce_qui_est_ecrit

    job = _dossier_partiel(9)

    with patch("documents.services.assemble_document") as assemblage, \
         patch("documents.livrable_word.chaine_word_active", return_value=False):
        _assembler_ce_qui_est_ecrit(job)

    assemblage.assert_called_once_with(job)


@pytest.mark.django_db
def test_un_dossier_sans_aucun_chapitre_n_assemble_rien() -> None:
    """CONTRE-ÉPREUVE : un document vide n'est pas un document.

    Un socle qui echoue avant le premier chapitre ne laisse rien a assembler.
    Produire un PDF de couverture seule ferait croire a un livrable.
    """
    from generation.tasks import _assembler_ce_qui_est_ecrit

    job = _dossier_partiel(0)

    with patch("documents.services.assemble_document") as assemblage:
        _assembler_ce_qui_est_ecrit(job)

    assemblage.assert_not_called()


@pytest.mark.django_db
def test_un_echec_d_assemblage_ne_masque_pas_l_echec_d_origine() -> None:
    """L'echec de generation est celui qu'on veut voir remonter.

    Si l'assemblage levait, il remplacerait la cause reelle par un incident de
    mise en page — et le motif affiche a la cliente designerait le mauvais
    coupable (regle 2).
    """
    from generation.tasks import _assembler_ce_qui_est_ecrit

    job = _dossier_partiel(9)

    with patch("documents.livrable_word.chaine_word_active", return_value=False), \
         patch("documents.services.assemble_document", side_effect=OSError("disque plein")):
        _assembler_ce_qui_est_ecrit(job)  # ne doit pas lever


@pytest.mark.django_db
def test_le_document_assemble_ne_declenche_aucun_envoi() -> None:
    """Un dossier en echec ne s'envoie pas tout seul.

    Le document existe et se telecharge — chez l'administrateur comme dans
    l'espace du client, qui liste tout artefact pret quel que soit le statut du
    dossier. Mais c'est un document INCOMPLET : son envoi reste une decision.
    """
    from pathlib import Path

    import generation.tasks as taches

    source = Path(taches.__file__).read_text(encoding="utf-8")
    corps = source.split("def _assembler_ce_qui_est_ecrit")[1].split("\ndef ")[0]

    assert "deliver_job_task" not in corps
    assert "Aucun email" in corps
