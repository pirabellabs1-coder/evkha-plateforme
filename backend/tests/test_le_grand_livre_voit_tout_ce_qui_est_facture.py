"""Ce qu'Anthropic facture doit se retrouver dans le grand livre. Tout.

Deux fuites mesurées sur le dossier réel `b561c2d6` — l'étude de marché validée
par la cliente le 08/08/2026 :

- **Les tentatives refusées.** Le chapitre 19 a consommé six appels rejetés
  (réponse tronquée, puis schéma jugé incomplet). Anthropic les facture comme
  n'importe quel appel. Ils n'étaient comptés nulle part : le `raise` emportait
  la consommation avec lui, entre `generer_chapitre` et la boucle de reprise.
  Le plafond de dépense portait donc sur un total inférieur à la facture, et il
  échouait en silence — c'est la règle 1 appliquée à l'argent.
- **Le cache de prompt.** `ClaudeResult` porte `cache_creation_input_tokens` et
  `cache_read_input_tokens` depuis le début. Personne ne les transportait
  jusqu'à la base. La console affichait 20 % de succès pendant le run ; après
  le run, il n'en restait rien. Impossible de mesurer l'économie, impossible de
  voir une régression du cache autrement que par une facture qui monte sans
  raison.

## Pourquoi deux champs et non un seul

`cost_eur` répond à « combien a coûté ce qu'on a gardé » — c'est lui qu'on
compare au prix de vente. `cost_perdu_eur` répond à « combien les reprises
coûtent » — c'est lui qui dira si une consigne s'améliore. Fondus ensemble, la
seconde question devient impossible à poser, et personne ne s'apercevrait
qu'elle a disparu.

Le PLAFOND, lui, porte sur la somme : la facture n'a qu'un seul montant.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.runner import ChapitreInvalideError
from generation.chapitres.services import _compter_la_tentative_perdue
from generation.cost import (
    CostBudgetExceededError,
    current_job_cost_eur,
    estimate_call_cost_eur,
    record_chapter_cost,
    record_tentative_perdue,
)
from generation.models import ChapterGeneration, GenerationJob
from orders.models import Order

CONSOMMATION = {
    "input_tokens": 30_000,
    "output_tokens": 3_000,
    "cache_write_tokens": 12_000,
    "cache_read_tokens": 18_000,
}


@pytest.fixture
def chapitre(db: Any) -> ChapterGeneration:
    offre = Offer.objects.create(
        name="EM", slug="grand-livre", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="grand-livre@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-grand-livre", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("8.0000"),
    )
    return ChapterGeneration.objects.create(
        job=job, chapter_number=19, chapter_title="Chapitre d'essai", prompt_key="em.19",
    )


def test_les_compteurs_de_cache_atteignent_la_base(chapitre: ChapterGeneration) -> None:
    """Le défaut exact : ils existaient sur le résultat, jamais en base."""
    record_chapter_cost(
        chapter=chapitre,
        input_tokens=CONSOMMATION["input_tokens"],
        output_tokens=CONSOMMATION["output_tokens"],
        cache_write_tokens=CONSOMMATION["cache_write_tokens"],
        cache_read_tokens=CONSOMMATION["cache_read_tokens"],
    )

    chapitre.refresh_from_db()
    assert chapitre.cache_write_tokens == 12_000
    assert chapitre.cache_read_tokens == 18_000


def test_le_cache_se_cumule_comme_les_jetons_qu_il_accompagne(
    chapitre: ChapterGeneration,
) -> None:
    """Écrits en absolu, ils mentiraient dès la première reprise.

    Et ils mentiraient là où ça compte le plus : un chapitre repris travaille
    sur un prompt déjà chaud, donc sur le cache le plus efficace de l'étude.
    """
    for _ in range(2):
        record_chapter_cost(
            chapter=chapitre, input_tokens=30_000, output_tokens=3_000,
            cache_write_tokens=12_000, cache_read_tokens=18_000,
        )

    chapitre.refresh_from_db()
    assert chapitre.cache_write_tokens == 24_000
    assert chapitre.cache_read_tokens == 36_000
    assert chapitre.input_tokens == 60_000


def test_une_tentative_refusee_est_facturee_et_comptee(
    chapitre: ChapterGeneration,
) -> None:
    attendu = estimate_call_cost_eur(30_000, 3_000)

    perdu = record_tentative_perdue(
        chapter=chapitre, input_tokens=30_000, output_tokens=3_000
    )

    chapitre.refresh_from_db()
    assert perdu == attendu
    assert chapitre.cost_perdu_eur == attendu
    # Le travail retenu reste a zero : rien n'a ete garde.
    assert chapitre.cost_eur == Decimal("0.0000")


def test_le_total_du_dossier_inclut_ce_qui_a_ete_perdu(
    chapitre: ChapterGeneration,
) -> None:
    """Sans cela, le plafond porte sur le résultat et non sur la facture."""
    record_chapter_cost(chapter=chapitre, input_tokens=30_000, output_tokens=3_000)
    record_tentative_perdue(chapter=chapitre, input_tokens=30_000, output_tokens=3_000)

    chapitre.refresh_from_db()
    total = current_job_cost_eur(chapitre.job)

    assert total == chapitre.cost_eur + chapitre.cost_perdu_eur
    assert total > chapitre.cost_eur


def test_six_tentatives_perdues_finissent_par_couper(
    chapitre: ChapterGeneration,
) -> None:
    """Le cas réel du chapitre 19, ramené à son plafond.

    Six appels refusés d'affilée. Avant, ils ne coûtaient rien au compteur et le
    dossier continuait. Le garde-fou doit désormais les voir.
    """
    chapitre.job.budget_eur = Decimal("1.0000")
    chapitre.job.save(update_fields=["budget_eur", "updated_at"])

    with pytest.raises(CostBudgetExceededError):
        for _ in range(6):
            record_tentative_perdue(
                chapter=chapitre, input_tokens=400_000, output_tokens=16_000
            )

    chapitre.refresh_from_db()
    assert chapitre.cost_perdu_eur > Decimal("0")


def test_une_tentative_sans_consommation_n_invente_aucun_cout(
    chapitre: ChapterGeneration,
) -> None:
    """Contre-épreuve : un chiffre faux est pire qu'un chiffre absent (règle 2)."""
    record_tentative_perdue(chapter=chapitre, input_tokens=0, output_tokens=0)

    chapitre.refresh_from_db()
    assert chapitre.cost_perdu_eur == Decimal("0.0000")


def test_seule_une_reponse_du_modele_compte_comme_depense(
    chapitre: ChapterGeneration,
) -> None:
    """Une panne réseau n'a rien coûté : elle ne doit rien inscrire.

    C'est la distinction que porte `ChapitreInvalideError` — elle ne survient
    qu'APRÈS que le modèle a répondu. Prêter un montant à une erreur survenue
    avant l'appel fabriquerait une dépense imaginaire.
    """
    _compter_la_tentative_perdue(chapitre.job, 19, ConnectionError("réseau coupé"))

    chapitre.refresh_from_db()
    assert chapitre.cost_perdu_eur == Decimal("0.0000")


def test_un_refus_du_modele_est_bien_porte_au_grand_livre(
    chapitre: ChapterGeneration,
) -> None:
    """Le chemin complet, de l'exception jusqu'à la base."""
    erreur = ChapitreInvalideError(
        ["reponse tronquee a 16000 jetons de sortie"],
        {"input_tokens": 30_000, "output_tokens": 3_000},
    )

    _compter_la_tentative_perdue(chapitre.job, 19, erreur)

    chapitre.refresh_from_db()
    assert chapitre.cost_perdu_eur == estimate_call_cost_eur(30_000, 3_000)


def test_l_exception_transporte_sa_consommation() -> None:
    """Sans ce transport, tout le reste est inatteignable."""
    erreur = ChapitreInvalideError(["motif"], {"input_tokens": 12, "output_tokens": 3})

    assert erreur.consommation == {"input_tokens": 12, "output_tokens": 3}
    assert ChapitreInvalideError(["motif"]).consommation == {}
