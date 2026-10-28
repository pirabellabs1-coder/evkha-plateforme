"""« données du projet » : 34 occurrences, puis 37 après l'avoir interdit.

## La mesure qui tranche

Business plan `578c7024` puis `7f737b7b` — le MÊME brief relancé, entre les
deux un correctif de prompt qui a cessé de prescrire « données du projet » et
s'est mis à l'interdire, en nommant à la place l'entreprise du dossier :

    578c7024  « données du projet » dans le document ENTIER : 34
    7f737b7b  idem, après le correctif de prompt            : 37
    FINDRAX v3 (référence validée de la cliente)            :  0

Le correctif de prompt n'a rien corrigé. Il a déplacé l'expression de la prose
vers les cellules de tableau, et l'essentiel se trouve dans l'annexe des
chiffres, sous la forme « Hypothèse — données du projet ».

Deux raisons, et aucune ne se règle par une huitième formulation :

1. **Le dépôt se contredisait.** Deux prompts de `chapitres/runner.py`
   interdisaient l'expression pendant que quatre prompts de `qa.py` écrivaient
   « Appuie-toi STRICTEMENT sur les données du projet fournies en contexte ».
   C'est la règle 5 : deux modules qui ne sont pas d'accord.
2. **Interdire une expression la met sous les yeux du modèle.** Six prompts la
   nommaient déjà. Une règle présente dans six prompts et ignorée ne se règle
   pas par une septième (voir la mémoire `un-controle-ne-commande-pas`).

## La réparation

Déterministe, au rendu, et sur la CLASSE : une attribution qui ne porte ni nom
propre ni année ne nomme aucune source. Elle ne s'imprime donc pas, et dans
l'annexe elle cède la place à l'explication que le fichier contenait déjà —
« Déclarée — fournie par vous, dans votre dossier ».

Énumérer les expressions aurait été incomplet (règle 4) : « données du
projet », « données internes », « le projet », « dossier client » attribuent
tous aussi peu.

Ces tests échouent sur le code d'avant : `attribue_quelque_chose` n'existait
pas, `libelle_de_source` imprimait « Source : données du projet », et
`_origine` recopiait l'attribution telle quelle.
"""
from __future__ import annotations

import pytest

from generation.rendu_word.annexe_chiffres import _origine
from generation.rendu_word.composants import attribue_quelque_chose, libelle_de_source
from generation.socle.referentiel import Fiabilite


class _Donnee:
    """Le strict nécessaire que `_origine` lit d'un chiffre du socle."""

    def __init__(self, fiabilite: object, source: str, libelle: str = "") -> None:
        self.fiabilite = fiabilite
        self.source = source
        self.libelle = libelle


# ---------------------------------------------------------------------------
# Le critère de classe
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "attribution",
    [
        "données du projet",
        "données internes",
        "le projet",
        "dossier client",
        "estimation interne",
        "",
    ],
)
def test_une_attribution_sans_nom_ni_annee_n_attribue_rien(attribution: str) -> None:
    """La CLASSE, pas les quatre instances mesurées."""
    assert not attribue_quelque_chose(attribution)


@pytest.mark.parametrize(
    "attribution",
    [
        "ÉCLORE, données internes",
        "Insee, démographie des entreprises, 2026",
        "prévisionnel 2027",
        "ÉCLORE, relevé de prix",
        "Banque de France",
    ],
)
def test_une_attribution_qui_nomme_une_source_est_gardee(attribution: str) -> None:
    """CONTRE-ÉPREUVE : la permissivité ne doit pas avaler les vraies sources.

    « ÉCLORE, données internes » contient les mots qui ne suffisent pas — et
    le nom de l'entreprise, qui suffit. C'est exactement la forme que le
    prompt demande désormais ; l'effacer rendrait le correctif pire que le
    défaut.
    """
    assert attribue_quelque_chose(attribution)


# ---------------------------------------------------------------------------
# Les deux endroits où elle s'imprimait
# ---------------------------------------------------------------------------


def test_sous_un_chiffre_cle_rien_ne_s_imprime() -> None:
    """« Source : données du projet » occupait la place d'une information."""
    assert libelle_de_source("données du projet") == ""


def test_sous_un_chiffre_cle_une_vraie_source_s_imprime_toujours() -> None:
    """CONTRE-ÉPREUVE : la ligne « Source : … » ne disparaît pas pour autant."""
    libelle = libelle_de_source("Insee, 2026")

    assert libelle.startswith("Source")
    assert "Insee, 2026" in libelle


def test_dans_l_annexe_l_explication_prend_la_place() -> None:
    """Et elle en dit PLUS que l'attribution qu'elle remplace.

    C'est le cas majoritaire mesuré : « Hypothèse — données du projet » et
    « Déclarée — données du projet » font l'essentiel des 37 occurrences.
    """
    declaree = _origine(_Donnee(Fiabilite.DECLAREE, "données du projet"))
    scenario = _origine(_Donnee(Fiabilite.SCENARIO, "données du projet"))

    assert "données du projet" not in declaree
    assert declaree == "Déclarée — fournie par vous, dans votre dossier"
    assert "données du projet" not in scenario
    assert scenario == "Hypothèse — posée pour raisonner, à confirmer"


def test_dans_l_annexe_une_vraie_source_reste_citee() -> None:
    """CONTRE-ÉPREUVE : l'annexe sert à dire D'OÙ vient le chiffre."""
    origine = _origine(_Donnee(Fiabilite.OBSERVEE, "Insee, démographie 2026"))

    assert "Insee, démographie 2026" in origine


def test_un_calcul_garde_sa_formule() -> None:
    """CONTRE-ÉPREUVE : la cliente demande à VOIR le calcul (29/07/2026).

    Le libellé d'un calcul passe avant l'attribution : sans ce test, le
    nouveau critère aurait pu le court-circuiter.
    """
    origine = _origine(
        _Donnee(
            Fiabilite.ESTIMEE,
            "données du projet",
            libelle="Calculé : chiffre d'affaires moins charges",
        )
    )

    assert "Calculé : chiffre d'affaires moins charges" in origine


# ---------------------------------------------------------------------------
# La contradiction qui entretenait le défaut
# ---------------------------------------------------------------------------


def test_aucun_prompt_ne_met_plus_l_expression_sous_les_yeux_du_modele() -> None:
    """Quatre prompts de `qa.py` l'écrivaient POSITIVEMENT (règle 5).

    Ils demandaient « Appuie-toi STRICTEMENT sur les données du projet
    fournies en contexte » pendant que deux autres prompts l'interdisaient.
    Ce test échoue sur le code d'avant.

    Les mentions qui RESTENT, dans `chapitres/runner.py`, sont les
    interdictions elles-mêmes : elles doivent nommer ce qu'elles interdisent.
    C'est précisément pourquoi la réparation est déterministe et ne compte
    plus sur elles.
    """
    from pathlib import Path

    qa = (
        Path(__file__).resolve().parents[1] / "generation" / "qa.py"
    ).read_text(encoding="utf-8")

    assert "données du projet" not in qa
