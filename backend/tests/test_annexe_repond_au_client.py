"""L'annexe REPOND au client ; elle ne classe pas ses questions sans reponse.

## Le defaut, releve par la cliente le 18/08/2026

Etude de concurrence `743e6a2b` — celle qu'elle venait de valider par ailleurs.
Son chapitre 8, le dernier qu'elle lit :

    | 8  | Non traitée | canaux d'acquisition des concurrents
    | 10 | Non traitée | pression des freelances, cadre reglementaire
    « Neuf demandes sur onze sont couvertes integralement »

Son mot : « pour le client, voir plusieurs "non traite" en fin d'etude est
assez frustrant ».

Elle l'avait deja dit le 09/08, autrement : « l'etude passe son temps a dire
donnees a definir, a verifier — je n'aime pas cela, j'aime apporter de vraies
reponses. »

## La cause

Le prompt PRESCRIVAIT ce vocabulaire : « Attribue a chaque demande un statut
unique parmi trois. Traitee / Partiellement traitee / Non traitee ». Le modele
obeissait. Le defaut n'etait pas dans le document, il etait dans la consigne.

## La regle 10 du depot : le correctif vaut pour TOUS les livrables

Le business plan portait la meme instruction en une ligne. La strategie, elle,
faisait deja ce qu'il faut — « fournis une reponse synthetique » — et sert de
modele.
"""
from __future__ import annotations

import pytest

from generation.prompt_library import prompt_instruction

ANNEXES = ["ec.08.annexe_brief", "bp.20.annexes"]


@pytest.mark.parametrize("cle", ANNEXES)
def test_l_annexe_ne_prescrit_plus_de_statut(cle: str) -> None:
    """Echoue sur le code d'avant : le prompt imposait les trois statuts.

    On verifie que le vocabulaire n'est plus PRESCRIT. Il subsiste sous forme
    d'interdiction — « n'ecris jamais qu'une demande est non traitee » — et
    c'est exactement ce qu'on veut.
    """
    texte = prompt_instruction(cle).lower()
    assert "statut unique" not in texte
    assert "traitee / partiellement / non traitee" not in texte
    # Le mot ne subsiste que precede d'une interdiction.
    for interdit in ("non traitee", "partiellement traitee"):
        if interdit in texte:
            avant = texte.split(interdit)[0]
            assert "jamais" in avant[-220:], (
                f"« {interdit} » apparait sans interdiction dans {cle}"
            )


@pytest.mark.parametrize("cle", ANNEXES)
def test_l_annexe_exige_une_reponse_et_une_demarche(cle: str) -> None:
    """Ce qui remplace le statut : ce qui est etabli, ce qui manque, comment l'obtenir."""
    texte = prompt_instruction(cle).lower()
    assert "repond" in texte or "réponds" in texte
    assert "demarche" in texte
    assert "manque" in texte


def test_la_synthese_ne_compte_plus_les_demandes_par_statut() -> None:
    """« Neuf demandes sur onze couvertes » est un bulletin de notes.

    Echoue sur le code d'avant : la synthese demandait explicitement « nombre
    de demandes traitees integralement, mention des demandes partiellement
    traitees ou non traitees ».
    """
    texte = prompt_instruction("ec.08.annexe_brief").lower()
    assert "nombre de demandes traitees" not in texte
    assert "ne compte pas les demandes par statut" in texte


def test_la_strategie_reste_le_modele() -> None:
    """Contre-epreuve : la strategie repondait deja, on n'y touche pas."""
    texte = prompt_instruction("str.19.annexe_brief").lower()
    assert "reponse synthetique" in texte
    assert "non traitee" not in texte


def test_le_socle_exige_de_chercher_l_edition_la_plus_recente() -> None:
    """« je vois 2024, or je sais que 2025 existe et est publie ».

    Echoue sur le code d'avant : la consigne disait « les plus recents
    disponibles », un vœu que rien n'obligeait a verifier.
    """
    from generation.socle.prompt import construire_prompt_socle

    texte = construire_prompt_socle(
        deliverable_type="market_study",
        variables={"SECTEUR": "conseil", "PAYS": "France"},
        brief_recherche="",
    )
    assert "édition la plus récente" in texte
    assert "Le premier résultat trouvé n'est pas le plus récent" in texte
    assert "publication la plus récente disponible" in texte
