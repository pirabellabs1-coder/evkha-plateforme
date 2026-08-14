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
    SELECTEURS_D_ACTEURS,
    DonneeSocle,
    Socle,
    famille_de_l_unite,
    unite_lisible,
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

    Celle qui place le PLUS GRAND montant entre 1 et 1 000. C'est la borne qui
    garantit qu'aucun nombre ne devient illisible.

    Deux règles ont été essayées avant, et chacune a échoué à l'usage :

    - l'échelle du plus grand montant, prise au sens « ≥ facteur » : un TAM à
      1,2 Md€ s'affichait « 1,2 » et le SOM « 0,0018 ». Deux valeurs sur trois
      sous l'unité ;
    - celle qui laisse le plus de valeurs au-dessus de l'unité : mesurée le
      05/08/2026 sur le livrable réel, elle a choisi le millier d'euros pour un
      entonnoir mondial, et la première marche est sortie en **`3.2e+11 kEUR`**.
      Optimiser la lisibilité des petites valeurs au prix d'une notation
      scientifique sur les grandes, c'est déplacer le défaut, pas le corriger.

    Un entonnoir dont la dernière marche est un millionième de la première
    reste écrasé — c'est la donnée qui le veut, pas le rendu. Mais aucun de ses
    chiffres n'est illisible, et c'est ce qu'on peut garantir.
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
    sommet = max(abs(valeur) for valeur in bases) or 1.0
    # La plus grande magnitude qui laisse le sommet au-dessus de 1 : il tombe
    # donc dans [1, 1000[ et ne part jamais en notation scientifique.
    prefixe, facteur = next(
        (
            (nom, valeur) for nom, valeur in _MAGNITUDES_AFFICHAGE
            if sommet >= valeur
        ),
        _MAGNITUDES_AFFICHAGE[-1],
    )
    return [valeur / facteur for valeur in bases], f"{prefixe}{devise}"


def _suffixe(unite: str) -> str:
    """Unité accolée à une valeur, écrite POUR LE LECTEUR.

    `unite_lisible` est la source unique : `MdEUR` devient `Md€` ici comme dans
    la ligne du socle injectée au prompt. Deux traductions de la même notation
    auraient fini par diverger, et le document aurait porté les deux (règle 5).
    """
    if unite == "%":
        return ""
    lisible = unite_lisible(unite)
    return f" {lisible}" if lisible else ""


def _valeur_lisible(valeur: float, unite: str) -> str:
    """Un montant écrit à SON échelle, comme un analyste l'écrirait.

    « 600 k€ », pas « 0,0006 Md€ ». Réservé aux figures sans axe commun —
    l'entonnoir — où rien n'oblige deux marches à partager une unité.

    Une grandeur non monétaire traverse inchangée : un pourcentage n'a pas de
    magnitude, et lui en chercher une produirait des « 0,055 k% ».
    """
    decompose = _decomposer(unite)
    if decompose is None:
        return f"{valeur:g}{_suffixe(unite)}"

    magnitude_source, devise = decompose
    base = valeur * dict(_MAGNITUDES_AFFICHAGE)[magnitude_source]
    for prefixe, facteur in _MAGNITUDES_AFFICHAGE:
        if abs(base) >= facteur:
            return f"{base / facteur:g} {unite_lisible(f'{prefixe}{devise}')}"
    return f"{base:g} {unite_lisible(devise)}"


def _decomposer(unite: str) -> tuple[str, str] | None:
    """`MdEUR` -> (`Md`, `EUR`), en s'appuyant sur le socle et pas sur une copie."""
    from ..socle.schema import valeur_en_unites_de_base  # noqa: PLC0415

    converti = valeur_en_unites_de_base(1.0, unite)
    if converti is None:
        return None
    facteur, devise = converti
    for prefixe, valeur in _MAGNITUDES_AFFICHAGE:
        if abs(facteur - valeur) < 1e-9:
            return prefixe, devise
    return "", devise


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
        # **Chaque marche porte SA propre échelle.** Un entonnoir n'a pas d'axe
        # commun : rien n'oblige ses cinq marches à partager une unité, et
        # beaucoup les sépare. Mesuré sur le livrable `4b827759` : du marché
        # mondial au marché atteignable, six ordres de grandeur — la dernière
        # marche s'affichait « 0.0006 MdEUR » là où un analyste écrit « 600 k€ ».
        affichees = [
            _valeur_lisible(valeur, unite) for _nom, valeur in paires
        ]
        return Resolution(
            type_demande,
            {"etapes": paires, "unite": _suffixe(unite),
             "valeurs_affichees": affichees},
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

    ## Le radical d'identifiant passe AVANT le périmètre

    Le périmètre suffisait tant que les seules trajectoires étaient
    géographiques : mondial, national — un périmètre, une série. Le
    prévisionnel d'un business plan casse cette hypothèse : `ca_previsionnel`,
    `resultat_net` et `tresorerie_fin` partagent TOUS le périmètre ENTREPRISE.
    Groupés par périmètre, leurs points s'écrasent mutuellement
    (`groupes[cle][annee] = valeur` — même clé, même année) : une figure
    « CA vs résultat sur trois exercices » rendait UNE série aux valeurs
    mélangées, sans qu'aucune erreur ne le dise.

    D'où la convention `<serie>_anN` du référentiel : une donnée qui la porte
    est groupée par son RADICAL (`ca_previsionnel_an2` → `ca_previsionnel`),
    les autres retombent sur le périmètre. Les deux mondes coexistent dans une
    même figure — « marché national vs CA du projet » groupe l'un par
    périmètre, l'autre par radical.
    """
    groupes: dict[str, dict[int, float]] = {}
    noms: dict[str, str] = {}
    for donnee, valeur in zip(donnees, valeurs, strict=True):
        serie = _RADICAL_ANNUEL.match(donnee.id)
        cle = serie.group("radical") if serie else str(donnee.perimetre)
        groupes.setdefault(cle, {})[donnee.annee] = valeur
        # Le nom de la série vient de sa première donnée — délestée de son
        # « — exercice N » pour une série annuelle : la série couvre les trois
        # exercices, son nom ne doit pas en désigner un seul.
        noms.setdefault(cle, _SUFFIXE_EXERCICE.sub("", etiquette_de(donnee)))

    series: list[tuple[str, list[float]]] = []
    for cle, points in groupes.items():
        if len(points) != len(annees):
            continue
        series.append((noms[cle], [points[annee] for annee in annees]))
    return series


#: La convention d'identifiant des séries annuelles d'entreprise, déclarée au
#: référentiel (`socle/referentiel.py`, section business plan) et verrouillée
#: par `test_referentiels_bp_et_str` : c'est la MÊME vérité aux deux bouts
#: (règle 5). Le motif accepte tout exercice à un ou deux chiffres.
_RADICAL_ANNUEL = re.compile(r"^(?P<radical>.+)_an\d{1,2}$")

#: « — exercice N » en fin d'étiquette, tiret cadratin ou simple, accents ou
#: non : la classe entière plutôt que la forme exacte de nos libellés (règle 4).
_SUFFIXE_EXERCICE = re.compile(r"\s*[—–-]\s*exercice\s+\d{1,2}\s*$", re.IGNORECASE)


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
    """Radar : plusieurs critères notés sur une même échelle.

    Deux matières possibles, et la grille passe en premier. Un chapitre qui
    cite des critères compare des ACTEURS sur ces axes — c'est la figure que
    six abandons de `5892daa5` réclamaient sans pouvoir l'obtenir, faute de
    notes dans le socle. À défaut, on retombe sur des identifiants chiffrés
    notés, qui décrivent un seul profil.
    """
    criteres = _criteres_cites(socle, identifiants)
    if criteres:
        return _radar_des_acteurs(
            socle, type_demande, criteres, _acteurs_cites(socle, identifiants)
        )

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


def _radar_des_acteurs(
    socle: Socle,
    type_demande: str,
    criteres: Sequence[Any],
    acteurs: Sequence[str] | None = None,
) -> Resolution:
    """Un axe par critère, une série par concurrent noté sur tous.

    `acteurs` dit LESQUELS. Sans lui, quatre radars de chapitres différents —
    les huit directs, puis les trois indirects — rendaient exactement la même
    image, et celui qui s'annonçait « indirects » affichait des directs.
    """
    if len(criteres) < 3:
        return Resolution(
            motif="un radar exige au moins trois axes ; "
            f"{len(criteres)} critère(s) cité(s)"
        )
    codes = [critere.code for critere in criteres]
    notes = socle.notes_sur(codes, acteurs=acteurs)
    if not notes:
        intitules = ", ".join(f"« {c.intitule} »" for c in criteres)
        precision = f" parmi {', '.join(acteurs)}" if acteurs else ""
        return Resolution(
            motif=f"aucun acteur{precision} n'est noté sur TOUS ces critères : "
            f"{intitules}"
        )

    retenus, motif = notes[:_SERIES_RADAR_MAX], ""
    if len(notes) > _SERIES_RADAR_MAX:
        ecartes = ", ".join(nom for nom, _ in notes[_SERIES_RADAR_MAX:])
        motif = (
            f"{len(notes)} acteurs notés, {_SERIES_RADAR_MAX} tracés : un radar "
            f"plus chargé ne se lit plus. Non tracés — {ecartes}."
        )

    return Resolution(
        type_demande,
        {"axes_noms": [critere.intitule for critere in criteres],
         "series": [(nom, valeurs) for nom, valeurs in retenus],
         "maximum": 5.0},
        motif=motif,
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


#: Séries au-delà desquelles un radar devient un plat de spaghettis.
#:
#: Onze concurrents superposés sur cinq axes ne se lisent pas. La borne est
#: basse volontairement : au-delà, la comparaison qui justifie le radar
#: disparaît sous les traits.
_SERIES_RADAR_MAX = 5


#: Sélecteurs d'acteurs qu'un chapitre peut citer parmi ses identifiants.
#: Écrits comme les codes de critères, ils disent QUELS concurrents la figure
#: compare — sans obliger le chapitre à recopier onze noms.
#: Repris du socle, jamais recopié : c'est lui qui décide de ce qu'un chapitre
#: a le droit d'écrire, et deux tables auraient divergé — elles l'ont fait le
#: 13/08/2026, quand `projet` est entré dans le vocabulaire d'un côté seulement.
_SELECTEURS_D_ACTEURS = SELECTEURS_D_ACTEURS


def _acteurs_cites(socle: Socle, identifiants: Sequence[str]) -> list[str] | None:
    """Les acteurs que la figure doit comparer, ou `None` pour tous.

    ## Le défaut que cette fonction répare

    Rien ne permettait à un chapitre de dire QUELS concurrents sa figure
    compare. Toute figure d'acteurs prenait donc la liste entière et gardait
    les premiers : quatre radars — chapitres 1, 2.3, 7.6, 7.7 — rendaient la
    MÊME image, et celui qui s'annonçait « concurrents indirects » affichait
    des directs. Signalé par la cliente le 11/08/2026 ; le résolveur écrit le
    matin même n'avait aucun moyen de faire autrement.

    Deux écritures acceptées, parce que les deux sont naturelles : un
    sélecteur (`directs`, `indirects`) ou les NOMS des acteurs voulus. Un nom
    inconnu du socle est ignoré — le chapitre ne peut pas inventer un
    concurrent par ce chemin.
    """
    voulus: list[str] = []
    designe = False
    connus = {a.nom.casefold(): a.nom for a in socle.concurrents}
    codes = {c.code.casefold() for c in socle.grille_notation}
    for identifiant in identifiants:
        cle = identifiant.strip().casefold()
        type_ = _SELECTEURS_D_ACTEURS.get(cle)
        if type_ is not None:
            designe = True
            voulus.extend(socle.acteurs_du_type(type_))
            continue
        if cle in connus:
            designe = True
            voulus.append(connus[cle])
            continue
        # Ni sélecteur, ni acteur connu, ni code de critère, ni donnée du
        # socle : le chapitre DÉSIGNAIT quelqu'un — un nom mal orthographié,
        # un acteur absent de la base. On le retient comme une intention.
        if cle not in codes and cle not in {i.casefold() for i in socle.identifiants}:
            designe = True

    retenus = list(dict.fromkeys(voulus))
    if retenus:
        # L'ENTREPRISE DU DOSSIER S'AJOUTE TOUJOURS.
        #
        # Demande de la cliente du 13/08/2026 : « tout graphique de benchmark,
        # positionnement, matrice concurrentielle ou radar destiné à comparer
        # les acteurs doit obligatoirement intégrer l'entreprise étudiée comme
        # point de référence ».
        #
        # La consigne le dit au rédacteur, et ce n'est pas suffisant : `directs`
        # rend les huit directs, un point c'est tout. La figure ne porterait
        # l'entreprise que les fois où le modèle pense à la nommer — c'est-à-dire
        # la plupart des fois, et pas toutes. On le fait ici, où c'est
        # mécanique : un lecteur qui regarde un benchmark cherche d'abord où il
        # se trouve, et une figure sur deux qui l'oublie est un défaut de plus à
        # relire.
        projet = socle.acteurs_du_type("projet")
        retenus.extend(nom for nom in projet if nom not in retenus)
        return retenus
    # Distinguer « aucun sélecteur » de « sélecteurs tous inconnus » : le
    # premier veut tous les acteurs, le second ne veut sûrement pas ceux
    # qu'on lui donnerait. Rendre la liste entière à un chapitre qui a
    # nommé quelqu'un, c'est produire la figure au titre menteur — le
    # défaut même qu'on répare.
    return [] if designe else None


def _criteres_cites(socle: Socle, identifiants: Sequence[str]) -> list[Any]:
    """Les critères de la grille cités par le chapitre, dans l'ordre donné.

    L'ordre compte : sur une carte de positionnement, le premier critère est
    l'abscisse et le second l'ordonnée. C'est le chapitre qui décide de la
    lecture, pas l'ordre de déclaration du socle.
    """
    trouves = [socle.critere(code) for code in identifiants]
    return [critere for critere in trouves if critere is not None]


def _matrice(
    socle: Socle, type_demande: str, identifiants: Sequence[str]
) -> Resolution:
    """Carte de positionnement : des concurrents notés, ou des risques.

    Le premier cas est arrivé après coup. Ce résolveur ne savait placer QUE des
    risques, sur des axes « Probabilité » et « Impact » écrits en dur — alors
    qu'une étude concurrentielle demande naturellement de positionner ses
    acteurs. Sur `5892daa5` (10/08/2026), cinq figures ont été abandonnées pour
    « le socle ne porte pas deux risques notés » : le modèle demandait de
    placer huit concurrents, et on lui répondait qu'il manquait des risques.

    Un chapitre qui cite des critères de la grille est donc en mode
    concurrents, et n'y échappe plus : se rabattre sur les risques dessinerait
    une figure juste répondant à une autre question, ce que le lecteur ne peut
    pas deviner (règle 3).
    """
    criteres = _criteres_cites(socle, identifiants)
    if criteres:
        if len(criteres) < 2:
            return Resolution(
                motif="une carte de positionnement demande DEUX critères de la "
                f"grille ; un seul est cité : « {criteres[0].intitule} »"
            )
        abscisse, ordonnee = criteres[0], criteres[1]
        notes = socle.notes_sur(
            [abscisse.code, ordonnee.code],
            acteurs=_acteurs_cites(socle, identifiants),
        )
        if len(notes) < 2:
            return Resolution(
                motif="moins de deux acteurs sont notés à la fois sur "
                f"« {abscisse.intitule} » et « {ordonnee.intitule} » ; "
                "aucune comparaison à dessiner"
            )
        return Resolution(
            type_demande,
            {"points": [(nom, valeurs[0], valeurs[1]) for nom, valeurs in notes],
             "axe_x": abscisse.intitule, "axe_y": ordonnee.intitule},
        )

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


def _chaleur(
    socle: Socle, type_demande: str, identifiants: Sequence[str]
) -> Resolution:
    """Carte de chaleur : des acteurs notés par critère, ou des risques.

    Le premier mode manquait, et c'est le correctif du matin qui l'a montré :
    j'avais étendu la carte de positionnement et le radar aux critères de la
    grille, PAS la carte de chaleur — l'exemple, pas la classe (règle 4,
    troisième résolveur sur trois). Le chapitre 3 de `6cb0fab3` a perdu sa
    « criticité concurrentielle par critère noté » sur le motif des risques,
    alors que le socle portait onze acteurs notés sur cinq critères.
    """
    criteres = _criteres_cites(socle, identifiants)
    if len(criteres) >= 2:
        codes = [critere.code for critere in criteres]
        notes = socle.notes_sur(codes, acteurs=_acteurs_cites(socle, identifiants))
        if len(notes) < 2:
            return Resolution(
                motif="moins de deux acteurs sont notés sur tous les critères "
                "cités ; une carte de chaleur à une ligne ne compare rien"
            )
        return Resolution(
            type_demande,
            {"lignes": [nom for nom, _ in notes],
             "colonnes": [critere.intitule for critere in criteres],
             "valeurs": [valeurs for _, valeurs in notes]},
        )

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
