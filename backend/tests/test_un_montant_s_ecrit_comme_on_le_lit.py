"""Un socle n'écrit pas « 16 500 000 000 € » à un modèle qui recopie.

## Le défaut, trouvé dans un document livré

Business plan 73dde3ab, 17/08/2026, chapitre 16 : « Le marché montre un
secteur qui pèse **16 500 000 000 euros** et croît de 2,5 % par an ». Cinq
occurrences du même nombre à dix chiffres, dans la prose et dans trois
tableaux. Aucun document financier n'écrit cela ; il écrit 16,5 Md€.

Personne ne l'avait signalé — ni la cliente, ni le gate, ni la QA — parce que
**le chiffre était juste**. Seule sa forme était illisible, et aucun contrôle
de ce dépôt ne juge la forme d'un nombre. C'est la règle 9 : ce qu'un contrôle
ne regarde pas est exactement là où sa réparation ne cherchera pas non plus.

## Pourquoi le correctif était à moitié fait depuis le 09/08/2026

La cliente avait demandé, mot pour mot : « remplacer les unités techniques
comme MEUR par des formats plus simples : 6,8 Md€, 1,02 Md€, 600 k€ ».
`unite_lisible` a donc appris à traduire `MdEUR` en `Md€`. Mais la VALEUR
n'a jamais été mise à l'échelle avec son unité, et la ligne du socle injectée
dans chaque prompt disait toujours `= 16500000000.0 €`.

La demande portait sur le couple. Une moitié a été livrée.

## La limite assumée : on ne convertit que si rien ne se perd

« 3 287 400 € » ne devient pas « 3,3 M€ ». Un chapitre qui recalcule à partir
d'une valeur arrondie diverge de celui qui a lu la valeur exacte — ce serait
fabriquer une incohérence pour le confort de lecture, et ce dépôt a déjà payé
pour des contrôles qui créent le défaut qu'ils cherchent (règle 2).
"""
from __future__ import annotations

import pytest

from generation.socle.schema import montant_lisible

LISIBLE = [
    pytest.param(16_500_000_000.0, "EUR", "16,5 Md€", id="le-cas-mesure"),
    pytest.param(3_300_000.0, "EUR", "3,3 M€", id="millions-exacts"),
    pytest.param(1_000_000.0, "EUR", "1 M€", id="pile-un-million"),
    pytest.param(320_000.0, "EUR", "320 000 €", id="un-ca-reste-en-clair"),
    pytest.param(6.5, "EUR", "6,5 €", id="un-panier-moyen"),
]


@pytest.mark.parametrize(("valeur", "unite", "attendu"), LISIBLE)
def test_un_grand_montant_s_ecrit_a_son_echelle(
    valeur: float, unite: str, attendu: str
) -> None:
    assert montant_lisible(valeur, unite) == attendu


INCHANGES = [
    pytest.param(3_287_400.0, "EUR", "3 287 400 €", id="arrondir-perdrait-de-l-info"),
    pytest.param(
        16_512_345_678.0, "EUR", "16 512 345 678 €", id="milliards-non-ronds"
    ),
]


@pytest.mark.parametrize(("valeur", "unite", "attendu"), INCHANGES)
def test_une_conversion_qui_arrondirait_n_a_pas_lieu(
    valeur: float, unite: str, attendu: str
) -> None:
    """Mieux vaut long et exact que court et faux."""
    assert montant_lisible(valeur, unite) == attendu


DEJA_A_L_ECHELLE = [
    pytest.param(16.5, "MdEUR", "16,5 Md€", id="milliards-stockes-comme-tels"),
    pytest.param(600.0, "kEUR", "600 k€", id="milliers-stockes-comme-tels"),
]


@pytest.mark.parametrize(("valeur", "unite", "attendu"), DEJA_A_L_ECHELLE)
def test_une_unite_deja_a_l_echelle_ne_se_convertit_pas_deux_fois(
    valeur: float, unite: str, attendu: str
) -> None:
    """`MdEUR` porte déjà sa magnitude : la valeur lui correspond."""
    assert montant_lisible(valeur, unite) == attendu


NON_MONETAIRES = [
    pytest.param(15_000.0, "unite", "15 000", id="un-denombrement"),
    pytest.param(3.0, "annees", "3 ans", id="une-duree"),
]


@pytest.mark.parametrize(("valeur", "unite", "attendu"), NON_MONETAIRES)
def test_ce_qui_n_est_pas_de_l_argent_garde_son_unite(
    valeur: float, unite: str, attendu: str
) -> None:
    assert montant_lisible(valeur, unite) == attendu


def test_la_ligne_du_socle_ne_porte_plus_le_nombre_brut() -> None:
    """La contre-épreuve de bout en bout : c'est CE texte que le modèle lit.

    Le test précédent ne prouverait rien si `_bloc_socle` appelait encore
    l'ancienne fonction — un contrôle qui ne regarde pas la sortie réelle est
    exactement ce que la règle 9 décrit.
    """
    from generation.chapitres import runner

    source = (runner.__file__ or "").replace("runner.py", "runner.py")
    with open(source, encoding="utf-8") as fichier:
        code = fichier.read()

    assert "montant_lisible(d.valeur, d.unite)" in code, (
        "la ligne du socle doit passer par montant_lisible, sinon le modèle "
        "relit le nombre brut et le recopie dans la prose du client"
    )
