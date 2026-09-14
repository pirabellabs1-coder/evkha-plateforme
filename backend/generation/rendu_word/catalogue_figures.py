"""Les figures RÉELLEMENT réalisables avec le socle de ce dossier.

## Le défaut, mesuré sur un livrable réel

Stratégie Zenitek, reprise `b098ded3` du 12/09/2026 : **31 figures demandées,
31 refusées, zéro rendue**. Le document est parti sans un seul graphique.

Aucune de ces demandes n'était absurde ; elles étaient simplement
irréalisables, et toujours pour les mêmes deux raisons :

    « unités hétérogènes : EUR, unite »     — 14 fois
    « le radar exige des notes »            — 9 fois
    « un radar exige au moins trois axes »  — 3 fois
    « un seul chiffre »                     — 2 fois

Le modèle demandait un entonnoir mêlant un nombre de prospects et un chiffre
d'affaires, ou un radar sur des montants. Il ne pouvait pas faire mieux : on
lui donnait la liste des identifiants du socle avec leurs unités, et la charge
de deviner quelles combinaisons le moteur de rendu accepterait.

## Ce que fait ce module

Il ÉNUMÈRE, pour un socle donné, les figures que le rendu accepte — en les
faisant résoudre par le moteur de rendu lui-même. Ce n'est donc pas une seconde
description des règles, qui divergerait le jour où l'une change (règle 5) :
c'est la même fonction, `resoudre`, appelée d'avance.

Le prompt du chapitre porte ensuite cette liste : le modèle CHOISIT dans un
catalogue au lieu d'inventer. Ce qu'il choisit se dessine, par construction.

## Ce que ce module ne fait pas

Il ne choisit pas à la place du modèle — quelle figure sert quel propos reste
une décision éditoriale. Et il ne promet pas l'exhaustivité : il propose les
combinaisons les plus utiles, pas toutes celles qui existent, dont le nombre
explose avec la taille du socle.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .donnees_graphiques import resoudre

if TYPE_CHECKING:
    from ..socle.schema import Socle

#: Les formes qui se contentent de valeurs scalaires comparables. L'ordre est
#: celui de la préférence de lecture : une comparaison se lit mieux en barres
#: qu'en camembert, une part d'un tout mieux en anneau.
_FORMES_SCALAIRES = (
    "barres", "barres_horizontales", "anneau", "camembert", "entonnoir", "jauges",
)

#: Le rang final d'une série : `prix_offre_2`, `ca_objectif_an3`.
_RACINE_DE_SERIE = re.compile(r"_(?:an)?\d+$")

#: Les formes qu'une SÉRIE admet, selon ce qu'elle est. La rotation des formes
#: ignorait le sens : la trajectoire du chiffre d'affaires année par année
#: sortait en camembert — des parts d'un total qui n'existe pas (14/09/2026).
#:
#: - une trajectoire (`_an1`, `_an2`…) se lit dans le temps ;
#: - les composantes d'un total (charges par poste, chiffre d'affaires par
#:   activité, clients par segment) admettent les parts ;
#: - toute autre série (prix des formules, tarifs) se compare, sans parts.
_FORMES_DE_PARTS = frozenset({"anneau", "camembert"})
_FORMES_TRAJECTOIRE = ("courbes", "barres")
_FORMES_COMPOSANTES = ("anneau", "barres_horizontales", "barres")
_FORMES_COMPARAISON = ("barres", "barres_horizontales")
_RACINES_DE_COMPOSANTES = re.compile(r"^(?:charge_poste|ca_activite|clients_segment)$")


def _formes_de_la_serie(identifiants: tuple[str, ...]) -> tuple[str, ...] | None:
    """Les formes admises pour ce groupe s'il est une série ; `None` sinon."""
    racines = {_RACINE_DE_SERIE.sub("", i) for i in identifiants}
    if len(racines) != 1 or next(iter(racines)) == identifiants[0]:
        return None
    if all(re.search(r"_an\d+$", i) for i in identifiants):
        return _FORMES_TRAJECTOIRE
    if _RACINES_DE_COMPOSANTES.match(next(iter(racines))):
        return _FORMES_COMPOSANTES
    return _FORMES_COMPARAISON

#: Au-delà, les étiquettes se chevauchent (mesuré sur le dossier `90cbb3d9`).
_DONNEES_PAR_FIGURE_MAX = 4

#: En deçà, ce n'est pas une figure : « un graphique à une barre n'apprend rien ».
_DONNEES_PAR_FIGURE_MIN = 2

#: Combien de propositions le catalogue porte au plus. Un socle de quarante
#: données produit des milliers de combinaisons ; un prompt n'a pas à les
#: porter, et un modèle noyé choisit moins bien qu'un modèle guidé.
MAX_PROPOSITIONS = 24


@dataclass(frozen=True)
class Proposition:
    """Une figure que le moteur de rendu accepte, avec les données qui la portent."""

    type_graphique: str
    identifiants: tuple[str, ...]
    #: L'unité commune, telle que le rendu l'affichera. Elle dit au modèle ce
    #: que la figure compare — des euros, des pourcentages, des effectifs.
    unite: str

    def ligne(self) -> str:
        return (
            f"- `{self.type_graphique}` : {', '.join(self.identifiants)}"
            f" — en {self.unite}" if self.unite else
            f"- `{self.type_graphique}` : {', '.join(self.identifiants)}"
        )


def _groupes_compatibles(socle: Socle) -> list[tuple[str, ...]]:
    """Les groupes d'identifiants qui partagent une unité comparable.

    Des groupes DISTINCTS, jamais les sous-ensembles les uns des autres :
    proposer « ca_actuel, ca_cible, panier » puis « ca_actuel, ca_cible » puis
    « ca_actuel, panier » remplit le catalogue de la même figure et noie les
    autres natures de données. Un socle riche en euros écraserait alors les
    pourcentages et les effectifs.
    """
    # Une SÉRIE d'abord — `prix_offre_1`, `prix_offre_2`… ou `ca_an1`, `ca_an2` :
    # ses éléments se comparent entre eux. Mêlés au reste de leur unité, les
    # prix de trois formules (12, 19, 29 €) partaient sur le même axe qu'un
    # chiffre d'affaires de 120 000 € — une figure où ils ne se voyaient plus
    # (14/09/2026).
    par_serie: dict[tuple[str, str], list[str]] = {}
    for donnee in socle.donnees:
        racine = _RACINE_DE_SERIE.sub("", donnee.id)
        if racine != donnee.id:
            par_serie.setdefault((str(donnee.unite), racine), []).append(donnee.id)
    en_serie = {
        identifiant
        for identifiants in par_serie.values() if len(identifiants) >= _DONNEES_PAR_FIGURE_MIN
        for identifiant in identifiants
    }

    par_unite: dict[str, list[str]] = {}
    for donnee in socle.donnees:
        if donnee.id not in en_serie:
            par_unite.setdefault(str(donnee.unite), []).append(donnee.id)

    groupes: list[tuple[str, ...]] = []
    for identifiants in [*par_serie.values(), *par_unite.values()]:
        if len(identifiants) < _DONNEES_PAR_FIGURE_MIN:
            continue
        # Par paquets de quatre : un socle de dix montants donne deux figures
        # lisibles plutôt qu'une figure illisible ou deux cents variantes.
        for debut in range(0, len(identifiants), _DONNEES_PAR_FIGURE_MAX):
            paquet = tuple(identifiants[debut : debut + _DONNEES_PAR_FIGURE_MAX])
            if len(paquet) >= _DONNEES_PAR_FIGURE_MIN:
                groupes.append(paquet)
    return groupes


def figures_possibles(socle: Socle, *, limite: int = MAX_PROPOSITIONS) -> list[Proposition]:
    """Les figures que ce socle peut réellement alimenter.

    Chaque proposition est VÉRIFIÉE par le moteur de rendu : ce qui figure ici
    se dessinera. C'est la seule garantie qui vaille — une liste écrite à la
    main aurait vieilli à la première règle changée.
    """
    propositions: list[Proposition] = []

    # Le radar d'abord : c'est la figure la plus demandée et la plus refusée,
    # et quand il est possible il structure tout un chapitre.
    for groupe in _groupes_radar(socle):
        resolution = resoudre(socle, "radar", list(groupe))
        if resolution.retenu:
            propositions.append(Proposition(
                "radar", tuple(groupe), _unite_commune(socle, groupe)
            ))

    # Puis les scalaires. La FORME tourne d'un groupe à l'autre : quatre
    # entonnoirs de suite tiendraient le compte en trahissant la demande —
    # « les graphes ne seront pas toujours les mêmes » (cliente).
    for rang, groupe in enumerate(_groupes_compatibles(socle)):
        formes_de_serie = _formes_de_la_serie(groupe)
        # Un regroupement LIBRE — des montants qui partagent une unité sans
        # former un tout — n'admet pas les parts : « chiffre d'affaires, panier
        # moyen » en camembert inventait un total qui n'existe nulle part.
        formes = formes_de_serie or tuple(
            forme
            for decalage in range(len(_FORMES_SCALAIRES))
            if (forme := _FORMES_SCALAIRES[(rang + decalage) % len(_FORMES_SCALAIRES)])
            not in _FORMES_DE_PARTS
        )
        for forme in formes:
            resolution = resoudre(socle, forme, list(groupe))
            if resolution.retenu:
                propositions.append(Proposition(
                    resolution.type_graphique or forme,
                    tuple(groupe),
                    _unite_commune(socle, groupe),
                ))
                break
        if len(propositions) >= limite:
            break
    return propositions


def _groupes_radar(socle: Socle) -> list[tuple[str, ...]]:
    """Le radar se nourrit d'une grille de notation, jamais de montants."""
    if not getattr(socle, "grille_notation", None):
        return []
    identifiants = [critere.code for critere in socle.grille_notation]
    if len(identifiants) < 3:
        return []
    return [tuple(identifiants[:6])]


def _unite_commune(socle: Socle, identifiants: tuple[str, ...]) -> str:
    unites = {
        donnee.unite for donnee in socle.donnees if donnee.id in identifiants
    }
    return unites.pop() if len(unites) == 1 else ""


def bloc_figures_possibles(socle: Socle) -> str:
    """Le catalogue, écrit pour le prompt du chapitre. Vide si rien n'est possible.

    Un catalogue vide ne s'écrit pas : annoncer « figures réalisables : aucune »
    ferait écrire au modèle que le document n'en aura pas, ce qui n'a rien à
    faire dans un livrable.
    """
    propositions = figures_possibles(socle)
    if not propositions:
        return ""
    lignes = "\n".join(
        f"- `{p.type_graphique}` : {', '.join(p.identifiants)}"
        + (f" (en {p.unite})" if p.unite else "")
        for p in propositions
    )
    return (
        "FIGURES RÉALISABLES AVEC CE SOCLE — la liste est CLOSE.\n"
        "Chaque ligne a été vérifiée par le moteur qui dessine : une figure "
        "prise ici SERA dessinée. Une combinaison inventée ailleurs ne se "
        "dessine pas, et disparaît du document sans que le lecteur le sache.\n"
        f"{lignes}\n"
        "\n"
        "Règles qui expliquent cette liste, et qu'aucune demande ne contourne :\n"
        "- une figure compare des grandeurs de MÊME NATURE : des euros avec "
        "des euros, des pourcentages avec des pourcentages. Mêler un montant "
        "et un effectif ne se dessine pas ;\n"
        "- il faut au moins deux valeurs : une seule barre n'apprend rien ;\n"
        "- un radar exige une grille de NOTES sur au moins trois critères, "
        "jamais des montants ;\n"
        "- si aucune ligne ne sert ton propos, n'en demande pas : écris le "
        "tableau qui le porte. Un tableau juste vaut mieux qu'un dessin "
        "impossible."
    )
