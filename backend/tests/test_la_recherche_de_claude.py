"""La recherche web passe par l'outil `web_search` de Claude — et elle se paie.

Décision du client, 13/09/2026, après six dossiers de suite partis sans une
seule adresse web : le fournisseur gratuit s'était tu. La recherche de Claude
s'exécute chez Anthropic et ne dépend pas de l'adresse de notre serveur.

Ces tests ne font AUCUN appel réseau : le SDK est remplacé par une doublure qui
rend des blocs de la forme exacte du SDK installé (`WebSearchToolResultBlock`,
`WebSearchResultBlock`, `CitationsWebSearchResultLocation`, `ServerToolUsage`).

Ils échouent sur le code d'avant : ni `ClaudeWebSearchClient`, ni le fournisseur
« claude », ni `record_recherche_web` n'existaient.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace as NS
from typing import Any

import pytest

from generation.research import collecter_la_recherche
from integrations.search import (
    ClaudeWebSearchClient,
    DuckDuckGoWebSearchClient,
    StubWebSearchClient,
    get_search_client,
)


def _reponse(*, resultats: Any, citations: list[Any] | None = None, recherches: int = 1) -> Any:
    return NS(
        content=[
            NS(type="server_tool_use", name="web_search"),
            NS(type="web_search_tool_result", content=resultats),
            NS(type="text", text="Constats.", citations=citations or []),
        ],
        usage=NS(
            input_tokens=12000, output_tokens=300,
            server_tool_use=NS(web_search_requests=recherches, web_fetch_requests=0),
        ),
    )


class _Sdk:
    def __init__(self, reponse: Any) -> None:
        self.reponse = reponse
        self.appels: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kwargs: Any) -> Any:
        self.appels.append(kwargs)
        return self.reponse


_INSEE = NS(type="web_search_result", url="https://www.insee.fr/a", title="Insee",
            page_age="2025-03-01", encrypted_content="xxx")
_NUMEUM = NS(type="web_search_result", url="https://numeum.fr/b", title="Numeum",
             page_age=None, encrypted_content="yyy")


def test_les_citations_deviennent_les_extraits_des_sources() -> None:
    """LE test : le texte des pages est chiffré ; seules les citations le portent."""
    sdk = _Sdk(_reponse(
        resultats=[_NUMEUM, _INSEE, _INSEE],
        citations=[NS(type="web_search_result_location", url="https://www.insee.fr/a",
                      title="Insee", cited_text="4,5 millions d'entreprises en 2023.",
                      encrypted_index="z")],
    ))
    client = ClaudeWebSearchClient(sdk_client=sdk, model_id="claude-sonnet-4-6")

    reponse = client.search(query="entreprises France", max_results=5)

    urls = [r.url for r in reponse.results]
    assert urls == ["https://www.insee.fr/a", "https://numeum.fr/b"], "citée d'abord, sans doublon"
    assert reponse.results[0].content == "4,5 millions d'entreprises en 2023."
    assert reponse.results[0].published_date == "2025-03-01"
    # Une source jamais citée garde son adresse — on ne lui invente pas d'extrait.
    assert reponse.results[1].content == ""


def test_la_requete_emploie_l_outil_serveur_et_le_modele_du_projet() -> None:
    sdk = _Sdk(_reponse(resultats=[_INSEE]))
    ClaudeWebSearchClient(sdk_client=sdk, model_id="claude-sonnet-4-6").search(query="q")

    appel = sdk.appels[0]
    assert appel["model"] == "claude-sonnet-4-6"
    # La variante BASIQUE : la dynamique rendait zéro citation, en 105 s
    # depuis la production (mesure du 13/09/2026, voir `TYPE_OUTIL`).
    assert appel["tools"] == [{"type": "web_search_20250305", "name": "web_search", "max_uses": 1}]
    # Effort BAS : trouver et citer ne demande pas de réflexion. Sur le dossier
    # `a678b10a`, ~2 100 jetons de sortie par requête ; 515 avec ce réglage.
    assert appel["output_config"] == {"effort": "low"}
    assert "UNE phrase courte" in appel["messages"][0]["content"]


def test_une_erreur_de_l_outil_n_est_pas_un_resultat_vide() -> None:
    """L'erreur revient en HTTP 200, à la place de la liste. Elle doit LEVER.

    Sinon la collecte la compterait comme « aucun résultat » — exactement le
    silence qui a coûté quatre semaines de sources absentes.
    """
    sdk = _Sdk(_reponse(resultats=NS(type="web_search_tool_result_error",
                                     error_code="too_many_requests")))
    client = ClaudeWebSearchClient(sdk_client=sdk, model_id="m")

    resultat = collecter_la_recherche(
        "business_strategy",
        {"SECTEUR": "assistance informatique", "PAYS": "France", "ZONE": "Paris"},
        client=client, pause_s=0,
    )

    assert resultat.muette
    assert any("too_many_requests" in e for e in resultat.erreurs), resultat.erreurs


def test_une_seconde_recherche_refusee_ne_jette_pas_la_premiere() -> None:
    """Le défaut de la première requête réelle en production (13/09/2026).

    Le modèle a tenté une seconde recherche au-delà de `max_uses` : l'outil a
    rendu les résultats de la première ET un bloc `max_uses_exceeded`. Rejeter
    toute la réponse dès la première erreur rendait zéro résultat.
    """
    reponse = _reponse(resultats=[_INSEE, _NUMEUM])
    reponse.content.append(NS(
        type="web_search_tool_result",
        content=NS(type="web_search_tool_result_error", error_code="max_uses_exceeded"),
    ))
    client = ClaudeWebSearchClient(sdk_client=_Sdk(reponse), model_id="m")

    resultats = client.search(query="q").results

    assert [r.url for r in resultats] == ["https://www.insee.fr/a", "https://numeum.fr/b"]


def test_une_reponse_sans_recherche_n_est_pas_un_vide() -> None:
    """Avec un effort bas, rien n'oblige le modèle à appeler l'outil.

    Une réponse sans bloc de recherche rendue comme une liste vide ferait passer
    « pas cherché » pour « rien trouvé » (relecture du 13/09/2026).
    """
    reponse = NS(
        content=[NS(type="text", text="Voici ce que je sais.", citations=[])],
        usage=NS(input_tokens=100, output_tokens=20,
                 server_tool_use=NS(web_search_requests=0, web_fetch_requests=0)),
    )
    client = ClaudeWebSearchClient(sdk_client=_Sdk(reponse), model_id="m")

    with pytest.raises(RuntimeError, match="non exécutée"):
        client.search(query="q")


def test_la_collecte_rapporte_ce_que_la_recherche_a_consomme() -> None:
    sdk = _Sdk(_reponse(resultats=[_INSEE], recherches=1))
    client = ClaudeWebSearchClient(sdk_client=sdk, model_id="claude-sonnet-4-6")

    resultat = collecter_la_recherche(
        "business_strategy",
        {"SECTEUR": "assistance informatique", "PAYS": "France", "ZONE": "Paris"},
        client=client, pause_s=0,
    )

    assert resultat.requetes == len(sdk.appels)
    assert resultat.recherches_facturees == resultat.requetes
    assert resultat.input_tokens == 12000 * resultat.requetes
    assert resultat.modele == "claude-sonnet-4-6"
    assert "insee.fr" in resultat.brief


def test_un_fournisseur_gratuit_ne_rapporte_aucune_consommation() -> None:
    """CONTRE-ÉPREUVE : aucun coût inventé pour ce qui ne se paie pas."""
    resultat = collecter_la_recherche(
        "business_strategy",
        {"SECTEUR": "assistance informatique", "PAYS": "France", "ZONE": "Paris"},
        client=StubWebSearchClient(), pause_s=0,
    )
    assert (resultat.input_tokens, resultat.recherches_facturees) == (0, 0)


# ── Le choix du fournisseur ─────────────────────────────────────────────────


def test_le_fournisseur_claude_s_active_par_reglage_explicite(
    settings: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.EVKHA_USE_STUB_SEARCH = False
    settings.EVKHA_SEARCH_PROVIDER = "claude"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    assert isinstance(get_search_client(), ClaudeWebSearchClient)


def test_sans_cle_le_fournisseur_claude_se_replie_sur_le_gratuit(
    settings: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une recherche ne bloque jamais un dossier faute de clé."""
    settings.EVKHA_USE_STUB_SEARCH = False
    settings.EVKHA_SEARCH_PROVIDER = "claude"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_search_client(), DuckDuckGoWebSearchClient)


def test_la_doublure_reste_la_regle_par_defaut(settings: Any) -> None:
    """CONTRE-ÉPREUVE : rien de payant ne s'active implicitement."""
    settings.EVKHA_USE_STUB_SEARCH = True
    settings.EVKHA_SEARCH_PROVIDER = "claude"
    assert isinstance(get_search_client(), StubWebSearchClient)


# ── Le coût entre au budget ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_le_cout_de_la_recherche_est_dans_le_total_du_dossier() -> None:
    """Un coût qu'on ne compte pas est un plafond qui ment."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.cost import (
        COUT_RECHERCHE_WEB_EUR,
        estimate_call_cost_eur,
        record_recherche_web,
    )
    from generation.models import GenerationJob
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="STR", slug="str-cout-recherche", deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )
    client = Customer.objects.create(email="cout-recherche@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-cout-recherche", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "x", "PAYS": "France"},
    )
    job = bootstrap_generation_job(soumission)

    montant = record_recherche_web(
        job, input_tokens=192000, output_tokens=4800, recherches=16,
        model="claude-sonnet-4-6",
    )

    attendu = (
        estimate_call_cost_eur(192000, 4800, "claude-sonnet-4-6")
        + COUT_RECHERCHE_WEB_EUR * 16
    )
    assert montant == attendu
    assert GenerationJob.objects.get(pk=job.pk).total_cost_eur == attendu
    assert montant > Decimal("0.1"), "seize recherches ne sont pas gratuites"
