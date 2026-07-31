"""Contrat de sortie d'un chapitre (§6.1 du cahier des charges).

Un chapitre ne rend plus du texte libre : il rend une structure. C'est ce qui
permet de savoir, sans analyser une chaîne de caractères, quelles données du
socle il a utilisées et quels graphiques il déclare.

Conséquence directe : un graphique ne peut plus contredire le texte qu'il
illustre, puisqu'il ne porte pas de valeurs — il porte des identifiants du
socle, résolus au rendu.
"""
from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator


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


class Tableau(BaseModel):
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
        largeur = len(self.entetes)
        for rang, ligne in enumerate(self.lignes, start=1):
            if len(ligne) != largeur:
                msg = (
                    f"La ligne {rang} compte {len(ligne)} cellules pour "
                    f"{largeur} colonnes déclarées."
                )
                raise ValueError(msg)
        return self


class Section(BaseModel):
    model_config = {"extra": "forbid"}

    titre: str = Field(min_length=1, max_length=220)
    contenu: str = Field(min_length=1)
    #: Tableau portant l'information de la section. Facultatif, mais c'est lui
    #: qui donne au livrable sa densité : voir `Tableau`.
    tableau: Tableau | None = None


class Graphique(BaseModel):
    """Demande de visuel. Ne porte AUCUNE valeur, seulement des identifiants."""

    model_config = {"extra": "forbid"}

    type: TypeGraphique
    titre: str = Field(min_length=1, max_length=220)
    donnees_ids: list[str] = Field(min_length=1)
    commentaire: str = ""


class Encadre(BaseModel):
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


class CelluleKpi(BaseModel):
    """Un chiffre clé : la valeur, ce qu'elle mesure, d'où elle vient."""

    model_config = {"extra": "forbid"}

    valeur: str = Field(min_length=1, max_length=40)
    libelle: str = Field(min_length=1, max_length=160)
    source: str = ""


class BlocSousTitre(BaseModel):
    """Titre de sous-section : « 1.1 Deux périmètres à ne pas confondre »."""

    model_config = {"extra": "forbid"}

    type: Literal["titre_sous_section"] = "titre_sous_section"
    numero: str = Field(min_length=1, max_length=8)
    intitule: str = Field(min_length=1, max_length=220)


class BlocParagraphe(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["paragraphe"] = "paragraphe"
    texte: str = Field(min_length=1)


class BlocTableau(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["tableau"] = "tableau"
    tableau: Tableau


class BlocEncadre(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["encadre"] = "encadre"
    encadre: Encadre


class BlocGraphique(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["graphique"] = "graphique"
    graphique: Graphique


class BlocGrilleKpi(BaseModel):
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


class ChapitrePayload(BaseModel):
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
        declares = set(self.donnees_utilisees)
        for graphique in self.graphiques:
            hors = [i for i in graphique.donnees_ids if i not in declares]
            if hors:
                msg = (
                    f"Le graphique « {graphique.titre} » utilise {hors}, "
                    "absent de `donnees_utilisees`. Un graphique ne peut pas "
                    "reposer sur une donnée que le chapitre ne déclare pas."
                )
                raise ValueError(msg)
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


def valider_chapitre(
    payload: ChapitrePayload,
    *,
    numero_attendu: int,
    identifiants_socle: frozenset[str],
    resume_mots_min: int,
    resume_mots_max: int,
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

    return motifs
