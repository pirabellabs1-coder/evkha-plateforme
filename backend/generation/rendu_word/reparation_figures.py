"""Une figure impossible est RÉPARÉE avec ses propres données, quand elles le permettent.

## Le défaut mesuré

Stratégie Zenitek `a678b10a`, 13/09/2026 : **29 figures demandées, 6 dessinées**.
Les 23 autres étaient imprimées en tableau — l'information restait, le dessin
disparaissait. Et le catalogue fermé du prompt n'y changeait rien : le modèle
redemandait les mêmes combinaisons impossibles, pour les mêmes motifs.

    unités hétérogènes : %, EUR, unite            9 fois
    le radar / les jauges exigent des notes        6 fois
    un seul chiffre                                4 fois
    une frise sans date                            4 fois

Les deux premières familles ne sont pas des erreurs de FOND. Le modèle choisit
des données qui vont ensemble dans son raisonnement — un chiffre d'affaires, un
nombre d'abonnés, un taux de marge — et le moteur, à raison, refuse de les
tracer sur un même axe. Mais dans ce lot, deux montants ou deux effectifs
peuvent souvent former une figure juste.

## Ce que fait la réparation

Elle cherche, PARMI LES DONNÉES DEMANDÉES, le plus grand groupe de même nature
(au moins deux), et le fait juger par `resoudre` — le moteur qui dessine, pas
une seconde description de ses règles (règle 5) :

- d'abord sous le type demandé, s'il n'exige ni notes ni parts d'un tout ;
- sinon en barres, la forme qui montre les valeurs telles qu'elles sont.

Les données écartées ne sont pas perdues : l'assemblage les imprime en tableau
sous la figure.

## Ce qu'elle ne fait pas

- Elle n'INVENTE aucune donnée : un seul chiffre reste un seul chiffre.
- Elle ne répare pas une forme qui exige ce que les données n'ont pas : une
  frise sans dates, une matrice sans coordonnées, une carte de chaleur, une
  pyramide des âges. Les tracer en barres ferait mentir leur titre.
- Elle ne se fait pas passer pour le modèle : une figure réparée est comptée à
  part (`graphiques_repares`), jamais parmi celles qu'il a obtenues.

## Pourquoi au rendu, et pas dans le prompt ou le schéma

Une consigne ou une contrainte de schéma se VÉRIFIE sur une génération réelle.
Il n'y en aura plus (décision du client, 13/09/2026). La réparation, elle, se
mesure sur les chapitres déjà écrits : le dossier `a678b10a` se re-rend avec ce
code, à zéro centime (`/api/dashboard/jobs/<id>/mesure/`).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..socle.schema import DonneeSocle, Socle, valeur_en_unites_de_base
from .donnees_graphiques import (
    RAPPORT_D_ECHELLE_MAX,
    Resolution,
    _famille,
    radical_de,
    resoudre,
)

#: Formes dont les données exigées ne se déduisent pas d'un groupe de valeurs.
#: Les dessiner autrement ferait mentir leur titre.
_FORMES_NON_REPARABLES = frozenset({
    "chronologie", "matrice_positionnement", "carte_chaleur", "pyramide_ages",
})

#: Formes réparées UNIQUEMENT en barres, qui montrent les valeurs telles
#: qu'elles sont.
#:
#: - `radar`, `jauges` exigent des notes que les données ne sont pas ;
#: - `camembert`, `anneau`, `barres_empilees`, `aires` représentent les PARTS
#:   D'UN TOUT, et `entonnoir` une suite d'étapes emboîtées. Tracées sur une
#:   partie seulement des données demandées, elles inventent des parts et un
#:   total qui n'existent nulle part : un anneau « segment A, segment B,
#:   autres » réparé sans « autres » affichait 57 % / 43 % et un total de
#:   700 000 € — des chiffres absents du dossier. Relecture du 13/09/2026 ;
#:   `_scalaires` appelle ce défaut « la pire forme d'erreur » (dossier
#:   `f8a29b66`).
_FORMES_REPAREES_EN_BARRES = frozenset({
    "radar", "jauges",
    "camembert", "anneau", "barres_empilees", "aires", "entonnoir",
})

_FORME_NEUTRE = "barres"
_DONNEES_MIN = 2


@dataclass(frozen=True)
class FigureReparee:
    resolution: Resolution
    #: Les identifiants effectivement tracés.
    identifiants: tuple[str, ...]
    #: Ceux de la demande laissés hors de la figure — à imprimer en tableau.
    ecartes: tuple[str, ...]


def _groupes_de_meme_nature(socle: Socle, identifiants: Sequence[str]) -> list[list[str]]:
    """Les identifiants présents dans le socle, groupés par nature, plus grands d'abord.

    Puis, dans chaque nature, par ORDRE DE GRANDEUR : un marché en milliards
    et deux chiffres d'affaires en milliers d'euros sont tous des euros, mais
    la règle du client du 30/09/2026 (« rapport max/min inférieur à 1 000 »)
    refuse de les poser sur un même axe. Sans ce découpage, la réparation
    reproposait le groupe entier, que `resoudre` refusait à nouveau : la
    figure partait en tableau alors que les deux chiffres d'affaires se
    dessinaient.
    """
    groupes: dict[str, list[str]] = {}
    for identifiant in dict.fromkeys(identifiants):
        donnee = socle.donnee(identifiant)
        if donnee is None:
            continue
        famille = _famille(donnee)
        cle = f"famille:{famille}" if famille is not None else f"unite:{donnee.unite}"
        groupes.setdefault(cle, []).append(identifiant)
    return sorted(
        (
            paquet
            for groupe in groupes.values()
            for paquet in par_ordre_de_grandeur(socle, groupe)
            if len(paquet) >= _DONNEES_MIN
        ),
        key=len,
        reverse=True,
    )


def _en_base(donnee: DonneeSocle) -> float:
    """La valeur à l'unité de base de sa devise : 2 MdEUR et 300 kEUR se comparent."""
    convertie = valeur_en_unites_de_base(donnee.valeur, donnee.unite)
    return abs(convertie[0] if convertie is not None else donnee.valeur)


def par_ordre_de_grandeur(socle: Socle, groupe: Sequence[str]) -> list[list[str]]:
    """Le groupe découpé en paquets dont le rapport max/min reste sous le plafond.

    Ce sont les SÉRIES qui se comparent, comme dans les résolveurs
    (`donnees_graphiques.ecart_d_echelle_des_series`) : les exercices d'une
    même trajectoire (`tresorerie_fin_an1..3`, de 500 € à 70 000 €) restent
    ensemble, chacune pesant sa plus grande valeur. Découpée point par point,
    la trajectoire perdait son premier exercice ici alors que `resoudre` la
    dessinait entière — deux lectures d'une même règle (revue du 30/09/2026).

    Les séries sont parcourues de la plus petite à la plus grande ; un paquet
    se ferme dès qu'une série atteint mille fois la plus petite (non nulle) du
    paquet. Chaque paquet garde l'ordre de la demande.
    """
    series: dict[str, list[str]] = {}
    echelles: dict[str, float] = {}
    for identifiant in groupe:
        donnee = socle.donnee(identifiant)
        if donnee is None:
            continue
        radical = radical_de(identifiant)
        series.setdefault(radical, []).append(identifiant)
        echelles[radical] = max(echelles.get(radical, 0.0), _en_base(donnee))
    paquets: list[list[str]] = [[]]
    plancher = 0.0
    for radical in sorted(echelles, key=echelles.__getitem__):
        echelle = echelles[radical]
        if echelle and plancher and echelle / plancher >= RAPPORT_D_ECHELLE_MAX:
            paquets.append([])
            plancher = 0.0
        paquets[-1].extend(series[radical])
        if echelle and not plancher:
            plancher = echelle
    rang = {identifiant: place for place, identifiant in enumerate(groupe)}
    return [sorted(paquet, key=rang.__getitem__) for paquet in paquets if paquet]


def pourquoi_irreparable(socle: Socle, type_demande: str, identifiants: Sequence[str]) -> str:
    """La raison pour laquelle `reparer_la_figure` rend `None` — pour la mesure.

    Sans elle, le rapport ne gardait que le motif de la figure DEMANDÉE
    (« unités hétérogènes ») et jamais celui de la réparation : 188 figures
    perdues sur les stratégies du corpus, et aucun moyen de savoir laquelle des
    deux étapes refusait (14/09/2026).
    """
    if type_demande in _FORMES_NON_REPARABLES:
        return f"forme `{type_demande}` non réparable"
    groupes = _groupes_de_meme_nature(socle, identifiants)
    if not groupes:
        return "aucun groupe de deux données de même nature dans la demande"
    formes = (
        [_FORME_NEUTRE]
        if type_demande in _FORMES_REPAREES_EN_BARRES
        else list(dict.fromkeys([type_demande, _FORME_NEUTRE]))
    )
    motifs = [
        f"{forme} sur {', '.join(groupe)} : {resoudre(socle, forme, groupe).motif}"
        for groupe in groupes for forme in formes
    ]
    return " | ".join(motifs)


def reparer_la_figure(
    socle: Socle, type_demande: str, identifiants: Sequence[str],
) -> FigureReparee | None:
    """La figure valide la plus proche de la demande, ou `None`."""
    if type_demande in _FORMES_NON_REPARABLES:
        return None
    formes = (
        [_FORME_NEUTRE]
        if type_demande in _FORMES_REPAREES_EN_BARRES
        else list(dict.fromkeys([type_demande, _FORME_NEUTRE]))
    )
    for groupe in _groupes_de_meme_nature(socle, identifiants):
        for forme in formes:
            resolution = resoudre(socle, forme, groupe)
            if resolution.retenu:
                traces = set(groupe)
                return FigureReparee(
                    resolution=resolution,
                    identifiants=tuple(groupe),
                    ecartes=tuple(
                        i for i in dict.fromkeys(identifiants) if i not in traces
                    ),
                )
    return None
