"""Le modele ne peut pas eviter de se repeter s'il ignore ce qu'il a deja fait.

Mesure sur le livrable reel `4b827759` du 05/08/2026, dix figures rendues :
DEUX entonnoirs quasi identiques — « Du marche mondial au marche atteignable
par Joalie » et « Du marche national au marche atteignable par Joalie ». La
cliente l'a vu immediatement : « on voit un certain graphe meme plusieurs
fois ».

La consigne disait pourtant « ne repete pas deux fois la meme forme ». Elle
demandait l'impossible : le modele ecrit UN chapitre a la fois et ne voit ni
les autres chapitres, ni les figures qu'il y a placees. Une regle qu'on ne peut
pas appliquer n'est pas une regle.

On lui donne donc la memoire : la liste des formes deja employees par les
chapitres precedents du meme dossier, lue dans leurs payloads — seule source
qui sache ce que l'etude porte reellement.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from catalog.models import DeliverableType
from generation.chapitres.runner import formes_deja_employees
from generation.models import ChapterGeneration, ChapterStatus, GenerationJob


def _payload(numero: int, formes: list[str]) -> dict[str, Any]:
    return {
        "chapitre": numero,
        "titre": f"Chapitre {numero}",
        "resume": "r " * 160,
        "donnees_utilisees": ["marche_national_taille"],
        "blocs": [
            {
                "type": "graphique",
                "graphique": {
                    "type_graphique": forme,
                    "titre": f"Figure {forme}",
                    "donnees_ids": ["marche_national_taille"],
                },
            }
            for forme in formes
        ],
    }


@pytest.fixture
def job() -> Any:
    from catalog.models import Offer
    from customers.models import Customer
    from orders.models import Order

    offre = Offer.objects.create(
        name="EM", slug="test-variete", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="variete@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-variete", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("4.00"),
    )


def _ecrire(job: Any, numero: int, formes: list[str]) -> None:
    ChapterGeneration.objects.create(
        job=job, chapter_number=numero, chapter_title=f"Chapitre {numero}",
        prompt_key=f"em.{numero:02d}.x", status=ChapterStatus.DONE,
        payload=_payload(numero, formes),
    )


@pytest.mark.django_db
def test_les_formes_des_chapitres_precedents_sont_relues(job: Any) -> None:
    """Sur le code d'avant, cette liste n'existait pas : le modele ecrivait a l'aveugle."""
    _ecrire(job, 1, ["entonnoir"])
    _ecrire(job, 2, ["courbes", "camembert"])

    assert formes_deja_employees(job, avant=5) == ["entonnoir", "courbes", "camembert"]


@pytest.mark.django_db
def test_seuls_les_chapitres_PRECEDENTS_comptent(job: Any) -> None:
    """Un chapitre ne doit pas se voir lui-meme, ni ceux qui le suivent."""
    _ecrire(job, 1, ["entonnoir"])
    _ecrire(job, 4, ["radar"])

    assert formes_deja_employees(job, avant=4) == ["entonnoir"]


@pytest.mark.django_db
def test_un_chapitre_illisible_ne_prive_pas_le_suivant(job: Any) -> None:
    """Un payload corrompu doit couter sa propre ligne, pas la memoire entiere.

    C'est la difference entre une degradation et une panne (regle 1).
    """
    _ecrire(job, 1, ["entonnoir"])
    ChapterGeneration.objects.create(
        job=job, chapter_number=2, chapter_title="Casse", prompt_key="em.02.x",
        status=ChapterStatus.DONE, payload={"chapitre": "pas un entier"},
    )
    _ecrire(job, 3, ["radar"])

    assert formes_deja_employees(job, avant=9) == ["entonnoir", "radar"]


@pytest.mark.django_db
def test_le_prompt_nomme_les_formes_vues_et_celles_qui_restent(job: Any) -> None:
    """Nommer ce qui est pris ne suffit pas : il faut nommer ce qui est libre.

    Sans la seconde liste, le modele doit deduire le complementaire d'un
    catalogue de quinze entrees a chaque chapitre.
    """
    from datetime import date

    from generation.chapitres.runner import _bloc_visuels
    from generation.socle.schema import Socle, Zone

    _ecrire(job, 1, ["entonnoir"])
    _ecrire(job, 2, ["entonnoir"])

    bloc = _bloc_visuels(
        Socle(
            secteur="joaillerie de créateurs",
            zone=Zone(pays="France"),
            date_socle=date(2026, 8, 5),
        ),
        job,
        numero=6,
    )

    assert "FORMES DÉJÀ EMPLOYÉES" in bloc
    assert "`entonnoir` ×2" in bloc
    assert "Encore libres" in bloc
    assert "`radar`" in bloc


#: Plancher exige par la cliente le 06/08/2026 : « au moins 17 a 25 graphes par
#: document, c'est une obligation absolue ».
#:
#: La charte demande PLUS que ce plancher, et c'est deliberé : mesure du dossier
#: 9be9a422, quinze figures demandees pour onze rendues. Le rendu refuse
#: legitimement celles dont la donnee ne se prete pas (unites melangees, radar
#: sans notes). Viser le plancher exact le manquerait une fois sur deux.
PLANCHER_CLIENTE = 17

#: Ecrit en toutes lettres dans la charte, parce qu'un modele suit mieux un mot
#: qu'un chiffre noye dans une phrase.
NOMBRES_EN_LETTRES = {
    "QUINZE": 15, "SEIZE": 16, "DIX-SEPT": 17, "DIX-HUIT": 18, "DIX-NEUF": 19,
    "VINGT": 20, "VINGT-ET-UNE": 21, "VINGT-DEUX": 22, "VINGT-TROIS": 23,
    "VINGT-QUATRE": 24, "VINGT-CINQ": 25,
}


def _figures_demandees(prompt: str) -> int:
    """Combien de figures la charte reclame-t-elle, quel que soit le mot employe."""
    for mot, valeur in NOMBRES_EN_LETTRES.items():
        if f"{mot} figures" in prompt:
            return valeur
    raise AssertionError("la charte ne chiffre plus son objectif de figures")


def test_l_objectif_chiffre_est_dit_au_modele() -> None:
    """« Il faut au moins 10 graphes differents […] plus de 15 graphes » — 05/08.
    Puis « au moins 17 a 25 graphes par document » — 06/08.

    Une ambition qui n'est pas chiffree n'en est pas une : la consigne d'avant
    disait « emploie-les », et l'etude en portait deux.

    Le test ne compare plus au MOT « QUINZE » : il lisait la formulation, pas
    l'exigence, et tombait des que la cliente relevait la barre — en donnant
    l'impression d'une regression alors que le produit s'ameliorait. Il verifie
    desormais que la charte chiffre son objectif, et que ce chiffre atteint le
    plancher demande.
    """
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)

    assert _figures_demandees(prompt) >= PLANCHER_CLIENTE
    assert "FORMES DIFFERENTES" in prompt
    assert "un chapitre sans figure doit etre l'exception" in prompt
