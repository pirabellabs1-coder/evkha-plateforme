"""Le coût d'un appel suit le tarif du modèle APPELÉ, relevé sur la grille d'Anthropic.

29/09/2026 : la table ne connaissait que deux familles, « sonnet » à 3 $ / 15 $
et « opus » à 15 $ / 75 $. La production tourne sur `claude-sonnet-5`, facturé
2 $ / 10 $ (grille officielle, tarif définitif) : chaque dossier était compté
50 % au-dessus de sa facture, et le plafond coupait sur ce compte — la reprise
ÉCLORE `bf98827c` s'est arrêtée à « 8,12 € » pour ~5,41 € réellement dépensés.
"""
from __future__ import annotations

from decimal import Decimal

from django.test import override_settings

from generation.cost import estimate_call_cost_eur

UN_MILLION = 1_000_000


def _cout(modele: str | None) -> Decimal:
    """Un million de jetons en entrée ET en sortie, en euros (1 $ = 0,90 €)."""
    return estimate_call_cost_eur(UN_MILLION, UN_MILLION, modele)


def test_sonnet_5_est_compte_a_son_tarif() -> None:
    """Le modèle de la production : (2 $ + 10 $) × 0,90 = 10,80 €."""
    assert _cout("claude-sonnet-5") == Decimal("10.8000")


def test_le_reglage_de_production_est_compte_a_son_tarif() -> None:
    """Sans modèle nommé, le coût suit `EVKHA_ANTHROPIC_MODEL_ID` — le chemin des chapitres."""
    with override_settings(EVKHA_ANTHROPIC_MODEL_ID="claude-sonnet-5"):
        assert _cout(None) == Decimal("10.8000")


def test_un_identifiant_date_suit_son_modele() -> None:
    assert _cout("claude-sonnet-5-20260801") == Decimal("10.8000")
    assert _cout("claude-sonnet-5-5") == Decimal("10.8000")


def test_chaque_modele_a_son_propre_tarif() -> None:
    assert _cout("claude-sonnet-4-6") == Decimal("16.2000")
    assert _cout("claude-opus-5-5") == Decimal("21.6000")
    assert _cout("claude-opus-4-7") == Decimal("27.0000")


def test_haiku_ne_fait_plus_planter_le_calcul() -> None:
    assert _cout("claude-haiku-4-5") == Decimal("5.4000")


def test_un_alias_ou_une_version_inconnue_prend_le_plus_cher_de_sa_famille() -> None:
    """Contre-épreuve : on ne sous-estime jamais — « claude-sonnet » reste au tarif le plus haut."""
    assert _cout("claude-sonnet") == Decimal("16.2000")
    assert _cout("claude-sonnet-9") == Decimal("16.2000")
