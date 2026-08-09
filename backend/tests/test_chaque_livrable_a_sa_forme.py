"""Trois livrables non décrits par le modèle ne doivent pas recevoir la même forme.

## Ce qui n'allait pas

`modele_couvre` ne reconnaît que l'étude de marché. Business plan, stratégie et
étude concurrentielle retombaient donc tous les trois sur `_bloc_forme()` — un
texte **identique pour les trois, et pour chacun de leurs chapitres**. Chaque
chapitre de business plan sort d'ailleurs marqué en base
`[non contrôlé] type de livrable non décrit par le modèle` : il est accepté,
jamais jugé sur sa forme.

Or ces documents n'ont ni le même objet, ni le même lecteur. Un plan d'affaires
se juge sur des chiffres qui s'enchaînent d'un chapitre à l'autre ; une étude
concurrentielle sur des comparaisons à critères constants ; une stratégie sur
des décisions datées et assignées. Leur servir une consigne moyenne produit
trois documents de la même forme.

## Ce que ce test NE prétend PAS

Ce n'est pas un modèle de référence, et il ne faut pas le lire comme tel. Le
modèle de l'étude de marché a été **mesuré** sur `references/joalie_2026.docx`,
une étude réelle livrée à la cliente. Ces consignes-ci ne sont mesurées sur
rien, et aucun contrôle de conformité ne s'y adosse.

En dériver un depuis un business plan que nous avons nous-mêmes produit
n'apprendrait rien : cela encoderait ce que le moteur fait déjà, puis le
déclarerait conforme. Une boucle qui valide contre sa propre mesure se donne
raison toute seule (règle 9). Il faut un business plan validé, écrit hors de
cette chaîne.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType
from generation.chapitres.runner import _FORME_PAR_LIVRABLE, _bloc_forme
from generation.modele.chargement import MODELES_PAR_LIVRABLE, modele_couvre

#: Recopiés à la main : un test qui relit la table qu'il vérifie ne vérifie rien.
NON_DECRITS = (
    DeliverableType.BUSINESS_PLAN,
    DeliverableType.BUSINESS_STRATEGY,
    DeliverableType.COMPETITOR_STUDY,
)


def test_seule_l_etude_de_marche_est_decrite_par_un_modele() -> None:
    """L'état réel, énoncé — pour qu'il se voie le jour où il change."""
    assert set(MODELES_PAR_LIVRABLE) == {DeliverableType.MARKET_STUDY}
    assert modele_couvre(DeliverableType.MARKET_STUDY)
    for livrable in NON_DECRITS:
        assert not modele_couvre(livrable), livrable


@pytest.mark.parametrize("livrable", sorted(NON_DECRITS))
def test_chaque_livrable_non_decrit_recoit_une_forme_propre(livrable: str) -> None:
    assert livrable in _FORME_PAR_LIVRABLE, (
        f"{livrable} retombe sur la consigne moyenne : trois documents "
        "différents en sortiraient avec la même forme."
    )


def test_les_trois_formes_sont_reellement_differentes() -> None:
    """Trois entrées identiques satisferaient le test précédent sans rien régler."""
    formes = [_bloc_forme(livrable) for livrable in NON_DECRITS]

    assert len(set(formes)) == len(formes)


@pytest.mark.parametrize(
    ("livrable", "attendu"),
    [
        (DeliverableType.BUSINESS_PLAN, "ENCHAÎNENT"),
        (DeliverableType.COMPETITOR_STUDY, "CRITÈRES CONSTANTS"),
        (DeliverableType.BUSINESS_STRATEGY, "ÉCHÉANCE"),
    ],
)
def test_chaque_forme_porte_sa_contrainte_caracteristique(
    livrable: str, attendu: str
) -> None:
    """Ce que chacune doit dire, et que les deux autres n'ont pas à dire."""
    assert attendu in _bloc_forme(livrable)


def test_la_partie_commune_reste_commune() -> None:
    """La forme propre s'AJOUTE, elle ne remplace pas — sinon la mesure se perd.

    « 52 % des mots dans des tableaux » vient du document validé et vaut pour
    tous les livrables. Une forme propre qui l'écraserait ferait reculer les
    trois documents qu'elle prétend améliorer.
    """
    for livrable in (*NON_DECRITS, DeliverableType.MARKET_STUDY, ""):
        assert "FORME ATTENDUE" in _bloc_forme(livrable), livrable
        assert "TABLEAUX" in _bloc_forme(livrable), livrable


def test_un_livrable_inconnu_recoit_la_partie_commune_seule() -> None:
    """Pas de silence, pas d'invention : ce qu'on sait, et rien de plus."""
    forme = _bloc_forme("livrable_qui_n_existe_pas")

    assert "FORME ATTENDUE" in forme
    assert forme == _bloc_forme("")


def test_la_table_des_modeles_est_une_table() -> None:
    """Le jour où un second modèle arrive, c'est une ligne de données.

    Ce test échouerait sur le code d'avant, où la couverture était portée par
    une constante scalaire `TYPE_LIVRABLE_MODELE` : rien à indexer.
    """
    assert isinstance(MODELES_PAR_LIVRABLE, dict)
    assert MODELES_PAR_LIVRABLE[DeliverableType.MARKET_STUDY] == "etude_de_marche"
