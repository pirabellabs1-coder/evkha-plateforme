"""Une stratégie qui analyse sans décider n'est pas une stratégie.

Cliente, 12/08/2026, sur une stratégie notée 7,5/10 :

    « le document est encore trop proche d'un audit / diagnostic stratégique :
    il analyse beaucoup, explique beaucoup et répète parfois les constats. Je
    souhaite que la stratégie apporte davantage de solutions, méthodes,
    décisions et actions directement applicables. […] Mes 4 piliers doivent
    devenir la colonne vertébrale OBLIGATOIRE du livrable. […] À la fin, le
    client ne doit pas simplement se dire "je comprends mieux mon entreprise",
    mais "je sais exactement ce que je dois faire maintenant, dans quel ordre,
    comment et avec quels indicateurs pour savoir si cela fonctionne". »

## Ce que le contrôle d'avant laissait passer

`verifier_piliers_strategie` vérifie qu'un AXE est traité. Il rendait donc
`passed` sur un chapitre qui analyse le positionnement pendant mille six cents
mots sans jamais dire lequel est retenu — exactement le document décrit
ci-dessus. Un axe traité n'est pas une décision prise, et c'est cette distance
qui sépare un diagnostic d'une stratégie.

## Verrouillée ou seulement demandée

Une décision porte un motif quand elle a une formulation française stable —
« cible prioritaire », « planning éditorial », « 90 jours ». Elle n'en porte
pas quand sa présence ne se lit pas sans interpréter : « montrer le parcours
logique du client entre les offres » est une exigence de fond, pas une chaîne
de caractères. Prétendre la contrôler produirait un motif faux, pire qu'un
contrôle absent (règle 2). Le test le vérifie explicitement, pour qu'on ne
puisse pas croire que tout est verrouillé.
"""
from __future__ import annotations

from generation.checks_evangeline import (
    DECISIONS_STRATEGIE,
    verifier_decisions_strategie,
)

#: Un document qui DÉCIDE, écrit comme un consultant l'écrirait — pas comme
#: les expressions régulières l'attendent. Si le contrôle refusait celui-ci,
#: il refuserait le livrable que la cliente demande.
STRATEGIE_QUI_TRANCHE = """
La cible prioritaire est le café-restaurant indépendant ; la cible secondaire,
l'amateur équipé qui achète en ligne. Le positionnement retenu est celui du
torréfacteur de quartier à traçabilité complète, et la spécialisation
recommandée porte sur les cafés d'origine unique. L'offre phare est
l'abonnement mensuel. La proposition de valeur tient en une phrase, et le
message commercial principal la reprend telle quelle. La vente en grande
distribution, elle, est écartée.

Le catalogue se resserre : deux références sont à conserver, la formule
découverte est à modifier. L'architecture cible tient en trois niveaux, d'une
offre d'entrée de gamme à une offre premium. La montée en gamme s'organise par
l'abonnement, et le parcours client va de la dégustation à l'abonnement annuel.

Les canaux prioritaires sont le référencement local et la prescription par les
cafés partenaires. Les canaux secondaires restent la presse locale. Les canaux
à éviter sont les places de marché généralistes. La fréquence de publication
est arrêtée, et le planning éditorial couvre le premier mois. La prospection
directe auprès des restaurateurs porte le reste de l'acquisition.

Le prix cible du paquet est supérieur au tarif pratiqué aujourd'hui, et
l'impact attendu sur la marge justifie la reprise du positionnement.

À 30 jours, la grille tarifaire est affichée ; à 60 jours, l'abonnement ouvre ;
à 90 jours, deux partenariats sont signés. À 6 mois, la boutique en ligne
ouvre. Les indicateurs de suivi sont le nombre d'abonnés actifs et la marge
brute. Au-delà de la cible du troisième mois, poursuivre ; sous cette cible,
modifier le message ; loin dessous, arrêter la campagne.
"""

#: Le document que la cliente a noté 7,5/10 : lucide, structuré, et qui ne
#: tranche rien.
STRATEGIE_QUI_SE_CONTENTE_D_ANALYSER = """
Le positionnement actuel du business repose sur une expertise réelle mais peu
formalisée. L'analyse des offres montre un catalogue dense, dont la lisibilité
souffre. Les canaux d'acquisition sont examinés un à un et leur cohérence avec
le positionnement est discutée. La lecture économique fait apparaître une
dépendance forte au temps du dirigeant, dont les conséquences futures sont
identifiées. À retenir : le modèle est viable mais fragile.
"""


def test_un_document_qui_analyse_sans_trancher_est_signale() -> None:
    """Le cas exact de la cliente : tout est traité, rien n'est décidé."""
    manquantes = verifier_decisions_strategie(
        STRATEGIE_QUI_SE_CONTENTE_D_ANALYSER
    )

    libelles = {m.libelle for m in manquantes}
    assert "la cible prioritaire, nommée" in libelles
    assert "le positionnement retenu" in libelles
    assert any("30, 60 et 90 jours" in libelle for libelle in libelles)


def test_un_document_qui_tranche_passe_entier() -> None:
    """LA contre-épreuve : le contrôle ne doit pas punir le livrable voulu.

    Écrite en français ordinaire, pas sur mesure pour les motifs. Sans elle,
    on verrouillerait une formulation particulière au lieu d'une exigence —
    et le prochain document juste serait bloqué.
    """
    manquantes = verifier_decisions_strategie(STRATEGIE_QUI_TRANCHE)

    assert manquantes == [], [m.libelle for m in manquantes]


def test_chaque_manque_designe_le_chapitre_qui_doit_l_accueillir() -> None:
    """Le motif doit être réparable : un défaut sans adresse tourne en rond."""
    par_libelle = {
        m.libelle: m.chapitre_porteur
        for m in verifier_decisions_strategie(STRATEGIE_QUI_SE_CONTENTE_D_ANALYSER)
    }

    assert par_libelle["la cible prioritaire, nommée"] == 8
    assert par_libelle["les canaux prioritaires"] == 13


def test_le_jugement_porte_sur_le_document_entier() -> None:
    """Une décision posée au chapitre 6 vaut pour le chapitre 8.

    Bloquer sur l'EMPLACEMENT punirait un document juste : rien ne garantit
    que le modèle range la cible prioritaire là où le plan l'attendait.
    """
    ailleurs = "Chapitre 6. La cible prioritaire est le restaurateur indépendant."
    manquantes = verifier_decisions_strategie(ailleurs)

    assert all(m.libelle != "la cible prioritaire, nommée" for m in manquantes)


def test_ce_qui_ne_se_controle_pas_ne_pretend_pas_se_controler() -> None:
    """Règle 2 : un contrôle qui n'a rien de fiable à comparer se tait — mais
    il le DIT, au lieu de laisser croire que tout est verrouillé."""
    sans_motif = [
        d.libelle
        for bloc in DECISIONS_STRATEGIE
        for d in bloc.decisions
        if not d.motif
    ]

    assert "les éléments concrets de différenciation" in sans_motif
    assert any("parcours" in libelle or "rôle de chaque offre" in libelle
               for libelle in sans_motif)


# ── La cause, pas seulement le contrôle ─────────────────────────────────────


def test_la_consigne_reclame_exactement_ce_que_le_gate_exige() -> None:
    """Une seule liste, deux lecteurs (règle 5).

    Écrire la demande d'un côté et le contrôle de l'autre, c'est la
    contradiction interne qui a coûté 5,22 € le 10/08/2026 : une consigne qui
    ordonne ce qu'un contrôle ignore, ou l'inverse. Le test le rend
    impossible — la consigne est CONSTRUITE depuis la déclaration.
    """
    from catalog.models import DeliverableType
    from generation.prompts import _consigne_specifique_livrable

    consigne = _consigne_specifique_livrable(DeliverableType.BUSINESS_STRATEGY)

    for bloc in DECISIONS_STRATEGIE:
        for decision in bloc.decisions:
            assert decision.libelle in consigne, (
                f"« {decision.libelle} » est exigée au gate et absente de la "
                "consigne : le modèle ne peut pas deviner ce qu'on lui reproche"
            )


def test_la_strategie_str_execute_le_controle() -> None:
    """Il pourrait exister sans être branché — défaut mesuré six fois ici."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "generation" / "strategies" / "str_.py"
    ).read_text(encoding="utf-8")

    assert "verifier_decisions_strategie" in source
    assert "decision_absente" in source
