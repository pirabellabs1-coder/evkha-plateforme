"""Deux exercices d'une même série du socle sont une trajectoire, pas une plage.

## Le défaut mesuré

Corpus du 15/09/2026 :

- `b8da2640` : « Chiffre d'affaires prévisionnel en progression de 320 000 à
  430 000 euros entre la première et la troisième année » ;
- `73dde3ab` : « la progression de 320 000 à 430 000 euros sur trois exercices
  (soit 34,4 %) ».

320 000 et 430 000 sont `ca_previsionnel_an1` et `ca_previsionnel_an3`. Le gate
disait « le document doit citer un chiffre unique » d'un départ et d'une
arrivée — motif faux routé vers une réécriture payée (règle 2).

## Pourquoi la série, et pas le mot

« Une hausse de 3 à 5 % » est une plage (décision du 14/09/2026), et « une
progression de 3 à 5 % » peut l'être. Le verbe ne tranche pas ; deux exercices
d'une même grandeur verrouillés au socle, si.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from generation.gate import _check_fourchettes
from generation.rendering import RenderedSection
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone


def _donnee(identifiant: str, valeur: float, unite: str = "EUR") -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, valeur=valeur, unite=unite, libelle=identifiant,
        annee=2026, perimetre=Perimetre.ENTREPRISE, source="données du projet",
        fiabilite=Fiabilite.OBSERVEE,
    )


def _job(db: Any, *donnees: DonneeSocle) -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob, SocleDonnees, SocleStatut
    from orders.models import Order

    offer = Offer.objects.create(
        name="BP", slug="bp", deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email="trajectoire@example.com")
    order = Order.objects.create(systeme_order_id="o_traj", customer=customer, offer=offer)
    job = GenerationJob.objects.create(order=order, deliverable_type=DeliverableType.BUSINESS_PLAN)
    if donnees:
        socle = Socle(
            secteur="boulangerie", zone=Zone(pays="France"),
            date_socle=date(2026, 9, 15), donnees=list(donnees),
        )
        SocleDonnees.objects.create(
            job=job, statut=SocleStatut.VALIDE, contenu=socle.model_dump(mode="json"),
        )
    return job


def _plages(job: Any, texte: str) -> int:
    section = RenderedSection(number=6, title="Marché", kind="chapter", body=texte)
    return len(_check_fourchettes(job, (section,)))


PREVISIONNEL = (
    _donnee("ca_previsionnel_an1", 320_000),
    _donnee("ca_previsionnel_an2", 375_000),
    _donnee("ca_previsionnel_an3", 430_000),
    _donnee("resultat_net_an3", 45_000),
)


@pytest.mark.django_db
@pytest.mark.parametrize("texte", [
    "Chiffre d'affaires prévisionnel en progression de 320 000 à 430 000 euros "
    "entre la première et la troisième année.",
    "la progression de 320 000 à 430 000 euros sur trois exercices (soit 34,4 %)",
    "Le chiffre d'affaires recule de 430 000 à 375 000 € dans le scénario bas.",
])
def test_deux_exercices_d_une_meme_serie_sont_une_trajectoire(db: Any, texte: str) -> None:
    assert _plages(_job(db, *PREVISIONNEL), texte) == 0


@pytest.mark.django_db
def test_deux_series_differentes_ne_font_pas_une_trajectoire(db: Any) -> None:
    """CONTRE-ÉPREUVE : un résultat net et un chiffre d'affaires ne se relient pas."""
    assert _plages(_job(db, *PREVISIONNEL), "un montant de 45 000 à 320 000 euros") == 1


@pytest.mark.django_db
def test_sans_socle_une_progression_reste_une_plage(db: Any) -> None:
    """CONTRE-ÉPREUVE : le mot « progression » ne suffit pas."""
    assert _plages(_job(db), "une progression de 320 000 à 430 000 euros") == 1


@pytest.mark.django_db
def test_une_plage_hesitante_hors_serie_reste_une_plage(db: Any) -> None:
    """CONTRE-ÉPREUVE, décision du 14/09/2026."""
    assert _plages(_job(db, *PREVISIONNEL), "Une hausse de 3 à 5 % de la marge.") == 1
