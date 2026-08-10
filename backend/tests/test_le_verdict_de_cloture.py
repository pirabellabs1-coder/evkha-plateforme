"""L'étude se ferme sur un verdict, pas sur un résumé.

## La demande

Cliente, 09/08/2026, après la V2 : « le client doit sortir de l'étude avec une
direction et des conclusions, pas avec une liste de choses à vérifier ensuite ».
Et, très précisément : un verdict de clôture sur six axes — marché porteur,
potentiel pour un nouvel entrant, niveau de concurrence, saturation, potentiel
de rentabilité, viabilité globale — avec une justification courte pour chacun.

## Pourquoi le vocabulaire est FERMÉ

Un verdict libre redevient une nuance. « Plutôt favorable dans certaines
conditions » ne se compare pas d'une étude à l'autre et ne décide rien. Trois
mots par axe, et le lecteur sait où il est.

## Pourquoi il n'est demandé qu'au dernier chapitre

Confié à tous, il produirait vingt-trois verdicts contradictoires. C'est le
défaut exact qui a fait sortir la recommandation de clôture du modèle de
langage pour la confier au rendu — une consigne « une seule fois » adressée à
chaque chapitre est tenue zéro ou vingt-trois fois.
"""
from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.runner import AXES_DU_VERDICT, _bloc_verdict
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

VARIABLES = {"SECTEUR": "e-commerce animalier", "PAYS": "France"}


@pytest.fixture
def job(db: Any) -> Any:
    offre = Offer.objects.create(
        name="EM", slug="verdict", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="verdict@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-verdict", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=VARIABLES,
    )
    return bootstrap_generation_job(soumission)


def _dernier(job: Any) -> int:
    return job.chapters.order_by("-chapter_number").first().chapter_number


def test_le_dernier_chapitre_recoit_la_consigne(job: Any) -> None:
    consigne = _bloc_verdict(job, _dernier(job))

    assert "VERDICT DE CLÔTURE" in consigne
    assert "`tableau`" in consigne


@pytest.mark.parametrize(
    ("axe", "valeurs"),
    [(axe, valeurs) for axe, valeurs in AXES_DU_VERDICT],
)
def test_les_six_axes_et_leur_vocabulaire_sont_transmis(
    job: Any, axe: str, valeurs: tuple[str, ...]
) -> None:
    """Un axe annoncé sans ses mots laisserait le modèle inventer sa nuance."""
    consigne = _bloc_verdict(job, _dernier(job))

    assert axe in consigne
    for mot in valeurs:
        assert mot in consigne, f"{axe} : « {mot} » manque"


def test_il_y_a_bien_SIX_axes() -> None:
    """Recopié à la main : un test qui relit la table ne vérifie rien."""
    assert len(AXES_DU_VERDICT) == 6
    assert [axe for axe, _ in AXES_DU_VERDICT] == [
        "Marché porteur",
        "Potentiel pour un nouvel entrant",
        "Niveau de concurrence",
        "Marché saturé",
        "Potentiel de rentabilité",
        "Viabilité globale",
    ]


def test_chaque_axe_propose_TROIS_reponses() -> None:
    """Deux vaudraient un oui/non brutal ; quatre rouvriraient la nuance."""
    for axe, valeurs in AXES_DU_VERDICT:
        assert len(valeurs) == 3, axe
        assert len(set(valeurs)) == 3, axe


def test_AUCUN_autre_chapitre_ne_recoit_la_consigne(job: Any) -> None:
    """LA contre-épreuve : vingt-trois verdicts ne seraient plus un verdict."""
    dernier = _dernier(job)
    autres = [
        numero
        for numero in job.chapters.values_list("chapter_number", flat=True)
        if numero != dernier
    ]

    assert autres, "le dossier doit avoir plusieurs chapitres"
    for numero in autres:
        assert _bloc_verdict(job, numero) == "", f"chapitre {numero}"


def test_la_consigne_reclame_une_justification_courte(job: Any) -> None:
    """Un verdict sans raison ne se défend pas devant un banquier."""
    consigne = _bloc_verdict(job, _dernier(job))

    assert "Pourquoi" in consigne
    assert "une phrase" in consigne
