"""Mesure l'écart entre un chapitre produit et le modèle de référence."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .chargement import Dosage, chapitre_du_modele, dosage_attendu

#: Tolérances de la spécification.
TOLERANCE_TABLEAUX = 1
TOLERANCE_PARAGRAPHES = 1
TOLERANCE_VOLUME = 0.15

#: Une variable de gabarit laissée telle quelle : `{{client.nom}}`.
_VARIABLE = re.compile(r"\{\{[^}]*\}\}")

#: Blocs dont l'ordre porte le sens et dont la place ne se rattrape pas au
#: rendu. Le contrôle de séquence les compare position par position ; les
#: paragraphes et tableaux, eux, gardent la tolérance de ±1 du cahier des
#: charges et ne sont pas comparés dans l'ordre.
_ORDRE_SIGNIFIANT = ("titre_sous_section", "graphique", "encadre", "grille_kpi")


class Gravite(StrEnum):
    BLOQUANTE = "bloquante"
    AVERTISSEMENT = "avertissement"


@dataclass(frozen=True)
class Ecart:
    """Un écart au modèle. Le détail doit être trouvable dans le chapitre.

    La règle 2 est explicite là-dessus : un motif d'échec qu'on ne retrouve pas
    dans le document envoie corriger la mauvaise chose.
    """

    regle: str
    gravite: Gravite
    detail: str


@dataclass(frozen=True)
class RapportConformite:
    chapitre: int
    ecarts: list[Ecart] = field(default_factory=list)
    #: Règles réellement exécutées.
    controles_executes: list[str] = field(default_factory=list)
    #: Règles que le contrat actuel ne permet PAS d'exécuter, avec leur raison.
    #: Elles ne sont ni réussies ni échouées : elles sont absentes, et ça se dit.
    controles_impossibles: dict[str, str] = field(default_factory=dict)

    @property
    def bloquantes(self) -> list[Ecart]:
        return [e for e in self.ecarts if e.gravite is Gravite.BLOQUANTE]

    @property
    def conforme(self) -> bool:
        """Le chapitre peut-il être rendu ?

        Un rapport sans contrôle exécuté n'est PAS conforme : ne rien avoir
        vérifié n'est pas avoir vérifié sans rien trouver (règle 1).
        """
        return bool(self.controles_executes) and not self.bloquantes

    def resume(self) -> str:
        if not self.controles_executes:
            return "Aucun contrôle exécuté."
        if not self.ecarts:
            return f"{len(self.controles_executes)} contrôles, aucun écart."
        compte: dict[str, int] = {}
        for ecart in self.ecarts:
            compte[ecart.gravite] = compte.get(ecart.gravite, 0) + 1
        detail = ", ".join(f"{nombre} {gravite}" for gravite, nombre in compte.items())
        return f"{len(self.controles_executes)} contrôles, {detail}."


# ── Projection du chapitre produit dans le vocabulaire du modèle ─────────────


@dataclass(frozen=True)
class Comptes:
    paragraphes: int
    tableaux: int
    encadres: int
    graphiques: int
    sous_sections: int


def sequence(payload: Any) -> list[str]:
    """Types des blocs du chapitre, dans l'ordre. Le contrat porte l'ordre."""
    return [str(bloc.type) for bloc in payload.blocs]


def sequence_attendue(chapitre_modele: dict[str, Any]) -> list[str]:
    """Types des blocs du modèle, dans l'ordre.

    Les `ligne_source` sont retirées : elles sont écrites par le rendu sous un
    graphique, jamais demandées au modèle de langage. Les compter reviendrait à
    reprocher au chapitre de ne pas produire ce qu'on ne lui demande pas.
    """
    return [
        str(b.get("type"))
        for b in chapitre_modele.get("blocs", [])
        if b.get("type") != "ligne_source"
    ]


def compter(payload: Any) -> Comptes:
    """Compte les blocs du chapitre par type."""
    types = sequence(payload)
    return Comptes(
        paragraphes=types.count("paragraphe"),
        tableaux=types.count("tableau"),
        encadres=types.count("encadre"),
        graphiques=types.count("graphique"),
        sous_sections=types.count("titre_sous_section"),
    )


def _textes(payload: Any) -> Iterable[tuple[str, str]]:
    """Tous les textes du chapitre, avec l'endroit où les trouver.

    Parcourt les blocs dans l'ordre : le numéro de bloc annoncé dans un motif
    d'écart doit permettre de retrouver l'endroit exact (règle 2).
    """
    yield "titre", payload.titre
    yield "accroche", payload.accroche or ""
    yield "résumé", payload.resume
    for index, bloc in enumerate(payload.blocs, start=1):
        type_bloc = str(bloc.type)
        if type_bloc == "titre_sous_section":
            yield f"bloc {index} — sous-titre", bloc.intitule
        elif type_bloc == "paragraphe":
            yield f"bloc {index} — paragraphe", bloc.texte
        elif type_bloc == "tableau":
            for entete in bloc.tableau.entetes:
                yield f"bloc {index} — en-tête de tableau", entete
            for rang, ligne in enumerate(bloc.tableau.lignes, start=1):
                for cellule in ligne:
                    yield f"bloc {index} — tableau, ligne {rang}", cellule
        elif type_bloc == "encadre":
            yield f"bloc {index} — intitulé d'encadré", bloc.encadre.intitule
            for ligne in bloc.encadre.lignes:
                yield f"bloc {index} — encadré", ligne
        elif type_bloc == "grille_kpi":
            for cellule in bloc.cellules:
                yield f"bloc {index} — chiffre clé", cellule.valeur
                yield f"bloc {index} — libellé", cellule.libelle
        elif type_bloc == "graphique":
            yield f"bloc {index} — titre de graphique", bloc.graphique.titre


def _signes(payload: Any) -> int:
    """Volume mesuré sur la MÊME base que `signes_comparables` du modèle.

    Titres de sous-section et paragraphes, rien d'autre. Ni l'accroche, qui a sa
    propre cible, ni les encadrés, que l'extraction ne compte pas. Compter des
    choses différentes des deux côtés produirait un écart qui n'existe pas.
    """
    total = 0
    for bloc in payload.blocs:
        type_bloc = str(bloc.type)
        if type_bloc == "titre_sous_section":
            total += len(bloc.numero) + 1 + len(bloc.intitule)
        elif type_bloc == "paragraphe":
            total += len(bloc.texte)
    return total


# ── Les contrôles ────────────────────────────────────────────────────────────


def _controler_dosage(comptes: Comptes, attendu: Dosage) -> list[Ecart]:
    ecarts: list[Ecart] = []

    if abs(comptes.tableaux - attendu.tableaux) > TOLERANCE_TABLEAUX:
        ecarts.append(Ecart(
            "dosage_tableaux", Gravite.BLOQUANTE,
            f"{comptes.tableaux} tableau(x) pour {attendu.tableaux} au modèle "
            f"(tolérance ±{TOLERANCE_TABLEAUX})",
        ))

    if abs(comptes.paragraphes - attendu.paragraphes) > TOLERANCE_PARAGRAPHES:
        ecarts.append(Ecart(
            "dosage_paragraphes", Gravite.BLOQUANTE,
            f"{comptes.paragraphes} paragraphe(s) pour {attendu.paragraphes} au "
            f"modèle (tolérance ±{TOLERANCE_PARAGRAPHES})",
        ))

    # Les encadrés portent la méthode : leur nombre est celui du modèle, sans
    # tolérance. Un encadré en moins, c'est une décision qui disparaît.
    if comptes.encadres != attendu.encadres:
        ecarts.append(Ecart(
            "dosage_encadres", Gravite.BLOQUANTE,
            f"{comptes.encadres} encadré(s) pour {attendu.encadres} au modèle",
        ))

    if comptes.sous_sections != attendu.sous_sections:
        ecarts.append(Ecart(
            "dosage_sous_sections", Gravite.AVERTISSEMENT,
            f"{comptes.sous_sections} sous-section(s) pour {attendu.sous_sections} "
            "au modèle",
        ))

    return ecarts


def _controler_sequence(payload: Any, chapitre_modele: dict[str, Any]) -> list[Ecart]:
    """Compare l'ORDRE des blocs porteurs de sens.

    Ce contrôle était impossible tant que le contrat portait `sections`,
    `encadres` et `graphiques` en trois listes séparées : la position d'un
    graphique entre deux paragraphes ne pouvait pas s'exprimer, et le moteur
    produisait la même forme pour les vingt-et-un chapitres.

    Seuls les blocs dont la place ne se rattrape pas au rendu sont comparés
    position par position. Les paragraphes et les tableaux gardent la tolérance
    de ±1 du cahier des charges : les inclure ici la contredirait, et deux
    règles qui se contredisent en font une de trop (règle 5).
    """
    produit = [t for t in sequence(payload) if t in _ORDRE_SIGNIFIANT]
    attendu = [
        t for t in sequence_attendue(chapitre_modele) if t in _ORDRE_SIGNIFIANT
    ]
    if produit == attendu:
        return []

    for rang, (obtenu, voulu) in enumerate(zip(produit, attendu, strict=False), start=1):
        if obtenu != voulu:
            return [Ecart(
                "sequence_des_blocs", Gravite.BLOQUANTE,
                f"au {rang}e bloc porteur : « {obtenu} » là où le modèle place "
                f"« {voulu} »",
            )]
    return [Ecart(
        "sequence_des_blocs", Gravite.BLOQUANTE,
        f"{len(produit)} bloc(s) porteur(s) pour {len(attendu)} au modèle : "
        + " / ".join(attendu),
    )]


def _controler_graphiques(comptes: Comptes, attendu: Dosage) -> list[Ecart]:
    if comptes.graphiques >= attendu.graphiques_min:
        return []
    return [Ecart(
        "graphiques_min", Gravite.BLOQUANTE,
        f"{comptes.graphiques} graphique(s) demandé(s) pour un minimum de "
        f"{attendu.graphiques_min}",
    )]


def _controler_volume(payload: Any, attendu: Dosage) -> list[Ecart]:
    if attendu.signes <= 0:
        return []
    produit = _signes(payload)
    ecart = abs(produit - attendu.signes) / attendu.signes
    if ecart <= TOLERANCE_VOLUME:
        return []
    sens = "au-dessus" if produit > attendu.signes else "en dessous"
    return [Ecart(
        "volume", Gravite.BLOQUANTE,
        f"{produit} signes contre {attendu.signes} au modèle, "
        f"{ecart * 100:.0f} % {sens} de la tolérance de "
        f"{TOLERANCE_VOLUME * 100:.0f} %",
    )]


def _controler_data_refs(payload: Any, identifiants_socle: frozenset[str]) -> list[Ecart]:
    """Tout identifiant cité doit exister au socle.

    On ne vérifie PAS qu'un chiffre écrit en toutes lettres correspond à sa
    donnée : c'est le rôle de la vérification du lot 4, qui lit le document
    produit. Deux contrôles jugeant sur la même évidence se donneraient raison
    l'un l'autre (règle 9).
    """
    ecarts: list[Ecart] = []
    inconnus = [i for i in payload.donnees_utilisees if i not in identifiants_socle]
    if inconnus:
        ecarts.append(Ecart(
            "data_refs_inconnus", Gravite.BLOQUANTE,
            "identifiant(s) absent(s) du socle : " + ", ".join(sorted(inconnus)),
        ))
    for index, graphique in enumerate(payload.graphiques, start=1):
        hors = [i for i in graphique.donnees_ids if i not in identifiants_socle]
        if hors:
            ecarts.append(Ecart(
                "data_refs_inconnus", Gravite.BLOQUANTE,
                f"graphique {index} « {graphique.titre} » cite "
                + ", ".join(sorted(hors)) + " — absent(s) du socle",
            ))
    return ecarts


def _controler_variables(payload: Any) -> list[Ecart]:
    """Aucune variable de gabarit ne doit survivre dans le texte livré."""
    ecarts: list[Ecart] = []
    for endroit, texte in _textes(payload):
        restantes = _VARIABLE.findall(texte or "")
        if restantes:
            ecarts.append(Ecart(
                "variable_non_resolue", Gravite.BLOQUANTE,
                f"{endroit} : {', '.join(sorted(set(restantes)))}",
            ))
    return ecarts


# ── Point d'entrée ───────────────────────────────────────────────────────────

#: Contrôles que le contrat du lot 2 ne permet pas d'exécuter aujourd'hui.
#: Déclarés, jamais tus : c'est la différence entre « vérifié » et « pas de
#: nouvelle » (règle 1).
IMPOSSIBLES: dict[str, str] = {}


#: Règles dont l'écart rend le document **faux**, et non seulement hors forme.
#: Un `{{client.nom}}` imprimé tel quel ou un chiffre qui ne vient pas du socle
#: se voient à la première lecture et discréditent l'étude entière. Ceux-là ne
#: partent jamais, quel que soit le nombre de tentatives déjà brûlées.
REGLES_REDHIBITOIRES = frozenset({
    "variable_non_resolue",
    "data_refs_inconnus",
    # Un intitulé du document de référence recopié tel quel place le sujet d'un
    # AUTRE secteur dans l'étude du client. Ce n'est pas un écart de forme :
    # c'est une erreur de fond, visible du premier coup d'œil, et elle ne
    # s'améliore pas en étant tolérée sur la dernière tentative.
    "contamination_du_modele",
})

#: Règles qui mesurent une RESSEMBLANCE AU MODÈLE, et rien d'autre.
#:
#: Décision du 08/08/2026 : « on n'a pas besoin de suivre exactement le modèle,
#: le modèle est pour l'entraînement et c'est tout. » Elles étaient traitées
#: comme un refus tant qu'il restait une tentative, ce qui faisait rejouer le
#: chapitre jusqu'à ce qu'il ressemble au gabarit.
#:
#: Mesuré sur l'étude de marché réelle `b561c2d6` : le rythme est passé de 6,1 à
#: 10,2 minutes par chapitre à mesure que l'étude avançait, parce que les
#: chapitres tardifs — les plus longs et les plus chiffrés — s'écartaient le plus
#: du volume du modèle. 3,14 EUR consommés pour 14 chapitres sur 23, contre
#: 2,28 EUR pour les 22 chapitres du business plan, qui n'a PAS de modèle.
#: Le contrôle coûtait donc davantage que le document lui-même.
#:
#: L'écart n'est pas tu pour autant : il est consigné dans `acceptes`, et c'est
#: la différence entre « vérifié » et « pas de nouvelle » (règle 1). Ce qui
#: change, c'est qu'on ne repaye plus un appel pour le corriger.
#:
#: `graphiques_min` n'y figure PAS, et c'est délibéré : ce n'est pas une
#: ressemblance au modèle mais un PLANCHER de figures. Le rendre consultatif
#: réduirait le nombre de graphiques, alors que la cliente en demande davantage.
REGLES_DE_RESSEMBLANCE = frozenset({
    "volume",
    "sequence_des_blocs",
    "dosage_tableaux",
    "dosage_paragraphes",
    "dosage_encadres",
})

#: Un chapitre que le modèle ne décrit pas — la fiche projet, numérotée 00. Le
#: rapport le déclare bloquant, à juste titre : il ne peut RIEN vérifier, et un
#: contrôle sans point de comparaison est un échec (règle 1). Mais bloquer
#: l'étude pour un écart connu, documenté et sans rapport avec la qualité du
#: texte serait absurde. On le consigne comme non contrôlé, et on avance.
REGLE_HORS_MODELE = "modele_absent"


@dataclass(frozen=True)
class Arbitrage:
    """Ce qu'on refuse, ce qu'on accepte en le disant.

    La séparation existe parce qu'une passe de conformité tout-ou-rien coûterait
    plus qu'elle ne rapporte : vingt-et-un chapitres × trois tentatives, à
    environ deux euros la génération, pour finir en `intervention_requise` sur
    un écart de dosage d'un tableau. Un chapitre légèrement hors dosage reste un
    chapitre lisible ; une étude bloquée n'est rien.

    Ce qui est accepté n'est jamais tu : c'est la différence entre « vérifié »
    et « pas de nouvelle » (règle 1).
    """

    refus: list[str] = field(default_factory=list)
    acceptes: list[str] = field(default_factory=list)
    non_controle: str = ""

    @property
    def bloque(self) -> bool:
        return bool(self.refus)


def arbitrer(rapport: RapportConformite, *, derniere_tentative: bool) -> Arbitrage:
    """Décide du sort d'un chapitre au vu de son rapport de conformité.

    Trois issues, et une seule dépend du compte des tentatives :

    - un écart rédhibitoire refuse **toujours** ;
    - un écart de forme refuse tant qu'il reste une tentative, et est accepté
      puis consigné sur la dernière ;
    - un chapitre hors modèle n'est pas jugé, et le dit.
    """
    hors_modele = next(
        (e for e in rapport.ecarts if e.regle == REGLE_HORS_MODELE), None
    )
    if hors_modele is not None:
        return Arbitrage(non_controle=hors_modele.detail)

    if not rapport.controles_executes:
        # Ne rien avoir vérifié n'est pas avoir vérifié sans rien trouver.
        return Arbitrage(refus=["aucun contrôle de conformité n'a pu être exécuté"])

    redhibitoires = [
        f"{e.regle} : {e.detail}"
        for e in rapport.bloquantes
        if e.regle in REGLES_REDHIBITOIRES
    ]
    # Ressemblance au modèle : constatée et consignée, jamais rejouée.
    ressemblance = [
        f"{e.regle} : {e.detail}"
        for e in rapport.bloquantes
        if e.regle in REGLES_DE_RESSEMBLANCE
    ]
    # Ce qui reste : ni faux, ni simple ressemblance — `graphiques_min`
    # aujourd'hui. Un plancher se rattrape en rejouant, donc on rejoue.
    forme = [
        f"{e.regle} : {e.detail}"
        for e in rapport.bloquantes
        if e.regle not in REGLES_REDHIBITOIRES
        and e.regle not in REGLES_DE_RESSEMBLANCE
    ]

    if redhibitoires:
        return Arbitrage(refus=redhibitoires + forme, acceptes=ressemblance)
    if forme and not derniere_tentative:
        return Arbitrage(refus=forme, acceptes=ressemblance)
    return Arbitrage(acceptes=forme + ressemblance)


#: Le secteur sur lequel le modèle de forme a été MESURÉ.
#:
#: Le modèle vient d'une étude de joaillerie (`references/joalie_2026.docx`).
#: Ses intitulés portent donc les mots de ce secteur-là, et ce sont EUX qui
#: contaminent une étude sur un autre sujet — pas les intitulés de méthode.
#:
#: ## Pourquoi une liste, alors que la règle 4 les condamne
#:
#: Parce qu'elle ne décrit pas une classe de défauts, mais un FAIT : le secteur
#: d'un document précis. Elle ne s'allongera pas à chaque découverte ; elle
#: changera le jour où le modèle sera mesuré sur un autre document, et ce
#: jour-là c'est tout le modèle qu'on remplace.
#:
#: ## Pourquoi ce filtre existe
#:
#: La première version condamnait TOUT intitulé de référence recopié. Elle
#: refusait « Positionnement recommandé » et « Sources principales » — des mots
#: de méthode qu'une étude sur n'importe quel sujet emploie légitimement.
#: Chaque refus coûte une reprise, et un garde-fou qui bloque du bon travail est
#: exactement le défaut corrigé le même jour sur le gate de livraison (règle 2).
_SECTEUR_DE_REFERENCE = frozenset({
    "joaillerie", "joaillier", "bijou", "bijoux", "bijouterie",
    "galerie", "galeries", "sur-mesure", "vintage", "orfèvrerie",
    "gemme", "gemmologie", "lingot", "once", "carat", "sertissage",
})

#: Longueur à partir de laquelle un intitulé recopié n'est plus une coïncidence.
#:
#: « Synthèse » ou « À retenir » se retrouvent légitimement dans deux études :
#: ce sont des mots de méthode. « FOCUS — Approfondissement demandé : marché
#: international des galeries et du sur-mesure » ne se retrouve nulle part par
#: hasard. Le seuil sépare les deux.
_LONGUEUR_CONTAMINANTE = 25


def _porte_le_secteur_de_reference(texte: str) -> bool:
    """Ce libellé nomme-t-il le secteur du document de référence ?

    C'est le seul signal qui distingue une contamination d'une reprise
    légitime. « Positionnement recommandé » ne dit rien de la joaillerie ;
    « … galeries et du sur-mesure » ne parle que d'elle.
    """
    mots = set(re.findall(r"[\w-]+", texte.casefold()))
    return bool(mots & _SECTEUR_DE_REFERENCE)


def _intitules_du_modele(chapitre_modele: dict[str, Any]) -> list[str]:
    """Libellés du chapitre qui nomment le secteur d'origine, et eux seuls."""
    sortie: list[str] = []
    for bloc in chapitre_modele.get("blocs", []):
        for cle in ("etiquette", "intitule_reference"):
            valeur = str(bloc.get(cle, "") or "").strip()
            if (
                len(valeur) >= _LONGUEUR_CONTAMINANTE
                and _porte_le_secteur_de_reference(valeur)
            ):
                sortie.append(valeur)
    return sortie


def _controler_contamination(
    payload: Any, chapitre_modele: dict[str, Any]
) -> list[Ecart]:
    """Refuse un intitulé du document de référence recopié tel quel.

    ## Le cas réel

    Le modèle de forme a été mesuré sur une étude de JOAILLERIE. Ses intitulés
    sont donc écrits avec les mots de ce secteur, et le plan les montre au
    modèle pour qu'il en reprenne la FONCTION — pas le sujet.

    Sur le dossier `c8b4e60a`, une étude consacrée à l'e-commerce pour animaux,
    le lecteur trouvait en page 52 : **« FOCUS — Approfondissement demandé :
    marché international des galeries et du sur-mesure »**. Signalé par la
    cliente. Le modèle n'a rien inventé — on lui avait remis cette étiquette
    telle quelle, sans lui dire de la réécrire.

    ## Pourquoi rédhibitoire et non consultatif

    Les écarts de RESSEMBLANCE sont consultatifs depuis le 08/08/2026 : ils
    mesurent une distance au gabarit, et la cliente a tranché que le modèle
    entraîne sans imposer. Celui-ci est d'une autre nature. Ce n'est pas une
    forme qui s'écarte, c'est le sujet d'une AUTRE étude qui entre dans
    celle-ci. Toléré sur la dernière tentative, il partirait chez le client.

    ## Ce qu'il ne condamne pas

    Les intitulés courts — « Synthèse », « À retenir », « Ce qu'il faut
    retenir » — sont des mots de méthode, communs à toutes les études par
    construction. Seuls les libellés assez longs pour porter un sujet sont
    comparés : au-delà de vingt-cinq signes, une reprise mot pour mot n'est plus
    une coïncidence.
    """
    references = _intitules_du_modele(chapitre_modele)
    if not references:
        return []

    produits: list[str] = []
    for bloc in getattr(payload, "blocs", ()) or ():
        for champ in ("intitule", "etiquette", "titre"):
            valeur = getattr(bloc, champ, None)
            if isinstance(valeur, str):
                produits.append(valeur)
        for imbrique in ("encadre", "tableau", "graphique"):
            interne = getattr(bloc, imbrique, None)
            for champ in ("intitule", "titre"):
                valeur = getattr(interne, champ, None)
                if isinstance(valeur, str):
                    produits.append(valeur)

    ecarts: list[Ecart] = []
    for reference in references:
        normalisee = reference.casefold().strip()
        for produit in produits:
            if produit.casefold().strip() == normalisee:
                ecarts.append(Ecart(
                    "contamination_du_modele", Gravite.BLOQUANTE,
                    f"« {reference} » est l'intitulé du document de référence, "
                    "écrit pour un AUTRE secteur. Il décrit la fonction du "
                    "bloc, pas son sujet : réécris-le pour le secteur de cette "
                    "étude.",
                ))
                break
    return ecarts


def verifier_chapitre(
    payload: Any,
    *,
    identifiants_socle: Iterable[str],
    chemin_modele: str | None = None,
) -> RapportConformite:
    """Compare un chapitre produit au chapitre correspondant du modèle.

    Un chapitre sans modèle est BLOQUANT, pas ignoré : c'est le cas du chapitre
    00 « Fiche projet », que le moteur produit et que le modèle n'a pas.
    """
    numero = int(payload.chapitre)
    modele = chapitre_du_modele(numero, chemin=chemin_modele)
    if modele is None:
        return RapportConformite(
            chapitre=numero,
            ecarts=[Ecart(
                "modele_absent", Gravite.BLOQUANTE,
                f"aucun chapitre {numero:02d} au modèle de référence — le modèle "
                "va de 01 à 21 et n'a pas de fiche projet",
            )],
            controles_executes=["modele_present"],
            controles_impossibles=dict(IMPOSSIBLES),
        )

    attendu = dosage_attendu(modele)
    comptes = compter(payload)
    identifiants = frozenset(identifiants_socle)

    ecarts: list[Ecart] = []
    ecarts += _controler_sequence(payload, modele)
    ecarts += _controler_dosage(comptes, attendu)
    ecarts += _controler_graphiques(comptes, attendu)
    ecarts += _controler_volume(payload, attendu)
    ecarts += _controler_data_refs(payload, identifiants)
    ecarts += _controler_variables(payload)
    ecarts += _controler_contamination(payload, modele)

    return RapportConformite(
        chapitre=numero,
        ecarts=ecarts,
        controles_executes=[
            "modele_present", "sequence_des_blocs", "dosage_tableaux",
            "dosage_paragraphes", "dosage_encadres", "dosage_sous_sections",
            "graphiques_min", "volume", "data_refs_inconnus",
            "variable_non_resolue",
        ],
        controles_impossibles=dict(IMPOSSIBLES),
    )
