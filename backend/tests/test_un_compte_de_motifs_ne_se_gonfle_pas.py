"""« 22 point(s) non résolu(s) » était dix remarques comptées par chapitre.

## La mesure

Les deux études de marché lancées par la cliente le 28/10/2026 ont ouvert un
incident HIGH chacune : « Gate qualité : **22** point(s) non résolu(s) » et
« **24** ». En ouvrant les `details.failures` du premier :

    22 lignes d'échec  ->  10 notes DISTINCTES

Le relecteur avait écrit dix remarques, chacune portant sur plusieurs
chapitres (« non valide sur les chapitres [18, 19, 20] »), et chacune était
répétée une fois par chapitre nommé. Le compte triplait le problème.

## Pourquoi ce n'est pas cosmétique

Un chiffre faux fait prendre des décisions. La veille au soir, « 22 incidents »
m'ont fait conclure que le correctif du taux de capture avait échoué — alors
que le document, relu, l'appliquait correctement (« taux de capture retenu de
0,1 % … ordre de grandeur raisonnable pour une marque inconnue »). J'allais
écrire un contrôle pour un défaut déjà réglé.

Un motif doit être vrai de ce que le lecteur constatera (règle 2), et **un
compte est un motif**.

## Ce qui ne change pas

Les lignes d'échec restent entières dans `details` : c'est leur
`chapter_number` qui dit à la boucle de correction quoi réécrire. Les
dédoublonner priverait des chapitres de leur réparation — la correction aurait
l'air plus propre et réparerait moins.

Ces tests échouent sur le code d'avant : il annonçait `len(report.failures)`.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from generation.gate import GateFailure


@pytest.fixture
def job() -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from orders.models import Order

    offre = Offer.objects.create(
        name="EM", slug="test-compte-motifs",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="compte@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-compte", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.MARKET_STUDY,
    )


def _rapport(*failures: GateFailure) -> Any:
    return type("R", (), {"passed": False, "failures": failures, "as_details": dict})()


#: Recopiée d'un incident réel de `6832779f`, raccourcie.
NOTE_18_19_20 = (
    "CHECK 9 (bloc I — Analyse transformee en decision) non valide sur les "
    "chapitres [18, 19, 20]. Note du relecteur : remplacer la regle de capacite."
)
NOTE_21_22 = (
    "CHECK FINAL (bloc J — Controle final avant livraison) non valide sur les "
    "chapitres [21, 22]. Note du relecteur : remplacer la reference Vega-info."
)


@pytest.mark.django_db
def test_le_titre_compte_les_remarques_pas_les_lignes(job: Any) -> None:
    """Le cas réel : deux remarques sur cinq chapitres, pas cinq points."""
    from generation import tasks
    from monitoring.models import OperationalIncident

    rapport = _rapport(
        GateFailure(check="check_bloc_non_resolu", detail=NOTE_18_19_20, chapter_number=18),
        GateFailure(check="check_bloc_non_resolu", detail=NOTE_18_19_20, chapter_number=19),
        GateFailure(check="check_bloc_non_resolu", detail=NOTE_18_19_20, chapter_number=20),
        GateFailure(check="check_bloc_non_resolu", detail=NOTE_21_22, chapter_number=21),
        GateFailure(check="check_bloc_non_resolu", detail=NOTE_21_22, chapter_number=22),
    )
    with patch("generation.gate.run_delivery_gate", return_value=rapport):
        tasks._rendre_le_verdict_du_gate(job)

    titre = OperationalIncident.objects.filter(job=job).latest("created_at").title

    assert "2 remarque(s) non résolue(s) sur 5 chapitres" in titre, titre
    assert "5 point(s)" not in titre


@pytest.mark.django_db
def test_sans_duplication_le_titre_ne_parle_pas_de_chapitres(job: Any) -> None:
    """CONTRE-ÉPREUVE : pas de « sur N chapitres » quand il n'y a rien à expliquer.

    Sans cela, un dossier à trois remarques distinctes afficherait « 3 sur 3 »,
    ce qui suggère une duplication inexistante.
    """
    from generation import tasks
    from monitoring.models import OperationalIncident

    rapport = _rapport(
        GateFailure(check="troncature", detail="Un", chapter_number=1),
        GateFailure(check="densite", detail="Deux", chapter_number=2),
    )
    with patch("generation.gate.run_delivery_gate", return_value=rapport):
        tasks._rendre_le_verdict_du_gate(job)

    titre = OperationalIncident.objects.filter(job=job).latest("created_at").title

    assert "2 remarque(s) non résolue(s), document" in titre, titre
    assert "chapitres" not in titre


@pytest.mark.django_db
def test_les_lignes_d_echec_restent_entieres(job: Any) -> None:
    """CONTRE-ÉPREUVE : la boucle de correction garde ses cinq cibles.

    C'est ce qui distingue « mieux compter » de « en voir moins ».
    """
    from generation import tasks

    failures = (
        GateFailure(check="check_bloc_non_resolu", detail=NOTE_18_19_20, chapter_number=18),
        GateFailure(check="check_bloc_non_resolu", detail=NOTE_18_19_20, chapter_number=19),
        GateFailure(check="check_bloc_non_resolu", detail=NOTE_21_22, chapter_number=21),
    )
    rapport = _rapport(*failures)
    with patch("generation.gate.run_delivery_gate", return_value=rapport):
        tasks._rendre_le_verdict_du_gate(job)

    assert len(rapport.failures) == 3
    assert [f.chapter_number for f in rapport.failures] == [18, 19, 21]
