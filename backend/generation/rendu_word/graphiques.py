"""Catalogue de graphiques matplotlib, à la charte du livrable.

Le document de référence porte dix images PNG de 1960 à 2320 pixels de large :
ce sont des sorties matplotlib haute résolution, pas des graphiques Word.

**Le type de graphique dépend du secteur d'activité, jamais du numéro de
chapitre.** Une étude sur la restauration appelle une saisonnalité et une
répartition de ticket moyen ; une étude sur la joaillerie appelle un entonnoir
de marché et une matrice de positionnement ; une étude sur le service à la
personne appelle une pyramide des âges. Le `CATALOGUE` en bas de module décrit
ce que chaque type attend et ce à quoi il sert : c'est en le lisant que la
couche de génération choisit, en connaissance du secteur.

Contraintes du lot 0, appliquées à tous les types :
fond `FDFBF6`, séries dans l'ordre principale / or bronze / crème / rose grisé,
aucun cadre, étiquettes en Aptos, 200 dpi, 2000 px de large.
"""
from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import matplotlib

matplotlib.use("Agg")  # aucun serveur graphique sur le VPS

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from .palette import Palette  # noqa: E402

DPI = 200
LARGEUR_PX = 2000

#: Chaîne de repli des étiquettes de graphique.
#
# Ces graphiques ne sont pas du texte : ce sont des PNG rendus ICI, sur le
# serveur, puis encastrés dans le `.docx`. Leur police est donc figée à la
# génération — contrairement au texte du document, qu'un Word équipé d'Aptos
# affichera correctement chez la cliente. Un repli mal choisi se voit
# definitivement, dans le Word COMME dans le PDF.
#
# Mesure du 05/08/2026, en rendant un document et en le comparant à
# `references/joalie_2026.docx` : ni Aptos ni Segoe UI n'existent sur l'image
# Debian de production (le Dockerfile le dit lui-même — polices Microsoft non
# redistribuables). La chaîne tombait donc sur DejaVu Sans, une grotesque très
# éloignée d'Aptos : les étiquettes juraient avec le texte qui les entoure.
#
# `Carlito` s'intercale : clone libre métriquement compatible de Calibri, DÉJÀ
# installé dans l'image (`fonts-crosextra-carlito`) pour WeasyPrint. Aptos a
# remplacé Calibri comme police par défaut d'Office — c'est le repli le plus
# proche disponible sans embarquer de police sous licence Microsoft.
POLICE = ["Aptos", "Segoe UI", "Carlito", "DejaVu Sans"]

#: Emplacements de légende employés. `Axes.legend` n'accepte pas un `str`
#: quelconque : la liste est fermée côté matplotlib, on la reflète ici.
_Position = Literal["upper left", "upper right", "lower left", "lower right"]


def _figure(palette: Palette, hauteur_ratio: float = 0.42) -> tuple[Figure, Axes]:
    largeur_pouces = LARGEUR_PX / DPI
    figure, axes = plt.subplots(
        figsize=(largeur_pouces, largeur_pouces * hauteur_ratio), dpi=DPI
    )
    # Mise en page contrainte plutôt que `bbox_inches="tight"` : ce dernier
    # RECADRE la figure et ramenait la sortie à 1 672 px au lieu des 2 000
    # exigés. Ici la taille demandée est la taille obtenue.
    figure.set_layout_engine("constrained")
    figure.patch.set_facecolor(palette.fond_graphique)
    axes.set_facecolor(palette.fond_graphique)
    for cote in ("top", "right", "left", "bottom"):
        axes.spines[cote].set_visible(False)
    axes.tick_params(length=0, labelsize=9, colors=palette.texte_corps)
    plt.rcParams["font.family"] = POLICE
    return figure, axes


def _exporter(figure: Figure, palette: Palette) -> bytes:
    tampon = io.BytesIO()
    figure.savefig(tampon, format="png", dpi=DPI, facecolor=palette.fond_graphique)
    plt.close(figure)
    tampon.seek(0)
    return tampon.read()


def _couleurs(palette: Palette, nombre: int) -> list[str]:
    base = palette.series_graphique
    return [base[index % len(base)] for index in range(nombre)]


def _legende(
    axes: Axes, palette: Palette, position: _Position = "upper left"
) -> None:
    legende = axes.legend(frameon=False, fontsize=9, loc=position)
    for texte in legende.get_texts():
        texte.set_color(palette.texte_corps)


# ── Comparaisons ─────────────────────────────────────────────────────────────


def barres_verticales(
    palette: Palette, etiquettes: Sequence[str], valeurs: Sequence[float], unite: str = ""
) -> bytes:
    figure, axes = _figure(palette)
    axes.bar(list(etiquettes), list(valeurs), color=palette.primaire, width=0.55)
    axes.grid(axis="y", color=palette.fond_clair_alt, linewidth=0.8)
    axes.set_axisbelow(True)
    axes.set_xticks(range(len(etiquettes)))
    axes.set_xticklabels(etiquettes, rotation=0)
    for index, valeur in enumerate(valeurs):
        axes.text(
            index, valeur, f" {valeur:g}{unite}", ha="center", va="bottom",
            fontsize=9, color=palette.prune_fonce,
        )
    return _exporter(figure, palette)


def barres_horizontales(
    palette: Palette, etiquettes: Sequence[str], valeurs: Sequence[float], unite: str = ""
) -> bytes:
    figure, axes = _figure(palette, hauteur_ratio=0.06 * max(len(etiquettes), 4))
    positions = range(len(etiquettes))
    axes.barh(list(positions), list(valeurs), color=palette.primaire, height=0.55)
    axes.set_yticks(list(positions))
    axes.set_yticklabels(etiquettes)
    axes.invert_yaxis()
    axes.grid(axis="x", color=palette.fond_clair_alt, linewidth=0.8)
    axes.set_axisbelow(True)
    for index, valeur in enumerate(valeurs):
        axes.text(
            valeur, index, f" {valeur:g}{unite}", va="center",
            fontsize=9, color=palette.prune_fonce,
        )
    return _exporter(figure, palette)


def barres_groupees(
    palette: Palette,
    etiquettes: Sequence[str],
    series: Sequence[tuple[str, Sequence[float]]],
    unite: str = "",
) -> bytes:
    """Comparaison de plusieurs séries : concurrents, années, zones."""
    figure, axes = _figure(palette)
    positions = np.arange(len(etiquettes), dtype=float)
    largeur = 0.8 / max(len(series), 1)
    couleurs = _couleurs(palette, len(series))
    for index, (nom, valeurs) in enumerate(series):
        axes.bar(
            positions + index * largeur, list(valeurs), largeur * 0.9,
            label=nom, color=couleurs[index],
        )
    axes.set_xticks(positions + largeur * (len(series) - 1) / 2)
    axes.set_xticklabels(etiquettes)
    axes.grid(axis="y", color=palette.fond_clair_alt, linewidth=0.8)
    axes.set_axisbelow(True)
    _legende(axes, palette)
    if unite:
        axes.set_ylabel(unite, fontsize=9, color=palette.texte_legende)
    return _exporter(figure, palette)


def barres_empilees(
    palette: Palette,
    etiquettes: Sequence[str],
    series: Sequence[tuple[str, Sequence[float]]],
    unite: str = "",
) -> bytes:
    """Structure d'un total : mix produit, décomposition d'un chiffre d'affaires."""
    figure, axes = _figure(palette)
    couleurs = _couleurs(palette, len(series))
    cumul = np.zeros(len(etiquettes))
    for index, (nom, valeurs) in enumerate(series):
        hauteurs = np.array(list(valeurs), dtype=float)
        axes.bar(
            list(etiquettes), hauteurs, bottom=cumul, label=nom,
            color=couleurs[index], width=0.55,
        )
        cumul += hauteurs
    axes.grid(axis="y", color=palette.fond_clair_alt, linewidth=0.8)
    axes.set_axisbelow(True)
    _legende(axes, palette)
    if unite:
        axes.set_ylabel(unite, fontsize=9, color=palette.texte_legende)
    return _exporter(figure, palette)


# ── Évolutions ───────────────────────────────────────────────────────────────


def courbes(
    palette: Palette,
    abscisses: Sequence[str],
    series: Sequence[tuple[str, Sequence[float]]],
    unite: str = "",
) -> bytes:
    figure, axes = _figure(palette)
    couleurs = _couleurs(palette, len(series))
    for index, (nom, valeurs) in enumerate(series):
        axes.plot(
            list(abscisses), list(valeurs), marker="o", markersize=4, linewidth=2,
            color=couleurs[index], label=nom,
        )
    axes.grid(axis="y", color=palette.fond_clair_alt, linewidth=0.8)
    axes.set_axisbelow(True)
    if len(series) > 1:
        _legende(axes, palette)
    if unite:
        axes.set_ylabel(unite, fontsize=9, color=palette.texte_legende)
    return _exporter(figure, palette)


def aires(
    palette: Palette,
    abscisses: Sequence[str],
    series: Sequence[tuple[str, Sequence[float]]],
    unite: str = "",
) -> bytes:
    """Évolution d'une composition : saisonnalité, montée en charge."""
    figure, axes = _figure(palette)
    couleurs = _couleurs(palette, len(series))
    axes.stackplot(
        list(abscisses), *[list(valeurs) for _, valeurs in series],
        labels=[nom for nom, _ in series], colors=couleurs, alpha=0.92,
    )
    axes.grid(axis="y", color=palette.fond_clair_alt, linewidth=0.8)
    axes.set_axisbelow(True)
    _legende(axes, palette)
    if unite:
        axes.set_ylabel(unite, fontsize=9, color=palette.texte_legende)
    return _exporter(figure, palette)


# ── Répartitions ─────────────────────────────────────────────────────────────


def camembert(
    palette: Palette, etiquettes: Sequence[str], valeurs: Sequence[float]
) -> bytes:
    """Parts d'un tout : structure d'un marché, poids des canaux."""
    figure, axes = _figure(palette, hauteur_ratio=0.52)
    axes.pie(
        list(valeurs), labels=list(etiquettes),
        colors=_couleurs(palette, len(valeurs)),
        autopct="%1.0f %%", startangle=90, counterclock=False,
        textprops={"fontsize": 9, "color": palette.texte_corps},
        wedgeprops={"edgecolor": palette.fond_graphique, "linewidth": 2},
    )
    axes.set_aspect("equal")
    return _exporter(figure, palette)


def anneau(
    palette: Palette,
    etiquettes: Sequence[str],
    valeurs: Sequence[float],
    centre: str = "",
) -> bytes:
    """Camembert évidé, avec un chiffre au centre. Plus lisible qu'un camembert."""
    figure, axes = _figure(palette, hauteur_ratio=0.52)
    axes.pie(
        list(valeurs), labels=list(etiquettes),
        colors=_couleurs(palette, len(valeurs)),
        autopct="%1.0f %%", startangle=90, counterclock=False, pctdistance=0.78,
        textprops={"fontsize": 9, "color": palette.texte_corps},
        wedgeprops={"width": 0.42, "edgecolor": palette.fond_graphique, "linewidth": 2},
    )
    if centre:
        axes.text(
            0, 0, centre, ha="center", va="center", fontsize=15,
            color=palette.primaire, fontweight="bold",
        )
    axes.set_aspect("equal")
    return _exporter(figure, palette)


def entonnoir(
    palette: Palette, etapes: Sequence[tuple[str, float]], unite: str = ""
) -> bytes:
    """Marché total vers marché atteignable, ou parcours de conversion.

    Chaque étape est une barre centrée dont la largeur est proportionnelle à sa
    valeur : la forme en entonnoir se lit sans légende.
    """
    figure, axes = _figure(palette, hauteur_ratio=0.11 * max(len(etapes), 3))
    maximum = max((valeur for _, valeur in etapes), default=1.0) or 1.0
    couleurs = _couleurs(palette, len(etapes))
    for index, (nom, valeur) in enumerate(etapes):
        largeur = valeur / maximum
        axes.barh(
            index, largeur, left=(1 - largeur) / 2, height=0.62, color=couleurs[index]
        )
        couleur_texte = (
            palette.texte_sur_primaire if index == 0 else palette.prune_fonce
        )
        axes.text(
            0.5, index, f"{nom}  ·  {valeur:g}{unite}", ha="center", va="center",
            fontsize=10, color=couleur_texte, fontweight="bold",
        )
    axes.set_xlim(0, 1)
    axes.invert_yaxis()
    axes.set_xticks([])
    axes.set_yticks([])
    return _exporter(figure, palette)


# ── Évaluations ──────────────────────────────────────────────────────────────


def radar(
    palette: Palette,
    axes_noms: Sequence[str],
    series: Sequence[tuple[str, Sequence[float]]],
    maximum: float = 5.0,
) -> bytes:
    """Notation multi-critères : diagnostic, comparaison à un concurrent."""
    largeur_pouces = LARGEUR_PX / DPI
    figure = plt.figure(figsize=(largeur_pouces, largeur_pouces * 0.52), dpi=DPI)
    figure.set_layout_engine("constrained")
    figure.patch.set_facecolor(palette.fond_graphique)
    plt.rcParams["font.family"] = POLICE
    axes = figure.add_subplot(111, polar=True)
    axes.set_facecolor(palette.fond_graphique)

    angles = np.linspace(0, 2 * np.pi, len(axes_noms), endpoint=False).tolist()
    angles += angles[:1]
    couleurs = _couleurs(palette, len(series))
    for index, (nom, valeurs) in enumerate(series):
        points = [*list(valeurs), list(valeurs)[0]]
        axes.plot(angles, points, linewidth=2, color=couleurs[index], label=nom)
        axes.fill(angles, points, color=couleurs[index], alpha=0.18)
    axes.set_xticks(angles[:-1])
    axes.set_xticklabels(list(axes_noms), fontsize=9, color=palette.texte_corps)
    axes.set_ylim(0, maximum)
    axes.tick_params(colors=palette.texte_legende, labelsize=8)
    axes.grid(color=palette.fond_clair_alt, linewidth=0.8)
    axes.spines["polar"].set_visible(False)
    if len(series) > 1:
        legende = axes.legend(
            frameon=False, fontsize=9, loc="upper right", bbox_to_anchor=(1.28, 1.10)
        )
        for texte in legende.get_texts():
            texte.set_color(palette.texte_corps)
    return _exporter(figure, palette)


def jauges(
    palette: Palette, notes: Sequence[tuple[str, float]], maximum: float = 5.0
) -> bytes:
    """Scores sur un maximum commun : critères d'un diagnostic, notation d'un site."""
    figure, axes = _figure(palette, hauteur_ratio=0.075 * max(len(notes), 4))
    positions = list(range(len(notes)))
    axes.barh(positions, [maximum] * len(notes), color=palette.fond_clair, height=0.5)
    axes.barh(
        positions, [note for _, note in notes], color=palette.primaire, height=0.5
    )
    axes.set_yticks(positions)
    axes.set_yticklabels([nom for nom, _ in notes], fontsize=9)
    axes.invert_yaxis()
    axes.set_xlim(0, maximum)
    axes.set_xticks([])
    for index, (_, note) in enumerate(notes):
        axes.text(
            note, index, f"  {note:g} / {maximum:g}", va="center",
            fontsize=9, color=palette.prune_fonce, fontweight="bold",
        )
    return _exporter(figure, palette)


def matrice_positionnement(
    palette: Palette,
    points: Sequence[tuple[str, float, float]],
    axe_x: str = "",
    axe_y: str = "",
) -> bytes:
    """Nuage étiqueté : positionnement concurrentiel, matrice de risques."""
    figure, axes = _figure(palette, hauteur_ratio=0.62)
    couleurs = _couleurs(palette, len(points))
    for index, (nom, x, y) in enumerate(points):
        axes.scatter(x, y, s=260, color=couleurs[index], zorder=3)
        axes.annotate(
            nom, (x, y), textcoords="offset points", xytext=(0, 14),
            ha="center", fontsize=9, color=palette.texte_corps,
        )
    axes.grid(color=palette.fond_clair_alt, linewidth=0.8)
    axes.set_axisbelow(True)
    axes.set_xlabel(axe_x, fontsize=9, color=palette.texte_legende)
    axes.set_ylabel(axe_y, fontsize=9, color=palette.texte_legende)
    axes.set_xlim(0, 5.5)
    axes.set_ylim(0, 5.5)
    return _exporter(figure, palette)


def carte_chaleur(
    palette: Palette,
    lignes: Sequence[str],
    colonnes: Sequence[str],
    valeurs: Sequence[Sequence[float]],
) -> bytes:
    """Grille colorée : criticité des risques, attractivité par marché."""
    figure, axes = _figure(palette, hauteur_ratio=0.085 * max(len(lignes), 4))
    echelle = LinearSegmentedColormap.from_list(
        "evkha", [palette.fond_clair, palette.rose_pale, palette.primaire]
    )
    grille = np.array([list(ligne) for ligne in valeurs], dtype=float)
    axes.imshow(grille, cmap=echelle, aspect="auto")
    axes.set_xticks(range(len(colonnes)))
    axes.set_xticklabels(list(colonnes), fontsize=9)
    axes.set_yticks(range(len(lignes)))
    axes.set_yticklabels(list(lignes), fontsize=9)
    maximum = float(grille.max()) if grille.size else 1.0
    for i in range(grille.shape[0]):
        for j in range(grille.shape[1]):
            valeur = float(grille[i, j])
            couleur = (
                palette.texte_sur_primaire
                if valeur > maximum * 0.62
                else palette.prune_fonce
            )
            axes.text(
                j, i, f"{valeur:g}", ha="center", va="center",
                fontsize=9, color=couleur, fontweight="bold",
            )
    return _exporter(figure, palette)


# ── Démographie et temps ─────────────────────────────────────────────────────


def pyramide_ages(
    palette: Palette,
    tranches: Sequence[str],
    gauche: Sequence[float],
    droite: Sequence[float],
    libelles: tuple[str, str] = ("Femmes", "Hommes"),
) -> bytes:
    """Structure démographique d'une clientèle ou d'un bassin de population."""
    figure, axes = _figure(palette, hauteur_ratio=0.075 * max(len(tranches), 5))
    positions = np.arange(len(tranches), dtype=float)
    axes.barh(
        positions, [-valeur for valeur in gauche], color=palette.primaire,
        height=0.72, label=libelles[0],
    )
    axes.barh(
        positions, list(droite), color=palette.or_bronze,
        height=0.72, label=libelles[1],
    )
    axes.set_yticks(positions)
    axes.set_yticklabels(list(tranches), fontsize=9)
    maximum = max([*list(gauche), *list(droite)], default=1.0) or 1.0
    axes.set_xlim(-maximum * 1.15, maximum * 1.15)
    axes.set_xticks([])
    axes.axvline(0, color=palette.fond_clair_alt, linewidth=1)
    _legende(axes, palette)
    return _exporter(figure, palette)


def chronologie(palette: Palette, jalons: Sequence[tuple[str, str]]) -> bytes:
    """Frise horizontale : vagues d'ouverture, plan à trois horizons."""
    figure, axes = _figure(palette, hauteur_ratio=0.30)
    positions = np.linspace(0.05, 0.95, max(len(jalons), 1))
    axes.plot([0.02, 0.98], [0, 0], color=palette.fond_clair_alt, linewidth=3, zorder=1)
    couleurs = _couleurs(palette, len(jalons))
    for index, ((date, texte), abscisse) in enumerate(
        zip(jalons, positions, strict=False)
    ):
        axes.scatter(abscisse, 0, s=300, color=couleurs[index], zorder=3)
        haut = index % 2 == 0
        axes.annotate(
            date, (abscisse, 0), textcoords="offset points",
            xytext=(0, 30 if haut else -34), ha="center",
            fontsize=10, fontweight="bold", color=palette.primaire,
        )
        axes.annotate(
            texte, (abscisse, 0), textcoords="offset points",
            xytext=(0, 15 if haut else -50), ha="center",
            fontsize=8, color=palette.texte_corps,
        )
    axes.set_xlim(0, 1)
    axes.set_ylim(-1, 1)
    axes.set_xticks([])
    axes.set_yticks([])
    return _exporter(figure, palette)


# ── Catalogue ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DefinitionGraphique:
    """Ce qu'un type de graphique attend, et ce à quoi il sert.

    Ce catalogue est destiné à être lu par la couche de génération : elle y
    choisit un visuel adapté au secteur d'activité, au lieu d'appliquer un type
    figé par chapitre. Le champ `usage` est repris tel quel dans le prompt.
    """

    nom: str
    usage: str
    champs: tuple[str, ...]


#: Types déclarables dans le contrat de chapitre -> fonction de rendu.
RENDU_PAR_TYPE = {
    "barres": barres_verticales,
    "barres_horizontales": barres_horizontales,
    "barres_groupees": barres_groupees,
    "barres_empilees": barres_empilees,
    "courbes": courbes,
    "aires": aires,
    "camembert": camembert,
    "anneau": anneau,
    "entonnoir": entonnoir,
    "radar": radar,
    "jauges": jauges,
    "matrice_positionnement": matrice_positionnement,
    "carte_chaleur": carte_chaleur,
    "pyramide_ages": pyramide_ages,
    "chronologie": chronologie,
}

CATALOGUE: dict[str, DefinitionGraphique] = {
    "barres": DefinitionGraphique(
        "barres", "Comparer des grandeurs de même nature",
        ("etiquettes", "valeurs", "unite")),
    "barres_horizontales": DefinitionGraphique(
        "barres_horizontales", "Classer des éléments dont les libellés sont longs",
        ("etiquettes", "valeurs", "unite")),
    "barres_groupees": DefinitionGraphique(
        "barres_groupees", "Comparer plusieurs séries : concurrents, années, zones",
        ("etiquettes", "series", "unite")),
    "barres_empilees": DefinitionGraphique(
        "barres_empilees", "Montrer la structure d'un total : mix produit, canaux",
        ("etiquettes", "series", "unite")),
    "courbes": DefinitionGraphique(
        "courbes", "Suivre une évolution passée ou une projection",
        ("abscisses", "series", "unite")),
    "aires": DefinitionGraphique(
        "aires", "Évolution d'une composition : saisonnalité, montée en charge",
        ("abscisses", "series", "unite")),
    "camembert": DefinitionGraphique(
        "camembert", "Répartition en parts d'un tout",
        ("etiquettes", "valeurs")),
    "anneau": DefinitionGraphique(
        "anneau", "Répartition avec un chiffre clé mis en avant au centre",
        ("etiquettes", "valeurs", "centre")),
    "entonnoir": DefinitionGraphique(
        "entonnoir", "Marché total vers atteignable, ou parcours de conversion",
        ("etapes", "unite")),
    "radar": DefinitionGraphique(
        "radar", "Notation multi-critères : diagnostic, comparaison à un concurrent",
        ("axes_noms", "series", "maximum")),
    "jauges": DefinitionGraphique(
        "jauges", "Scores sur un maximum commun",
        ("notes", "maximum")),
    "matrice_positionnement": DefinitionGraphique(
        "matrice_positionnement", "Positionner des acteurs sur deux axes",
        ("points", "axe_x", "axe_y")),
    "carte_chaleur": DefinitionGraphique(
        "carte_chaleur", "Criticité croisée : risques, attractivité par marché",
        ("lignes", "colonnes", "valeurs")),
    "pyramide_ages": DefinitionGraphique(
        "pyramide_ages", "Structure démographique d'une clientèle ou d'un bassin",
        ("tranches", "gauche", "droite", "libelles")),
    "chronologie": DefinitionGraphique(
        "chronologie", "Jalons dans le temps : vagues d'ouverture, plan par horizons",
        ("jalons",)),
}

#: Liste fermée des types, dans l'ordre alphabétique. Sert d'`enum` au schéma
#: de chapitre : le modèle ne peut déclarer que ces valeurs.
TYPES_DISPONIBLES: tuple[str, ...] = tuple(sorted(RENDU_PAR_TYPE))


def resume_catalogue() -> str:
    """Le catalogue en texte, à insérer dans un prompt de chapitre."""
    return "\n".join(
        f"- `{definition.nom}` : {definition.usage}. "
        f"Champs : {', '.join(definition.champs)}."
        for definition in CATALOGUE.values()
    )


def rendre(palette: Palette, type_graphique: str, donnees: dict[str, Any]) -> bytes:
    """Produit le PNG d'un graphique. Repli en barres si le type est inconnu.

    Le repli est délibéré : un visuel approximatif vaut mieux qu'un livrable
    qui ne sort pas parce que le modèle a inventé un nom de type.
    """
    fonction = RENDU_PAR_TYPE.get(type_graphique)
    if fonction is None:
        return barres_verticales(
            palette, donnees.get("etiquettes", []), donnees.get("valeurs", []),
            donnees.get("unite", ""),
        )
    return fonction(palette, **donnees)  # type: ignore[operator,no-any-return]
