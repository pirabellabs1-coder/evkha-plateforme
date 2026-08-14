"""Contrat de sortie d'un chapitre (§6.1 du cahier des charges).

Un chapitre ne rend plus du texte libre : il rend une structure. C'est ce qui
permet de savoir, sans analyser une chaîne de caractères, quelles données du
socle il a utilisées et quels graphiques il déclare.

Conséquence directe : un graphique ne peut plus contredire le texte qu'il
illustre, puisqu'il ne porte pas de valeurs — il porte des identifiants du
socle, résolus au rendu.
"""
from __future__ import annotations

import logging
import re
from enum import Enum, StrEnum
from functools import lru_cache
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, Field, model_validator

_log = logging.getLogger(__name__)


def _differe_d_un_signe(a: str, b: str) -> bool:
    """`a` et `b` ne diffèrent-ils que d'une insertion, suppression ou substitution ?

    Distance d'édition bornée à un, écrite explicitement plutôt qu'empruntée à
    une similarité floue : un seuil de ressemblance se règle au jugé et dérive.
    « à un signe près » se raisonne, se teste, et ne rapproche jamais deux mots
    réellement distincts.
    """
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = 0
    ecart = False
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        if ecart:
            return False
        ecart = True
        if len(a) == len(b):
            i += 1
        j += 1
    return True


def rapprocher_les_cles(valeurs: Any, modele: type[BaseModel]) -> Any:
    """Rattache une clé inconnue au champ dont elle ne diffère que d'un signe.

    ## Le défaut

    Génération réelle `5ed4f03f`, 05/08/2026 : le modèle a écrit `intitulo` au
    lieu de `intitule` dans un titre de sous-section. Le contrat refuse les
    champs inconnus — à raison, c'est ce qui empêche un chapitre d'inventer sa
    structure — et l'étude est morte au chapitre 18, après **trois tentatives
    identiques** et 2,10 EUR, sur une faute de frappe d'une lettre.

    Trois fois la même : la reprise ne sauve pas ce cas, parce que le refus
    arrive à la validation du schéma, avant l'arbitrage de conformité. Et le
    motif rendu au modèle — « intitulo : Extra inputs are not permitted » —
    dit ce qui est refusé sans dire ce qui est attendu.

    ## Pourquoi accepter, et jusqu'où

    Une clé à un signe d'un champ connu ne porte aucune ambiguïté sur
    l'intention : c'est du TRANSPORT, pas du fond. Le geste est le même que
    `depuis_ancien_format` et que la forme aplatie des blocs — accepter une
    autre écriture du même contenu sans créer une seconde vérité.

    Ce qui reste refusé, et doit l'être : une clé qui ne ressemble à rien de
    connu, et une clé qui ressemble à DEUX champs à la fois. Dans les deux cas
    l'intention est incertaine, et deviner reviendrait à ranger du contenu
    sous un champ qui n'est pas le sien. Le contrat refuse alors, comme avant.

    On ne recouvre jamais une clé déjà présente : si le modèle a écrit les
    deux, la valeur juste est celle qu'il a nommée juste.
    """
    if not isinstance(valeurs, dict):
        return valeurs
    attendus = {
        champ.alias or nom for nom, champ in modele.model_fields.items()
    } | set(modele.model_fields)
    inconnues = [cle for cle in valeurs if cle not in attendus]
    if not inconnues:
        return valeurs

    corrige = dict(valeurs)
    for cle in inconnues:
        candidats = [
            attendu for attendu in attendus
            if _differe_d_un_signe(str(cle), attendu)
        ]
        if len(candidats) != 1:
            continue
        cible = candidats[0]
        if cible in corrige:
            # Le modèle a écrit les DEUX. La valeur juste est celle qu'il a
            # nommée juste ; l'autre est un doublon dont on ne peut rien dire.
            # On l'écarte plutôt que de laisser tomber le chapitre entier — et
            # on le DIT, parce qu'écarter du contenu en silence est le défaut
            # que ce dépôt paie le plus cher (règle 1).
            _log.warning(
                "Contrat %s : clé « %s » écartée, « %s » est déjà renseigné.",
                modele.__name__, cle, cible,
            )
            corrige.pop(cle)
            continue
        corrige[cible] = corrige.pop(cle)
    return corrige


class SortieDeChapitre(BaseModel):
    """Base des modèles du contrat : champs inconnus refusés, typos rattrapées.

    Le refus des champs inconnus est la garantie centrale du contrat — sans
    lui, un chapitre inventerait sa structure. Le rattrapage d'un signe ne
    l'affaiblit pas : il ne crée aucun champ, il en renomme un dont
    l'intention est certaine.
    """

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def _accepter_une_typo(cls, valeurs: Any) -> Any:
        return rapprocher_les_cles(valeurs, cls)


class TypeGraphique(StrEnum):
    """Types de visuels qu'un chapitre peut demander.

    Liste fermée : le moteur de rendu doit savoir dessiner chacun d'eux. Un
    type inconnu ferait échouer le rendu après coup, donc il est refusé ici.

    Cette liste doit rester exactement celle de `rendu_word.graphiques
    .RENDU_PAR_TYPE` (règle 5 : une seule source par vérité). Elle n'est pas
    dérivée par le code — un `StrEnum` construit dynamiquement priverait le
    reste du module de vérification statique —, mais un test compare les deux
    et échoue dès qu'elles divergent.

    **Le choix du type dépend du secteur d'activité**, pas du numéro de
    chapitre : voir `rendu_word.secteurs`, dont la consigne est injectée dans
    le prompt de chapitre.
    """

    BARRES = "barres"
    BARRES_HORIZONTALES = "barres_horizontales"
    BARRES_GROUPEES = "barres_groupees"
    BARRES_EMPILEES = "barres_empilees"
    COURBES = "courbes"
    AIRES = "aires"
    CAMEMBERT = "camembert"
    ANNEAU = "anneau"
    ENTONNOIR = "entonnoir"
    RADAR = "radar"
    JAUGES = "jauges"
    MATRICE_POSITIONNEMENT = "matrice_positionnement"
    CARTE_CHALEUR = "carte_chaleur"
    PYRAMIDE_AGES = "pyramide_ages"
    CHRONOLOGIE = "chronologie"


class Tableau(SortieDeChapitre):
    """Tableau de données porté par une section.

    Ajouté au lot 3. Le contrat initial ne prévoyait qu'un champ `contenu` en
    texte libre ; or la mesure du document de référence est sans appel :
    **52 % de ses mots vivent dans des tableaux**, et la médiane de ses
    paragraphes est de douze mots. Un chapitre qui ne rend que de la prose
    produit mécaniquement le mur de texte que la cliente a refusé.

    Le champ reste facultatif : les chapitres produits avant cet ajout restent
    valides et se rendent en prose.
    """

    model_config = {"extra": "forbid"}

    #: Neuf colonnes au maximum, et non six. Le plafond était à six ; le modèle
    #: de référence porte un tableau des opportunités commerciales à NEUF
    #: colonnes au chapitre 19 — cible, pays, offre, canal, partenaire,
    #: priorité, coût, délai, indicateur. Une contrainte qui interdit ce que le
    #: document validé contient est une contrainte fausse.
    entetes: list[str] = Field(min_length=2)
    lignes: list[list[str]] = Field(min_length=1)
    source: str = ""

    @model_validator(mode="before")
    @classmethod
    def _au_plus_neuf_colonnes(cls, valeurs: Any) -> Any:
        """Ramène le tableau à neuf colonnes plutôt que de perdre le chapitre.

        Neuf est une contrainte de LARGEUR DE PAGE : une dixième colonne sort
        de la feuille A4 et rend le tableau illisible. C'est donc un excédent
        de forme, exactement comme l'encadré à sept lignes qui a tué le
        chapitre 0 de `0f9fb13a` (11/08/2026) — et la réponse doit être la
        même : couper, journaliser, continuer.

        La coupe porte sur les en-têtes ET sur chaque ligne, sans quoi le
        tableau cesserait d'être rectangulaire et le validateur suivant
        refuserait ce que celui-ci vient de sauver.

        Elle a lieu AVANT la validation des champs : c'est la seule position
        d'où l'on peut désamorcer un plafond que Pydantic appliquerait sinon
        le premier.
        """
        if not isinstance(valeurs, dict):
            return valeurs
        entetes = valeurs.get("entetes")
        if not isinstance(entetes, list) or len(entetes) <= 9:
            return valeurs

        _log.warning(
            "Tableau : %s colonnes ramenées à 9. Retirées : %s",
            len(entetes), " | ".join(str(e) for e in entetes[9:]),
        )
        corrige = dict(valeurs)
        corrige["entetes"] = entetes[:9]
        lignes = corrige.get("lignes")
        if isinstance(lignes, list):
            corrige["lignes"] = [
                ligne[:9] if isinstance(ligne, list) else ligne for ligne in lignes
            ]
        return corrige

    @model_validator(mode="after")
    def _lignes_au_format_des_entetes(self) -> Tableau:
        """Complète une ligne trop courte au lieu de rejeter le chapitre entier.

        ## Le cas réel qui a changé cette règle

        Étude concurrentielle `5892daa5`, 09/08/2026, en production : « la ligne
        10 compte 8 cellules pour 9 colonnes déclarées ». Le chapitre 1 a été
        rejoué jusqu'à épuisement des tentatives et le dossier est mort, après
        avoir brûlé **0,76 EUR sur un seul chapitre** — quand l'étude
        concurrentielle complète de la veille en avait coûté 1,27 EUR pour dix.

        Une cellule manquante sur les quatre-vingt-dix d'un tableau. Le contenu
        des huit autres était bon.

        ## Pourquoi réparer, et pas refuser

        Le dépôt applique déjà ce principe à `raccourcir_le_resume` et à la
        typographie : **réparer quand la réparation atteint exactement le but
        que la règle poursuit**. La règle veut un tableau rectangulaire ; la
        compléter d'une cellule vide le rend rectangulaire. Rejouer un appel
        entier pour cela coûte six centimes et plusieurs minutes, et le modèle
        peut refaire la même étourderie — c'est ce qui vient d'arriver.

        Une cellule vide se voit dans le document et se corrige à la main. Un
        chapitre manquant, non.

        ## Ce qui reste refusé

        Une ligne PLUS LONGUE que ses en-têtes : on ne sait pas laquelle des
        cellules est en trop, et en choisir une au hasard détruirait de la
        donnée. Le refus reste le bon comportement quand la réparation devrait
        deviner (règle 2).
        """
        largeur = len(self.entetes)
        for rang, ligne in enumerate(self.lignes, start=1):
            if len(ligne) > largeur:
                msg = (
                    f"La ligne {rang} compte {len(ligne)} cellules pour "
                    f"{largeur} colonnes déclarées. Une cellule en trop ne peut "
                    "pas être retirée sans deviner laquelle."
                )
                raise ValueError(msg)
            if len(ligne) < largeur:
                ligne.extend([""] * (largeur - len(ligne)))
        return self


class Section(SortieDeChapitre):
    model_config = {"extra": "forbid"}

    titre: str = Field(min_length=1, max_length=220)
    contenu: str = Field(min_length=1)
    #: Tableau portant l'information de la section. Facultatif, mais c'est lui
    #: qui donne au livrable sa densité : voir `Tableau`.
    tableau: Tableau | None = None


class Graphique(SortieDeChapitre):
    """Demande de visuel. Ne porte AUCUNE valeur, seulement des identifiants.

    ## Pourquoi le champ s'appelle `type_graphique` dans le contrat

    Il s'appelait `type`, comme le discriminant du bloc qui le contient. Le même
    mot désignait donc deux choses emboîtées : la NATURE DU BLOC au niveau du
    dessus (« graphique »), et la NATURE DU VISUEL ici (« courbe », « barres »).

    Mesuré le 05/08/2026, génération réelle `6557b06b` : le modèle a résolu la
    collision tout seul, et de la seule façon possible — il a écrit
    `type_graphique` et remonté les champs d'un cran, produisant
    `{type: "graphique", type_graphique: …, titre: …}` au lieu de
    `{type: "graphique", graphique: {type: …, titre: …}}`. Trois fois de suite,
    sur deux chapitres : déterministe, pas un aléa. L'étude est morte au
    chapitre 1 pour 0,41 EUR.

    L'alias donne au contrat un nom qui ne se confond avec rien, et
    `populate_by_name` continue d'accepter `type` : les chapitres déjà en base
    restent lisibles, et le rendu lit toujours `graphique.type` en Python.
    """

    model_config = {"extra": "forbid", "populate_by_name": True}

    type: TypeGraphique = Field(alias="type_graphique")
    titre: str = Field(min_length=1, max_length=220)
    donnees_ids: list[str] = Field(min_length=1)
    commentaire: str = ""


class Encadre(SortieDeChapitre):
    """Encadré de synthèse fermant une analyse.

    C'est l'élément le plus répété du livrable de référence : une occurrence par
    chapitre sur quinze chapitres, sur le patron « Opportunité / Limite /
    Décision ». Il porte la méthode, pas de la décoration : c'est là que
    l'analyse devient une décision.

    L'intitulé était décrit ici comme « LECTURE EVKHA ». Cette docstring part
    dans le schéma de l'outil, donc dans la consigne du modèle : chaque vrai
    document aurait reproduit le nom de la plateforme, alors que le livrable est
    remis en marque blanche. L'intitulé reste libre — « Lecture du chapitre »,
    « À retenir », « Verdict » —, il ne nomme simplement personne.
    """

    model_config = {"extra": "forbid"}

    #: Cent-vingt caractères, et non quatre-vingts. Le plafond était à 80 ; le
    #: modèle de référence porte au chapitre 20 un encadré intitulé « FOCUS —
    #: Approfondissement demandé : marché international des galeries et du
    #: sur-mesure », soit 86 caractères. Une contrainte qui interdit ce que le
    #: document validé contient est une contrainte fausse.
    intitule: str = Field(min_length=1, max_length=120)
    lignes: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _au_plus_six_lignes(self) -> Encadre:
        """Garde les six premières au lieu de refuser le chapitre entier.

        ## Le cas réel qui a changé cette règle

        Stratégie `0f9fb13a` (11/08/2026), cliente : le chapitre 0 — la fiche
        projet, celle qui conditionne toute la génération — est mort sur

            blocs.14.encadre.encadre.lignes : List should have at most
            6 items after validation, not 7

        **Une ligne de trop.** Un chapitre entier, payé, correct par ailleurs,
        perdu pour un excédent qui se retire en une opération.

        ## Pourquoi couper, et pas refuser

        Le plafond protège la MISE EN PAGE : un encadré de douze lignes cesse
        d'être un encadré. Six suffisent au patron du document de référence —
        opportunité, limite, décision — et l'excédent ne porte, par
        construction, que ce qui vient après l'essentiel.

        Refuser coûte une reprise entière ; couper coûte une ligne. Ce dépôt a
        déjà tranché trois fois dans ce sens — la ligne de tableau trop courte
        qu'on complète, le résumé trop long qu'on raccourcit, la typographie
        qu'on répare. La règle est la même : un défaut de FORME ne doit jamais
        coûter un livrable.

        On ne se tait pas pour autant : la coupe est journalisée avec ce
        qu'elle retire (règle 1).
        """
        if len(self.lignes) <= 6:
            return self
        _log.warning(
            "Encadré « %s » : %s lignes ramenées à 6. Retirées : %s",
            self.intitule, len(self.lignes), " | ".join(self.lignes[6:]),
        )
        self.lignes = self.lignes[:6]
        return self


class CelluleKpi(SortieDeChapitre):
    """Un chiffre clé : la valeur, ce qu'elle mesure, d'où elle vient."""

    model_config = {"extra": "forbid"}

    valeur: str = Field(min_length=1, max_length=40)
    libelle: str = Field(min_length=1, max_length=160)
    source: str = ""


class BlocSousTitre(SortieDeChapitre):
    """Titre de sous-section : « 1.1 Deux périmètres à ne pas confondre »."""

    model_config = {"extra": "forbid"}

    type: Literal["titre_sous_section"] = "titre_sous_section"
    numero: str = Field(min_length=1, max_length=8)
    intitule: str = Field(min_length=1, max_length=220)


class BlocParagraphe(SortieDeChapitre):
    model_config = {"extra": "forbid"}

    type: Literal["paragraphe"] = "paragraphe"
    texte: str = Field(min_length=1)


def _renester(valeurs: Any, cle: str, modele: type[BaseModel]) -> Any:
    """Remonte dans `cle` les champs que le modèle a écrits à plat.

    Ces trois blocs ont la même forme — un discriminant `type`, et un objet
    imbriqué sous une clé qui répète ce discriminant. Le modèle aplatit
    régulièrement cette imbrication : elle lui demande d'écrire deux fois le
    même mot pour deux sens différents. Constaté en génération réelle sur le
    graphique (`6557b06b`, 05/08/2026), trois échecs identiques.

    On répare le TRANSPORT, jamais le fond : re-nicher des clés ne change aucune
    valeur et n'invente rien. C'est le même geste que `depuis_ancien_format`,
    qui accepte déjà une autre écriture du même contenu sans créer une seconde
    vérité. Ce qui juge le contenu — « un chapitre n'exploite que des données du
    socle » — reste `valider_chapitre`, intact.

    Et on vise la CLASSE : la correction porte sur les trois blocs à
    enveloppe, pas sur le seul graphique qui a échoué (règle 4). Le tableau et
    l'encadré présentent exactement la même invitation à l'erreur.

    Les champs sont lus sur le modèle cible, jamais recopiés ici : une liste
    locale divergerait au premier champ ajouté (règle 5).

    **On retient l'alias quand il existe, jamais les deux noms.** Retenir aussi
    le nom Python happerait `type` — qui, au niveau du bloc, est le
    discriminant : la forme aplatie perdrait sa nature de bloc en même temps
    qu'elle retrouverait sa structure. C'est précisément le nom que l'alias
    existe pour désambiguïser.
    """
    if not isinstance(valeurs, dict) or cle in valeurs:
        return valeurs
    noms = {
        champ.alias or nom
        for nom, champ in modele.model_fields.items()
    }

    def _appartient(candidat: str) -> bool:
        # « à un signe près » vaut ici AUSSI : sans quoi une clé aplatie ET
        # mal orthographiée resterait dehors, le bloc serait re-niché sans
        # elle, et le contrat la refuserait — le chapitre mourrait pour la
        # combinaison de deux écarts que l'on sait chacun rattraper.
        return any(nom == candidat or _differe_d_un_signe(candidat, nom) for nom in noms)

    interieur = {nom: valeur for nom, valeur in valeurs.items() if _appartient(str(nom))}
    if not interieur:
        return valeurs
    dehors = {
        nom: valeur for nom, valeur in valeurs.items() if not _appartient(str(nom))
    }
    dehors[cle] = interieur
    return dehors


class BlocTableau(SortieDeChapitre):
    model_config = {"extra": "forbid"}

    type: Literal["tableau"] = "tableau"
    tableau: Tableau

    @model_validator(mode="before")
    @classmethod
    def _accepter_la_forme_aplatie(cls, valeurs: Any) -> Any:
        return _renester(valeurs, "tableau", Tableau)


class BlocEncadre(SortieDeChapitre):
    model_config = {"extra": "forbid"}

    type: Literal["encadre"] = "encadre"
    encadre: Encadre

    @model_validator(mode="before")
    @classmethod
    def _accepter_la_forme_aplatie(cls, valeurs: Any) -> Any:
        return _renester(valeurs, "encadre", Encadre)


class BlocGraphique(SortieDeChapitre):
    model_config = {"extra": "forbid"}

    type: Literal["graphique"] = "graphique"
    graphique: Graphique

    @model_validator(mode="before")
    @classmethod
    def _accepter_la_forme_aplatie(cls, valeurs: Any) -> Any:
        return _renester(valeurs, "graphique", Graphique)


class BlocGrilleKpi(SortieDeChapitre):
    """Rangée de chiffres clés. Le modèle en aligne trois par rangée."""

    model_config = {"extra": "forbid"}

    type: Literal["grille_kpi"] = "grille_kpi"
    cellules: list[CelluleKpi] = Field(min_length=2)

    @model_validator(mode="after")
    def _au_plus_quatre_cellules(self) -> BlocGrilleKpi:
        """Garde les quatre premières — même famille que l'encadré à 7 lignes.

        Le plafond tient à la MISE EN PAGE : au-delà de quatre, la rangée de
        chiffres clés ne tient plus sur une ligne et cesse d'être une rangée.
        Une cinquième cellule est un excédent, pas une erreur de fond : la
        retirer coûte un chiffre, refuser coûte le chapitre (règle 4 — la
        classe, pas l'exemple).
        """
        if len(self.cellules) <= 4:
            return self
        _log.warning(
            "Grille de KPI : %s cellules ramenées à 4. Retirées : %s",
            len(self.cellules),
            " | ".join(c.libelle for c in self.cellules[4:]),
        )
        self.cellules = self.cellules[:4]
        return self


class Canvas(BaseModel):
    """Les neuf briques du Business Model Canvas d'Osterwalder.

    Champs NOMMÉS plutôt qu'une liste de neuf lignes : la disposition du canvas
    n'est pas un ordre, c'est une CARTE. Ce que l'entreprise fait est à gauche,
    ce que le client reçoit à droite, l'argent en bas. Un tableau de neuf
    lignes perd cette lecture — et c'est ce que la cliente a demandé de
    corriger le 13/08/2026, modèle AFE à l'appui.

    Un bloc vide reste vide : un modèle sans partenaires clés est une
    information, et l'inventer pour remplir la case serait exactement ce que ce
    projet combat.
    """

    model_config = {"extra": "forbid"}

    partenaires_cles: list[str] = Field(default_factory=list)
    activites_cles: list[str] = Field(default_factory=list)
    ressources_cles: list[str] = Field(default_factory=list)
    proposition_valeur: list[str] = Field(default_factory=list)
    relation_client: list[str] = Field(default_factory=list)
    canaux: list[str] = Field(default_factory=list)
    segments_clientele: list[str] = Field(default_factory=list)
    structure_couts: list[str] = Field(default_factory=list)
    sources_revenus: list[str] = Field(default_factory=list)


class BlocCanvas(SortieDeChapitre):
    """Le Business Model Canvas, dessiné dans sa disposition d'origine."""

    model_config = {"extra": "forbid"}

    type: Literal["canvas"] = "canvas"
    canvas: Canvas
    source: str = ""


#: Un bloc du chapitre, discriminé par son champ `type`.
Bloc = Annotated[
    BlocSousTitre | BlocParagraphe | BlocTableau | BlocEncadre | BlocGraphique
    | BlocGrilleKpi | BlocCanvas,
    Field(discriminator="type"),
]

#: Le variant derrière chaque valeur du discriminant. Dérivé de l'union, jamais
#: recopié : une table écrite à la main divergerait au premier bloc ajouté
#: (règle 5). Sert au motif de refus, qui doit nommer les champs admis.
BLOC_PAR_TYPE: dict[str, type[SortieDeChapitre]] = {
    str(modele.model_fields["type"].default): modele
    for modele in (
        BlocSousTitre, BlocParagraphe, BlocTableau, BlocEncadre,
        BlocGraphique, BlocGrilleKpi, BlocCanvas,
    )
}


def depuis_ancien_format(valeurs: dict[str, Any]) -> dict[str, Any]:
    """Convertit un payload écrit avant l'ordonnancement des blocs.

    Le contrat portait `sections`, `encadres` et `graphiques` en trois listes
    séparées. Il ne pouvait donc pas exprimer « graphique entre le deuxième et
    le troisième paragraphe », et le modèle de référence — qui décrit une forme
    DIFFÉRENTE pour chacun des vingt-et-un chapitres — restait hors de portée :
    le moteur produisait la même forme partout.

    Les chapitres déjà en base gardent l'ancienne forme. Les convertir à la
    lecture évite de les rendre illisibles sans créer une seconde vérité :
    `blocs` reste la seule, l'ancien format n'est qu'une porte d'entrée.

    L'ordre reconstruit est celui que produisait le rendu — sous-titre,
    paragraphe, tableau pour chaque section, puis les graphiques, puis les
    encadrés. C'est une reconstitution fidèle de ce qui était rendu, pas une
    amélioration : on ne devine pas un ordre que la donnée ne porte pas.
    """
    if "blocs" in valeurs or "sections" not in valeurs:
        return valeurs

    converti = dict(valeurs)
    numero = converti.get("chapitre", 0)
    blocs: list[dict[str, Any]] = []

    for rang, brut in enumerate(converti.pop("sections", None) or [], start=1):
        section = brut if isinstance(brut, dict) else brut.model_dump()
        blocs.append({
            "type": "titre_sous_section",
            "numero": f"{numero}.{rang}",
            "intitule": section.get("titre") or "Sous-section",
        })
        contenu = (section.get("contenu") or "").strip()
        if contenu:
            blocs.append({"type": "paragraphe", "texte": contenu})
        if section.get("tableau"):
            blocs.append({"type": "tableau", "tableau": section["tableau"]})

    for graphique in converti.pop("graphiques", None) or []:
        blocs.append({"type": "graphique", "graphique": graphique})
    for encadre in converti.pop("encadres", None) or []:
        blocs.append({"type": "encadre", "encadre": encadre})

    converti["blocs"] = blocs
    return converti


class ChapitrePayload(SortieDeChapitre):
    """Sortie structurée d'un chapitre : une SUITE ORDONNÉE de blocs.

    L'ordre EST le contrat. Le modèle de référence décrit, chapitre par
    chapitre, quels blocs se suivent : le chapitre 09 aligne quatre grilles de
    chiffres et aucun paragraphe, le 19 enchaîne treize tableaux et neuf
    encadrés. Trois listes séparées ne pouvaient pas dire cela — elles
    produisaient la même forme pour les vingt-et-un chapitres, et le validateur
    de conformité mesurait zéro chapitre conforme sur vingt-et-un.
    """

    model_config = {"extra": "forbid"}

    chapitre: int = Field(ge=0, le=99)
    titre: str = Field(min_length=1, max_length=220)
    #: Phrase d'accroche affichée sous le titre dans le bandeau de chapitre.
    accroche: str = Field(default="", max_length=400)
    blocs: list[Bloc] = Field(min_length=1)
    #: Identifiants du socle réellement exploités par ce chapitre.
    donnees_utilisees: list[str] = Field(default_factory=list)
    #: Résumé transmis aux chapitres suivants (§6.1 : 150 à 250 mots).
    resume: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _accepter_ancien_format(cls, valeurs: Any) -> Any:
        return depuis_ancien_format(valeurs) if isinstance(valeurs, dict) else valeurs

    # ── Vues dérivées ────────────────────────────────────────────────────────
    # Elles LISENT `blocs`, elles ne le doublent pas : une seule source par
    # vérité. Elles évitent que chaque appelant refasse le même filtrage.

    @property
    def graphiques(self) -> list[Graphique]:
        return [b.graphique for b in self.blocs if isinstance(b, BlocGraphique)]

    @property
    def encadres(self) -> list[Encadre]:
        return [b.encadre for b in self.blocs if isinstance(b, BlocEncadre)]

    @property
    def tableaux(self) -> list[Tableau]:
        return [b.tableau for b in self.blocs if isinstance(b, BlocTableau)]

    @property
    def paragraphes(self) -> list[str]:
        return [b.texte for b in self.blocs if isinstance(b, BlocParagraphe)]

    @property
    def sous_titres(self) -> list[BlocSousTitre]:
        return [b for b in self.blocs if isinstance(b, BlocSousTitre)]

    @model_validator(mode="after")
    def _coherence_interne(self) -> ChapitrePayload:
        """Complète `donnees_utilisees` avec ce que les graphiques emploient.

        **Cette cohérence était une cause de rejet, et elle a tué une étude.**
        Le modèle demandait un graphique citant `marche_continental_taille`
        sans l'inscrire dans `donnees_utilisees`. Trois tentatives, trois fois
        le même oubli : ce n'est pas un aléa, c'est une étourderie de tenue de
        registre que le modèle reproduit.

        Or les deux champs sont remplis par le MÊME modèle, sur le MÊME
        chapitre. Leur désaccord ne dit rien de faux sur le marché : il dit que
        la déclaration est incomplète. La compléter la rend vraie.

        **Ce que cette réparation ne peut PAS masquer.** La règle de fond n'est
        pas « les deux champs concordent », c'est « un chapitre n'exploite que
        des données du socle » — et elle est vérifiée ailleurs, par
        `valider_chapitre`, qui refuse tout identifiant absent du socle
        verrouillé. Un graphique qui inventerait une donnée est donc toujours
        rejeté, par le contrôle qui regarde la bonne évidence (règle 9).

        Autrement dit : on ajoute la donnée à la déclaration, et c'est le socle
        qui tranche. Le contrôle qui reste est celui qui compare à quelque
        chose.
        """
        declares = list(self.donnees_utilisees)
        connus = set(declares)
        for graphique in self.graphiques:
            for identifiant in graphique.donnees_ids:
                if identifiant not in connus:
                    declares.append(identifiant)
                    connus.add(identifiant)

        if len(declares) != len(self.donnees_utilisees):
            self.donnees_utilisees = declares
        return self

    @property
    def texte(self) -> str:
        """Prose du chapitre : sous-titres et paragraphes, dans l'ordre."""
        morceaux: list[str] = []
        for bloc in self.blocs:
            if isinstance(bloc, BlocSousTitre):
                morceaux.append(f"{bloc.numero} {bloc.intitule}")
            elif isinstance(bloc, BlocParagraphe):
                morceaux.append(bloc.texte)
        return "\n\n".join(morceaux)


def compter_mots(texte: str) -> int:
    return len([mot for mot in re.split(r"\s+", texte.strip()) if mot])


def raccourcir_le_resume(payload: ChapitrePayload, *, maximum: int) -> str:
    """Ramène un résumé trop long dans sa borne. Retourne la mention, ou "".

    **Pourquoi réparer plutôt que refuser.** Le motif de rejet disait lui-même
    à quoi sert cette borne : « il est relu par tous les chapitres suivants :
    trop court il perd des chiffres, trop long il sature leur contexte ».
    Raccourcir atteint exactement ce but. Rejeter le chapitre ne l'atteint pas
    — il le détruit, et avec lui l'étude entière, puisque le runner de
    production ne réessaie pas.

    Mesuré : la seconde génération réelle est morte au chapitre 5 sur un résumé
    de **254 mots pour 250 attendus**. Quatre mots. Quatre chapitres écrits et
    payés, perdus.

    Ce qui n'est PAS réparé : un résumé trop COURT. On ne peut pas inventer le
    contenu manquant, et prétendre le contraire serait la règle 1 à l'envers —
    une réparation qui ne répare rien mais fait taire le contrôle.

    La coupe se fait sur une frontière de phrase quand il en existe une dans la
    borne : couper au mot près rendrait un résumé qui s'interrompt au milieu
    d'une idée, et ce résumé est LU par les chapitres suivants.
    """
    mots = payload.resume.split()
    if len(mots) <= maximum:
        return ""

    tronque = " ".join(mots[:maximum])
    derniere_phrase = max(
        tronque.rfind(". "), tronque.rfind(" ! "), tronque.rfind(" ? ")
    )
    # On ne coupe a la phrase que si cela ne sacrifie pas la moitie du resume :
    # un resume ampute de trop perdrait les chiffres qu'il doit transmettre.
    if derniere_phrase > len(tronque) // 2:
        tronque = tronque[: derniere_phrase + 1]

    ancien_compte = len(mots)
    payload.resume = tronque.rstrip()
    return (
        f"résumé raccourci de {ancien_compte} à "
        f"{len(payload.resume.split())} mots (maximum {maximum})"
    )


#: Un identifiant se lit en jetons : `taille_marche` vaut `("taille", "marche")`.
#: Les accents tombent, la casse aussi — le modèle écrit `critere_accessibilité`
#: là où le socle porte `accessibilite`, et cette différence-là n'en est pas une.
_SEPARATEURS = re.compile(r"[^0-9a-z]+")

#: Table de dépouillement des accents, sans dépendance : `str.translate` sur les
#: quelques lettres que le français emploie. Une normalisation Unicode complète
#: (`NFKD`) ferait le même travail, mais dépouillerait aussi des caractères
#: qu'un identifiant n'a de toute façon pas le droit de porter.
_SANS_ACCENT = str.maketrans("àâäçéèêëîïôöùûüÿœæ", "aaaceeeeiioouuuyoa")


def _jetons(identifiant: str) -> tuple[str, ...]:
    depouille = identifiant.casefold().translate(_SANS_ACCENT)
    return tuple(j for j in _SEPARATEURS.split(depouille) if j)


def resoudre_identifiant(declare: str, connus: frozenset[str]) -> str | None:
    """L'identifiant du socle que `declare` DÉSIGNE, ou None si aucun.

    ## Le défaut mesuré

    Business plan `2a8872d0` (12/08/2026), chapitre 7 « Analyse
    concurrentielle » : mort après TROIS tentatives, pour zéro centime de
    contenu utile, sur trois motifs identiques —

        `critere_accessibilite_evkha` ne figure pas dans le socle verrouillé.

    Le modèle n'a rien inventé : il a DÉCORÉ. Un préfixe qui dit la nature
    (`critere_`), un suffixe qui dit la maison (`_evkha`, au passage le nom de
    la marque dans un livrable en marque blanche). Le contrôle, lui, compare à
    la lettre près, et un chapitre entier meurt d'un préfixe.

    ## Pourquoi une résolution et non une liste de préfixes

    Énumérer `critere_`, `donnee_`, `id_`, `_evkha`… c'est la règle 4 du dépôt
    prise à l'envers : « si votre correctif énumère des cas, il est incomplet ».
    On ne connaît pas la prochaine décoration.

    Un identifiant du socle est donc RECONNU quand ses jetons apparaissent, à
    la suite, dans ceux du nom déclaré. Le plus long gagne — `prix_median` prime
    sur `prix`. Deux candidats de même longueur : on ne tranche pas, et le
    chapitre est refusé comme avant. Mieux vaut redemander que deviner (règle 2).
    """
    if declare in connus:
        return declare

    jetons = _jetons(declare)
    if not jetons:
        return None

    meilleurs: list[str] = []
    longueur_max = 0
    for connu in connus:
        cible = _jetons(connu)
        if not cible or len(cible) > len(jetons):
            continue
        contigu = any(
            jetons[i : i + len(cible)] == cible
            for i in range(len(jetons) - len(cible) + 1)
        )
        if not contigu:
            continue
        if len(cible) > longueur_max:
            longueur_max, meilleurs = len(cible), [connu]
        elif len(cible) == longueur_max:
            meilleurs.append(connu)

    return meilleurs[0] if len(meilleurs) == 1 else None


def valider_chapitre(
    payload: ChapitrePayload,
    *,
    numero_attendu: int,
    identifiants_socle: frozenset[str],
    resume_mots_min: int,
    resume_mots_max: int,
    secteur: str = "",
    derniere_tentative: bool = False,
) -> list[str]:
    """Contrôles croisés avec le socle et le chapitrage.

    Retourne les motifs de rejet ; liste vide = chapitre recevable.

    Le contrôle central est celui-ci : **toute donnée déclarée doit exister
    dans le socle**. C'est la traduction du principe « un chapitre n'a jamais
    le droit de produire un chiffre ».
    """
    motifs: list[str] = []

    if payload.chapitre != numero_attendu:
        motifs.append(
            f"Le chapitre annoncé ({payload.chapitre}) ne correspond pas au "
            f"chapitre demandé ({numero_attendu})."
        )

    # On RÉSOUT avant de refuser : un préfixe ou un suffixe décoratif n'est pas
    # une donnée hors socle, et faire mourir un chapitre dessus coûte un trou
    # dans le document livré (business plan `2a8872d0`, chapitre 7).
    inconnues: list[str] = []
    resolus: list[str] = []
    for declare in payload.donnees_utilisees:
        vrai = resoudre_identifiant(declare, identifiants_socle)
        if vrai is None:
            inconnues.append(declare)
            resolus.append(declare)
            continue
        if vrai != declare:
            _log.info(
                "identifiant décoré ramené au socle : %r -> %r", declare, vrai
            )
        resolus.append(vrai)
    payload.donnees_utilisees = resolus

    if inconnues and derniere_tentative:
        # DERNIER essai : on garde le chapitre, on jette la DÉCLARATION.
        #
        # `donnees_utilisees` est une liste déclarative — elle sert à tracer et
        # à résoudre les figures, pas à porter le texte. Perdre tout un
        # chapitre parce qu'elle contient un nom inconnu, c'est payer un trou
        # dans le document au prix d'une métadonnée.
        #
        # Business plan `2a8872d0` (12/08/2026) : le chapitre 7 est mort CINQ
        # fois là-dessus, pour 4,19 €, et la cliente n'a pas eu son analyse
        # concurrentielle. Deux fois de suite.
        #
        # Le refus reste la règle sur les essais précédents : le modèle a
        # toutes ses chances de citer juste, et il y arrive presque toujours.
        # Ce qui change, c'est ce qu'on fait quand il n'y arrive pas — et une
        # figure qui s'appuierait sur un identifiant jeté est de toute façon
        # abandonnée par le résolveur, avec son motif.
        _log.warning(
            "Chapitre %s, dernier essai : %s identifiant(s) hors socle "
            "abandonné(s) plutôt que le chapitre entier — %s",
            numero_attendu, len(set(inconnues)), ", ".join(sorted(set(inconnues))),
        )
        payload.donnees_utilisees = [
            i for i in resolus if i in identifiants_socle
        ]
        inconnues = []

    for identifiant in sorted(set(inconnues)):
        motifs.append(
            f"`{identifiant}` ne figure pas dans le socle verrouillé. "
            "Un chapitre ne peut exploiter que des données du socle."
        )

    doublons = {
        i for i in payload.donnees_utilisees
        if payload.donnees_utilisees.count(i) > 1
    }
    for identifiant in sorted(doublons):
        motifs.append(f"`{identifiant}` est déclaré plusieurs fois dans `donnees_utilisees`.")

    mots = compter_mots(payload.resume)
    if mots < resume_mots_min or mots > resume_mots_max:
        motifs.append(
            f"Le résumé fait {mots} mots ; attendu entre {resume_mots_min} et "
            f"{resume_mots_max}. Il est relu par tous les chapitres suivants : "
            "trop court il perd des chiffres, trop long il sature leur contexte."
        )

    titres = [bloc.intitule.strip().lower() for bloc in payload.sous_titres]
    if len(set(titres)) != len(titres):
        motifs.append("Deux sous-sections portent le même titre.")

    motifs.extend(motifs_de_balisage(payload))

    return motifs


def motifs_de_secteur_etranger(payload: ChapitrePayload, secteur: str) -> list[str]:
    """RETIRÉ DE LA VALIDATION le 09/08/2026. Conservé pour mémoire, jamais appelé.

    ## Ce qu'il a cassé, en production, le jour même de sa mise en service

    Étude concurrentielle `5892daa5`, secteur déclaré : « Fintech patrimoniale
    spécialisée dans **l'or physique et les métaux précieux** : achat, rachat,
    stockage sécurisé… ». Un chapitre écrivait, très légitimement :

        « Le rachat de BIJOUX et pièces anciennes fait partie du cœur de métier »

    « bijoux » figure dans `_SECTEUR_DE_REFERENCE`, la liste des mots de la
    joaillerie sur laquelle le modèle de forme a été mesuré. Et comme le secteur
    déclaré dit « or » et « métaux précieux » sans dire « bijou », le garde-fou
    ne s'est pas reconnu comme concerné : il a refusé le chapitre, l'étude est
    morte à 2,07 EUR.

    ## Pourquoi il ne pouvait PAS marcher

    Il repose sur une liste fermée de mots, et la règle 4 de ce dépôt condamne
    exactement cela : « si votre correctif énumère des cas, il est incomplet ».
    Un secteur ADJACENT — l'or, le rachat, le luxe, la seconde main — partage
    forcément du vocabulaire avec la joaillerie sans être elle. Aucun
    allongement de la liste ne répare ce défaut ; il le déplace.

    ## Ce qui reste, et qui est juste

    `modele.conformite._controler_contamination`. Il ne devine rien : il compare
    l'intitulé produit aux intitulés EXACTS du chapitre du modèle. « FOCUS —
    Approfondissement demandé : marché international des galeries et du
    sur-mesure » recopié mot pour mot est une contamination certaine ; « le
    rachat de bijoux » dans une étude sur l'or ne l'est pas.

    Un contrôle précis qui couvre un seul livrable vaut mieux qu'un contrôle
    large qui tue des chapitres corrects. La couverture des trois autres
    livrables reste ouverte, et se fera avec un signal qui ne devine pas.
    """
    if not secteur.strip():
        # Pas de secteur déclaré : rien à quoi comparer. On ne juge pas — et on
        # ne prétend pas avoir jugé (règle 1). Le cas ne se produit pas en
        # production, le socle portant toujours son secteur.
        return []

    from ..modele.conformite import (  # noqa: PLC0415 — évite un cycle
        _SECTEUR_DE_REFERENCE,
        _porte_le_secteur_de_reference,
    )

    mots_du_secteur = set(re.findall(r"[\w-]+", secteur.casefold()))
    if mots_du_secteur & _SECTEUR_DE_REFERENCE:
        # L'étude PORTE sur ce secteur : ces mots y sont chez eux.
        return []

    motifs: list[str] = []
    for index, bloc in enumerate(getattr(payload, "blocs", ()) or ()):
        for champ, texte in _textes_du_bloc(bloc):
            if not _porte_le_secteur_de_reference(texte):
                continue
            motifs.append(
                f"Bloc {index} ({bloc.type}), champ `{champ}` : ce passage parle "
                f"d'un secteur qui n'est pas celui de l'étude (« {secteur} ») — "
                f"« {texte[:110]} ». Il vient d'un exemple écrit pour un autre "
                "document : réécris-le pour CE sujet."
            )
            break
    return motifs


#: Une VRAIE balise : un chevron ouvrant, un nom d'élément connu, un chevron
#: fermant. Pas « 1 < 2 », pas « panier < 220 € » — des comparaisons légitimes
#: qu'un motif plus large condamnerait, et qui abondent dans un plan d'affaires
#: (seuils d'alerte, conditions de déclenchement). Un correctif qui casse ce qui
#: était correct est pire que le défaut qu'il traite (règles 2 et 6).
_BALISE = re.compile(
    r"</?\s*(?:table|thead|tbody|tfoot|tr|td|th|div|span|p|br|hr|h[1-6]|"
    r"strong|em|b|i|u|small|code|pre|ul|ol|li|img|a|font)\b[^>]*>",
    re.IGNORECASE,
)

#: Longueur du fragment cité dans le motif de rejet. Assez pour que la personne
#: qui lit le motif RETROUVE le passage dans le chapitre (règle 2), pas assez
#: pour noyer le motif.
_EXTRAIT = 120

#: Données BRUTES glissées dans un texte : CSV, colonnes tabulées, ligne de
#: tableau markdown, JSON, bloc de code.
#:
#: Signalé par la cliente le 09/08/2026 : « du code / CSV brut est visible dans
#: le document ». La cause exacte n'est pas établie — et n'a pas besoin de
#: l'être. C'est la CLASSE qu'on interdit, comme pour le HTML deux jours plus
#: tôt : un format de données n'a rien à faire dans une phrase, quelle que soit
#: la façon dont il y est arrivé (règle 4).
#:
#: ## Chaque motif est choisi pour ne PAS mordre sur du français
#:
#: - trois points-virgules ou plus : une phrase française en porte rarement un,
#:   jamais trois ;
#: - deux barres verticales ou plus : c'est une ligne de tableau markdown ;
#: - une tabulation : elle ne survit à aucune rédaction normale ;
#: - une accolade ou un crochet ouvrant suivi d'un guillemet et d'un
#:   deux-points : la signature du JSON ;
#: - trois accents graves : un bloc de code.
#:
#: Une énumération française — « le prix, la garantie, la livraison » — emploie
#: des virgules et traverse intacte. C'est la contre-épreuve qui compte.
_DONNEES_BRUTES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # L'ESPACE AVANT LE POINT-VIRGULE sépare le CSV du français.
    #
    # La première version comptait trois points-virgules, quelle que soit leur
    # ponctuation. Elle a tué une génération CLIENTE le 10/08/2026 —
    # `cc0dfe14`, étude de marché d'Eva, bloquée 89 minutes, chapitre 0 en
    # échec — sur cette phrase parfaitement française :
    #
    #   « Taille du marché français 2026 et part réalisée en ligne ;
    #     évolution et perspectives à 3-5 ans ; segments porteurs »
    #
    # Mes contre-épreuves testaient des phrases à UN point-virgule ; aucune ne
    # testait une énumération à trois, qui est la forme normale d'une cellule
    # de tableau. Le remède frappait ce qui n'était pas malade (règle 2), et il
    # le faisait sur un document payé, en cours, devant une cliente.
    #
    # La typographie française impose une espace avant le point-virgule ; un
    # fichier de données n'en met jamais. C'est ce signal qu'on lit désormais,
    # et non le seul comptage.
    ("lignes séparées par des points-virgules", re.compile(r"(?:[^;\n]{0,40}\S;){3,}")),
    ("ligne de tableau brute", re.compile(r"\|[^|\n]*\|[^|\n]*\|")),
    ("tabulations", re.compile(r"\t")),
    ("JSON", re.compile(r"[{\[]\s*\"[^\"]+\"\s*:")),
    ("bloc de code", re.compile(r"```")),
)

#: Notation INTERNE du prompt : la nature de chaque identifiant du socle, servie
#: entre crochets pour que le modèle sache ce qui se trace ensemble.
#:
#: Elle a fuité dans le document dès la première génération qui l'a reçue —
#: étude concurrentielle `2490c7cf`, un commentaire de figure disant « deux taux
#: de même nature [pourcentage] ». Une seule occurrence, presque lisible, et
#: c'est précisément ce qui la rend dangereuse : elle passe pour de la prose.
#:
#: La leçon est plus large que le cas. **Tout ce qu'on ajoute au prompt pour
#: aider le modèle peut ressortir dans le document.** C'était vrai des exemples
#: HTML hérités, ce l'est de cette notation-ci, ce le sera de la suivante. Une
#: aide au raisonnement doit donc arriver AVEC son interdiction de la recopier,
#: le même jour — sans quoi on ferme une fuite en en ouvrant une autre.
_NOTATION_INTERNE = re.compile(
    r"\[(?:monetaire|effectif|pourcentage|duree|ratio|inconnue)\]",
    re.IGNORECASE,
)

#: Le vocabulaire du DISPOSITIF, jamais celui du marché.
#:
#: La cliente, 11/08/2026 : « il y a encore quelques éléments qui ressortent
#: comme socle bloqué / pipeline système etc qui ne doivent pas être vus du
#: client ». Elle lit une étude, pas le journal de la machine qui l'a écrite.
#:
#: ## Chaque motif porte SON QUALIFICATIF, et c'est tout le soin
#:
#: « socle », « pipeline », « prompt », « runner » sont des mots français ou
#: des mots de métier parfaitement légitimes : un pipeline COMMERCIAL, un
#: socle de CLIENTÈLE, un socle RÉGLEMENTAIRE, un prompt dans une étude sur
#: l'IA, un runner dans une étude sur la course à pied. Les bannir seuls
#: tuerait des chapitres justes — c'est exactement l'erreur commise le
#: 10/08/2026 avec une liste de mots sectoriels trop large, qui a coûté un
#: chapitre parfaitement correct.
#:
#: On ne retient donc que des locutions qui n'ont AUCUN sens hors de nos
#: propres rouages.
_VOCABULAIRE_INTERNE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("socle verrouillé/bloqué", re.compile(
        r"\bsocle\s+(?:verrouill|bloqu|de\s+donn[ée]es\b)", re.IGNORECASE)),
    ("hors socle", re.compile(r"\bhors[- ]socle\b", re.IGNORECASE)),
    # Pas de nom de plateforme ICI : ce fichier part dans le schéma de
    # l'outil, et le modèle recopie ce qu'on lui montre. Un premier document
    # en portait vingt-deux occurrences, écrites depuis une docstring de ce
    # module. Le garde-fou de marque blanche l'a rattrapé le 11/08/2026.
    # « pipeline SYSTÈME » seulement, et plus « pipeline de génération ».
    #
    # 13/08/2026, stratégie d'entreprise en cours de génération : le chapitre 11
    # est MORT et le 12 a été signalé sur « la pipeline de génération de
    # livrables est développée et utilisée en production ». Cette phrase décrit
    # le PRODUIT de la cliente — sa plateforme fabrique des livrables — et le
    # garde-fou l'a prise pour une fuite de la machine.
    #
    # C'est le risque propre à ce contrôle chez CE client : notre dispositif et
    # son métier portent les mêmes mots. La fuite réellement mesurée le 10/08
    # disait « pipeline système » ; « pipeline de génération » est un terme
    # industriel ordinaire, que quiconque vend une chaîne de production de
    # documents emploiera pour parler de lui-même.
    #
    # Entre laisser passer une formulation qu'on n'a jamais observée et tuer un
    # chapitre payé qui décrit l'activité du client, le second coûte plus cher
    # — et se voit moins.
    ("pipeline système", re.compile(
        r"\bpipeline\s+syst[èe]me\b", re.IGNORECASE)),
    ("gate qualité", re.compile(
        r"\bgate\s+(?:qualit|de\s+livraison)", re.IGNORECASE)),
    ("prompt système", re.compile(r"\bprompt\s+syst[èe]me\b", re.IGNORECASE)),
    ("chapitre 0", re.compile(r"\bchapitre\s+0\b", re.IGNORECASE)),
    ("identifiant du socle", re.compile(
        r"\bidentifiants?\s+du\s+socle\b", re.IGNORECASE)),
    ("livrable bloqué", re.compile(r"\blivrable\s+bloqu[ée]", re.IGNORECASE)),
    # « Socle EVKHA », lu par la cliente sous des tableaux le 12/08/2026.
    #
    # Le motif d'en haut exige « verrouillé », « bloqué » ou « de données »
    # après « socle » — pour laisser passer un socle de compétences ou un socle
    # tarifaire, qui sont du français. « Socle » suivi d'un NOM PROPRE, lui,
    # n'est jamais du français : c'est une attribution de source, et la source
    # citée est notre entrepôt interne.
    # `[Ss]ocle` écrit à la main, et SANS `IGNORECASE` : c'est la capitale du
    # mot SUIVANT qui distingue « socle EVKHA » d'« un socle commun ». Rendre
    # tout le motif insensible à la casse effacerait précisément le signal.
    ("socle nommé comme une source", re.compile(
        r"\b[Ss]ocle\s+[A-ZÀ-Þ][\wÀ-ÿ-]*")),
    # Les identifiants eux-mêmes : `ca_previsionnel_an1`,
    # `marche_national_taille`. Vus le même jour, sous les mêmes tableaux.
    #
    # CLASSE, et non liste (règle 4) : on ne connaît pas les identifiants que
    # le socle portera demain, mais on sait qu'AUCUN mot français ne s'écrit en
    # minuscules avec des tirets bas. Le motif décrit donc la forme, pas le
    # vocabulaire — un identifiant ajouté plus tard est couvert sans que
    # personne y pense.
    #
    # Les adresses web sont retirées du texte avant l'examen (voir
    # `_sans_les_adresses`) : « /mon_article » n'est pas une fuite.
    ("identifiant technique", re.compile(r"\b[a-zà-ÿ]{2,}_[a-zà-ÿ0-9_]{2,}\b")),
)

#: Une adresse web porte légitimement des tirets bas.
_ADRESSE_WEB = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)

#: Les champs que le RENDU consomme, et que le lecteur ne voit jamais.
#:
#: `donnees_ids` porte les identifiants du socle qu'une figure trace :
#: « ca_previsionnel_an1 », « marche_national_taille ». C'est sa RAISON D'ÊTRE.
#: Le rendu les résout en barres et en courbes ; aucun n'atteint le document.
#:
#: Sans cette exclusion, la règle « identifiant technique » ajoutée le
#: 12/08/2026 refusait TOUTE figure, sur les quatre livrables — vérifié avant
#: déploiement sur un graphique parfaitement légitime, trois motifs levés. Un
#: garde-fou qui refuse le fonctionnement normal du système ne protège personne :
#: il aurait fait échouer chaque chapitre portant un graphique.
#:
#: Ce jeu se maintient : `test_aucun_champ_machine_n_echappe_a_l_inventaire`
#: échoue si le schéma gagne un champ de ce genre sans qu'on l'ait déclaré ici.
_CHAMPS_LUS_PAR_LA_MACHINE = frozenset({"donnees_ids"})


@lru_cache(maxsize=1)
def _valeurs_structurelles() -> frozenset[str]:
    """Toutes les constantes que le SCHÉMA lui-même déclare.

    Les discriminants de blocs — « titre_sous_section », « grille_kpi » — et
    les valeurs d'énumération — « barres_empilees ». Ce sont des noms de
    STRUCTURE : le rendu s'en sert pour savoir quoi dessiner, et aucun
    n'atteint jamais le document.

    ## Pourquoi cette fonction existe

    La règle « identifiant technique » du 12/08/2026 les prenait tous pour des
    fuites : la répétition à blanc a rendu un défaut interne sur presque chaque
    chapitre des quatre livrables. Exclure les champs un par un ne suffisait
    pas — le discriminant s'appelle `type`, un nom qu'on ne peut pas réserver.

    On juge donc la VALEUR, pas le champ : un texte qui est exactement une
    constante du schéma est structurel. « Source : marche_national_taille
    (2026) » n'en est pas une, et reste refusé — c'est bien une phrase, écrite
    pour être lue.

    Calculé une fois : le schéma ne change pas en cours d'exécution.
    """
    valeurs: set[str] = set()
    for objet in list(globals().values()):
        if isinstance(objet, type) and issubclass(objet, Enum):
            valeurs.update(str(membre.value) for membre in objet)
        elif isinstance(objet, type) and issubclass(objet, BaseModel):
            for info in objet.model_fields.values():
                valeurs.update(
                    str(argument)
                    for argument in get_args(info.annotation)
                    if isinstance(argument, str)
                )
    return frozenset(valeurs)


def _sans_les_adresses(texte: str) -> str:
    """Le texte débarrassé de ses URL, pour juger la prose seule."""
    return _ADRESSE_WEB.sub(" ", texte)


def motifs_de_balisage(payload: ChapitrePayload) -> list[str]:
    """Refuse un chapitre dont le TEXTE contient du balisage.

    ## Le défaut, mesuré sur les deux livrables validés

    Le 08/08/2026, `b561c2d6` (étude de marché) et `09f32041` (business plan)
    portaient tous deux des tableaux HTML **imprimés en toutes lettres** dans
    le corps du document : `<table style="border-collapse:collapse;width:100%…`.
    Dix balises dans l'un, quarante-quatre dans l'autre. La cliente les a vus
    avant nous.

    ## D'où ils viennent

    Les fichiers d'instruction des chapitres montrent des exemples de tableaux
    HTML — ils datent du moteur HÉRITÉ, qui produisait du HTML et pour lequel
    ces exemples étaient justes. Le moteur STRUCTURÉ les reçoit toujours, et le
    modèle fait ce qu'on lui montre : il recopie le motif dans un bloc de texte,
    où il n'a plus aucun sens. La cause est traitée dans la consigne ; ce
    contrôle est la dernière ligne, celle qui regarde ce que le lecteur va
    vraiment lire (règle 3).

    ## Pourquoi un refus et non un nettoyage

    Retirer les balises laisserait le contenu du tableau aplati en une phrase
    illisible, et le chapitre passerait pour bon. Le refus fait rejouer la
    tentative — la machinerie de reprise existe déjà — et le modèle produit
    alors un bloc `tableau`, c'est-à-dire ce qu'il aurait dû produire.
    """
    motifs: list[str] = []
    motifs.extend(_motifs_de_notation_interne(payload))
    motifs.extend(_motifs_de_vocabulaire_interne(payload))
    motifs.extend(_motifs_de_parts_incoherentes(payload))
    motifs.extend(_motifs_de_donnees_brutes(payload))
    # `getattr` et non `payload.blocs` : `valider_chapitre` accepte aussi des
    # porteurs minimaux, que plusieurs tests emploient pour isoler leur sujet
    # sans construire un chapitre entier. Ce n'est pas une permissivite — un
    # objet sans blocs n'a aucun texte, donc rien a examiner, et le dire
    # autrement serait inventer un defaut (regle 2). Un vrai `ChapitrePayload`
    # porte toujours ses blocs : le contrat les exige (`min_length=1`).
    for index, bloc in enumerate(getattr(payload, "blocs", ()) or ()):
        for champ, texte in _textes_du_bloc(bloc):
            trouvee = _BALISE.search(texte)
            if trouvee is None:
                continue
            debut = max(trouvee.start() - 20, 0)
            motifs.append(
                f"Bloc {index} ({bloc.type}), champ `{champ}` : du balisage HTML "
                f"figure dans le TEXTE et sera imprimé tel quel — "
                f"« …{texte[debut:debut + _EXTRAIT]}… ». Un tableau se demande "
                "avec un bloc `tableau`, jamais en HTML ; les exemples HTML des "
                "instructions viennent d'un moteur précédent."
            )
    return motifs


def _motifs_de_donnees_brutes(payload: ChapitrePayload) -> list[str]:
    """Refuse un format de données glissé dans un texte.

    Même famille que `motifs_de_balisage`, et pour la même raison : le rendu
    imprime le champ tel quel, donc tout ce qui n'est pas une phrase arrive chez
    le client sous sa forme brute.

    On ne cherche pas la cause — elle n'est pas établie et n'a pas besoin de
    l'être pour interdire la classe. Un tableau se demande avec un bloc
    `tableau` ; aucune autre façon d'aligner des colonnes n'a de sens ici.
    """
    motifs: list[str] = []
    for index, bloc in enumerate(getattr(payload, "blocs", ()) or ()):
        for champ, texte in _textes_du_bloc(bloc):
            # Un texte deja signale comme HTML n'est pas signale une seconde
            # fois : `style="border-collapse:collapse;width:100%;…"` porte
            # quatre points-virgules et ressemble donc a un CSV. Le passage est
            # le meme, le chapitre est rejoue de toute facon, mais le second
            # motif enverrait corriger un fichier de donnees qui est en realite
            # une feuille de style (regle 2 — un motif doit etre trouvable tel
            # qu'il est ecrit). Le diagnostic HTML est le plus precis des deux.
            if _BALISE.search(texte) is not None:
                continue
            for nom, motif in _DONNEES_BRUTES:
                trouvee = motif.search(texte)
                if trouvee is None:
                    continue
                debut = max(trouvee.start() - 10, 0)
                motifs.append(
                    f"Bloc {index} ({bloc.type}), champ `{champ}` : {nom} dans "
                    f"le TEXTE — « …{texte[debut:debut + _EXTRAIT]}… ». Ce sera "
                    "imprimé tel quel chez le client. Un tableau se demande "
                    "avec un bloc `tableau` et ses cellules."
                )
                break
    return motifs


#: Un en-tête de colonne qui annonce une répartition du marché.
_COLONNE_DE_PART = re.compile(
    r"\bparts?\s+(?:de\s+)?march[ée]|\bpart\s*\(\s*%|\bpdm\b", re.IGNORECASE
)

#: Un pourcentage dans une cellule : « 12 % », « 12,4% », « 12.4 % ».
_POURCENTAGE_CELLULE = re.compile(r"^\s*(\d{1,3}(?:[.,]\d+)?)\s*%\s*$")



def _motifs_de_parts_incoherentes(payload: ChapitrePayload) -> list[str]:
    """Des parts de marché qui totalisent plus de 100 % sont fausses.

    ## La demande, mot pour mot

    Cliente, 11/08/2026 : « Toutes les parts de marché doivent utiliser le
    même périmètre. Avant de comparer des parts de marché, LE SYSTÈME DOIT
    CONTRÔLER : même pays, même année, même secteur, même canal, même
    périmètre produit/service, même unité. »

    Six critères, dont aucun ne se lit dans un tableau. Ce qui se lit, en
    revanche, c'est leur CONSÉQUENCE arithmétique : mélanger des périmètres
    fait presque toujours déborder le total. Une part nationale posée à côté
    d'une part régionale, une part 2024 à côté d'une part 2026, une part du
    canal en ligne à côté d'une part du marché entier — et la somme dépasse
    cent.

    C'est le seul symptôme MÉCANIQUEMENT vérifiable des six critères, et il
    est sans appel : aucune répartition d'un même tout ne dépasse 100 %,
    quelle qu'en soit la cause.

    ## Ce que ce contrôle ne prétend pas faire

    Il ne lit ni le pays, ni l'année, ni le canal — rien dans une cellule ne
    les porte. Un document qui compare deux périmètres SANS déborder passe
    donc, et c'est la consigne qui doit l'en empêcher. Prétendre l'inverse
    fabriquerait des motifs faux (règle 2) ; le dire ici évite qu'on croie ce
    contrôle plus large qu'il n'est (règle 1 dans l'autre sens).

    Un total INFÉRIEUR à 100 % est parfaitement normal : un tableau des huit
    premiers acteurs n'épuise pas le marché.
    """
    motifs: list[str] = []
    for index, bloc in enumerate(getattr(payload, "blocs", ()) or ()):
        tableau = getattr(bloc, "tableau", None)
        if tableau is None:
            continue
        for colonne, entete in enumerate(tableau.entetes):
            if not _COLONNE_DE_PART.search(entete):
                continue
            parts = []
            for ligne in tableau.lignes:
                if colonne >= len(ligne):
                    continue
                trouve = _POURCENTAGE_CELLULE.match(ligne[colonne])
                if trouve:
                    ecrit = trouve.group(1)
                    _, separateur, apres = ecrit.replace(".", ",").partition(",")
                    parts.append((
                        float(ecrit.replace(",", ".")),
                        len(apres) if separateur else 0,
                    ))
            if len(parts) < 2:
                continue
            total = sum(valeur for valeur, _ in parts)
            # La marge se DÉDUIT de l'écriture, elle ne se choisit pas.
            #
            # Chaque part arrondie porte au plus la moitié de sa dernière
            # décimale d'écart : « 33,3 % » vaut entre 33,25 et 33,35. Trois
            # parts au dixième tolèrent donc 0,15 point, douze en tolèrent
            # 0,6. Un seuil fixe serait trop serré pour un tableau à douze
            # acteurs — et refuserait un tableau juste — ou trop lâche pour
            # trois, laissant passer une vraie incohérence.
            marge = sum(0.5 * 10 ** (-decimales) for _, decimales in parts)
            if total <= 100 + marge:
                continue
            motifs.append(
                f"Bloc {index} (tableau), colonne « {entete} » : les parts "
                f"totalisent {total:.1f} %, ce qui est impossible pour une "
                "répartition d'un même marché. Vérifie que toutes portent le "
                "MÊME périmètre — même pays, même année, même secteur, même "
                "canal, même périmètre de produits, même unité — et écarte "
                "celles qui n'y répondent pas."
            )
    return motifs


def _motifs_de_vocabulaire_interne(payload: ChapitrePayload) -> list[str]:
    """Refuse le vocabulaire du dispositif dans le document du client.

    Voir `_VOCABULAIRE_INTERNE` : chaque locution porte son qualificatif, pour
    qu'un pipeline commercial, un socle de clientèle ou un prompt dans une
    étude sur l'IA traversent intacts. Le refus vaut mieux qu'un nettoyage :
    retirer « socle verrouillé » d'une phrase laisserait une phrase qui parle
    encore de nos rouages.
    """
    motifs: list[str] = []
    for index, bloc in enumerate(getattr(payload, "blocs", ()) or ()):
        for champ, texte_brut in _textes_du_bloc(bloc):
            if champ.rsplit(".", 1)[-1] in _CHAMPS_LUS_PAR_LA_MACHINE:
                continue
            if texte_brut.strip() in _valeurs_structurelles():
                continue
            texte = _sans_les_adresses(texte_brut)
            for nom, motif in _VOCABULAIRE_INTERNE:
                trouvee = motif.search(texte)
                if trouvee is None:
                    continue
                debut = max(trouvee.start() - 20, 0)
                motifs.append(
                    f"Bloc {index} ({bloc.type}), champ `{champ}` : « "
                    f"{trouvee.group(0)} » nomme le DISPOSITIF, pas le marché "
                    f"({nom}) — « …{texte[debut:debut + _EXTRAIT]}… ». Le client "
                    "lit une étude, jamais le journal de la machine qui l'a "
                    "écrite. Dis la chose du marché, ou retire la phrase."
                )
                break
    return motifs


def _motifs_de_notation_interne(payload: ChapitrePayload) -> list[str]:
    """Refuse la notation du prompt recopiée dans le document.

    Mesuré sur `2490c7cf` : le modèle a écrit « deux taux de même nature
    [pourcentage] » dans un commentaire de figure. Il n'a rien fait de mal — on
    lui a montré cette notation, il l'a employée. C'est à nous de dire qu'elle
    ne se recopie pas, et de le vérifier.

    La réparation aurait été possible ici (retirer les crochets). On refuse
    quand même : contrairement à une double espace, la présence de cette
    notation signale que le modèle PARLE de sa consigne au lieu de rédiger.
    Effacer les crochets laisserait la phrase « deux taux de même nature », qui
    n'a rien à faire dans une étude remise à un client.
    """
    motifs: list[str] = []
    for index, bloc in enumerate(getattr(payload, "blocs", ()) or ()):
        for champ, texte in _textes_du_bloc(bloc):
            trouvee = _NOTATION_INTERNE.search(texte)
            if trouvee is None:
                continue
            motifs.append(
                f"Bloc {index} ({bloc.type}), champ `{champ}` : « "
                f"{trouvee.group(0)} » est une notation de la CONSIGNE, pas du "
                "français. Le socle te donne la nature de chaque identifiant "
                "entre crochets pour que tu saches ce qui se trace ensemble ; "
                "elle ne se recopie jamais dans le document. Écris la phrase "
                "sans elle, ou sans la mention de nature du tout."
            )
    return motifs


def _textes_du_bloc(bloc: BaseModel, prefixe: str = "") -> list[tuple[str, str]]:
    """Tous les champs textuels d'un bloc, y compris IMBRIQUÉS.

    Parcourt le modèle plutôt qu'une liste de noms écrite à la main : un bloc
    ajouté demain sera couvert sans que personne y pense, et une liste fermée
    est exactement ce que la règle 4 condamne.

    **La descente dans les modèles imbriqués n'est pas un raffinement.** Un
    `BlocTableau` ne porte pas de texte : il porte un `Tableau`, qui porte
    `entetes` et `lignes`. Une première version restée en surface ne voyait donc
    aucune cellule — c'est-à-dire précisément l'endroit où un tableau HTML a le
    plus de chances d'atterrir, puisque c'est un tableau que le modèle essayait
    de faire. Le contrôle aurait été vert sur le défaut qu'il vise (règle 1).
    """
    sortie: list[tuple[str, str]] = []
    for nom in type(bloc).model_fields:
        chemin = f"{prefixe}{nom}"
        sortie.extend(_textes_de_la_valeur(getattr(bloc, nom, None), chemin))
    return sortie


def _textes_de_la_valeur(valeur: Any, chemin: str) -> list[tuple[str, str]]:
    """Chaînes contenues dans une valeur, quelle que soit sa profondeur."""
    if isinstance(valeur, str):
        return [(chemin, valeur)]
    if isinstance(valeur, BaseModel):
        return _textes_du_bloc(valeur, prefixe=f"{chemin}.")
    if isinstance(valeur, (list, tuple)):
        sortie: list[tuple[str, str]] = []
        for element in valeur:
            sortie.extend(_textes_de_la_valeur(element, chemin))
        return sortie
    return []
