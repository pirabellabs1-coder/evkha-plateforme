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
from enum import StrEnum
from typing import Annotated, Any, Literal

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
    entetes: list[str] = Field(min_length=2, max_length=9)
    lignes: list[list[str]] = Field(min_length=1)
    source: str = ""

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
    lignes: list[str] = Field(min_length=1, max_length=6)


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
    cellules: list[CelluleKpi] = Field(min_length=2, max_length=4)


#: Un bloc du chapitre, discriminé par son champ `type`.
Bloc = Annotated[
    BlocSousTitre | BlocParagraphe | BlocTableau | BlocEncadre | BlocGraphique
    | BlocGrilleKpi,
    Field(discriminator="type"),
]

#: Le variant derrière chaque valeur du discriminant. Dérivé de l'union, jamais
#: recopié : une table écrite à la main divergerait au premier bloc ajouté
#: (règle 5). Sert au motif de refus, qui doit nommer les champs admis.
BLOC_PAR_TYPE: dict[str, type[SortieDeChapitre]] = {
    str(modele.model_fields["type"].default): modele
    for modele in (
        BlocSousTitre, BlocParagraphe, BlocTableau, BlocEncadre,
        BlocGraphique, BlocGrilleKpi,
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


def valider_chapitre(
    payload: ChapitrePayload,
    *,
    numero_attendu: int,
    identifiants_socle: frozenset[str],
    resume_mots_min: int,
    resume_mots_max: int,
    secteur: str = "",
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

    inconnues = [i for i in payload.donnees_utilisees if i not in identifiants_socle]
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
    ("lignes séparées par des points-virgules", re.compile(r"(?:[^;\n]*;){3,}")),
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
