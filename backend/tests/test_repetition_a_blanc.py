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
