"""Le modèle sait quelles figures sont DÉJÀ posées, avec leurs données.

## Le défaut, mesuré

Business plan `68fc68b4` : **treize** lignes « Figure présentée au chapitre N
— … » dans le document livré. Étude de la concurrence `e150aade` : sept, dont
quatre identiques.

Ces lignes ne sont pas des légendes orphelines : c'est le traitement délibéré
d'une figure en DOUBLON (`rendu_word.assemblage._renvoi`, revue du
29/09/2026). La seconde occurrence est remplacée par un renvoi.

Mais le lecteur voit « Figure présentée… » là où un graphique était annoncé, et
le classe parmi les placeholders — c'est exactement ce que la cliente a fait le
28/10/2026 : « graphiques annoncés mais absents », « encadrés répétés à
l'identique ».

## Pourquoi le modèle ne pouvait pas l'éviter

`formes_deja_employees` lui disait quels TYPES avaient servi. Or un doublon se
définit par sa forme ET ses données (`assemblage._signature`). Rien ne lui
disait quelles DONNÉES étaient déjà tracées : il redemandait la même figure
sans aucun moyen de le savoir.

Ces tests échouent sur le code d'avant : `donnees_deja_tracees` n'existait pas,
et `_bloc_visuels` ne transmettait que les formes.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.runner import (
    _figures_deja_posees,
    donnees_deja_tracees,
    formes_deja_employees,
)
from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
from orders.models import Order

BP = DeliverableType.BUSINESS_PLAN

#: La figure de l'emboîtement du marché, telle qu'un chapitre la demande.
EMBOITEMENT = {
    "chapitre": 1,
    "titre": "Le marché",
    "blocs": [
        {"type": "paragraphe", "texte": "Le marché se resserre du total à l'atteignable."},
        {"type": "graphique", "graphique": {
            "type_graphique": "entonnoir",
            "titre": "Du marché total au marché atteignable",
            "donnees_ids": ["marche_total", "marche_export", "marche_atteignable"],
        }},
    ],
    "resume": "Le chapitre pose les trois tailles de marché et leur emboîtement.",
}


@pytest.fixture
def job(db: Any) -> GenerationJob:
    offre = Offer.objects.create(name="BP", slug="figures-doublon", deliverable_type=BP)
    client = Customer.objects.create(email="figures@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-figures", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=BP, budget_eur=Decimal("8.0000"),
    )


def _ecrire(job: GenerationJob, numero: int, payload: dict[str, Any]) -> None:
    ChapterGeneration.objects.create(
        job=job, chapter_number=numero, chapter_title="T",
        prompt_key=f"bp.{numero:02d}", status=ChapterStatus.DONE, payload=payload,
    )


def test_les_donnees_tracees_sont_retenues(job: GenerationJob) -> None:
    """Le test qui échoue sur le code d'avant : seules les FORMES traversaient."""
    _ecrire(job, 1, EMBOITEMENT)

    [(titre, ids)] = donnees_deja_tracees(job, avant=5)
    assert titre == "Du marché total au marché atteignable"
    assert ids == ("marche_total", "marche_export", "marche_atteignable")

    # La mémoire des FORMES existait déjà, et elle ne suffisait pas : elle ne
    # dit pas quelles données ont servi.
    assert formes_deja_employees(job, avant=5) == ["entonnoir"]


def test_le_bloc_nomme_la_figure_et_ses_identifiants(job: GenerationJob) -> None:
    _ecrire(job, 1, EMBOITEMENT)

    bloc = _figures_deja_posees(job, numero=5)

    assert "FIGURES DÉJÀ POSÉES" in bloc
    assert "Du marché total au marché atteignable" in bloc
    assert "marche_atteignable" in bloc
    # Et la raison, pour que le modèle sache ce qu'il risque.
    assert "Figure présentée au chapitre" in bloc
    # Plus l'issue de secours : renvoyer en prose, ou tracer autre chose.
    assert "trace AUTRE CHOSE" in bloc


def test_le_premier_chapitre_ne_recoit_rien(job: GenerationJob) -> None:
    """Contre-épreuve : rien de posé, aucun bloc — et pas de bloc vide."""
    assert _figures_deja_posees(job, numero=1) == ""
    assert donnees_deja_tracees(job, avant=1) == []


def test_un_chapitre_ne_voit_pas_les_figures_des_SUIVANTS(job: GenerationJob) -> None:
    """Contre-épreuve : l'étude s'écrit dans l'ordre."""
    _ecrire(job, 7, EMBOITEMENT)

    assert donnees_deja_tracees(job, avant=5) == []


def test_un_chapitre_en_echec_ne_compte_pas(job: GenerationJob) -> None:
    """Contre-épreuve : sa figure n'est pas dans le document."""
    ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="T", prompt_key="bp.01",
        status=ChapterStatus.FAILED, payload=EMBOITEMENT,
    )
    assert donnees_deja_tracees(job, avant=5) == []


def test_un_payload_illisible_ne_prive_pas_le_suivant(job: GenerationJob) -> None:
    """Un chapitre abîmé ne doit pas faire perdre la mémoire des autres."""
    _ecrire(job, 1, {"chapitre": "pas un nombre", "blocs": "cassé"})
    _ecrire(job, 2, EMBOITEMENT)

    assert len(donnees_deja_tracees(job, avant=5)) == 1


def test_le_bloc_part_bien_dans_le_prompt_des_visuels(job: GenerationJob) -> None:
    """Écrit mais pas branché, c'est le défaut de Gamma : on vérifie le câble."""
    from generation.chapitres.runner import _bloc_visuels
    from generation.socle.prompt import construire_prompt_socle
    from generation.socle.schema import Socle
    from generation.socle.stub import socle_de_demonstration

    _ecrire(job, 1, EMBOITEMENT)
    socle = Socle.model_validate(socle_de_demonstration(
        construire_prompt_socle(deliverable_type=BP, variables={"SECTEUR": "agroalimentaire"})
    ))
    visuels = _bloc_visuels(socle, job, 5)

    assert "FIGURES DÉJÀ POSÉES" in visuels
    assert "marche_atteignable" in visuels
    # La mémoire des formes reste, elle ne doit pas avoir été écrasée.
    assert "FORMES DÉJÀ EMPLOYÉES" in visuels
