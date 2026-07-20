"""Phase 19 — La cible de mots doit etre TENUE, pas souhaitee.

Mesure sur le premier vrai BP SYNAPSES (juillet 2026) :

    cible du pipeline : 25 900 mots (max_words, par section quand chunked)
    produit           : 33 311 mots  (+29 %)
    previsionnel      : 2 800 vises -> 5 639 produits (+101 %)
    BP manuel de la cliente : 22 074 mots

Le depassement n'est pas cosmetique. Gamma borne une carte a ~500 mots et 60
cartes au total : a 33 000 mots le document ne rentre pas, Gamma le comprime et
74 % du texte disparait. A la cible, il passe (~52 cartes). Le meme defaut
explique la limite de 80 pages depassee et une part du cout (les tokens de
sortie sont le poste le plus cher).

Deux causes, deux verrous testes ici :
1. le prompt DEMANDAIT le depassement (« budget indicatif », « c'est
   acceptable », « la completude prime sur toute autre contrainte ») ;
2. rien ne l'empechait physiquement : 8 192 tokens par appel (~5 100 mots) et
   jusqu'a 3 appels enchaines, pour une cible de 900 mots.
"""
from __future__ import annotations

from generation.cost import tokens_pour_cible
from integrations.claude import _DEFAULT_MAX_TOKENS


def test_le_plafond_est_derive_de_la_cible() -> None:
    """Une cible de 900 mots ne doit pas ouvrir 8 192 tokens de sortie."""
    plafond = tokens_pour_cible(900)

    assert plafond < _DEFAULT_MAX_TOKENS
    # ~900 mots + marge de balisage, pas 5 100.
    assert 1500 <= plafond <= 2500


def test_le_plafond_croit_avec_la_cible() -> None:
    """Un chapitre dense garde la place dont il a besoin."""
    assert tokens_pour_cible(1600) > tokens_pour_cible(900)


def test_pas_de_cible_pas_de_plafond() -> None:
    """Sans cible editoriale, on ne contraint rien (0 = pas de borne)."""
    assert tokens_pour_cible(0) == 0


def test_le_plafond_ne_descend_jamais_sous_le_plancher() -> None:
    """Contre-epreuve : une borne trop basse couperait en pleine phrase.

    Une troncature declenche un retry, donc coute PLUS cher que la place
    gagnee. Le plancher protege de ce faux gain.
    """
    assert tokens_pour_cible(50) >= 900


def test_la_marge_absorbe_le_balisage() -> None:
    """Un chapitre a tableaux consomme des tokens qui ne sont pas du texte.

    Le plafond doit laisser de quoi ecrire la cible EN ENTIER, sinon on
    fabrique des troncatures. ~1,6 token par mot francais, plus la marge.
    """
    for cible in (900, 1200, 1400, 1600):
        mots_possibles = tokens_pour_cible(cible) / 1.6
        assert mots_possibles > cible, f"cible {cible} intenable"
        # Mais pas au point de rendre la borne inutile.
        assert mots_possibles < cible * 1.6, f"cible {cible} trop laxiste"
