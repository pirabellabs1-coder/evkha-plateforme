"""Une réponse coupée doit dire qu'elle est coupée, pas accuser le schéma.

`complete_structured` ne fait **qu'un seul appel** — il n'a pas la boucle de
continuation de `complete()`. Un chapitre qui demande plus que `max_tokens`
rend donc un appel d'outil tronqué, dont l'`input` perd ses derniers champs.

La validation annonçait alors « blocs : champ requis ; resume : champ requis »,
ce qui envoie chercher un défaut de schéma — alors que le schéma est intact.

Mesuré le 08/08/2026 sur l'étude de marché réelle `b561c2d6` : le chapitre 19 a
échoué **six fois de suite** sur ce motif, et le vrai motif — `stop_reason`
valant `max_tokens` — était capturé par `StructuredResult` sans que personne ne
le lise. Un motif faux coûte plus cher qu'un motif absent (règle 2) : il a
envoyé chercher au mauvais endroit à chaque tentative.
"""
from __future__ import annotations

import pytest

from generation.chapitres.runner import MAX_TOKENS_CHAPITRE, motif_de_troncature

#: Consommation OBSERVÉE des chapitres voisins du 19, en jetons de sortie.
#: Recopiée du run réel : 5 383, 6 375 et 5 874. Le plus gros sert de repère.
CONSOMMATION_OBSERVEE = 6400


def test_une_troncature_est_nommee_comme_telle() -> None:
    """Le motif doit désigner la troncature, jamais le schéma."""
    motifs = motif_de_troncature("max_tokens", MAX_TOKENS_CHAPITRE)

    assert motifs
    assert "tronquee" in motifs[0]
    assert str(MAX_TOKENS_CHAPITRE) in motifs[0]


def test_le_motif_dit_quoi_faire() -> None:
    """Un motif qui ne dit pas quoi corriger fait perdre le temps qu'il gagne.

    Six tentatives ont été passées à chercher un défaut de schéma inexistant.
    Le motif nomme donc explicitement les deux issues possibles.
    """
    motif = motif_de_troncature("max_tokens", MAX_TOKENS_CHAPITRE)[0]

    assert "borne de sortie" in motif
    assert "cible editoriale" in motif


@pytest.mark.parametrize("stop_reason", ["end_turn", "tool_use", "stop_sequence", ""])
def test_une_reponse_terminee_ne_declenche_rien(stop_reason: str) -> None:
    """Contre-épreuve : on n'a pas remplacé un motif faux par un autre.

    Si la réponse s'est terminée normalement et qu'il manque quand même des
    champs, c'est bien le contrat qui est rompu — et la validation du schéma
    doit reprendre la main, avec son propre motif.
    """
    assert motif_de_troncature(stop_reason, MAX_TOKENS_CHAPITRE) == []


def test_la_borne_laisse_de_la_place_aux_chapitres_mesures() -> None:
    """Les voisins du chapitre 19 consommaient 5 400 à 6 400 jetons.

    Une borne à 8 192 les laissait passer de justesse et coupait le suivant. Ce
    test n'invente pas un seuil : il exige que la borne dépasse nettement la
    consommation OBSERVÉE, faute de quoi le défaut reviendra au prochain
    chapitre un peu plus long.
    """
    assert MAX_TOKENS_CHAPITRE >= CONSOMMATION_OBSERVEE * 2


def test_la_borne_reste_sous_le_seuil_du_flux() -> None:
    """Contre-épreuve : on ne règle pas le problème en la poussant à l'infini.

    Au-delà d'environ 16 000 jetons, un appel NON diffusé en flux risque
    d'expirer avant de rendre sa réponse — et ce client n'utilise pas le flux.
    Relever la borne sans cette limite échangerait une troncature contre un
    délai dépassé, ce qui serait pire : l'appel serait facturé sans rien rendre.
    """
    assert MAX_TOKENS_CHAPITRE <= 16000
