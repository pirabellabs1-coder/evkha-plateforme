"""Ce qu'Anthropic facture deux fois doit être compté deux fois.

Le plafond de dépense d'un dossier ne vaut que s'il porte sur l'argent
RÉELLEMENT dépensé. `record_chapter_cost` écrasait `chapter.cost_eur`, et le
chemin de régénération — CHECK de bloc, boucle de correction — repasse par
`_generate_chapter`, donc par cette fonction. La première tentative
disparaissait du total.

`enforce_budget` comparait donc la dépense à un chiffre qui oublie les
reprises. Le défaut échouait en silence : ni erreur, ni incident, seulement un
total sous-estimé. Sur le dernier run complet journalisé, six chapitres ont été
signalés `check_bloc_non_resolu` — six régénérations dont le coût initial
n'était compté nulle part.

C'est la règle 1 appliquée à l'argent : un garde-fou qui juge sur une mesure
fausse n'est pas un garde-fou.

Ces tests passent par de VRAIS objets en base, et pas par des doublures. Le
total du job est recalculé depuis ses chapitres (`current_job_cost_eur`) : une
doublure en mémoire aurait vérifié l'arithmétique sans vérifier qu'elle
remonte jusqu'au chiffre que le plafond regarde.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.cost import current_job_cost_eur, record_chapter_cost
from generation.models import ChapterGeneration, GenerationJob
from orders.models import Order


@pytest.fixture
def chapitre() -> ChapterGeneration:
    """Un chapitre neuf, rattaché à un job au budget large.

    Budget volontairement hors de portée : ces tests mesurent le CUMUL, pas le
    déclenchement du plafond. Les mêler ferait échouer le cumul pour la raison
    du plafond, et on corrigerait le mauvais défaut (règle 2).
    """
    offre = Offer.objects.create(
        name="EM test", slug="em-test", deliverable_type=DeliverableType.MARKET_STUDY
    )
    client = Customer.objects.create(email="cout@exemple.test")
    commande = Order.objects.create(
        systeme_order_id="cmd-cout", customer=client, offer=offre
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("999"),
    )
    return ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Marche", prompt_key="em.01"
    )


@pytest.mark.django_db
def test_une_premiere_passe_pose_le_cout(chapitre: ChapterGeneration) -> None:
    """Garde-fou : sans lui, un cumul toujours nul passerait pour un succès."""
    record_chapter_cost(chapter=chapitre, input_tokens=1000, output_tokens=500)

    assert chapitre.cost_eur > Decimal("0")
    assert chapitre.input_tokens == 1000
    assert chapitre.output_tokens == 500


@pytest.mark.django_db
def test_une_reprise_s_ajoute_au_lieu_d_ecraser(chapitre: ChapterGeneration) -> None:
    """LE défaut corrigé.

    Deux passes identiques doivent coûter deux fois — c'est ce qu'Anthropic
    facture. Avant, la seconde effaçait la première et le total restait celui
    d'une seule.
    """
    premier = record_chapter_cost(chapter=chapitre, input_tokens=1000, output_tokens=500)
    apres_une_passe = chapitre.cost_eur

    second = record_chapter_cost(chapter=chapitre, input_tokens=1000, output_tokens=500)

    assert premier == second
    assert chapitre.cost_eur == apres_une_passe * 2
    assert chapitre.input_tokens == 2000
    assert chapitre.output_tokens == 1000


@pytest.mark.django_db
def test_le_total_du_job_suit_les_reprises(chapitre: ChapterGeneration) -> None:
    """Ce qui compte vraiment : le chiffre que le plafond regarde.

    `enforce_budget` juge sur `current_job_cost_eur`, recalculé depuis les
    chapitres. Vérifier le seul champ du chapitre laisserait passer une
    régression entre les deux.
    """
    unitaire = record_chapter_cost(chapter=chapitre, input_tokens=900, output_tokens=450)
    record_chapter_cost(chapter=chapitre, input_tokens=900, output_tokens=450)

    assert current_job_cost_eur(chapitre.job) == unitaire * 2


@pytest.mark.django_db
def test_trois_reprises_comptent_trois_fois(chapitre: ChapterGeneration) -> None:
    """La boucle de correction peut régénérer un chapitre plusieurs fois.

    Le cumul doit rester exact au-delà de deux passes, sinon le plafond dérive
    d'autant plus que le dossier est difficile — c'est-à-dire exactement quand
    il compte le plus.
    """
    unitaire = record_chapter_cost(chapter=chapitre, input_tokens=800, output_tokens=400)
    for _ in range(2):
        record_chapter_cost(chapter=chapitre, input_tokens=800, output_tokens=400)

    assert chapitre.cost_eur == unitaire * 3


@pytest.mark.django_db
def test_un_appel_sans_jetons_ne_fabrique_pas_de_depense(
    chapitre: ChapterGeneration,
) -> None:
    """Contre-épreuve : le cumul ne doit pas inventer de dépense (règle 6).

    Un chapitre neuf vaut zéro, et une passe à zéro jeton ne doit rien ajouter
    — sans quoi le plafond se déclencherait sur du vent.
    """
    record_chapter_cost(chapter=chapitre, input_tokens=0, output_tokens=0)

    assert chapitre.cost_eur == Decimal("0")
    assert chapitre.input_tokens == 0
