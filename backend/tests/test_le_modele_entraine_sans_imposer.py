"""Le modèle de référence entraîne le rédacteur ; il ne lui impose pas sa forme.

Décision du 08/08/2026 : « on n'a pas besoin de suivre exactement le modèle, le
modèle est pour l'entraînement et c'est tout. »

Jusque-là, un écart de volume ou d'ordre des blocs valait REFUS tant qu'il
restait une tentative : le chapitre était rejoué jusqu'à ressembler au gabarit.
Mesuré sur l'étude de marché réelle `b561c2d6` — 3,14 € pour 14 chapitres sur
23, contre 2,28 € pour les 22 chapitres du business plan, qui n'a pas de
modèle. Le rythme s'était dégradé de 6,1 à 10,2 minutes par chapitre, parce que
les chapitres tardifs, les plus longs, s'écartaient le plus du volume attendu.

Le contrôle coûtait donc plus que le document. Ces écarts sont désormais
CONSIGNÉS sans être rejoués — la différence entre « vérifié » et « pas de
nouvelle » est préservée, ce qui change est qu'on ne repaye plus un appel.

Deux familles restent bloquantes, et pour des raisons opposées :

- `variable_non_resolue` et `data_refs_inconnus` rendent le document **faux**.
  Un `{{client.nom}}` imprimé tel quel, un chiffre absent du socle : cela se
  voit à la première lecture et discrédite l'étude ;
- `graphiques_min` est un **plancher**, pas une ressemblance. Le rendre
  consultatif réduirait le nombre de figures, alors qu'on en veut davantage.
"""
from __future__ import annotations

import pytest

from generation.modele.conformite import (
    REGLES_DE_RESSEMBLANCE,
    REGLES_REDHIBITOIRES,
    Ecart,
    Gravite,
    RapportConformite,
    arbitrer,
)

CONTROLES = ["sequence_des_blocs", "volume", "graphiques_min"]

#: Les règles de ressemblance, RECOPIÉES à dessein.
#:
#: Paramétrer sur `REGLES_DE_RESSEMBLANCE` elle-même était une faute, découverte
#: en jouant la contre-épreuve : vider la constante faisait DISPARAÎTRE les cas
#: de test au lieu de les faire échouer, et la suite restait verte sur un code
#: revenu au comportement d'avant. Un contrôle qui n'a plus rien à comparer
#: n'est pas un succès (règle 1).
RESSEMBLANCE_ATTENDUE = (
    "volume",
    "sequence_des_blocs",
    "dosage_tableaux",
    "dosage_paragraphes",
    "dosage_encadres",
)


def _rapport(*ecarts: Ecart) -> RapportConformite:
    return RapportConformite(
        chapitre=4, ecarts=list(ecarts), controles_executes=CONTROLES,
        controles_impossibles={},
    )


def _ecart(regle: str) -> Ecart:
    return Ecart(regle, Gravite.BLOQUANTE, f"détail de {regle}")


def test_les_deux_familles_ne_se_recouvrent_pas() -> None:
    """Garde-fou : une règle dans les deux ensembles rendrait l'arbitrage flou.

    Sans lui, ajouter une règle au mauvais endroit passerait inaperçu — et le
    comportement dépendrait de l'ordre des tests dans `arbitrer`.
    """
    assert REGLES_DE_RESSEMBLANCE == frozenset(RESSEMBLANCE_ATTENDUE)
    assert not (REGLES_DE_RESSEMBLANCE & REGLES_REDHIBITOIRES)
    assert "graphiques_min" not in REGLES_DE_RESSEMBLANCE
    assert "graphiques_min" not in REGLES_REDHIBITOIRES


@pytest.mark.parametrize("regle", RESSEMBLANCE_ATTENDUE)
def test_un_ecart_de_ressemblance_ne_fait_pas_rejouer(regle: str) -> None:
    """LE changement. Première tentative, donc le pire cas pour l'ancien code."""
    arbitrage = arbitrer(_rapport(_ecart(regle)), derniere_tentative=False)

    assert not arbitrage.bloque
    assert any(regle in ligne for ligne in arbitrage.acceptes)


@pytest.mark.parametrize("regle", RESSEMBLANCE_ATTENDUE)
def test_un_ecart_de_ressemblance_reste_consigne(regle: str) -> None:
    """Accepté n'est pas tu : sinon on ne saurait plus ce qu'on a laissé passer."""
    arbitrage = arbitrer(_rapport(_ecart(regle)), derniere_tentative=False)

    assert arbitrage.acceptes, f"{regle} accepté en silence"


@pytest.mark.parametrize("regle", sorted(REGLES_REDHIBITOIRES))
def test_un_ecart_redhibitoire_refuse_toujours(regle: str) -> None:
    """Contre-épreuve : l'assouplissement ne doit pas ouvrir la porte au faux."""
    arbitrage = arbitrer(_rapport(_ecart(regle)), derniere_tentative=True)

    assert arbitrage.bloque
    assert any(regle in ligne for ligne in arbitrage.refus)


def test_le_plancher_de_figures_fait_encore_rejouer() -> None:
    """`graphiques_min` n'est pas une ressemblance — on veut PLUS de figures."""
    arbitrage = arbitrer(_rapport(_ecart("graphiques_min")), derniere_tentative=False)

    assert arbitrage.bloque


def test_le_plancher_de_figures_cede_a_la_derniere_tentative() -> None:
    """Une étude sans figure vaut mieux qu'une étude bloquée.

    C'est la règle d'origine, et elle ne change pas : sur la dernière tentative
    l'écart est accepté puis consigné.
    """
    arbitrage = arbitrer(_rapport(_ecart("graphiques_min")), derniere_tentative=True)

    assert not arbitrage.bloque
    assert arbitrage.acceptes


def test_un_ecart_faux_l_emporte_sur_une_ressemblance() -> None:
    """Mêlés, le rédhibitoire décide — et la ressemblance reste consignée."""
    arbitrage = arbitrer(
        _rapport(_ecart("variable_non_resolue"), _ecart("volume")),
        derniere_tentative=False,
    )

    assert arbitrage.bloque
    assert any("variable_non_resolue" in x for x in arbitrage.refus)
    assert any("volume" in x for x in arbitrage.acceptes)


def test_un_chapitre_conforme_passe_sans_rien_signaler() -> None:
    """Contre-épreuve du garde-fou : ne rien trouver doit rester possible."""
    arbitrage = arbitrer(_rapport(), derniere_tentative=False)

    assert not arbitrage.bloque
    assert not arbitrage.acceptes
