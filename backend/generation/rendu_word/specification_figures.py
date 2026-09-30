"""Une figure dit ce que ses données disent : contrôle de la SPÉCIFICATION, avant le dessin.

## Le défaut, mesuré

Business plan ÉCLORE `28a257bf`, 30/09/2026. Le gate de livraison listait des
conversions comme celles-ci :

    Structure du chiffre d'affaires par univers, 2027 et 2029 :
        barres_empilees → barres (une seule dimension : rendu en barres simples)
    Montée en charge du chiffre d'affaires sur les trois phases :
        aires → courbes (une seule série)
    Structure de l'investissement de démarrage par famille de besoin :
        barres_empilees → barres

Chaque conversion était juste — les données n'avaient qu'une dimension. Mais
le TITRE restait, et promettait un découpage « par univers » que la figure ne
portait pas : le même chiffre d'affaires à deux dates, sous un titre qui en
annonçait la structure. Rien ne comparait le titre aux données : les
résolveurs ne voient que la forme demandée et les identifiants.

## Les règles du client (30/09/2026), et où chacune vit

Sur les DONNÉES d'une forme — dans les résolveurs (`donnees_graphiques`), pour
que la réparation, la complétion, le catalogue proposé au modèle et le
jugement du chapitre les appliquent aussi, sans seconde description :

1. même unité et même ordre de grandeur (rapport max/min < 1 000) ;
2. pas d'anneau, de camembert, d'aires ni de barres empilées qui additionnent
   des grandeurs non additives (flux et stocks, marché et apport) ;
4. pas deux barres égales ;
6. l'entreprise du dossier n'est jamais coupée par le plafond de séries ;
7. les libellés sont repliés, jamais tronqués (`donnees_graphiques.replier`,
   et `graphiques._replier_le_nom` pour la carte de positionnement).

Sur le TITRE et la LÉGENDE — ici, parce que les résolveurs ne les voient pas :

3. « par X », « répartition », « structure » exigent au moins deux séries ou
   catégories — trois en anneau ou en camembert ;
5. les années du titre sont des années des données, et la légende d'une
   série ne la date pas d'une seule année ;
6. si le titre ou la légende nomme le projet, il est dans les séries ;
7. aucun libellé affiché ne finit par « … », aucun ne se confond avec un autre
   du même axe.

## La chaîne de repli

Résolution → réparation (`reparation_figures`, dans l'assemblage) → contrôle
de spécification ici → RE-DÉRIVATION depuis la spécification (les mêmes
données, le même titre, une autre forme) → sinon TABLEAU. Le tableau ne reprend
pas en légende un titre jugé faux : il imprimerait la promesse que la figure ne
tenait pas.

Une figure ne paie JAMAIS une reprise de chapitre à elle seule
(`runner._motifs_de_figure`, décision du 13/09/2026) : ses écarts voyagent avec
une reprise décidée pour une autre raison ; sinon l'assemblage applique la
chaîne ci-dessus.

## Ce que ce contrôle ne sait pas faire

Vérifier que les catégories d'un « par univers » sont bien des UNIVERS : les
noms des univers ne sont écrits nulle part ailleurs que dans le titre. Il
vérifie qu'il y a un découpage — au moins deux grandeurs distinctes —, pas
qu'il est le bon.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..socle.schema import DonneeSocle, Socle
from .donnees_graphiques import (
    FORMES_DE_PARTS,
    Resolution,
    _criteres_cites,
    radical_de,
    resoudre,
)


@dataclass(frozen=True)
class Ecart:
    """Un écart entre ce que la figure annonce et ce qu'elle porte.

    `regle` : `titre`, `forme`, `periode`, `legende`, `projet`, `libelle` ou
    `calendrier`.
    """

    regle: str
    motif: str


#: Les écarts qui disent que le TITRE ment : le tableau de repli ne le reprend
#: pas. La LÉGENDE des séries n'en fait pas partie : c'est notre code qui
#: l'écrit (`series_par_perimetre`), et une légende fautive ne rend pas faux le
#: titre écrit par le chapitre (revue du 30/09/2026).
_REGLES_DU_TITRE = frozenset({"titre", "periode", "projet", "calendrier"})


@dataclass(frozen=True)
class Controle:
    """Ce qu'il advient d'une figure après le contrôle de sa spécification."""

    resolution: Resolution
    ecarts: tuple[Ecart, ...] = ()
    #: Vrai si la figure a été redessinée sous une autre forme, depuis sa
    #: spécification, pour tenir les règles.
    rederivee: bool = False
    #: Vrai si ce que la figure dessinait ne venait PAS des identifiants
    #: demandés : la frise dessine les tendances, la carte des risques les
    #: risques, quels que soient les identifiants cités.
    matiere_hors_demande: bool = False

    @property
    def motif(self) -> str:
        return " ; ".join(ecart.motif for ecart in self.ecarts)

    @property
    def titre_en_cause(self) -> bool:
        return any(ecart.regle in _REGLES_DU_TITRE for ecart in self.ecarts)

    @property
    def sans_tableau(self) -> bool:
        """Aucun tableau ne remplace une figure dont les données ne sont pas citées.

        Le tableau de repli imprime les identifiants DEMANDÉS. Pour un
        calendrier du projet (29/09/2026), ou une frise et une carte des
        risques refusées ici, ce seraient des chiffres sans rapport avec ce
        que la figure montrait — sous un titre qui ne leur correspond pas.
        """
        return bool(self.ecarts) and (
            self.matiere_hors_demande
            or any(ecart.regle == "calendrier" for ecart in self.ecarts)
        )


#: Les formes essayées, dans l'ordre, quand une figure échoue à son contrôle :
#: les MÊMES données sous le MÊME titre, autrement dessinées. Seules les parts
#: ont une autre forme honnête — une répartition en deux parts se lit en
#: barres. Un titre qui promet ce que les données n'ont pas, une année absente,
#: un projet non noté : aucune forme ne le répare, et c'est le tableau.
_REDERIVATIONS: dict[str, tuple[str, ...]] = {
    "camembert": ("barres",),
    "anneau": ("barres",),
}

def _matiere_hors_demande(
    socle: Socle, type_graphique: str, identifiants: Sequence[str],
) -> bool:
    """Ce que la figure dessine ne vient-il PAS des identifiants demandés ?

    La frise dessine les tendances du socle ; la carte de positionnement, sans
    critère cité, les risques ; la carte de chaleur aussi, sous deux critères.
    Les mêmes seuils que les résolveurs (`donnees_graphiques._matrice`,
    `_chaleur`) : une autre lecture serait une seconde vérité (règle 5).
    """
    if type_graphique == "chronologie":
        return True
    criteres = _criteres_cites(socle, identifiants)
    if type_graphique == "matrice_positionnement":
        return not criteres
    if type_graphique == "carte_chaleur":
        return len(criteres) < 2
    return False


def controler_la_figure(
    socle: Socle,
    resolution: Resolution,
    *,
    identifiants: Sequence[str],
    titre: str,
    legende: str = "",
) -> Controle:
    """Contrôle la spécification d'une figure résolue ; la re-dérive si elle échoue.

    Rend la figure telle quelle si elle tient ; redessinée sous une autre forme
    si une forme la fait tenir ; sinon une résolution REFUSÉE dont le motif dit
    pourquoi — l'appelant imprime alors ses données en tableau.
    """
    if not resolution.retenu:
        return Controle(resolution)
    ecarts = ecarts_de_specification(
        socle, resolution, identifiants=identifiants, titre=titre, legende=legende,
    )
    if not ecarts:
        return Controle(resolution)
    hors_demande = _matiere_hors_demande(socle, resolution.type_graphique, identifiants)
    motif = " ; ".join(ecart.motif for ecart in ecarts)
    if not any(ecart.regle == "calendrier" for ecart in ecarts):
        for forme in _REDERIVATIONS.get(resolution.type_graphique, ()):
            essai = resoudre(socle, forme, identifiants)
            if essai.retenu and not ecarts_de_specification(
                socle, essai, identifiants=identifiants, titre=titre, legende=legende,
            ):
                deja = f"{resolution.motif} ; " if resolution.motif else ""
                return Controle(
                    Resolution(
                        essai.type_graphique, essai.donnees,
                        motif=f"{deja}{motif} — rendu en {essai.type_graphique}",
                        converti=True,
                    ),
                    tuple(ecarts),
                    rederivee=True,
                )
    return Controle(
        Resolution(motif=motif), tuple(ecarts), matiere_hors_demande=hors_demande,
    )


def ecarts_de_specification(
    socle: Socle,
    resolution: Resolution,
    *,
    identifiants: Sequence[str],
    titre: str,
    legende: str = "",
) -> list[Ecart]:
    """Tout ce qui sépare ce que la figure ANNONCE de ce qu'elle PORTE."""
    if resolution.donnees is None:
        return []
    if resolution.type_graphique == "chronologie" and annonce_un_calendrier_du_projet(titre):
        return [Ecart("calendrier", (
            f"le titre annonce un calendrier du projet (« {titre} ») et la frise "
            "ne sait dessiner que les tendances de marché du socle : rien n'est "
            "dessiné sous ce titre"
        ))]
    return [
        *_ecarts_de_decoupage(socle, resolution, identifiants, titre),
        *_ecarts_de_periode(socle, resolution, identifiants, titre),
        *_ecarts_de_projet(socle, resolution, identifiants, f"{titre}\n{legende}"),
        *_ecarts_de_libelles(resolution),
    ]


# ── Le calendrier du projet (déplacé d'`assemblage`, 30/09/2026) ─────────────

#: Un titre qui annonce le CALENDRIER DU PROJET. La frise ne sait dessiner que
#: les tendances de marché du socle (`donnees_graphiques._frise`), quels que
#: soient les identifiants demandés : il n'existe aucune donnée « calendrier ».
#: Business plan ÉCLORE, 29/09/2026 : un « rétroplanning » affichait des
#: tendances de marché (§ 3.12 du diagnostic). C'était le premier contrôle du
#: titre contre les données ; il vit désormais avec les autres.
#:
#: Le mot du calendrier SEUL ne suffit pas : « Calendrier des évolutions
#: réglementaires », « Jalons du marché » sont des frises de tendances
#: légitimes, et la première version les refusait sans repli (revue du
#: 29/09/2026). Il faut une marque du PROJET : un mot qui n'existe que pour
#: lui (rétroplanning, plan d'action), ou un mot du calendrier ET « du
#: projet », « de lancement », « de mise en œuvre ».
_CALENDRIER_DU_PROJET = re.compile(
    r"r[ée]tro[-\s]?planning|\bplans?\s+d['’]actions?\b", re.IGNORECASE,
)
_MOT_DU_CALENDRIER = re.compile(
    r"planning|calendrier|\bjalons?\b|[ée]ch[ée]ancier|chronogramme|\bgantt\b|"
    r"feuille\s+de\s+route|\broadmap\b|phasage|\b[ée]tapes?\b",
    re.IGNORECASE,
)
_MARQUE_DU_PROJET = re.compile(
    r"\bdu\s+projet\b|\bde\s+lancement\b|\bde\s+mise\s+en\s+(?:œuvre|oeuvre)\b",
    re.IGNORECASE,
)


def annonce_un_calendrier_du_projet(titre: str) -> bool:
    """Ce titre promet-il le calendrier DU PROJET, que la frise ne sait pas tracer ?"""
    return bool(
        _CALENDRIER_DU_PROJET.search(titre)
        or (_MOT_DU_CALENDRIER.search(titre) and _MARQUE_DU_PROJET.search(titre))
    )


# ── Règle 3 : le titre correspond aux données ────────────────────────────────

#: Les noms qui promettent un DÉCOUPAGE : « Structure du chiffre d'affaires »,
#: « Répartition des charges », « Mix produit ». Une figure qui n'a qu'une
#: grandeur ne découpe rien.
#:
#: « Structure » seulement comme NOM DU DÉCOUPAGE — suivi de ce qu'il découpe
#: (« structure du chiffre d'affaires »), jamais comme complément : « charges
#: de structure », « frais de structure » désignent les charges fixes, une
#: seule grandeur, et la première version refusait leur trajectoire (revue du
#: 30/09/2026).
_MOT_DE_DECOUPAGE = re.compile(
    r"\b(?P<mot>r[ée]partition|ventilation|d[ée]composition|composition|mix|"
    r"segmentation)\b"
    r"|(?<!\bde\s)\b(?P<structure>structure)(?=\s+(?:du|de|des|d['’]))",
    re.IGNORECASE,
)

#: « par univers », « par famille de besoin », « par type d'offre » : un
#: découpage s'écrit avec un nom NU. Suivi d'un déterminant (« par le projet »,
#: « par l'Insee ») ou d'un nom propre (« par Atelier Brume »), « par »
#: introduit un complément d'agent — qui a produit, estimé, réalisé —, pas un
#: découpage. La première version prenait l'article dans le motif : « chiffre
#: d'affaires généré par le projet » envoyait une trajectoire en tableau (revue
#: du 30/09/2026).
_PAR = re.compile(r"\bpar\s+(?P<objet>[^\W\d_][^\W_]*)", re.IGNORECASE)

#: Ce qui fait de « par » un complément d'agent : un déterminant, ou l'entité
#: même que l'étude décrit.
_DETERMINANTS = frozenset({
    "le", "la", "les", "l", "un", "une", "des", "du", "d", "son", "sa", "ses",
    "leur", "leurs", "ce", "cet", "cette", "ces", "notre", "nos", "votre", "vos",
    "projet", "entreprise",
})

#: « par » suivi d'une UNITÉ de compte : un taux (« dépense par habitant »,
#: « panier par visite ») ou une locution (« par rapport à »), pas un
#: découpage. Liste de garde seulement : un « par X » dont le X figure dans le
#: libellé d'une donnée tracée décrit cette grandeur, et n'est pas non plus un
#: découpage — c'est cette seconde règle qui porte la classe.
_PAR_UNITE = frozenset({
    "rapport", "exemple", "ailleurs", "consequent", "defaut", "nature",
    "principe", "hypothese", "construction",
    "an", "mois", "jour", "semaine", "heure", "minute",
    "habitant", "client", "personne", "tete", "foyer", "menage", "salarie",
    "collaborateur", "employe", "visite", "visiteur", "commande", "transaction",
    "achat", "unite", "piece", "article", "m²", "m2", "metre", "km", "place",
    "couvert", "nuitee", "utilisateur", "abonne", "adherent", "eleve", "patient",
    "lead", "prospect", "contact", "participant", "inscrit", "stagiaire",
    "apprenant", "membre", "beneficiaire",
})

#: Un découpage DANS LE TEMPS : il exige au moins deux dates, pas deux grandeurs.
_PAR_PERIODE = frozenset({
    "annee", "exercice", "trimestre", "semestre", "periode", "phase", "horizon",
    "millesime", "date",
})


def _plat(texte: str) -> str:
    """Sans accents, en minuscules : « Année » et « annee » sont le même mot."""
    decompose = unicodedata.normalize("NFKD", texte.casefold())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _formes(mot: str) -> set[str]:
    """Le mot à plat, et son singulier : « mois » reste « mois », « canaux » a « canau ».

    Tester le seul singulier rendait « mois » en « moi » et « ailleurs » en
    « ailleur » : deux entrées de `_PAR_UNITE` ne correspondaient jamais (revue
    du 30/09/2026).
    """
    plat = _plat(mot)
    return {plat, plat[:-1] if len(plat) > 3 and plat.endswith(("s", "x")) else plat}


def _promesse_de_decoupage(
    socle: Socle, titre: str, traces: Sequence[DonneeSocle],
) -> tuple[str, bool] | None:
    """(ce qui promet un découpage, s'il est temporel), ou `None`."""
    libelles = _plat(" ".join(donnee.libelle for donnee in traces))
    acteurs = [_plat(a.nom) for a in socle.concurrents if a.nom.strip()]
    for trouve in _PAR.finditer(titre):
        brut = trouve.group("objet")
        formes = _formes(brut)
        suite = _plat(titre[trouve.start("objet"):])
        if (
            brut[:1].isupper()  # un nom propre, une source, une enseigne
            or formes & _DETERMINANTS
            or any(suite.startswith(nom) for nom in acteurs)
            or formes & _PAR_UNITE
            or any(re.search(rf"\b{re.escape(forme)}", libelles) for forme in formes)
        ):
            continue
        return trouve.group(0), bool(formes & _PAR_PERIODE)
    nom = _MOT_DE_DECOUPAGE.search(titre)
    if nom is None:
        return None
    return nom.group("mot") or nom.group("structure"), False


def _ecarts_de_decoupage(
    socle: Socle, resolution: Resolution, identifiants: Sequence[str], titre: str,
) -> list[Ecart]:
    traces = _donnees_tracees(socle, identifiants)
    promesse = _promesse_de_decoupage(socle, titre, traces)
    if promesse is None:
        return []
    mot, temporel = promesse
    annees = _annees_portees(socle, resolution, identifiants, traces)
    if temporel:
        if len(annees) >= 2:
            return []
        return [Ecart("titre", (
            f"le titre annonce un découpage dans le temps (« {mot} ») et la "
            "figure ne porte qu'une date"
        ))]
    membres = _membres(socle, resolution, identifiants, traces)
    if len(membres) < 2:
        seule = f" — {membres[0]} —" if membres else ""
        suivie = ", suivie dans le temps" if len(annees) > 1 else ""
        return [Ecart("titre", (
            f"le titre annonce un découpage (« {mot} ») et la figure ne porte "
            f"qu'une grandeur{seule}{suivie} : rien ne la découpe"
        ))]
    if resolution.type_graphique in FORMES_DE_PARTS and len(membres) < 3:
        # Le titre dit vrai ici : c'est la FORME qui ne tient pas. D'où une
        # règle à part — la re-dérivation en barres garde le titre.
        return [Ecart("forme", (
            f"une répartition (« {mot} ») en {resolution.type_graphique} exige au "
            f"moins trois parts, et la figure n'en a que {len(membres)}"
        ))]
    return []


def _donnees_tracees(socle: Socle, identifiants: Sequence[str]) -> list[DonneeSocle]:
    return [
        donnee for donnee in (socle.donnee(i) for i in dict.fromkeys(identifiants))
        if donnee is not None
    ]


def _est_une_annee(texte: object) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}", str(texte).strip()))


def _membres(
    socle: Socle,
    resolution: Resolution,
    identifiants: Sequence[str],
    traces: Sequence[DonneeSocle],
) -> list[str]:
    """Les grandeurs DISTINCTES que la figure montre, hors du temps.

    Deux exercices du même chiffre d'affaires sont UNE grandeur suivie dans le
    temps, pas deux catégories : c'est exactement ce qui trahissait « par
    univers » sur ÉCLORE. Pour les formes à séries, ce sont les séries telles
    que le résolveur les a formées ; pour les autres, les radicaux des
    données tracées (`donnees_graphiques.radical_de`, la même convention).
    """
    donnees: dict[str, Any] = resolution.donnees or {}
    if "series" in donnees:
        noms = [str(nom) for nom, _ in donnees["series"]]
        axe = donnees.get("etiquettes") or donnees.get("axes_noms") or []
        if axe and not all(_est_une_annee(item) for item in axe) and len(axe) > len(noms):
            return [str(item) for item in axe]
        return noms
    # Acteurs, risques, tendances : ce que la figure place n'est pas une donnée.
    for cle, rang in (("points", 0), ("jalons", 1)):
        if cle in donnees:
            return [str(item[rang]) for item in donnees[cle]]
    if "lignes" in donnees:
        return [str(ligne) for ligne in donnees["lignes"]]
    # Barres, parts, marches d'entonnoir, jauges tirées des DONNÉES : leurs
    # radicaux, quelle que soit la forme. Compter les marches par leur nom
    # laissait passer l'entonnoir « exercice 1 → exercice 2 » d'un même
    # chiffre d'affaires sous un titre de répartition (revue du 30/09/2026).
    if traces and not _criteres_cites(socle, identifiants):
        noms_par_radical: dict[str, str] = {}
        for donnee in traces:
            noms_par_radical.setdefault(radical_de(donnee.id), donnee.libelle)
        return list(noms_par_radical.values())
    for cle in ("etapes", "notes"):
        if cle in donnees:
            return [str(item[0]) for item in donnees[cle]]
    return [str(item) for item in donnees.get("etiquettes") or []]


# ── Règle 5 : la période annoncée est celle des données ──────────────────────

#: Une année : ni collée à une lettre (« RE2020 », une norme), ni à un chiffre.
_ANNEE = re.compile(r"(?<![^\W\d_])(?<!\d)(?:19|20)\d{2}(?!\d)")

#: Le mot qui précède une année, pour reconnaître un NOM PROPRE daté.
_MOT_PRECEDENT = re.compile(r"([^\W\d_][\w'’-]*)\s+$")


def _annees_citees(titre: str) -> set[int]:
    """Les années que le titre ANNONCE comme période.

    Une année portée par un nom propre — « Plan France 2030 », « Vision
    2030 » — nomme un programme, pas la période de la figure : précédée d'un
    mot à capitale qui n'ouvre pas le titre, elle n'est pas lue (revue du
    30/09/2026). Le premier mot du titre porte sa capitale de phrase :
    « Marché 2024 » annonce bien 2024.
    """
    annees: set[int] = set()
    for trouvee in _ANNEE.finditer(titre):
        avant = titre[: trouvee.start()]
        mot = _MOT_PRECEDENT.search(avant)
        if mot and mot.group(1)[:1].isupper() and avant[: mot.start()].strip():
            continue
        annees.add(int(trouvee.group(0)))
    return annees


def _annees_portees(
    socle: Socle,
    resolution: Resolution,
    identifiants: Sequence[str],
    traces: Sequence[DonneeSocle],
) -> set[int]:
    """Les années que la figure MONTRE — son axe du temps, ou ses données.

    Vide pour une figure d'acteurs ou de risques : elle ne porte pas de date,
    et rien ne permet d'y juger une année du titre. Les années des
    identifiants CITÉS ne comptent pas quand la figure dessine autre chose
    qu'eux — une carte des risques jugée sur des chiffres qu'elle ne montre
    pas partait sans tableau (revue du 30/09/2026).
    """
    donnees: dict[str, Any] = resolution.donnees or {}
    if "jalons" in donnees:
        return {int(a) for date, _ in donnees["jalons"] for a in _ANNEE.findall(str(date))}
    if _matiere_hors_demande(socle, resolution.type_graphique, identifiants):
        return set()
    axe = donnees.get("abscisses") or (
        donnees.get("etiquettes") if "series" in donnees else None
    )
    if axe and all(_est_une_annee(item) for item in axe):
        return {int(str(item).strip()) for item in axe}
    return {donnee.annee for donnee in traces}


def _ecarts_de_periode(
    socle: Socle, resolution: Resolution, identifiants: Sequence[str], titre: str,
) -> list[Ecart]:
    """Les années du titre et de la légende des séries contre celles de la figure.

    Le COMMENTAIRE sous la figure n'est pas lu ici : il s'imprime à la place de
    la source (`assemblage._blocs_graphique`), et l'année d'une source —
    « Insee 2024 » — n'est pas la période de la figure.
    """
    annees = _annees_portees(
        socle, resolution, identifiants, _donnees_tracees(socle, identifiants),
    )
    if not annees:
        return []
    portees = ", ".join(str(annee) for annee in sorted(annees))
    ecarts: list[Ecart] = []
    hors = sorted(_annees_citees(titre) - annees)
    if hors:
        ecarts.append(Ecart("periode", (
            f"le titre cite {', '.join(str(a) for a in hors)} et la figure porte "
            f"{portees} : la période annoncée n'est pas celle des données"
        )))
    donnees: dict[str, Any] = resolution.donnees or {}
    if len(annees) > 1 and "series" in donnees:
        # Garde-fou : la légende est écrite par NOTRE code, délestée de toute
        # année (`donnees_graphiques.series_par_perimetre`). Si une année y
        # reparaît, c'est la légende qui est fausse, pas le titre du chapitre :
        # règle `legende`, hors de `_REGLES_DU_TITRE`.
        for nom, _ in donnees["series"]:
            if _ANNEE.search(str(nom)):
                ecarts.append(Ecart("legende", (
                    f"la légende « {' '.join(str(nom).split())} » date d'une seule "
                    f"année une série qui couvre {portees}"
                )))
    return ecarts


# ── Règle 6 : le projet nommé est dans les séries ────────────────────────────

_PROJET_EN_TOUTES_LETTRES = re.compile(
    r"\bprojet\b|\bentreprise\s+[ée]tudi[ée]e\b", re.IGNORECASE,
)


def _nomme_le_projet(socle: Socle, texte: str) -> bool:
    if _PROJET_EN_TOUTES_LETTRES.search(texte):
        return True
    plat = _plat(texte)
    return any(
        re.search(rf"(?<!\w){re.escape(_plat(nom.strip()))}(?!\w)", plat)
        for nom in socle.acteurs_du_type("projet") if nom.strip()
    )


def _acteurs_affiches(resolution: Resolution) -> list[str]:
    donnees: dict[str, Any] = resolution.donnees or {}
    if "series" in donnees:
        return [str(nom) for nom, _ in donnees["series"]]
    if "points" in donnees:
        return [str(point[0]) for point in donnees["points"]]
    return [str(item) for item in donnees.get("lignes") or donnees.get("etiquettes") or []]


def _ecarts_de_projet(
    socle: Socle, resolution: Resolution, identifiants: Sequence[str], texte: str,
) -> list[Ecart]:
    """Une figure d'ACTEURS qui nomme le projet doit le montrer.

    Seules les figures qui comparent des acteurs — celles qui citent des
    critères de la grille — sont concernées : un radar de notes du projet seul
    (`donnees_graphiques._notes`) le trace par construction.
    """
    if not _criteres_cites(socle, identifiants) or not _nomme_le_projet(socle, texte):
        return []
    projet = socle.acteurs_du_type("projet")
    affiches = {_plat(nom) for nom in _acteurs_affiches(resolution)}
    if any(_plat(nom) in affiches for nom in projet):
        return []
    raison = (
        f"« {projet[0]} » n'est pas noté sur tous les critères de la figure"
        if projet else "l'entreprise du dossier n'est pas notée sur la grille"
    )
    return [Ecart("projet", (
        f"le titre ou la légende nomme le projet, et la figure ne le compare pas : {raison}"
    ))]


# ── Règle 7 : des libellés entiers et distincts ──────────────────────────────


def _axes_de_libelles(donnees: dict[str, Any]) -> list[list[str]]:
    """Les libellés affichés, AXE PAR AXE : un doublon ne se juge que sur un axe."""
    axes = [
        [str(item) for item in donnees.get(cle) or []]
        for cle in ("etiquettes", "axes_noms", "lignes", "colonnes")
    ]
    axes += [
        [str(item[0]) for item in donnees.get(cle) or []]
        for cle in ("series", "etapes", "notes", "points")
    ]
    axes.append([str(texte) for _, texte in donnees.get("jalons") or []])
    return [axe for axe in axes if axe]


def _ecarts_de_libelles(resolution: Resolution) -> list[Ecart]:
    ecarts: list[Ecart] = []
    for axe in _axes_de_libelles(resolution.donnees or {}):
        lisibles = [" ".join(libelle.split()) for libelle in axe]
        for libelle in lisibles:
            if libelle.endswith(("…", "...")):
                ecarts.append(Ecart("libelle", f"libellé tronqué : « {libelle} »"))
        for libelle, nombre in Counter(lisibles).items():
            if nombre > 1 and not _est_une_annee(libelle):
                ecarts.append(Ecart("libelle", (
                    f"{nombre} éléments portent le même libellé, « {libelle} » : "
                    "le lecteur ne peut pas les distinguer"
                )))
    return ecarts
