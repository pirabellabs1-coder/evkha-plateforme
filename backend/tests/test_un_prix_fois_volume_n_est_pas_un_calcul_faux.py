"""« N clients à X € par mois, soit Y € par an » n'est pas un calcul faux quand Y = N × X × 12.

## Le faux motif

Audit du 14/09/2026, A4 : la projection de période lisait « 19 € par mois,
soit 57 000 € par an », multipliait 19 par 12, trouvait 228 et déclarait le
calcul faux. Le nombre d'abonnés posé juste avant — 250 — n'était pas vu. Or
250 × 19 × 12 = 57 000 : la phrase est juste.

C'est la forme exacte que la règle 5 de `PRIX_ET_MODELE_ECONOMIQUE` demande
d'écrire (« CHIFFRE D'AFFAIRES = PRIX x VOLUME, ET LE PRODUIT TOMBE JUSTE ») :
le prompt l'exigeait, le contrôle la punissait, et le chapitre était réécrit
avec un motif qui conseillait en plus de « préciser la saisonnalité ».

Ces tests échouent sur le code d'avant pour les phrases justes ; les
contre-épreuves — un résultat qui ne tombe juste avec aucun nombre de la
phrase — passent dans les deux versions.
"""
from __future__ import annotations

import pytest

from generation.arithmetique import verifier


@pytest.mark.parametrize("phrase", [
    "250 abonnés à 19 € par mois, soit 57 000 € par an.",
    "29 € par mois pour 40 clients, soit 13 920 € par an.",
])
def test_le_prix_multiplie_par_le_volume_est_juste(phrase: str) -> None:
    """LE test : les deux phrases de l'audit."""
    assert verifier(phrase) == []


def test_la_projection_simple_reste_juste() -> None:
    assert verifier("19 € par mois, soit 228 € par an.") == []


@pytest.mark.parametrize("phrase", [
    "250 abonnés à 19 € par mois, soit 60 000 € par an.",
    "26 000 € par mois, soit 300 000 € par an.",
])
def test_un_resultat_que_rien_ne_fait_tomber_juste_reste_faux(phrase: str) -> None:
    """CONTRE-ÉPREUVE : un effectif ne justifie que s'il donne le résultat EXACT."""
    assert verifier(phrase)
