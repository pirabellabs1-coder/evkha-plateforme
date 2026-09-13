"""Ce que la recherche web a rapporté au lancement doit ENCORE être là à la fin.

Sonde du 13/09/2026. Six stratégies Zenitek de suite finissent avec un brief de
recherche VIDE en base, alors que, rejouées depuis la production, quinze de
leurs seize requêtes rapportent cinq résultats chacune. La recherche n'est
écrite qu'à un seul endroit, juste après la collecte : si elle a disparu, c'est
que quelque chose réenregistre le dossier par-dessus.

Le test joue le dossier ENTIER, sur la doublure d'IA (zéro appel payant), avec
un fournisseur de recherche qui rapporte des résultats — puis lit la base.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import override_settings

from integrations.search import SearchResponse, SearchResult


class _Repond:
    def search(self, **kwargs: Any) -> SearchResponse:
        requete = str(kwargs.get("query", ""))
        return SearchResponse(
            query=requete,
            results=(
                SearchResult(
                    title="Insee",
                    url=f"https://www.insee.fr/fr/statistiques/{abs(hash(requete)) % 10**6}",
                    content="Nombre d'entreprises en France.",
                ),
            ),
        )


@pytest.mark.django_db
@pytest.mark.parametrize("livrable", ["business_strategy", "market_study"])
def test_le_brief_de_recherche_est_encore_en_base_a_la_fin(
    livrable: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from catalog.models import Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from generation.repetition import VARIABLES_DE_REPETITION
    from generation.runner import run_generation_job
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from integrations.claude import StubClaudeClient
    from orders.models import Order

    monkeypatch.setattr("generation.research.get_search_client", lambda: _Repond())
    monkeypatch.setattr("generation.research._PAUSE_ENTRE_REQUETES_S", 0.0)
    monkeypatch.setattr("generation.runner.debiter_pour_job", lambda job: (True, ""))

    offre = Offer.objects.create(name="X", slug=f"x-{livrable}", deliverable_type=livrable)
    client = Customer.objects.create(email=f"{livrable}@survie.local")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-survie-{livrable}", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables=dict(VARIABLES_DE_REPETITION),
    )
    job = bootstrap_generation_job(soumission)

    with override_settings(EVKHA_SOCLE_ENABLED=True):
        try:
            run_generation_job(job, client=StubClaudeClient())
        except Exception:  # noqa: BLE001 — on mesure la base, pas l'issue du dossier
            pass

    en_base = GenerationJob.objects.get(pk=job.pk).research_brief
    assert "insee.fr" in en_base, "le brief de recherche a disparu en cours de dossier"
