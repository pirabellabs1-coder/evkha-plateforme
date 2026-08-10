"""Les analyses qui font la valeur d'un dossier sont DEMANDÉES, pas espérées.

Retours de la cliente du 09/08/2026, après lecture de la première étude
concurrentielle réelle — notée 7/10, objectif 10/10. Ses mots : « ici il y a
plutôt des ajouts à mettre que des modifications, car sur les chiffres c'était
bien et correct ».

Ce fichier vérifie que chacun de ces ajouts atteint le modèle. Il ne vérifie
pas qu'il obéit — aucun test ne le peut sans appeler l'API. Mais ce projet a
mesuré trois fois cette semaine qu'une règle écrite ailleurs que dans le prompt
envoyé n'existe pas : les dix-huit figures perdues de `b561c2d6` venaient d'une
consigne parfaitement rédigée que le moteur de production n'envoyait jamais.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType
from generation.chapitres.runner import _bloc_forme

#: Ce que la cliente a demandé, et le mot qui doit se retrouver dans la consigne.
#: Fragments COURTS : viser une phrase entière ferait tomber ce test à la
#: première reformulation, sans qu'aucune règle ait changé.
AJOUTS_ETUDE_CONCURRENTIELLE = {
    "indicateurs observables quand le CA manque": "OBSERVABLES",
    "comparaison tarifaire adaptée au métier": "COMPARAISON TARIFAIRE",
    "coût réel par profil de client": "profils de",
    "canaux d'acquisition du secteur": "trouve ses clients",
    "avis clients et réputation": "AVIS CLIENTS",
    "concurrents les plus dangereux": "plus dangereux",
    "où le marché est saturé": "saturé",
    "erreurs à éviter": "erreurs",
    "priorités avant lancement": "priorités avant le lancement",
}


@pytest.mark.parametrize(
    ("demande", "fragment"), sorted(AJOUTS_ETUDE_CONCURRENTIELLE.items())
)
def test_chaque_ajout_atteint_la_consigne(demande: str, fragment: str) -> None:
    forme = _bloc_forme(DeliverableType.COMPETITOR_STUDY)

    assert fragment in forme, f"la consigne ne dit rien de : {demande}"


def test_l_echelle_de_notation_est_definie_et_vaut_pour_TOUS_les_livrables() -> None:
    """« Une note ne doit jamais être attribuée parce que l'acteur semble premium. »

    Une note sans échelle n'est pas une mesure, c'est une impression — et une
    impression chiffrée trompe davantage qu'une impression assumée.

    Elle vit dans la partie COMMUNE : un radar mal noté décrédibilise autant un
    business plan qu'une étude concurrentielle.
    """
    for livrable in (
        DeliverableType.MARKET_STUDY,
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.BUSINESS_STRATEGY,
        DeliverableType.COMPETITOR_STUDY,
    ):
        forme = _bloc_forme(livrable)
        assert "1 absent" in forme, livrable
        assert "5 référence du secteur" in forme, livrable
        assert "OBSERVABLE" in forme, livrable


def test_les_quatre_questions_valent_pour_tous_les_livrables() -> None:
    """La chaîne qui rend l'étude décisionnelle, et non descriptive."""
    for livrable in (
        DeliverableType.MARKET_STUDY,
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.BUSINESS_STRATEGY,
        DeliverableType.COMPETITOR_STUDY,
    ):
        assert "QUATRE questions" in _bloc_forme(livrable), livrable


def test_la_strategie_recommande_UN_scenario() -> None:
    """Trois scénarios à égalité renvoient la décision au lecteur."""
    forme = _bloc_forme(DeliverableType.BUSINESS_STRATEGY)

    assert "RECOMMANDÉ" in forme
    assert "renvoi de la décision" in forme


def test_les_ajouts_ne_debordent_pas_sur_les_autres_livrables() -> None:
    """CONTRE-ÉPREUVE : la comparaison tarifaire n'a rien à faire dans un BP.

    Sans elle, on retomberait sur le défaut corrigé la veille — une consigne
    moyenne servie aux quatre livrables, qui produit quatre documents de la
    même forme.
    """
    plan = _bloc_forme(DeliverableType.BUSINESS_PLAN)

    assert "COMPARAISON TARIFAIRE" not in plan
    assert "AVIS CLIENTS" not in plan
