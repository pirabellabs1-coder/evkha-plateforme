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

    entetes: list[str] = Field(min_length=2, max_length=6)
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

    C'est l'élément le plus répété du livrable de référence : « LECTURE EVKHA —
    Opportunité / Limite / Décision », une occurrence par chapitre sur quinze
    chapitres. Il porte la méthode, pas de la décoration : c'est là que
    l'analyse devient une décision.
    """

    model_config = {"extra": "forbid"}

    intitule: str = Field(min_length=1, max_length=80)
    lignes: list[str] = Field(min_length=1, max_length=6)


class ChapitrePayload(BaseModel):
    """Sortie structurée d'un chapitre."""

    model_config = {"extra": "forbid"}

    chapitre: int = Field(ge=0, le=99)
    titre: str = Field(min_length=1, max_length=220)
    #: Phrase d'accroche affichée sous le titre dans le bandeau de chapitre.
    accroche: str = Field(default="", max_length=400)
    sections: list[Section] = Field(min_length=1)
    #: Encadrés de synthèse. Vide accepté pour rester compatible avec les
    #: chapitres produits avant l'ajout de ce champ.
    encadres: list[Encadre] = Field(default_factory=list)
    #: Identifiants du socle réellement exploités par ce chapitre.
    donnees_utilisees: list[str] = Field(default_factory=list)
    graphiques: list[Graphique] = Field(default_factory=list)
    #: Résumé transmis aux chapitres suivants (§6.1 : 150 à 250 mots).
    resume: str = Field(min_length=1)

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
        return "\n\n".join(f"{s.titre}\n{s.contenu}" for s in self.sections)


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

    titres = [s.titre.strip().lower() for s in payload.sections]
    if len(set(titres)) != len(titres):
        motifs.append("Deux sections portent le même titre.")

    return motifs
