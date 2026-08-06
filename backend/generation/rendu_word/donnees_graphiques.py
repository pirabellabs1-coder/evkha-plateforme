"""Résolution d'un graphique déclaré par un chapitre contre le socle.

Un chapitre ne porte pas de valeurs : il porte le *type* de visuel qu'il veut
et les *identifiants* du socle qui doivent l'alimenter. C'est ici que les deux
se rencontrent, et c'est le seul endroit du système où une figure reçoit des
chiffres.

**Règle unique, et elle n'a pas d'exception : aucune valeur n'est fabriquée.**
Si le socle ne peut pas alimenter le type demandé, le graphique est abandonné
et le motif est enregistré. Il n'est jamais complété, jamais approché, jamais
rempli d'un ordre de grandeur plausible. Un graphique inventé est indétectable
à la lecture, contrairement à un graphique absent — c'est exactement le défaut
que la refonte doit supprimer.

Quand le type demandé n'est pas alimentable mais qu'un autre l'est avec les
mêmes données, le graphique est **converti** plutôt qu'abandonné : trois
montants demandés en courbes n'ont pas d'axe temporel, mais font des barres
parfaitement honnêtes.
"""
from __future__ import annotations

import re
import textwrap
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ..socle.referentiel import FamilleUnite
from ..socle.schema import (
    DonneeSocle,
    Socle,
    famille_de_l_unite,
    valeur_en_unites_de_base,
)

#: Types alimentés par une simple liste de valeurs scalaires.
_SCALAIRES = (
    "barres", "barres_horizontales", "camembert", "anneau", "entonnoir", "jauges"
)


@dataclass(frozen=True)
class Resolution:
    """Ce qu'on a pu faire de la demande du chapitre.

    `donnees` vide signifie abandon ; `motif` dit pourquoi, en clair, pour
    figurer dans le rapport d'assemblage. Un abandon silencieux serait un
    échec déguisé en succès (règle 1).
    """

    type_graphique: str = ""
    donnees: dict[str, Any] | None = None
    motif: str = ""
    #: Vrai si le type rendu diffère du type demandé par le chapitre.
    converti: bool = False

    @property
    def retenu(self) -> bool:
        return self.donnees is not None


#: Longueur au-delà de laquelle une étiquette de figure devient illisible.
#:
#: Mesurée, pas choisie. Première génération réelle complète (`90cbb3d9`,
#: 05/08/2026) : les deux graphiques du livrable portaient en abscisse
#: « Croissance annuelle estimée du marché mondial de la joaillerie, ordre de
#: grandeur sectoriel luxe/joaillerie » — 96 signes. Les deux étiquettes se
#: chevauchaient et débordaient de l'image.
ETIQUETTE_MAX = 34


def etiquette_de(donnee: DonneeSocle) -> str:
    """Nom COURT d'une donnée, pour l'axe d'une figure.

    Le `libelle` du socle est une définition : il doit lever toute ambiguïté sur
    ce que le chiffre mesure, donc il est long, et c'est très bien — il sert au
    modèle, aux contrôles et aux notes de source. Il ne peut simplement pas
    servir d'étiquette d'axe.

    La règle est générale, et pas une liste de cas (règle 4) : on garde le
    segment de tête — ce qui précède la première virgule, parenthèse ou tiret,
    qui porte toujours la nature de la grandeur — puis on borne. Un libellé
    déjà court traverse inchangé.

    Le nom n'est jamais remplacé par l'identifiant : `marche_mondial_croissance`
    est un repère de code, pas un mot que le lecteur d'une étude doit voir.

    **Ce qui dépasse est REPLIÉ, plus tronqué.** Le document validé écrit
    « Attractivité du / segment » et « Capacité de / preuve » sur deux lignes.
    Couper à « Marché parisien de la joaillerie… » fait perdre au lecteur
    précisément ce qui distingue cette barre de la suivante ; le repli garde
    tout, et matplotlib gère la hauteur.
    """
    tete = re.split(r"[,(—–:;]", donnee.libelle, maxsplit=1)[0].strip()
    tete = tete or donnee.libelle.strip()
    if len(tete) <= ETIQUETTE_MAX:
        return tete
    return "\n".join(textwrap.wrap(tete, ETIQUETTE_MAX, max_lines=2, placeholder="…"))


def _famille(donnee: DonneeSocle) -> FamilleUnite | None:
    """Famille d'unité, déduite de l'unité portée par la donnée.

    Déduite de l'unité et non lue au référentiel : le référentiel s'indexe par
    type de livrable, information que le socle chargé depuis la base ne porte
    plus. L'unité, elle, est toujours là.
    """
    return famille_de_l_unite(donnee.unite)


def _resoudre_ids(
    socle: Socle, identifiants: Sequence[str]
) -> tuple[list[DonneeSocle], str]:
    """Les données du socle correspondant aux identifiants, ou un motif d'échec."""
    trouvees, manquantes = [], []
    for identifiant in identifiants:
        donnee = socle.donnee(identifiant)
        if donnee is None:
            manquantes.append(identifiant)
        else:
            trouvees.append(donnee)
    if manquantes:
        return [], (
            "identifiants absents du socle : " + ", ".join(sorted(manquantes))
        )
    return trouvees, ""


#: Magnitudes d'affichage, de la plus grande à la plus petite. Le préfixe se
#: recolle à la devise (`Md` + `EUR`), comme `socle.schema.unites_monetaires`
#: les fabrique : la correspondance magnitude → facteur n'est pas redéclarée
#: ici (règle 5).
_MAGNITUDES_AFFICHAGE: tuple[tuple[str, float], ...] = (
    ("Md", 1e9), ("M", 1e6), ("k", 1e3), ("", 1.0),
)


def _harmoniser(
    donnees: Sequence[DonneeSocle],
) -> tuple[list[float], str] | None:
    """Valeurs comparables sur un même axe, et l'unité qui les porte.

    ## Ce que refusait la version d'avant, et qu'elle n'aurait pas dû

    Elle comparait les unités comme des CHAÎNES : `{"EUR", "MEUR", "MdEUR"}`
    faisait trois unités, donc « unités hétérogènes », donc figure abandonnée.
    Ce ne sont pas trois unités — c'est une monnaie à trois échelles.

    Mesuré sur la génération réelle `18ce3fca` du 05/08/2026, grâce à l'incident
    qui conserve désormais les motifs d'abandon : **12 figures sur 14 écartées,
    dont 11 pour « unités hétérogènes »**, et six d'entre elles listaient
    `EUR, MEUR, MdEUR` ou `MEUR, MdEUR`. Autrement dit, le moteur refusait de
    dessiner l'entonnoir TAM / SAM / SOM — la figure la plus attendue d'une
    étude de marché — parce qu'il ne savait pas que mille millions font un
    milliard.

    La conversion existait pourtant, complète, dans `socle.schema` :
    `valeur_en_unites_de_base` décompose `MdEUR` en magnitude et devise depuis
    le lot 1. Ce module ne l'appelait pas. C'est le défaut de la règle 8 —
    « intégré, testé… jamais exécuté » — sur une fonction et non sur un service.

    ## Ce qui reste refusé, et doit l'être

    Deux DEVISES différentes : sans taux de change, `MdEUR` et `MdUSD` sur un
    même axe produisent une figure fausse dont chaque chiffre est juste. Et un
    taux à côté d'un montant (`%` et `MdEUR`) : ce sont deux natures de
    grandeur, pas deux échelles.

    ## Quelle échelle afficher

    Celle qui laisse le PLUS de valeurs au-dessus de l'unité, et à égalité la
    plus grande — donc la moins bavarde en chiffres.

    Prendre simplement l'échelle du plus grand montant paraissait naturel et
    donnait le contraire de l'effet voulu : un TAM à 1,2 Md€, un SAM à 240 M€ et
    un SOM à 1,8 M€ s'affichaient « 1,2 / 0,24 / 0,0018 », deux valeurs sur
    trois sous l'unité. En millions, la même figure lit « 1 200 / 240 / 1,8 ».

    Un entonnoir dont la dernière marche est mille fois plus petite que la
    première reste écrasé — mais c'est la donnée qui le veut, pas le rendu, et
    les étiquettes portent les valeurs.
    """
    unites = {donnee.unite for donnee in donnees}
    if len(unites) == 1:
        return [donnee.valeur for donnee in donnees], unites.pop()

    bases: list[float] = []
    devises: set[str] = set()
    for donnee in donnees:
        converti = valeur_en_unites_de_base(donnee.valeur, donnee.unite)
        if converti is None:
            return None  # au moins une grandeur non monétaire : natures mêlées
        valeur, devise = converti
        bases.append(valeur)
        devises.add(devise)
    if len(devises) != 1:
        return None

    devise = devises.pop()
    prefixe, facteur = max(
        _MAGNITUDES_AFFICHAGE,
        key=lambda candidat: (
            sum(1 for valeur in bases if abs(valeur) >= candidat[1]),
            candidat[1],
        ),
    )
    return [valeur / facteur for valeur in bases], f"{prefixe}{devise}"


def _suffixe(unite: str) -> str:
    return "" if unite == "%" else f" {unite}"


# ── Résolveurs par forme de données ──────────────────────────────────────────


def _scalaires(
    socle: Socle, type_demande: str, identifiants: Sequence[str]
) -> Resolution:
    donnees, motif = _resoudre_ids(socle, identifiants)
    if motif:
        return Resolution(motif=motif)
    if len(donnees) < 2:
        return Resolution(
            motif="un seul chiffre : un graphique à une barre n'apprend rien"
        )

    harmonise = _harmoniser(donnees)
    if harmonise is None:
        return Resolution(
            motif="unités hétérogènes : "
            + ", ".join(sorted({d.unite for d in donnees}))
        )
    valeurs, unite = harmonise

    etiquettes = [etiquette_de(donnee) for donnee in donnees]

    if type_demande in ("camembert", "anneau"):
        if any(valeur < 0 for valeur in valeurs):
            return Resolution(
                motif="valeur négative : une part d'un tout ne peut pas être négative"
            )
        contenu: dict[str, Any] = {"etiquettes": etiquettes, "valeurs": valeurs}
        if type_demande == "anneau":
            contenu["centre"] = f"{sum(valeurs):g}{_suffixe(unite)}"
        return Resolution(type_demande, contenu)

    if type_demande == "entonnoir":
        # L'entonnoir se lit du plus large au plus étroit ; on trie plutôt que
        # d'exiger du modèle qu'il déclare ses identifiants dans le bon ordre.
        paires = sorted(zip(etiquettes, valeurs, strict=True), key=lambda p: -p[1])
        return Resolution(
            type_demande, {"etapes": paires, "unite": _suffixe(unite)}
        )

    if type_demande == "jauges":
        familles = {_famille(donnee) for donnee in donnees}
        if familles != {FamilleUnite.RATIO}:
            return Resolution(
                motif="les jauges exigent des notes ; ces données ne sont pas "
                "des ratios notés"
            )
        maximum = 10.0 if unite == "note_sur_10" else 5.0
        return Resolution(
            type_demande,
            {"notes": list(zip(etiquettes, valeurs, strict=True)), "maximum": maximum},
        )

    return Resolution(
        type_demande,
        {"etiquettes": etiquettes, "valeurs": valeurs, "unite": _suffixe(unite)},
    )


def series_par_perimetre(
    donnees: Sequence[DonneeSocle], valeurs: Sequence[float], annees: Sequence[int]
) -> list[tuple[str, list[float]]]:
    """Regroupe les points en séries : une série par périmètre géographique.

    ## Pourquoi pas par libellé, comme avant

    Le socle interdit les doublons — « un identifiant, une seule valeur » — et
    chaque donnée porte UNE année. Une courbe « marché mondial 2026 → 2035 » se
    déclare donc forcément avec DEUX identifiants distincts :
    `marche_mondial_taille` et `marche_mondial_projection`. Deux identifiants,
    donc deux libellés, donc — avec un regroupement par libellé — deux séries
    d'un seul point chacune. Aucune ne couvrait toutes les années, toutes
    étaient écartées, et la figure mourait sur « aucune série complète ».

    Autrement dit : **courbes, aires, barres groupées et barres empilées —
    quatre formes sur quinze, et les plus attendues d'une étude de marché —
    étaient structurellement infaisables.** Mesuré le 05/08/2026 en dessinant
    le catalogue hors ligne, sur un socle réaliste et sans un appel au modèle.

    Cela corrobore les abandons du livrable réel `18ce3fca`, qui portaient tous
    sur des trajectoires : « Marché mondial : évolution 2025 et projection
    2035 », « Trajectoires comparées 2025-2035 ». Le modèle demandait bien la
    bonne figure ; c'est le résolveur qui ne savait pas la construire.

    ## Le périmètre, et pas une table de correspondance

    `Perimetre` est déjà porté par chaque donnée du socle et vient du
    référentiel : la taille du marché mondial et sa projection le partagent, par
    construction. Écrire ici une table « ces identifiants vont ensemble »
    divergerait au premier identifiant ajouté (règle 5).

    Une série trouée reste écartée : une valeur manquante ne s'interpole pas,
    sous peine de faire mentir la pente.
    """
    groupes: dict[str, dict[int, float]] = {}
    noms: dict[str, str] = {}
    for donnee, valeur in zip(donnees, valeurs, strict=True):
        cle = str(donnee.perimetre)
        groupes.setdefault(cle, {})[donnee.annee] = valeur
        # Le nom de la série vient de la première donnée du périmètre : c'est
        # elle qui porte la grandeur observée, la suivante sa projection.
        noms.setdefault(cle, etiquette_de(donnee))

    series: list[tuple[str, list[float]]] = []
    for cle, points in groupes.items():
        if len(points) != len(annees):
            continue
        series.append((noms[cle], [points[annee] for annee in annees]))
    return series


def _temporel(
    socle: Socle, type_demande: str, identifiants: Sequence[str]
) -> Resolution:
    """Courbes et aires : exigent un axe des temps, donc plusieurs années.

    Une série par PÉRIMÈTRE, chaque année un point — voir
    `series_par_perimetre` pour ce que le regroupement par libellé rendait
    impossible.
    """
    donnees, motif = _resoudre_ids(socle, identifiants)
    if motif:
        return Resolution(motif=motif)

    annees = sorted({donnee.annee for donnee in donnees})
    if len(annees) < 2:
        # Reconversion honnête plutôt qu'abandon : les chiffres sont bons, seul
        # l'axe temporel manque.
        repli = _scalaires(socle, "barres", identifiants)
        if repli.retenu:
            return Resolution(
                "barres", repli.donnees,
                motif="une seule année : rendu en barres, faute d'axe temporel",
                converti=True,
            )
        return Resolution(motif="une seule année et " + repli.motif)

    harmonise = _harmoniser(donnees)
    if harmonise is None:
        return Resolution(
            motif="unités hétérogènes : "
            + ", ".join(sorted({d.unite for d in donnees}))
        )
    valeurs, unite = harmonise

    series = series_par_perimetre(donnees, valeurs, annees)

    if not series:
        return Resolution(
            motif="aucune série complète : chaque série doit couvrir toutes "
            "les années, et une valeur manquante ne s'interpole pas"
        )
    if type_demande == "aires" and len(series) < 2:
        return Resolution(
            "courbes",
            {"abscisses": [str(a) for a in annees], "series": series,
             "unite": unite},
            motif="une seule série : rendu en courbe, une aire empilée n'aurait "
            "rien à empiler",
            converti=True,
        )
    return Resolution(
        type_demande,
        {"abscisses": [str(annee) for annee in annees], "series": series,
         "unite": unite},
    )


def _groupees(
    socle: Socle, type_demande: str, identifiants: Sequence[str]
) -> Resolution:
    """Barres groupées ou empilées : une série par PÉRIMÈTRE, un groupe par année.

    Même correction que les courbes : le regroupement par libellé rendait ces
    deux formes infaisables, puisqu'un périmètre suivi dans le temps s'exprime
    forcément avec plusieurs identifiants (voir `series_par_perimetre`).
    """
    donnees, motif = _resoudre_ids(socle, identifiants)
    if motif:
        return Resolution(motif=motif)

    harmonise = _harmoniser(donnees)
    if harmonise is None:
        return Resolution(
            motif="unités hétérogènes : "
            + ", ".join(sorted({d.unite for d in donnees}))
        )
    valeurs, unite = harmonise
    if type_demande == "barres_empilees" and any(d.valeur < 0 for d in donnees):
        return Resolution(motif="valeur négative : un empilement deviendrait faux")

    annees = sorted({donnee.annee for donnee in donnees})
    series = series_par_perimetre(donnees, valeurs, annees)
    if len(series) < 2 or len(annees) < 2:
        repli = _scalaires(socle, "barres", identifiants)
        if repli.retenu:
            return Resolution(
                "barres", repli.donnees,
                motif="une seule dimension : rendu en barres simples",
                converti=True,
            )
        return Resolution(motif="pas de seconde dimension et " + repli.motif)

    return Resolution(
        type_demande,
        {"etiquettes": [str(annee) for annee in annees], "series": series,
         "unite": unite},
    )


def _notes(
    socle: Socle, type_demande: str, identifiants: Sequence[str]
) -> Resolution:
    """Radar : plusieurs critères notés sur une même échelle."""
    donnees, motif = _resoudre_ids(socle, identifiants)
    if motif:
        return Resolution(motif=motif)
    if len(donnees) < 3:
        return Resolution(motif="un radar exige au moins trois axes")
    if {_famille(donnee) for donnee in donnees} != {FamilleUnite.RATIO}:
        return Resolution(
            motif="le radar exige des notes ; ces données ne sont pas des "
            "ratios notés"
        )
    # Ici l'identité d'unité est EXIGÉE, pas harmonisée : `note_sur_5` et
    # `note_sur_10` ne sont pas deux échelles d'une même grandeur, ce sont deux
    # barèmes. Les ramener l'un à l'autre changerait le sens des notes.
    unites = {donnee.unite for donnee in donnees}
    if len(unites) != 1:
        return Resolution(motif="échelles de notation différentes sur un même radar")
    unite = unites.pop()
    return Resolution(
        type_demande,
        {"axes_noms": [etiquette_de(donnee) for donnee in donnees],
         "series": [("Projet", [donnee.valeur for donnee in donnees])],
         "maximum": 10.0 if unite == "note_sur_10" else 5.0},
    )


# ── Résolveurs alimentés par les collections du socle ────────────────────────
# Ces types ne se nourrissent pas d'identifiants chiffrés : leur matière est
# ailleurs dans le socle — les risques portent un couple probabilité/impact,
# les tendances portent un horizon. Les identifiants déclarés par le chapitre
# sont alors ignorés, et c'est volontaire : ils ne pourraient rien apporter.


def _risques_notes(socle: Socle) -> list[Any]:
    return [
        risque for risque in socle.risques
        if risque.probabilite is not None and risque.impact is not None
    ]


def _matrice(socle: Socle, type_demande: str, _: Sequence[str]) -> Resolution:
    risques = _risques_notes(socle)
    if len(risques) < 2:
        return Resolution(
            motif="le socle ne porte pas deux risques notés en probabilité "
            "et en impact ; aucune coordonnée à placer"
        )
    return Resolution(
        type_demande,
        {"points": [
            (risque.intitule, float(risque.probabilite), float(risque.impact))
            for risque in risques
        ],
         "axe_x": "Probabilité", "axe_y": "Impact"},
    )


def _chaleur(socle: Socle, type_demande: str, _: Sequence[str]) -> Resolution:
    risques = _risques_notes(socle)
    if len(risques) < 2:
        return Resolution(
            motif="le socle ne porte pas deux risques notés en probabilité "
            "et en impact"
        )
    return Resolution(
        type_demande,
        {"lignes": [risque.intitule for risque in risques],
         "colonnes": ["Probabilité", "Impact", "Criticité"],
         "valeurs": [
             [float(risque.probabilite), float(risque.impact),
              float(risque.probabilite) * float(risque.impact) / 5]
             for risque in risques
         ]},
    )


def _frise(socle: Socle, type_demande: str, _: Sequence[str]) -> Resolution:
    jalons = [
        (tendance.horizon, tendance.intitule)
        for tendance in socle.tendances
        if tendance.horizon.strip()
    ]
    if len(jalons) < 2:
        return Resolution(
            motif="moins de deux tendances portent un horizon : une frise "
            "sans date n'est pas une frise"
        )
    return Resolution(type_demande, {"jalons": jalons[:6]})


def _pyramide(_socle: Socle, _type: str, _ids: Sequence[str]) -> Resolution:
    """Jamais alimentable en l'état — et c'est un manque du socle, pas un bug.

    Une pyramide des âges suppose une répartition par tranche et par sexe. Le
    référentiel du lot 1, validé par la cliente, ne porte aucune structure
    démographique : ni tranches, ni effectifs par tranche. Le type existe dans
    le catalogue de rendu et il est privilégié par les profils « santé » et
    « services à la personne », mais rien ne peut l'alimenter aujourd'hui.

    L'abandon est donc déclaré ici explicitement plutôt que subi ailleurs, et
    le motif remonte dans le rapport d'assemblage : c'est une décision à
    prendre — étendre le référentiel, ou retirer le type — pas un accident.
    """
    return Resolution(
        motif="le référentiel du socle ne porte aucune structure démographique "
        "(tranches d'âge, effectifs) : ce type ne peut pas être alimenté"
    )


_Resolveur = Callable[[Socle, str, Sequence[str]], Resolution]

RESOLVEURS: dict[str, _Resolveur] = {
    **{type_graphique: _scalaires for type_graphique in _SCALAIRES},
    "courbes": _temporel,
    "aires": _temporel,
    "barres_groupees": _groupees,
    "barres_empilees": _groupees,
    "radar": _notes,
    "matrice_positionnement": _matrice,
    "carte_chaleur": _chaleur,
    "chronologie": _frise,
    "pyramide_ages": _pyramide,
}


def resoudre(
    socle: Socle, type_graphique: str, identifiants: Sequence[str]
) -> Resolution:
    """Alimente un graphique depuis le socle, ou explique pourquoi c'est impossible."""
    resolveur = RESOLVEURS.get(type_graphique)
    if resolveur is None:
        return Resolution(motif=f"type de graphique inconnu : {type_graphique!r}")
    return resolveur(socle, type_graphique, identifiants)
