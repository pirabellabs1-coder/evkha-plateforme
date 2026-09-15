"""Ce qui part RÉELLEMENT au modèle : chaque correction y arrive, aucune faute n'y est montrée.

## Pourquoi un test sur le prompt ASSEMBLÉ

Les consignes vivent dans une dizaine de sources — fichiers de chapitre,
consigne de fond, forme par livrable, bloc de décisions, catalogue des figures,
consigne de réécriture. Chaque source avait son test ; aucun ne regardait le
prompt tel qu'il part, chapitre par chapitre, une fois tout assemblé.

Audit du 15/09/2026, en rejouant la répétition à blanc avec un client qui
enregistre chaque appel (4 livrables, 98 appels) :

- la consigne de fond LISTAIT les six superlatifs que le gate refuse, et
  « sans équivalent » bloquait le business plan `8bda1173` mot pour mot ;
- toutes les corrections de consigne des 13, 14 et 15/09 arrivaient bien au
  modèle — ce test le verrouille, pour qu'un refactor ne débranche pas une
  consigne en silence (le défaut Gamma : intégré, testé, jamais exécuté).

## Ce que ce test ne prouve pas

Ce qu'un vrai modèle écrira (règle 7). Il prouve que la consigne est là, et
qu'elle ne montre pas la faute qu'un contrôle punira.
"""
from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType
from generation import repetition
from integrations.claude import StubClaudeClient

#: Une phrase de chaque correction de consigne, par livrable. Une consigne
#: réécrite doit mettre à jour cette liste : c'est voulu, elle dit ce qui
#: DOIT arriver au modèle.
CONSIGNES_ATTENDUES: dict[str, list[str]] = {
    DeliverableType.BUSINESS_PLAN: [
        "UN prix par variante",
        "Un montant se DÉCIDE",
        "adresse web, recopiée telle quelle",
        "FIGURES RÉALISABLES AVEC CE SOCLE",
        "cité par 9 comparateurs",
    ],
    DeliverableType.COMPETITOR_STUDY: [
        "UN prix par variante",
        "CA de référence estimé",
        "CA actuel estimé",
        "adresse web, recopiée telle quelle",
        "FIGURES RÉALISABLES AVEC CE SOCLE",
        "cité par 9 comparateurs",
    ],
    DeliverableType.BUSINESS_STRATEGY: [
        "UN prix par variante",
        "le coût mensuel retenu",
        "ce qu'un pilotage stratégique change",
        "Décisions retenues",
        "adresse web, recopiée telle quelle",
        "FIGURES RÉALISABLES AVEC CE SOCLE",
        "cité par 9 comparateurs",
    ],
    DeliverableType.MARKET_STUDY: [
        "FIGURES RÉALISABLES AVEC CE SOCLE",
        "cité par 9 comparateurs",
    ],
}


def _prompts_de_redaction(livrable: str, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Chaque prompt de rédaction de chapitre envoyé pendant la répétition à blanc."""
    envoyes: list[str] = []

    class Enregistreur(StubClaudeClient):
        def complete_structured(self, **kw: Any) -> Any:
            if kw.get("outil_nom") == "rendre_chapitre":
                envoyes.append(f"{kw.get('system', '')}\n\n{kw.get('prompt', '')}")
            return super().complete_structured(**kw)

    monkeypatch.setattr(repetition, "StubClaudeClient", Enregistreur)
    rapport = repetition.jouer_a_blanc(livrable)
    assert rapport.saine, rapport.defauts_internes
    assert envoyes, "aucun prompt de chapitre enregistré : le test ne jugerait rien (règle 1)"
    return envoyes


@pytest.mark.django_db
@pytest.mark.parametrize("livrable", list(CONSIGNES_ATTENDUES))
def test_chaque_correction_de_consigne_arrive_au_modele(
    livrable: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from generation import meta_discours
    from generation.chapitres.schema import _VOCABULAIRE_INTERNE
    from generation.checks_evangeline import detecter_fourchettes
    from generation.checks_post_rendu import detecter_ton_publicitaire

    prompts = _prompts_de_redaction(livrable, monkeypatch)
    tout = "\n".join(prompts)

    manquantes = [c for c in CONSIGNES_ATTENDUES[livrable] if c not in tout]
    assert manquantes == [], f"consignes qui n'arrivent pas au modèle : {manquantes}"

    fautes: set[str] = set()
    for prompt in prompts:
        fautes |= {f"ton : {t.expression}" for t in detecter_ton_publicitaire({1: prompt})}
        fautes |= {f"fabrication : {e}" for e in meta_discours.trouver_au_gate(prompt)}
        fautes |= {
            f"vocabulaire : {nom}" for nom, motif in _VOCABULAIRE_INTERNE
            # Les identifiants sont la matière du prompt : le bloc de chiffres
            # les nomme pour que les figures les emploient.
            if nom != "identifiant technique" and motif.search(prompt)
        }
        # L'étude de marché admet une fourchette sourcée : ses extraits de
        # modèle en montrent, légitimement.
        if livrable != DeliverableType.MARKET_STUDY:
            fautes |= {
                f"fourchette : {f.extrait}"
                for f in detecter_fourchettes(0, prompt, deliverable_type=livrable)
            }
    assert sorted(fautes) == []
