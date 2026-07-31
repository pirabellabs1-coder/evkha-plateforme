"""Du socle et des chapitres vers la structure de rendu (lot 3).

Le lot 0 a construit un moteur qui rend une étude décrite en JSON. Le lot 1 a
produit le socle, le lot 2 les chapitres. Ce module est le raccord : il traduit
les objets métier en blocs de rendu.

Il ne décide de rien d'éditorial. Sa seule liberté est la **mise en forme** :
quel bloc pour quel contenu, dans quel ordre. Les valeurs viennent du socle,
les phrases des chapitres.

Deux points structurent tout le module.

1. **La densité.** Le document validé par la cliente est fait de tableaux
   reliés par de la prose courte : 52 % de ses mots vivent dans des tableaux,
   la médiane de ses paragraphes est de douze mots. Une section qui porte un
   tableau le rend ; sa prose devient une amorce, pas un développement.

2. **Le rapport d'assemblage.** Tout ce qui n'a pas pu être rendu est
   enregistré avec son motif. Un graphique abandonné en silence ferait passer
   un livrable amputé pour un livrable complet (règle 1).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from ..chapitres.schema import ChapitrePayload, Graphique
from ..socle.schema import Socle
from . import secteurs
from .donnees_graphiques import resoudre

#: Au-delà, la prose d'une section est une amorce tronquée plutôt qu'un
#: paragraphe entier : c'est la mesure qui sépare le document de référence du
#: mur de texte refusé par la cliente.
#:
#: Calibré à 55, puis relevé à 90 sur mesure comparative. À 55, le document
#: rendu portait 2 599 mots de prose contre 4 131 au modèle validé, et la part
#: des mots vivant dans les tableaux montait à 66 % contre 52 %. La cliente
#: l'a lu comme « trop de tableaux » — à juste titre, mais la cause était
#: l'inverse : il n'y avait plus assez de texte autour d'eux.
#:
#: 90 mots par section × ~50 sections ≈ 4 500, l'ordre de grandeur du modèle.
#: La coupe reste faite sur une frontière de phrase, jamais au milieu.
MOTS_AMORCE_MAX = 90

#: Mention de repli, quand l'abonné n'a rien défini. Volontairement **neutre** :
#: elle ne nomme personne. Un document livré en marque blanche ne doit porter
#: que le nom de celui qui le remet à son client.
MENTION_PAR_DEFAUT = "Document confidentiel — reproduction interdite"


def mentions_finales(marque: dict[str, Any] | None) -> list[str]:
    """Mentions de quatrième de couverture, tirées de la marque de l'abonné.

    Elles étaient écrites en dur : « EVKHA · Système d'analyse de marché »,
    « Méthode déposée à l'INPI ». Chaque document réel aurait donc signé au nom
    de la plateforme un travail remis par l'abonné à SON client — exactement ce
    que la marque blanche interdit.

    Aucune mention inventée : si l'abonné n'a rien renseigné, il ne reste que
    la confidentialité, qui ne nomme personne.
    """
    marque = marque or {}
    lignes = [
        str(marque.get("nom", "")).strip(),
        str(marque.get("mention_legale", "")).strip(),
        str(marque.get("mention_confidentialite", "")).strip() or MENTION_PAR_DEFAUT,
    ]
    return [ligne for ligne in lignes if ligne]


@dataclass
class RapportAssemblage:
    """Ce qui a été rendu, et ce qui ne l'a pas été.

    Destiné à l'admin et au lot 4. Un livrable dont tous les graphiques ont été
    abandonnés reste un livrable, mais il ne doit pas passer pour complet.
    """

    graphiques_demandes: int = 0
    graphiques_rendus: int = 0
    graphiques_convertis: list[str] = field(default_factory=list)
    graphiques_abandonnes: list[str] = field(default_factory=list)
    chapitres: int = 0
    tableaux: int = 0
    #: Identifiants du socle effectivement portés par une figure rendue.
    #: La passe de vérification en a besoin : un chiffre dessiné dans un PNG
    #: est bien sous les yeux du lecteur, mais invisible à une relecture du
    #: texte. Sans cette liste, elle le déclarerait absent du livrable.
    identifiants_rendus: set[str] = field(default_factory=set)

    @property
    def complet(self) -> bool:
        return not self.graphiques_abandonnes

    def resume(self) -> str:
        parties = [
            f"{self.chapitres} chapitres",
            f"{self.tableaux} tableaux",
            f"{self.graphiques_rendus}/{self.graphiques_demandes} graphiques",
        ]
        if self.graphiques_convertis:
            parties.append(f"{len(self.graphiques_convertis)} convertis")
        if self.graphiques_abandonnes:
            parties.append(f"{len(self.graphiques_abandonnes)} abandonnés")
        return ", ".join(parties)


def _amorce(texte: str) -> str:
    """La prose d'une section, ramenée à une amorce.

    Couper à la phrase et non au mot : une amorce tronquée au milieu d'un
    groupe nominal se voit immédiatement à la lecture.
    """
    texte = " ".join(texte.split())
    if len(texte.split()) <= MOTS_AMORCE_MAX:
        return texte
    conserve: list[str] = []
    total = 0
    for phrase in texte.replace("! ", "!|").replace("? ", "?|").replace(
        ". ", ".|"
    ).split("|"):
        mots = len(phrase.split())
        if conserve and total + mots > MOTS_AMORCE_MAX:
            break
        conserve.append(phrase)
        total += mots
    return " ".join(conserve).strip()


def _blocs_graphique(
    socle: Socle,
    graphiques: Sequence[Graphique],
    profil: secteurs.ProfilSectoriel,
    rapport: RapportAssemblage,
    reference: str,
) -> list[dict[str, Any]]:
    blocs: list[dict[str, Any]] = []
    for demande in graphiques:
        rapport.graphiques_demandes += 1
        type_demande = str(demande.type)

        if type_demande in profil.graphiques_a_eviter:
            rapport.graphiques_abandonnes.append(
                f"{reference} · {demande.titre} : type `{type_demande}` hors "
                f"sujet pour le secteur « {profil.libelle} »"
            )
            continue

        resolution = resoudre(socle, type_demande, demande.donnees_ids)
        if not resolution.retenu:
            rapport.graphiques_abandonnes.append(
                f"{reference} · {demande.titre} : {resolution.motif}"
            )
            continue

        if resolution.converti:
            rapport.graphiques_convertis.append(
                f"{reference} · {demande.titre} : {type_demande} → "
                f"{resolution.type_graphique} ({resolution.motif})"
            )
        rapport.graphiques_rendus += 1
        rapport.identifiants_rendus.update(demande.donnees_ids)
        blocs.append({
            "type": "graphique",
            "graphique": resolution.type_graphique,
            "titre": demande.titre,
            "source": demande.commentaire,
            "donnees": resolution.donnees,
        })
    return blocs


def blocs_du_chapitre(
    payload: ChapitrePayload,
    socle: Socle,
    profil: secteurs.ProfilSectoriel,
    rapport: RapportAssemblage,
) -> list[dict[str, Any]]:
    """Un chapitre structuré, traduit en blocs de rendu."""
    rapport.chapitres += 1
    blocs: list[dict[str, Any]] = [{
        "type": "bandeau",
        "numero": payload.chapitre,
        "titre": payload.titre,
        "accroche": payload.accroche,
    }]

    # Les blocs sont parcourus DANS LEUR ORDRE. C'est tout l'objet du contrat :
    # le modèle de référence décrit une suite différente pour chacun des
    # vingt-et-un chapitres, et trois listes séparées ne pouvaient produire
    # qu'une forme unique, répétée partout.
    from ..chapitres.schema import (  # noqa: PLC0415 — évite un cycle d'import
        BlocEncadre,
        BlocGraphique,
        BlocGrilleKpi,
        BlocParagraphe,
        BlocSousTitre,
        BlocTableau,
    )

    for bloc in payload.blocs:
        if isinstance(bloc, BlocSousTitre):
            blocs.append({
                "type": "sous_titre",
                "texte": f"{bloc.numero} {bloc.intitule}".strip(),
            })
        elif isinstance(bloc, BlocParagraphe):
            amorce = _amorce(bloc.texte)
            if amorce:
                blocs.append({"type": "paragraphe", "texte": amorce})
        elif isinstance(bloc, BlocTableau):
            rapport.tableaux += 1
            blocs.append({
                "type": "tableau",
                "entetes": bloc.tableau.entetes,
                "lignes": bloc.tableau.lignes,
                "source": bloc.tableau.source,
            })
        elif isinstance(bloc, BlocEncadre):
            blocs.append({
                "type": "encadre",
                "libelle": bloc.encadre.intitule,
                "lignes": bloc.encadre.lignes,
                "verdict": _est_un_verdict(bloc.encadre.intitule),
            })
        elif isinstance(bloc, BlocGrilleKpi):
            # `chiffres`, et un TRIPLET par cellule : c'est ce qu'attend
            # `composants.grille_chiffres`. Une première version émettait
            # `cellules` avec des dictionnaires — la livraison échouait sur un
            # `KeyError: 'chiffres'`, et l'incident était le seul endroit où ça
            # se voyait.
            blocs.append({
                "type": "kpi",
                "chiffres": [
                    (c.valeur, c.libelle, c.source) for c in bloc.cellules
                ],
            })
        elif isinstance(bloc, BlocGraphique):
            # Résolu ICI, à sa place dans la suite. Les résoudre en bloc à la
            # fin les aurait tous rejetés en queue de chapitre, ce qui est
            # précisément ce que le contrat ordonné vient corriger.
            #
            # Pas de saut de page avant : il y en avait un, systématique, qui
            # produisait une page ENTIÈREMENT BLANCHE par chapitre — mesuré aux
            # pages 4, 7, 10, 13, 16, 19… Le titre, l'image et la légende sont
            # désormais liés par `keep_with_next` (voir `composants`).
            blocs.extend(_blocs_graphique(
                socle, [bloc.graphique], profil, rapport,
                reference=f"Chapitre {payload.chapitre}",
            ))

    return blocs


#: Intitulés dont l'encadré prend le fond soutenu de la référence. Comparaison
#: sur le début de l'intitulé, insensible à la casse : le modèle écrit aussi
#: bien « Verdict » que « Verdict — conditions de viabilité ».
_INTITULES_VERDICT = ("verdict", "conclusion", "décision", "decision")


def _est_un_verdict(intitule: str) -> bool:
    debut = intitule.strip().casefold()
    return any(debut.startswith(mot) for mot in _INTITULES_VERDICT)


def assembler_etude(
    *,
    socle: Socle,
    chapitres: Sequence[ChapitrePayload],
    titre: str,
    sous_titre: str = "",
    marque: dict[str, str] | None = None,
    mention: str = "Document confidentiel — usage stratégique interne",
) -> tuple[dict[str, Any], RapportAssemblage]:
    """Structure de rendu complète, plus le rapport de ce qui n'a pas suivi.

    Les chapitres sont rendus dans l'ordre de leur numéro et non dans l'ordre
    où ils arrivent : la génération est parallèle, la lecture ne l'est pas.
    """
    rapport = RapportAssemblage()
    profil = secteurs.profil_du_secteur(socle.secteur)

    ordonnes = sorted(chapitres, key=lambda payload: payload.chapitre)
    blocs_par_chapitre = [
        {
            "numero": payload.chapitre,
            "titre": payload.titre,
            "blocs": blocs_du_chapitre(payload, socle, profil, rapport),
        }
        for payload in ordonnes
    ]

    etude = {
        "titre": titre,
        "sous_titre": sous_titre or socle.secteur,
        "mention": mention,
        "secteur": socle.secteur,
        "profil_sectoriel": profil.code,
        "marque": marque or {},
        # Le document est livré en MARQUE BLANCHE : il porte le nom de
        # l'abonné, jamais celui de la plateforme. « EVKHA · Système d'analyse
        # de marché » était écrit en dur ici et serait donc parti sur chaque
        # document réel, signant le travail d'un tiers au nom d'un autre.
        "mentions_finales": mentions_finales(marque),
        "chapitres": blocs_par_chapitre,
    }
    return etude, rapport
