"""Ce que les cahiers des charges interdisent nommément est enfin LU.

## Où ces phrases sont écrites

Sous l'intitulé « Ne jamais écrire », dans
`references/systemes/02-etude-concurrence-cdc-v1.pdf` (18/05/2026),
`03-business-plan-v1.pdf` et `04-strategie-business-v1.pdf` — présents dans le
dépôt depuis le 30 juillet 2026.

## Pourquoi un contrôle et pas une consigne

Elles sont DÉJÀ interdites dans `prompts.py` et `prompt_library.py`. Depuis
cinq mois. La cliente les relève encore :

- 09/08/2026 : « l'étude passe son temps à dire données à définir, à vérifier —
  je n'aime pas cela, j'aime apporter de vraies réponses » ;
- 28/10/2026 : « Aucun texte générique ni placeholder ».

Vérifié avant d'écrire : `grep` sur ces phrases dans `backend/generation/` ne
les trouvait que dans des CHAÎNES DE PROMPT. Aucun contrôle ne les cherchait
dans le texte produit.

Ces tests échouent sur le code d'avant : `_formulations_interdites` n'existait
pas, et `redaction.controler` commençait par `del reference`.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType
from generation.relecture import Document, Reference, document_du_chapitre, relire
from generation.relecture.redaction import _formulations_interdites

BP = DeliverableType.BUSINESS_PLAN
STR = DeliverableType.BUSINESS_STRATEGY
EC = DeliverableType.COMPETITOR_STUDY


def _document(*paragraphes: str) -> Document:
    return document_du_chapitre({
        "chapitre": 5,
        "titre": "Analyse",
        "blocs": [{"type": "paragraphe", "texte": p} for p in paragraphes],
    })


# ── L'absence de donnée dite au lecteur : interdite partout ────────────────


@pytest.mark.parametrize("phrase", [
    "Nous n'avons pas trouvé de données sur ce segment.",
    "Pour ce pays, les données sont indisponibles.",
    "Peu de sources existent sur ce marché de niche.",
    "Aucune information disponible sur les volumes importés.",
])
def test_l_absence_de_donnee_fait_reprendre(phrase: str) -> None:
    [constat] = _formulations_interdites(_document(phrase), EC)
    assert constat.classe == "redaction"
    assert constat.grave is True
    assert "le cahier des charges l'interdit" in constat.detail


def test_elle_est_interdite_sur_les_quatre_livrables() -> None:
    """Les cahiers de l'EC ET du business plan la listent : c'est une règle de maison."""
    phrase = "Aucune information disponible sur ce point."
    for livrable in (EC, BP, STR, DeliverableType.MARKET_STUDY, ""):
        assert _formulations_interdites(_document(phrase), livrable), livrable


def test_dire_ce_qui_manque_precisement_est_permis() -> None:
    """Contre-épreuve : la forme que le dépôt DEMANDE ne doit pas être punie.

    Le prompt prescrit « ce qui manque EXACTEMENT — une donnée nommée, pas un
    manque vague ; puis la démarche concrète pour l'obtenir ». Un contrôle qui
    frapperait cette phrase-là viderait la consigne.
    """
    assert _formulations_interdites(_document(
        "Le volume importé par la Corée du Sud n'est pas publié par les douanes "
        "coréennes avant mars : la Fédération des exportateurs le diffuse sur "
        "demande, en trois semaines."
    ), EC) == []


# ── Ce que chaque livrable interdit en plus ─────────────────────────────────


def test_le_business_plan_interdit_sa_propre_formule() -> None:
    [constat] = _formulations_interdites(
        _document("Le projet est très ambitieux et innovant."), BP,
    )
    assert constat.grave is True
    # Contre-épreuve : elle ne vaut QUE pour le business plan.
    assert _formulations_interdites(
        _document("Le projet est très ambitieux et innovant."), EC,
    ) == []


@pytest.mark.parametrize("phrase", [
    "Il faut poster plus sur Instagram pour gagner en visibilité.",
    "Il faut être présent sur tous les réseaux dès le lancement.",
])
def test_la_strategie_interdit_les_conseils_creux(phrase: str) -> None:
    [constat] = _formulations_interdites(_document(phrase), STR)
    assert constat.grave is True
    # Contre-épreuve : propre à la stratégie.
    assert _formulations_interdites(_document(phrase), BP) == []


# ── Celles qui ne sont interdites que SANS chiffre ──────────────────────────


def test_une_affirmation_creuse_est_signalee_sans_etre_grave() -> None:
    """Le cahier ne l'interdit que « sans chiffres à l'appui »."""
    [constat] = _formulations_interdites(
        _document("Le marché est très porteur et mérite d'être adressé."), BP,
    )
    assert constat.grave is False
    assert "sans un chiffre" in constat.detail


def test_la_meme_affirmation_appuyee_ne_dit_rien() -> None:
    """Contre-épreuve : avec son chiffre, elle est un constat."""
    assert _formulations_interdites(
        _document("Le marché est très porteur : 2,7 Md€ en 2025, en hausse de 8 %."), BP,
    ) == []


# ── Le branchement ──────────────────────────────────────────────────────────


def test_le_constat_remonte_par_la_relecture() -> None:
    """Écrit mais pas branché, c'est le défaut de Gamma : on vérifie le câble.

    Et `redaction.controler` commençait par `del reference` : la liste propre au
    livrable n'aurait eu aucun moyen d'arriver.
    """
    constats = relire(
        _document("Il faut poster plus sur Instagram."), Reference(livrable=STR),
    )
    assert any(
        c.classe == "redaction" and "poster plus" in c.detail for c in constats
    ), [c.motif() for c in constats]
