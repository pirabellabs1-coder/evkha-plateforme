"""Business plan : un prix du marché cité avec sa source garde sa plage.

## La décision

Génération de preuve `7567ca2f` (15/09/2026), chapitre 8 : le tableau
comparatif cite « 20 à 50 € par mois pour un outil performant (Cabinet Osmose,
2026) » et « 3 000 à 8 000 € (PropulseByCA, 2026) ». Le gate les refusait au
nom du chiffre unique du business plan. Question posée au client : un prix du
MARCHÉ cité avec sa source peut-il rester une fourchette ? Réponse : « Oui, si
la source est citée ». Les prix du PROJET restent un par variante.

## Ce qui reste refusé

- « Étude de marché EVKHA à 149-195 € HT » : le prix du projet, sans source
  (le dossier donne quatre prix : 149, 149, 185 et 195 €) ;
- une source posée dans une AUTRE case de la ligne ;
- la même plage sourcée dans une stratégie : la décision porte sur le business
  plan.
"""
from __future__ import annotations

import pytest

from generation.checks_evangeline import detecter_fourchettes
from generation.prompts import _consigne_specifique_livrable

BP, STR = "business_plan", "business_strategy"


@pytest.mark.parametrize("texte", [
    "| Logiciel de business plan en ligne | 20 à 50 € par mois pour un outil performant "
    "(Cabinet Osmose, 2026) | Palier Solo à 129 €/mois |",
    "| Étude de marché sur mesure par un cabinet | 3 000 à 8 000 € (PropulseByCA, 2026) | x |",
    "Selon l'Observatoire des TPE, une étude sur mesure coûte de 3 000 à 8 000 €.",
])
def test_un_prix_de_marche_source_garde_sa_plage(texte: str) -> None:
    assert detecter_fourchettes(8, texte, BP) == []


@pytest.mark.parametrize(("texte", "livrable"), [
    # Le prix du projet, sans source (`7567ca2f`, chapitre 8).
    ("| Étude de marché EVKHA à 149-195 € HT, un rapport de 1 à plus de 15 |", BP),
    # La source est dans une autre case de la ligne.
    ("| Offre EVKHA | 149 à 195 € | (Cabinet Osmose, 2026) |", BP),
    # Une parenthèse de scénario n'est pas une source.
    ("Un budget de 3 000 à 8 000 € (scénario central 2027).", BP),
    # La décision porte sur le business plan.
    ("| Outil de gestion | 20 à 50 € par mois (Cabinet Osmose, 2026) |", STR),
])
def test_ce_qui_n_est_pas_un_prix_de_marche_source_reste_une_plage(
    texte: str, livrable: str,
) -> None:
    assert detecter_fourchettes(8, texte, livrable)


def test_la_consigne_du_business_plan_dit_l_exception_et_ses_bornes() -> None:
    consigne = _consigne_specifique_livrable(BP)
    assert "prix OBSERVÉ sur le marché" in consigne
    assert "Les prix du PROJET ne sont jamais concernés" in consigne
    # La consigne ne montre elle-même aucune plage (règle des consignes).
    assert detecter_fourchettes(0, consigne, BP) == []
