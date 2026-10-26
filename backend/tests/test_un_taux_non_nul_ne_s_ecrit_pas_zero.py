"""Un taux qui n'est pas nul ne s'écrit jamais « 0 % ».

26/10/2026, étude de marché à l'export relevée par la cliente : « un taux de
capture de 0,009 % s'affiche "0 %" à deux endroits ».

Le rendu Word écrivait ses étiquettes de répartition en `f"{part:.0f} %"`. Sur
0,009, cela donne « 0 % » — et le document AFFIRME alors que le projet ne capte
rien. Un zéro n'est pas un arrondi : c'est une autre affirmation, et tout le
raisonnement qui s'appuie dessus devient faux.

`montant_lisible` traitait déjà ce défaut sur les MONTANTS depuis le
29/09/2026 (« SOM = 0 Md€ » pour 480 000 €). La classe n'était fermée qu'à
moitié (règle 4).
"""
from __future__ import annotations

import pytest

from generation.socle.schema import INSECABLE, pourcentage_lisible


def _nu(texte: str) -> str:
    """Le texte avec son espace insécable remplacée, pour des assertions lisibles."""
    return texte.replace(INSECABLE, " ")


def test_le_defaut_mesure_ne_se_produit_plus() -> None:
    """0,009 % ne s'écrit plus « 0 % ».

    C'est le test qui échoue sur le code d'avant : `f"{0.009:.0f} %"` rendait
    exactement « 0 % ».
    """
    ecrit = _nu(pourcentage_lisible(0.009))
    assert ecrit != "0 %"
    # Le premier chiffre SIGNIFICATIF doit apparaître. « 0,01 % » ne le montre
    # pas — le 9 y est arrondi en 1 —, et la consigne `5 bis` du prompt ordonne
    # au rédacteur d'écrire « 0,009 % » : les deux écritures doivent concorder,
    # sinon le document porte deux valeurs pour une même grandeur.
    assert ecrit == "0,009 %"


def test_le_rendu_concorde_avec_la_consigne_donnee_au_redacteur() -> None:
    """La figure et la prose doivent écrire le même taux de la même façon.

    La consigne `5 bis` de `chapitres/runner.py` cite « 0,009 %, 0,0096 % »
    comme les écritures attendues. Un formateur qui en rendrait une autre
    fabriquerait l'incohérence que le correctif prétend fermer (règle 5).
    """
    assert _nu(pourcentage_lisible(0.009)) == "0,009 %"
    assert _nu(pourcentage_lisible(0.0096)) == "0,01 %"  # 3 décimales au plus


@pytest.mark.parametrize("valeur", [0.009, 0.0012, 0.5, -0.004, 0.001])
def test_aucun_taux_non_nul_ne_rend_un_zero(valeur: float) -> None:
    """La classe entière : rien de non nul ne doit s'afficher comme un zéro nu."""
    ecrit = _nu(pourcentage_lisible(valeur))
    assert ecrit not in {"0 %", "0,0 %", "0,00 %", "-0 %"}, ecrit


def test_un_taux_ordinaire_garde_son_ecriture_compacte() -> None:
    """Contre-épreuve : la précision voulue est respectée quand elle suffit.

    L'étiquette d'une bande de répartition doit rester courte ; le correctif ne
    doit pas transformer « 38 % » en « 37,5 % » partout.
    """
    assert _nu(pourcentage_lisible(37.5)) == "38 %"
    assert _nu(pourcentage_lisible(42.0)) == "42 %"


def test_une_precision_demandee_est_tenue() -> None:
    assert _nu(pourcentage_lisible(37.46, decimales=1)) == "37,5 %"


def test_un_vrai_zero_reste_zero() -> None:
    """Contre-épreuve : zéro s'écrit zéro. Le contrôle ne fabrique pas de valeur."""
    assert _nu(pourcentage_lisible(0)) == "0 %"
    assert _nu(pourcentage_lisible(0.0)) == "0 %"


def test_sous_le_millieme_on_dit_le_seuil() -> None:
    """En deçà de 0,001 %, aucune décimale ne montre un chiffre significatif.

    On écrit alors une borne, qui est vraie, plutôt qu'un zéro qui ne l'est
    pas — règle 1 : quand on ne peut pas dire la valeur, on ne se tait pas.
    """
    assert _nu(pourcentage_lisible(0.00004)) == "< 0,001 %"
    # Et pas « -< 0,001 % », qui se lirait « moins inférieur à » : un taux
    # négatif minuscule se borne par le haut.
    assert _nu(pourcentage_lisible(-0.00004)) == "> -0,001 %"


def test_l_espace_avant_le_signe_est_insecable() -> None:
    """Comme pour les montants : « 12 % » ne se coupe jamais en fin de ligne."""
    assert INSECABLE in pourcentage_lisible(12)
