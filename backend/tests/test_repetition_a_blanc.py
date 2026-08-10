"""La chaîne entière tient, sans un appel d'API — pour les quatre livrables.

## Ce que ce test attrape, et ce qu'il a coûté de ne pas l'avoir

Le 10/08/2026, trois défauts ont tué ou bloqué trois générations réelles
successives, pour 5,22 € d'essais :

  - la validation ignorait les codes de la grille que la consigne ordonnait
    de citer — chaque chapitre refusé, rejoué, refusé (`d326557e`) ;
  - le contrôle de la grille refusait un socle réparable et l'étude mourait
    avant son premier chapitre (`6a44baff`) ;
  - le gate exigeait un tableau HTML que `_SYSTEME` interdit dans le même
    prompt (`6cb0fab3`).

Trois contradictions INTERNES. Aucune n'avait besoin d'un vrai modèle pour
être vue — il suffisait de JOUER la chaîne. Personne ne la jouait : les tests
touchaient chacun un morceau, jamais le tout (règle 9 — ce que les contrôles
ne regardent pas est exactement là où le défaut vit).

## Ce que ce test ne prouve pas

Le contenu d'un vrai modèle (règle 7). Les échecs de gate portant sur le
contenu de la doublure — cardinaux, verticales, valeurs — sont LÉGITIMES ici.
Ce qui est verrouillé : aucun chapitre refusé, la chaîne va au bout, et aucun
motif de gate n'exige un format que le système interdit.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType
from generation.repetition import jouer_a_blanc


@pytest.mark.django_db
@pytest.mark.parametrize("livrable", list(DeliverableType.values))
def test_la_chaine_du_livrable_tient_sans_api(livrable: str) -> None:
    rapport = jouer_a_blanc(livrable)

    assert rapport.saine, (
        f"Défauts internes sur {livrable} :\n- " + "\n- ".join(rapport.defauts_internes)
    )
    assert rapport.chapitres_ok == rapport.chapitres_total, (
        f"{rapport.chapitres_total - rapport.chapitres_ok} chapitre(s) non "
        f"produit(s) sur {livrable}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("livrable", list(DeliverableType.values))
def test_le_gate_passe_entier_sur_la_doublure(livrable: str) -> None:
    """Le niveau atteint le 10/08/2026, verrouillé pour ne plus redescendre.

    Une doublure CONFORME — sous-titres, blocs de recul, annexes, statuts,
    visuels, sources tracées, rémunération chiffrée — traverse TOUS les
    contrôles du gate. Ce test tient donc les trois bouts à la fois :

      - un contrôle ajouté sans que la consigne et la doublure le sachent
        casse ici, le jour même, à zéro centime — plus jamais en payant une
        génération réelle (`6cb0fab3` a payé pour découvrir la matrice) ;
      - un contrôle aveugle au contrat structuré (chercher du HTML que le
        moteur ne produit pas) casse ici aussi ;
      - une doublure qui régresse — un chapitre qui perd sa structure — ne
        peut plus se faire passer pour saine.

    Il a fallu quatre itérations pour l'atteindre : moteur hérité joué par
    erreur, piliers comptés comme une liste, prose coupée sans point,
    sources diluées par les encadrés. Chacune était une leçon sur ce que le
    gate attend VRAIMENT d'un document — la doublure est désormais le
    document minimal qui satisfait le cahier des charges mécanisable.
    """
    rapport = jouer_a_blanc(livrable)

    assert rapport.saine, "\n- ".join(["défauts internes :", *rapport.defauts_internes])
    assert rapport.gate_passe, (
        f"Le gate bloque {livrable} sur la doublure conforme :\n- "
        + "\n- ".join(rapport.gate_echecs)
    )


@pytest.mark.django_db
@pytest.mark.parametrize("livrable", list(DeliverableType.values))
def test_aucun_motif_de_gate_n_exige_un_format_interdit(livrable: str) -> None:
    """La contradiction exacte de `6cb0fab3`, généralisée (règle 4).

    Un contrôle qui exige « HTML », « CSV » ou « Markdown » dans le texte
    exige ce que `_SYSTEME` interdit : le modèle ne peut pas gagner, quelle
    que soit sa réponse. Ce test échoue sur le code d'avant — le gate EC
    répondait « Le prompt exige explicitement un tableau HTML ».
    """
    rapport = jouer_a_blanc(livrable)

    interdits = ("HTML", "CSV", "Markdown")
    contradictoires = [
        echec
        for echec in rapport.gate_echecs
        if any(mot in echec for mot in interdits)
    ]
    assert contradictoires == [], (
        f"Le gate de {livrable} exige un format que le système interdit :\n- "
        + "\n- ".join(contradictoires)
    )
