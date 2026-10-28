"""« l'atelier passe de 85 € à 94 € et l'échappée de 390 € à 429 € » n'est pas une plage.

## Le motif faux

Business plan `acd30be3` (28/10/2026) : `qa_status: blocked`, et un seul motif
de gate — `fourchette_interdite` sur le chapitre 13. Son extrait :

    « ÉCLORE revalorise donc ses prix de 10 % en 2028 : l'atelier passe de
      85 € à 94 € TTC et l'échappée de 390 € à 429 € TTC. »

C'est une ÉVOLUTION de prix entre deux exercices, pas une fourchette. Et le
détecteur le sait déjà : la garde `_MOUVEMENT_AVANT` exempte correctement le
premier couple, 85 → 94, parce que « passe de » le précède.

## Pourquoi le second couple échouait

La garde regarde 30 caractères **sans chiffre** avant le « de ». Elle ne peut
donc jamais franchir les nombres du premier membre : dans « passe de 85 € à
94 € TTC et l'échappée de », le verbe est hors d'atteinte. Or il n'est écrit
qu'une fois et gouverne les deux membres — c'est une ellipse.

Mesuré avant d'écrire la garde : la phrase entière ne fait détecter que
390 → 429, et le même membre doté de son propre verbe (« l'échappée passe de
390 € à 429 € ») n'est pas détecté du tout.

## Ce qui sépare l'ellipse d'une vraie plage

Le membre elliptique est un GROUPE NOMINAL NU — « et l'échappée de ». Une
vraie plage coordonnée porte SON verbe — « et le tarif varie de 39 € à 45 € »
— et gouverne elle-même son « de ».

Ce second cas est la contre-épreuve qui compte, et il a été vérifié sur le
détecteur AVANT d'écrire la garde : élargir la fenêtre sans ce discriminant
l'aurait exempté à tort, c'est-à-dire aurait fabriqué un défaut en réparant un
motif faux.
"""
from __future__ import annotations

import pytest

from generation.checks_evangeline import detecter_fourchettes

#: Les caractères du document réel : apostrophe typographique et fine
#: insécable. Les remplacer par leurs équivalents ASCII change le découpage en
#: mots — « l'échappée » devient deux mots — et fait échouer le test sur un
#: code qui marche. C'est arrivé en écrivant celui-ci.
APOSTROPHE = "’"
FINE = " "
EURO = "€"


def _euros(montant: str) -> str:
    return f"{montant}{FINE}{EURO}"


#: Recopiée de l'extrait rendu par `jobs/acd30be3-…/mesure/`.
PHRASE_REELLE = (
    f"ÉCLORE revalorise donc ses prix de 10 % en 2028 : l{APOSTROPHE}atelier "
    f"passe de {_euros('85')} à {_euros('94')} TTC et l{APOSTROPHE}échappée "
    f"de {_euros('390')} à {_euros('429')} TTC."
)


def _plages(texte: str, livrable: str = "business_plan") -> list[tuple[str, str]]:
    return [
        (f.borne_basse, f.borne_haute)
        for f in detecter_fourchettes(13, texte, deliverable_type=livrable)
    ]


def test_une_evolution_de_prix_a_deux_membres_n_est_pas_signalee() -> None:
    """Le cas de `acd30be3`. Échoue sur le code d'avant, qui rendait 390 → 429."""
    assert _plages(PHRASE_REELLE) == []


def test_le_premier_membre_etait_deja_exempte() -> None:
    """La garde d'origine fonctionne : ce n'est pas elle qu'on remplace."""
    seul = (
        f"L{APOSTROPHE}atelier passe de {_euros('85')} à {_euros('94')} TTC."
    )

    assert _plages(seul) == []


def test_un_membre_coordonne_qui_porte_son_verbe_reste_une_plage() -> None:
    """LA contre-épreuve : sans elle, le correctif fabriquait un défaut.

    « varie de 39 € à 45 € » est une vraie fourchette. Elle est coordonnée à
    un mouvement, donc un élargissement naïf de la fenêtre l'aurait exemptée.
    """
    risque = (
        f"L{APOSTROPHE}atelier passe de {_euros('85')} à {_euros('94')} et le "
        f"tarif varie de {_euros('39')} à {_euros('45')}."
    )

    assert _plages(risque) == [("39", "45")]


@pytest.mark.parametrize(
    "texte",
    [
        "Le tarif varie de {bas} à {haut}.",
        "Le tarif se situe entre {bas} et {haut}.",
        "Le forfait va de {bas} à {haut} selon la formule.",
    ],
)
def test_les_vraies_fourchettes_restent_vues(texte: str) -> None:
    """CONTRE-ÉPREUVES : aucun mouvement dans la phrase, aucune exemption."""
    rendu = texte.format(bas=_euros("39"), haut=_euros("45"))

    assert _plages(rendu) == [("39", "45")]


def test_une_ellipse_sans_aucun_verbe_de_mouvement_reste_vue() -> None:
    """La garde exige LES DEUX : un mouvement dans la phrase, et l'ellipse.

    Sans le mouvement, « et l'échappée de 390 € à 429 € » n'a aucune raison
    d'être lu comme une évolution — et doit rester signalé.
    """
    sans_mouvement = (
        f"Deux formules coexistent : l{APOSTROPHE}atelier à {_euros('85')} et "
        f"l{APOSTROPHE}échappée de {_euros('390')} à {_euros('429')}."
    )

    assert _plages(sans_mouvement) == [("390", "429")]
