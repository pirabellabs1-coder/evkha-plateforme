"""Trois faux motifs relevés en rejouant le gate sur les dossiers réels (26/09/2026).

Le rejeu a validé les correctifs des lots 91–92 et fait apparaître trois motifs
qui ne décrivent aucun défaut du document :

1. « de 45 % à 35 % » (stratégie `cd639627`, ch. 5) est une BAISSE — deux états
   successifs — et le détecteur de fourchettes le lisait comme une plage. Des
   bornes à l'envers ne bornent rien.
2. « Apport personnel déjà engagé | 4 000 € » et « Apport personnel
   complémentaire à venir | 13 050 € » (BP `eab58554`, ch. 15) sont deux
   FRACTIONS d'un apport de 17 050 €, opposées comme deux apports.
3. « seuil de rentabilité … avec marge de sécurité de 9 581 158,5 CHF »
   (BP `6c794b18`, ch. 18) nomme la marge, pas le seuil.

Et un contrôle qui n'atteignait pas sa cible : le plafond d'IS français reste
appliqué aux dossiers verrouillés AVANT `devise_du_pays`, qui n'ont aucun fait
de devise quand le pays était « Genève, Suisse ». Le brief dit toujours le pays.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.checks_evangeline import (
    collecter_mentions,
    detecter_divergences,
    detecter_fourchettes,
)
from generation.models import GenerationJob
from generation.strategies.bp import BPStrategy
from intake.models import IntakeSubmission
from orders.models import Order

STRICT = "business_strategy"


# ── 1. Des bornes à l'envers ne bornent rien ─────────────────────────────────


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("la marge recule de 45 % à 35 % sur la période", id="baisse-pourcent"),
        pytest.param("un panier ramené de 890 € à 690 €", id="baisse-euros"),
    ],
)
def test_une_baisse_n_est_pas_une_fourchette(texte: str) -> None:
    assert detecter_fourchettes(5, texte, STRICT) == [], texte


def test_la_meme_paire_dans_le_bon_ordre_reste_une_plage() -> None:
    """Contre-épreuve : « de 35 % à 45 % » hésite bien entre deux valeurs."""
    assert len(detecter_fourchettes(5, "une marge de 35 % à 45 % selon les canaux", STRICT)) == 1


# ── 2 et 3. Une fraction ou une grandeur voisine n'est pas la grandeur ───────


def _divergences(*chapitres: tuple[int, str]) -> list:  # type: ignore[type-arg]
    mentions = [m for numero, texte in chapitres for m in collecter_mentions(numero, texte)]
    return detecter_divergences(mentions)


def test_les_deux_parts_d_un_apport_ne_se_contredisent_pas() -> None:
    assert _divergences(
        (15, "| Apport personnel déjà engagé (dépenses depuis juin 2026) | 4 000 € | Versé |\n"),
        (15, "| Apport personnel complémentaire à venir | 13 050 € | Prévu au lancement |\n"),
    ) == []


def test_la_marge_de_securite_n_est_pas_le_seuil() -> None:
    assert _divergences(
        (16, "Le seuil de rentabilité s'établit à 7 369 320 CHF en 2028."),
        (18, "| Passage du seuil de rentabilité 2029 avec marge de sécurité de 9 581 158 CHF |\n"),
    ) == []


def test_deux_apports_nus_divergent_toujours() -> None:
    """Contre-épreuve : sans qualificatif, deux valeurs restent une divergence."""
    assert len(_divergences(
        (15, "| Apport personnel | 4 000 € |\n"),
        (16, "| Apport personnel | 13 050 € |\n"),
    )) == 1


# ── Le plafond d'IS trouve sa juridiction dans le brief ──────────────────────


@pytest.mark.django_db
def test_sans_fait_de_devise_le_pays_du_brief_tranche(db: Any) -> None:
    offre = Offer.objects.create(
        name="BP", slug="bp-geneve", deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email="bp-geneve@test.local")
    commande = Order.objects.create(systeme_order_id="cmd-bp-geneve", customer=client, offer=offre)
    IntakeSubmission.objects.create(order=commande, normalized_variables={"PAYS": "Genève, Suisse"})
    job = GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN,
        budget_eur=Decimal("8.0000"),
    )
    corpus = {14: "Le prévisionnel retient un IS à 15 % sur tout le bénéfice de 60 000 CHF."}

    problemes = BPStrategy().problemes_de_coherence(job, corpus)

    assert "is_bracket" not in {p.categorie for p in problemes}
