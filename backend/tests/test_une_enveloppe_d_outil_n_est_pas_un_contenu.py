"""Une charge d'outil rangée sous une enveloppe est sortie de l'enveloppe, pas refusée.

## Le défaut mesuré

15/09/2026, génération de preuve `44bbd696` (reprise du business plan
`8bda1173`) : « Socle non recevable après 3 tentative(s) : secteur : Field
required ; zone : Field required ; date_socle : Field required ; socle : Extra
inputs are not permitted ». Le modèle rendait `{"socle": {…}}` ; zéro chapitre,
1,12 € dépensés. La répétition à blanc ne pouvait pas le voir : la doublure rend
toujours la bonne forme.

## Ce qui n'est PAS retiré

Une charge à plusieurs clés, une clé connue du schéma, une valeur qui n'est pas
un objet, un objet sans aucun champ requis : on ne devine pas ce que le modèle
voulait dire, la validation habituelle refuse.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.socle.builder import _analyser, schema_outil
from integrations.claude import sans_enveloppe

SCHEMA: dict[str, Any] = {
    "properties": {"secteur": {}, "zone": {}, "date_socle": {}, "donnees": {}},
    "required": ["secteur", "zone", "date_socle"],
}


def test_l_enveloppe_du_socle_est_retiree() -> None:
    contenu = {"secteur": "boulangerie", "zone": {"pays": "France"}, "date_socle": "2026-09-15"}
    assert sans_enveloppe({"socle": contenu}, SCHEMA) == contenu


@pytest.mark.parametrize("charge", [
    # Déjà à la racine.
    {"secteur": "boulangerie", "zone": {"pays": "France"}, "date_socle": "2026-09-15"},
    # Plusieurs clés : ce n'est pas une enveloppe.
    {"socle": {"secteur": "x"}, "note": "y"},
    # Une clé CONNUE du schéma, même seule, n'est pas une enveloppe.
    {"donnees": {"secteur": "x"}},
    # Une valeur qui n'est pas un objet.
    {"socle": ["secteur", "zone"]},
    # Un objet qui ne porte aucun champ requis : on ne devine pas.
    {"reponse": {"texte": "Voici le socle demandé."}},
])
def test_ce_qui_n_est_pas_une_enveloppe_reste_tel_quel(charge: dict[str, Any]) -> None:
    assert sans_enveloppe(charge, SCHEMA) == charge


def test_le_schema_reel_du_socle_du_business_plan_le_permet() -> None:
    """Le schéma que reçoit le modèle porte bien des champs requis à la racine :
    sans eux, la garde ne retirerait jamais rien (règle 1)."""
    schema = schema_outil("business_plan")
    assert {"secteur", "zone", "date_socle"} <= set(schema["required"])
    # Et le schéma ne nomme plus l'enveloppe qu'il a suggérée.
    assert "title" not in schema
    assert sans_enveloppe({"socle": {"secteur": "x"}}, schema) == {"secteur": "x"}


def test_sans_retrait_le_socle_enveloppe_est_refuse_avec_le_motif_de_production() -> None:
    """La validation du socle rend le motif lu en production sur `44bbd696`."""
    _socle, motifs = _analyser({"socle": {"secteur": "x"}}, "business_plan")
    assert any("Extra inputs" in m for m in motifs)


def test_le_client_reel_retire_l_enveloppe_avant_de_rendre_la_charge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le CÂBLAGE : la réponse de l'API passe par `sans_enveloppe`, sans appel réseau."""
    import sys
    from types import SimpleNamespace

    from integrations.claude import AnthropicClaudeClient

    bloc = SimpleNamespace(
        type="tool_use", name="produire_socle", input={"socle": {"secteur": "boulangerie"}},
    )
    message = SimpleNamespace(content=[bloc], usage=None, stop_reason="tool_use")
    faux = SimpleNamespace(
        Anthropic=lambda **_: SimpleNamespace(messages=SimpleNamespace(create=lambda **_: message)),
    )
    monkeypatch.setitem(sys.modules, "anthropic", faux)

    resultat = AnthropicClaudeClient(api_key="cle-de-test").complete_structured(
        system="s", prompt="p", outil_nom="produire_socle", outil_description="d",
        schema=SCHEMA,
    )
    assert resultat.payload == {"secteur": "boulangerie"}
