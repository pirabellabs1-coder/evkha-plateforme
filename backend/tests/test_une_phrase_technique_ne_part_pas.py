"""Une phrase où l'outil parle de sa fabrication ne part pas dans le document.

Business plan `8ead345f` (13/11/2026) : « Cette figure ne peut pas être
produite : le socle ne porte pas les quatre sources de revenus comme
identifiants séparés. » Demande de la cliente : un filtre avant la mise en page.
"""
from __future__ import annotations

import pytest

from generation.meta_discours import est_un_aveu_technique


@pytest.mark.parametrize("texte", [
    "Cette figure ne peut pas être produite : le socle ne porte pas les quatre "
    "sources de revenus comme identifiants séparés.",
    "Ce graphique ne peut être tracé faute de données.",
    "Le socle ne contient pas le détail par marché.",
    "Les montants ne figurent pas comme identifiants du socle.",
])
def test_un_aveu_technique_est_reconnu(texte: str) -> None:
    assert est_un_aveu_technique(texte)


@pytest.mark.parametrize("texte", [
    # Les emplois COURANTS des mêmes mots, relevés dans les documents livrés.
    "Home, censé être le socle récurrent, ne pèse que 5 % du chiffre d'affaires.",
    "Une fois le socle technique et le script de conversion stabilisés.",
    "Chaque client reçoit un identifiant et un mot de passe.",
    "Le numéro d'identifiant fiscal figure sur la facture.",
    "La figure montre la répartition du chiffre d'affaires par offre.",
    "Ce contrat ne peut pas être produit devant le tribunal sans traduction.",
])
def test_la_prose_ordinaire_n_est_pas_touchee(texte: str) -> None:
    assert not est_un_aveu_technique(texte)
