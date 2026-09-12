"""La stratégie chiffre chaque formule, et ne propose plus de fourchette.

Deux défauts du même chapitre, trouvés sur la stratégie du dossier `f7f2fad9`.

**1. Point 3 de la cliente (08/09/2026) :** « il manque la rentabilité réelle de
chaque abonnement ». Le document affichait pourtant les trois prix — 12, 19 et
29 € — côte à côte. Le chapitre parlait des ACTIVITÉS sans jamais descendre au
PALIER, alors que c'est là que se décide une grille tarifaire.

**2. Une consigne qui ordonnait ce qu'un contrôle punit.** Le gate refuse les
fourchettes hors étude de marché (`_check_fourchettes`), et le document a été
signalé pour « 60-65 €/h ». Or la consigne de ce chapitre demandait « une
fourchette OU un prix cible ». Le modèle a obéi à la consigne et le contrôle l'a
puni — la classe de défaut que le dépôt appelle « une consigne qui ordonne ce
qu'un contrôle interdit », et qui faisait trois défauts sur cinq le 10/08/2026.

Ces tests échouent sur le code d'avant.
"""
from __future__ import annotations

from generation.prompt_library import BUSINESS_STRATEGY_PROMPTS as PROMPTS

CHAPITRE = "str.14.rentabilite_modele"


def test_le_chapitre_exige_la_rentabilite_de_chaque_formule() -> None:
    consigne = PROMPTS[CHAPITRE]
    assert "Rentabilite de chaque formule" in consigne
    for attendu in ("prix", "marge par client", "part du chiffre d'affaires"):
        assert attendu in consigne, attendu
    # Ce qu'on ne veut surtout pas : une répartition inventée faute de donnée.
    assert "n'invente aucune " in consigne


def test_le_chapitre_ne_propose_plus_de_fourchette() -> None:
    """Le contrôle refuse les plages dans ce livrable : la consigne aussi."""
    consigne = PROMPTS[CHAPITRE]
    assert "une fourchette ou un prix" not in consigne
    assert "jamais une fourchette" in consigne


def test_la_consigne_reste_une_recommandation_chiffree() -> None:
    """CONTRE-ÉPREUVE : on retire la fourchette, pas la recommandation.

    La cliente demandait le contraire le 12/08/2026 — « la pipeline analyse les
    prix, mais doit davantage RECOMMANDER ».
    """
    consigne = PROMPTS[CHAPITRE]
    assert "RECOMMANDATION" in consigne
    assert "prix par niveau d'offre" in consigne
