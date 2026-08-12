"""Le socle de l'étude concurrentielle doit RÉCLAMER sa base concurrents.

Le référentiel annonçait que « l'essentiel du socle EC vit dans `concurrents` »,
et le schéma déclarait bien cette liste. Mais rien ne la demandait : le prompt du
socle ne contenait aucune occurrence du mot concurrent, et `concurrents` partait
donc vide à chaque étude.

Conséquence, invisible jusqu'ici : le chapitre 6 — estimation des chiffres
d'affaires et parts de marché — était IMPOSSIBLE par construction. La règle
absolue du moteur structuré interdit de produire un chiffre absent du socle ;
le socle EC ne portait que cinq emplacements, aucun CA par acteur. Le chapitre
sortait donc sans ses chiffres, et aucun contrôle ne le disait (règle 1).

Ces tests échouent sur le code d'avant (règle 6).
"""
from __future__ import annotations

from catalog.models import DeliverableType
from generation.socle.prompt import construire_prompt_socle
from generation.socle.schema import Concurrent

_MARQUEUR = "BASE CONSOLIDÉE CONCURRENTS"


def test_le_socle_ec_reclame_la_base_consolidee() -> None:
    prompt = construire_prompt_socle(
        deliverable_type=DeliverableType.COMPETITOR_STUDY, variables={}
    )

    assert _MARQUEUR in prompt
    # Les cardinaux sont figés par le document : 8 directs + 3 indirects.
    assert "8" in prompt
    assert "3" in prompt


def test_le_socle_ec_reclame_la_methode_d_estimation() -> None:
    """Le champ qui rend le chapitre 6 executable.

    Sans methode d'estimation, un acteur dont le CA n'est pas publie ne peut
    pas etre estime : l'etape reste lettre morte quel que soit le prompt du
    chapitre. C'est donc au SOCLE de la reclamer, pas au chapitre.
    """
    prompt = construire_prompt_socle(
        deliverable_type=DeliverableType.COMPETITOR_STUDY, variables={}
    )

    assert "methode_estimation" in prompt
    assert "non publié" in prompt


def test_les_livrables_sans_chapitre_de_concurrence_ne_recoivent_pas_ce_bloc() -> None:
    """Contre-épreuve : le correctif ne doit pas polluer les autres livrables.

    La liste comptait le BUSINESS PLAN, et c'était une erreur de classement,
    pas de principe : il porte un chapitre 7 « Analyse concurrentielle ». Le
    12/08/2026, ce chapitre est mort cinq fois pour 4,19 € parce que son socle
    n'avait ni concurrents ni grille — il inventait les identifiants qu'on ne
    lui donnait pas.

    L'exigence est désormais DÉDUITE du chapitrage plutôt que déclarée ici :
    restent l'étude de marché et la stratégie, qui n'ont réellement aucun
    chapitre de concurrence et dont le socle ne s'alourdit pas.
    """
    for livrable in (
        DeliverableType.MARKET_STUDY,
        DeliverableType.BUSINESS_STRATEGY,
    ):
        prompt = construire_prompt_socle(deliverable_type=livrable, variables={})
        assert _MARQUEUR not in prompt, livrable


def test_le_business_plan_recoit_ce_bloc_et_garde_son_previsionnel() -> None:
    """Les deux, pas l'un OU l'autre : la chaîne `elif` supposait le contraire."""
    prompt = construire_prompt_socle(
        deliverable_type=DeliverableType.BUSINESS_PLAN, variables={}
    )

    assert _MARQUEUR in prompt
    assert "PRÉVISIONNEL FINANCIER" in prompt


def test_le_schema_concurrent_porte_les_neuf_colonnes_du_document() -> None:
    """Un champ absent du schéma ne peut pas être rendu par le modèle.

    Le POINT DE CONTRÔLE « BASE CONSOLIDÉE CONCURRENTS » du cahier des charges
    en impose neuf. Le modèle n'en portait que quatre.
    """
    champs = set(Concurrent.model_fields)

    for attendu in (
        "nom",
        "type",
        "emplacement",
        "structure",
        "positionnement",
        "site_web",
        "ca_connu",
        "methode_estimation",
        "fiabilite",
    ):
        assert attendu in champs, attendu


def test_un_concurrent_minimal_reste_acceptable() -> None:
    """Contre-épreuve : les nouveaux champs ne rendent rien obligatoire.

    Les rendre requis aurait fait échouer tout socle produit avant ce
    changement, et casse le stub comme les études déjà en base.
    """
    acteur = Concurrent(nom="Boulangerie du Centre")

    assert acteur.type == "direct"
    assert acteur.ca_connu == ""
    assert acteur.methode_estimation == ""
