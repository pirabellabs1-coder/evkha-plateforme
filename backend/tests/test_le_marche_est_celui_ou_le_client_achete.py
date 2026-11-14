"""Le marché d'un projet est celui où ses clients achètent, pas celui de son siège.

Business plan de test `71a755fd` (14/11/2026), reprise de `8ead345f` : siège à
Paris, ventes en Chine continentale. Le socle a lu « taille du marché
national » comme la France ; le document a donc écrit « une part de marché de
< 0,001 % du marché français du e-commerce », et le seuil de franchise de TVA
des VENTES (93 500 €) pour une société qui ne facture que des services
(commissions, abonnements, logistique refacturée).

Deux défauts que les consignes du 13/11 n'avaient pas fait disparaître : la
règle sur les seuils distinguait biens et services sans dire COMMENT juger, et
la règle « le TAM se définit sur la zone de vente » ne visait que le TAM.
"""
from __future__ import annotations

from generation.chapitres.runner import REGLES_DE_FOND
from generation.socle.prompt import construire_prompt_socle

VARIABLES_EXPORT = {
    "SECTEUR": "Place de marché en ligne, produits du terroir",
    "PAYS": "France (siège social). Marchés de vente : Chine continentale dès 2027.",
}


def test_le_socle_mesure_le_marche_national_dans_le_pays_de_vente() -> None:
    for livrable in ("business_plan", "competitor_study", "business_strategy", "market_study"):
        prompt = construire_prompt_socle(deliverable_type=livrable, variables=VARIABLES_EXPORT)

        assert "désigne LE PAYS OÙ LES CLIENTS ACHÈTENT" in prompt, livrable
        assert "jamais celui du siège" in prompt, livrable


def test_le_redacteur_rapporte_ses_ventes_au_pays_des_clients() -> None:
    assert "dans le PAYS OÙ LES CLIENTS ACHÈTENT, jamais dans celui du siège" in REGLES_DE_FOND


def test_un_seuil_se_choisit_sur_ce_que_la_societe_facture() -> None:
    assert "ce que la SOCIÉTÉ FACTURE" in REGLES_DE_FOND
    assert "place de marché" in REGLES_DE_FOND.split("ce que la SOCIÉTÉ FACTURE")[1][:300]
