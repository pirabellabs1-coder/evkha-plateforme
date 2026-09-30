"""La recherche web passe par Claude Haiku 4.5 ; la rédaction reste sur Sonnet 5.

Décision du client du 30/09/2026 : la recherche pesait ~22 % d'un dossier
(20 requêtes d'environ 15 000 jetons pour un business plan). Haiku 4.5 coûte
1 $ / 5 $ par million de jetons, contre 2 $ / 10 $ pour Sonnet 5. Il refuse le
paramètre `effort` (400) : on ne l'envoie qu'aux modèles qui l'acceptent.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.test import override_settings

from integrations.search import ClaudeWebSearchClient


class _Sdk:
    """Un SDK qui garde la requête et rend une recherche avec une citation."""

    def __init__(self) -> None:
        self.appels: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kwargs: Any) -> Any:
        self.appels.append(kwargs)
        return SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=9000, output_tokens=400,
                server_tool_use=SimpleNamespace(web_search_requests=1),
            ),
            content=[
                SimpleNamespace(type="web_search_tool_result", content=[
                    SimpleNamespace(url="https://www.insee.fr/a", title="A", page_age=""),
                ]),
                SimpleNamespace(type="text", citations=[SimpleNamespace(
                    type="web_search_result_location", url="https://www.insee.fr/a",
                    cited_text="Le marché pèse 1,2 Md€ en 2025.",
                )]),
            ],
        )


def test_par_defaut_la_recherche_passe_par_haiku_sans_effort() -> None:
    sdk = _Sdk()
    with override_settings(EVKHA_ANTHROPIC_MODEL_ID="claude-sonnet-5"):
        client = ClaudeWebSearchClient(sdk_client=sdk)
        reponse = client.search(query="marché de la coiffure Lyon")
    appel = sdk.appels[0]
    assert appel["model"] == "claude-haiku-4-5"
    assert "output_config" not in appel, "Haiku 4.5 refuse `effort` (400)"
    assert client.modele == "claude-haiku-4-5", "le coût sera compté au tarif de Haiku"
    assert reponse.results and reponse.results[0].content


def test_sans_reglage_dedie_la_recherche_suit_le_modele_de_redaction() -> None:
    """Contre-épreuve : le retour arrière tient en un réglage vide, et l'effort revient."""
    sdk = _Sdk()
    with override_settings(EVKHA_RECHERCHE_MODEL_ID="", EVKHA_ANTHROPIC_MODEL_ID="claude-sonnet-5"):
        ClaudeWebSearchClient(sdk_client=sdk).search(query="q")
    appel = sdk.appels[0]
    assert appel["model"] == "claude-sonnet-5"
    assert appel["output_config"] == {"effort": "low"}
