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

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from ..chapitres.schema import ChapitrePayload, Graphique
from ..prompts import PLANCHER_FIGURES
from ..socle.schema import Socle, nombre_francais, unite_lisible
from . import secteurs
from .annexe_chiffres import a_son_echelle, blocs_annexe, meme_arrondi
from .donnees_graphiques import Resolution, resoudre
from .specification_figures import controler_la_figure
from .texte import libelle_court

_log = logging.getLogger(__name__)

#: Formes employées par la passe de complétion, dans cet ordre de préférence.
#:
#: Toutes se contentent d'une liste de valeurs scalaires — c'est la seule chose
#: dont la complétion dispose, puisqu'elle ne travaille qu'avec les
#: identifiants que le chapitre a lui-même cités. Les formes qui exigent une
#: série temporelle, des notes ou une matrice ne sont pas candidates : les
#: proposer produirait des abandons, c'est-à-dire du travail pour rien.
#:
#: L'ordre fait tourner les formes d'un chapitre à l'autre : quatre entonnoirs
#: de suite tiendraient le plancher tout en trahissant la demande — « les
#: graphes ne seront pas toujours les mêmes ».
_FORMES_DE_COMPLETION = (
    "barres_horizontales", "anneau", "barres", "camembert", "jauges", "entonnoir",
)

#: Identifiants portés par une figure de complétion. Deux au minimum — une
#: figure à une seule barre n'apprend rien —, quatre au plus : au-delà, les
#: étiquettes se chevauchent, défaut mesuré sur le dossier réel 90cbb3d9.
#: Ce plafond est aussi ce qui permet à un chapitre riche d'en porter deux.
_DONNEES_PAR_FIGURE = 4

#: Au-delà, la prose d'une section est ramenée à une amorce plutôt qu'un
#: paragraphe entier : c'est la mesure qui sépare le document de référence du
#: mur de texte refusé par la cliente.
#:
#: Calibré à 55, puis relevé à 90 sur mesure comparative. À 55, le document
#: rendu portait 2 599 mots de prose contre 4 131 au modèle validé, et la part
#: des mots vivant dans les tableaux montait à 66 % contre 52 %. La cliente
#: l'a lu comme « trop de tableaux » — à juste titre, mais la cause était
#: l'inverse : il n'y avait plus assez de texte autour d'eux.
#:
#: La coupe est faite sur une frontière de phrase, jamais au milieu.
#:
#: ── Relevé le 05/08/2026 : ce plafond empêchait de DÉPASSER le modèle ──────
#:
#: 90 mots × ~50 sections ≈ 4 500, soit exactement l'ordre de grandeur du
#: modèle. Le réglage visait donc à ATTEINDRE la référence — et interdisait
#: mécaniquement de la dépasser. Or le modèle est un standard, pas un plafond :
#: un client dont le besoin est plus large doit recevoir plus, pas la même
#: chose tronquée.
#:
#: Deux défauts distincts, et le second est le plus grave :
#:   1. le plafond bride la richesse du livrable ;
#:   2. la coupe était SILENCIEUSE. Un chapitre de 200 mots d'analyse en
#:      perdait 110 sans que rien ne le signale — ni au log, ni au rapport
#:      d'assemblage, ni à la vérification. Quelque chose refaisait le document
#:      après la génération et l'amputait (règle 3).
#:
#: Le garde-fou contre le mur de texte n'a pas disparu pour autant : il vit en
#: aval, dans `verification/controles.py`, qui mesure sur le FICHIER rendu la
#: part des tableaux, la médiane des paragraphes et la part des paragraphes
#: longs — trois seuils relevés sur le modèle et validés par la cliente. Cette
#: troncature en amont faisait double emploi avec lui, au prix du contenu.
#:
#: Réglable sans redéploiement, et désactivable : 0 = aucune coupe.
_MOTS_PARAGRAPHE_DEFAUT = 150


def mots_paragraphe_max() -> int:
    """Plafond de mots par section, ou 0 si la coupe est désactivée."""
    valeur = getattr(settings, "EVKHA_MOTS_PARAGRAPHE_MAX", _MOTS_PARAGRAPHE_DEFAUT)
    return max(int(valeur if valeur is not None else _MOTS_PARAGRAPHE_DEFAUT), 0)


#: Conservé pour les appelants existants (tests, imports). Lire la valeur par
#: `mots_paragraphe_max()` : elle seule tient compte du réglage.
MOTS_AMORCE_MAX = _MOTS_PARAGRAPHE_DEFAUT

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
    #: Figures refusées au dessin, imprimées en TABLEAU : l'information reste
    #: dans le document, et le lecteur ne perd que la forme.
    graphiques_en_tableau: list[str] = field(default_factory=list)
    graphiques_abandonnes: list[str] = field(default_factory=list)
    #: Pour la MESURE seulement (jamais montré au client) : chaque figure
    #: perdue, ses données demandées avec leur unité, et pourquoi la réparation
    #: a échoué. Le motif seul ne permettait pas de corriger la classe.
    diagnostic_des_abandons: list[dict[str, object]] = field(default_factory=list)
    #: Figures impossibles telles que demandées, DESSINÉES avec une partie de
    #: leurs propres données (`reparation_figures`). Comptées dans les rendues
    #: — elles sont dans le document — mais jamais parmi ce que le modèle a
    #: obtenu : la mesure les soustrait et les nomme.
    graphiques_repares: list[str] = field(default_factory=list)
    chapitres: int = 0
    tableaux: int = 0
    #: Identifiants du socle effectivement portés par une figure rendue.
    #: La passe de vérification en a besoin : un chiffre dessiné dans un PNG
    #: est bien sous les yeux du lecteur, mais invisible à une relecture du
    #: texte. Sans cette liste, elle le déclarerait absent du livrable.
    identifiants_rendus: set[str] = field(default_factory=set)
    #: Prose écartée du document au moment de l'assemblage. Ces deux compteurs
    #: existent parce que la coupe était silencieuse : le contenu disparaissait
    #: du livrable sans trace nulle part. Un livrable dont on a retiré 800 mots
    #: d'analyse reste un livrable, mais il ne doit pas passer pour intact.
    paragraphes_tronques: int = 0
    mots_tronques: int = 0
    #: Figures ajoutées par la passe de complétion, avec le chapitre et les
    #: identifiants employés. Une complétion silencieuse serait un mensonge par
    #: omission : le lecteur du rapport doit pouvoir distinguer une figure
    #: voulue par le modèle d'une figure ajoutée pour tenir le plancher.
    graphiques_completes: list[str] = field(default_factory=list)
    #: Commentaires de graphique écartés parce qu'ils étaient le brief du dessin
    #: (« Illustre l'écart… ») et non une phrase pour le client. Tracés ici
    #: plutôt que perdus : c'est aussi le signal que le modèle confond encore
    #: le champ, et qu'il faut regarder sa consigne.
    consignes_de_dessin_retirees: list[str] = field(default_factory=list)
    #: Figures ÉCARTÉES parce que le document portait déjà la même — même forme,
    #: mêmes données résolues. Elles ne font rien perdre au lecteur : l'image est
    #: plus haut. Elles ne rendent donc pas le livrable incomplet, mais elles se
    #: disent (règle 1).
    graphiques_en_double: list[str] = field(default_factory=list)
    #: La MÉMOIRE du document : chaque figure dessinée, par sa forme et ses
    #: données résolues (`_signature`), avec le chapitre et le titre sous
    #: lesquels elle est posée. Rien ne s'en souvenait — business plan ÉCLORE,
    #: 29/09/2026 : la même image deux fois (§ 3.11 du diagnostic). Le lieu
    #: sert au renvoi qui remplace le doublon.
    signatures_dessinees: dict[str, tuple[str, str]] = field(
        default_factory=dict, repr=False,
    )
    #: Idem pour les tableaux de repli : un repli ne remplace une figure en
    #: double que s'il n'est pas lui-même déjà imprimé.
    signatures_des_tableaux: set[str] = field(default_factory=set, repr=False)

    @property
    def complet(self) -> bool:
        return not self.graphiques_abandonnes and not self.paragraphes_tronques

    def resume(self) -> str:
        parties = [
            f"{self.chapitres} chapitres",
            f"{self.tableaux} tableaux",
            f"{self.graphiques_rendus}/{self.graphiques_demandes} graphiques",
        ]
        if self.graphiques_completes:
            parties.append(f"{len(self.graphiques_completes)} complétés")
        if self.graphiques_convertis:
            parties.append(f"{len(self.graphiques_convertis)} convertis")
        if self.graphiques_repares:
            parties.append(f"{len(self.graphiques_repares)} réparés")
        if self.graphiques_abandonnes:
            parties.append(f"{len(self.graphiques_abandonnes)} abandonnés")
        if self.graphiques_en_double:
            parties.append(f"{len(self.graphiques_en_double)} en double écartés")
        if self.consignes_de_dessin_retirees:
            parties.append(
                f"{len(self.consignes_de_dessin_retirees)} consigne(s) de dessin "
                "retirée(s) sous les graphiques"
            )
        if self.paragraphes_tronques:
            parties.append(
                f"{self.paragraphes_tronques} paragraphe(s) tronqué(s), "
                f"{self.mots_tronques} mots écartés"
            )
        return ", ".join(parties)


def _amorce(texte: str, rapport: RapportAssemblage | None = None) -> str:
    """La prose d'une section, ramenée à une amorce si elle dépasse le plafond.

    Couper à la phrase et non au mot : une amorce tronquée au milieu d'un
    groupe nominal se voit immédiatement à la lecture.

    Toute coupe est DÉCLARÉE au rapport. Elle était silencieuse : le document
    perdait de l'analyse sans que personne ne puisse le constater ailleurs que
    sur le fichier final, en comptant les mots. Ce qui refait le document après
    la génération doit se voir (règle 3).
    """
    plafond = mots_paragraphe_max()
    texte = " ".join(texte.split())
    mots_entree = len(texte.split())

    if plafond <= 0 or mots_entree <= plafond:
        return texte

    conserve: list[str] = []
    total = 0
    for phrase in texte.replace("! ", "!|").replace("? ", "?|").replace(
        ". ", ".|"
    ).split("|"):
        mots = len(phrase.split())
        if conserve and total + mots > plafond:
            break
        conserve.append(phrase)
        total += mots

    resultat = " ".join(conserve).strip()
    perdus = mots_entree - len(resultat.split())
    if perdus > 0:
        if rapport is not None:
            rapport.paragraphes_tronques += 1
            rapport.mots_tronques += perdus
        _log.warning(
            "Assemblage : paragraphe ramené de %s à %s mots (plafond %s). "
            "%s mots d'analyse écartés du document livré.",
            mots_entree, len(resultat.split()), plafond, perdus,
        )
    return resultat


def _tableau_de_repli(socle: Socle, demande: Graphique) -> dict[str, Any] | None:
    """Les données d'un graphique refusé, imprimées en tableau.

    Rend `None` quand le socle ne porte aucun des identifiants demandés : un
    tableau vide serait pire que pas de tableau.

    Le titre de la figure est la LÉGENDE du tableau, et sa source celle des
    données. Le titre était passé comme source : depuis que les sources
    s'annoncent (« Source : … », 29/09/2026), il se serait lu « Source :
    Diagnostic de maturité ».
    """
    par_id = {donnee.id: donnee for donnee in socle.donnees}
    donnees = [par_id[i] for i in dict.fromkeys(demande.donnees_ids) if i in par_id]
    if not donnees:
        return None
    lignes: list[list[str]] = []
    for donnee in donnees:
        # À une échelle qui ne perd rien : 0,0003 MdEUR s'écrivait « 0 » (voir
        # `annexe_chiffres.a_son_echelle`, 29/09/2026).
        valeur, unite = a_son_echelle(float(donnee.valeur), str(donnee.unite))
        lignes.append([
            # La première phrase, entière : ni coupe dure au milieu d'un mot
            # (29/09/2026), ni « … » (30/09/2026, business plan ÉCLORE
            # `28a257bf` : « aucune ligne de tableau tronquée »).
            libelle_court(donnee.libelle or donnee.id),
            # Le formateur du document, pas une recopie : le tableau écrivait
            # ses milliers avec une espace sécable et son unité en code de
            # stockage — « MEUR » sous les yeux du lecteur (26/09/2026).
            nombre_francais(valeur),
            unite_lisible(unite),
            str(donnee.annee or "—"),
        ])
    # Un seul arrondi par unité dans la colonne des valeurs (30/09/2026, « arrondi
    # identique pour tous les montants d'un même tableau »).
    for ligne, nombre in zip(
        lignes, meme_arrondi([(ligne[1], ligne[2]) for ligne in lignes]), strict=True,
    ):
        ligne[1] = nombre
    sources = dict.fromkeys(donnee.source.strip() for donnee in donnees if donnee.source.strip())
    return {
        "type": "tableau",
        "entetes": ["Donnée", "Valeur", "Unité", "Année"],
        "lignes": lignes,
        "titre": demande.titre,
        "source": " ; ".join(sources),
    }


def _tableau_des_notes(socle: Socle, demande: Graphique) -> dict[str, Any] | None:
    """Les notes d'une figure d'ACTEURS refusée, imprimées en tableau.

    `_tableau_de_repli` ne connaît que les données chiffrées : un radar, une
    carte de positionnement ou des barres de notes citent des CRITÈRES de la
    grille, et leur refus ne laissait rien — ni figure, ni tableau. Règle du
    client du 30/09/2026 : « si un graphique échoue : régénération depuis la
    spec, puis remplacement par un tableau ». Une ligne par acteur que la
    figure visait, une colonne par critère ; une note absente se dit « — »,
    elle ne s'invente pas.
    """
    from .donnees_graphiques import _acteurs_cites, _criteres_cites  # noqa: PLC0415

    criteres = _criteres_cites(socle, demande.donnees_ids)
    if not criteres:
        return None
    acteurs = _acteurs_cites(socle, demande.donnees_ids)
    voulus = None if acteurs is None else {nom.casefold() for nom in acteurs}
    lignes: list[list[str]] = []
    for acteur in socle.concurrents:
        if voulus is not None and acteur.nom.casefold() not in voulus:
            continue
        notes = [acteur.note_sur(critere.code) for critere in criteres]
        if all(note is None for note in notes):
            continue
        lignes.append([
            acteur.nom, *("—" if note is None else f"{note}/5" for note in notes),
        ])
    if not lignes:
        return None
    return {
        "type": "tableau",
        "entetes": ["Acteur", *(critere.intitule for critere in criteres)],
        "lignes": lignes,
        "titre": demande.titre,
        "source": "",
    }


def _renvoi(lieu: tuple[str, str], reference: str) -> str:
    """La ligne qui remplace une figure déjà posée ailleurs dans le document.

    Revue du 29/09/2026 : le doublon écarté était souvent celui du chapitre de
    fond (le premier exemplaire vit au résumé exécutif), et sa prose — « le
    graphique ci-dessous » — ne renvoyait plus à rien. Elle renvoie désormais à
    la figure, là où le lecteur la trouvera.
    """
    chapitre, titre = lieu
    if chapitre == reference:
        return f"Figure présentée plus haut dans ce chapitre — {titre}"
    return f"Figure présentée au {chapitre[:1].lower()}{chapitre[1:]} — {titre}"


def _signature(resolution: Resolution) -> str:
    """Ce qui fait qu'une figure est LA MÊME : sa forme et ses données résolues.

    Le titre n'en fait pas partie : deux titres sur une même image restent une
    image dessinée deux fois.
    """
    return json.dumps(
        [resolution.type_graphique, resolution.donnees],
        sort_keys=True, ensure_ascii=False, default=str,
    )


def _poser_le_repli(
    repli: dict[str, Any], rapport: RapportAssemblage, blocs: list[dict[str, Any]],
) -> bool:
    """Pose un tableau de repli, sauf s'il est déjà imprimé. Rend vrai s'il l'est."""
    signature = json.dumps([repli["entetes"], repli["lignes"]], ensure_ascii=False)
    if signature in rapport.signatures_des_tableaux:
        return False
    rapport.signatures_des_tableaux.add(signature)
    rapport.tableaux += 1
    blocs.append(repli)
    return True


def _blocs_graphique(
    socle: Socle,
    graphiques: Sequence[Graphique],
    profil: secteurs.ProfilSectoriel,
    rapport: RapportAssemblage,
    reference: str,
    sujets: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Les blocs d'une figure demandée : dessinée, réparée, en tableau, ou renvoyée.

    `sujets` dit de quoi parle la section qui la demande (son intitulé, les
    en-têtes de ses tableaux) : un renvoi vers une figure déjà posée ailleurs
    n'est écrit que s'il est à propos (voir la branche du doublon).
    """
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
        identifiants_traces: list[str] = list(demande.donnees_ids)
        ecartes: tuple[str, ...] = ()
        # La réparation n'est DÉCLARÉE qu'une fois la figure posée : une figure
        # réparée puis écartée comme doublon n'est pas dans le document.
        reparation = ""
        if not resolution.retenu:
            # Avant le tableau : la figure valide la plus proche, avec les
            # données de la demande. Voir `reparation_figures` — 23 figures sur
            # 29 imprimées en tableau sur la stratégie `a678b10a`.
            from .reparation_figures import reparer_la_figure  # noqa: PLC0415

            reparee = reparer_la_figure(socle, type_demande, demande.donnees_ids)
            if reparee is not None:
                reparation = (
                    f"{reference} · {demande.titre} : {type_demande} → "
                    f"{reparee.resolution.type_graphique} sur "
                    f"{len(reparee.identifiants)} donnée(s) ({resolution.motif})"
                )
                resolution = reparee.resolution
                identifiants_traces = list(reparee.identifiants)
                ecartes = reparee.ecartes
        repare = bool(reparation)
        # La SPÉCIFICATION de la figure — son titre, sa légende, ses libellés —
        # contre ce qu'elle porte, APRÈS la réparation : une figure réparée est
        # une figure refaite, elle se contrôle à son tour (règle 3). Voir
        # `specification_figures` : la figure qui échoue est re-dérivée sous une
        # autre forme quand une forme la fait tenir, sinon ses données passent
        # en tableau. Business plan ÉCLORE `28a257bf` (30/09/2026) : « Structure
        # du chiffre d'affaires par univers » dessinait le même chiffre
        # d'affaires à deux dates.
        controle = controler_la_figure(
            socle, resolution,
            identifiants=identifiants_traces,
            titre=demande.titre,
            legende=demande.commentaire,
        )
        resolution = controle.resolution
        # Une frise sous le calendrier du projet dessinerait les TENDANCES DE
        # MARCHÉ : une figure juste qui répond à une autre question. Pas de
        # tableau non plus : sous ce titre, des chiffres qui ne sont pas un
        # calendrier mentiraient de la même façon (29/09/2026).
        titre_trahi = controle.sans_tableau
        if not resolution.retenu:
            rapport.graphiques_abandonnes.append(
                f"{reference} · {demande.titre} : {resolution.motif}"
            )
            from .reparation_figures import pourquoi_irreparable  # noqa: PLC0415

            rapport.diagnostic_des_abandons.append({
                "chapitre": reference,
                "type": type_demande,
                "motif": resolution.motif,
                "donnees": [
                    {
                        "id": identifiant,
                        "unite": str(donnee.unite) if donnee else None,
                    }
                    for identifiant in demande.donnees_ids
                    for donnee in [socle.donnee(identifiant)]
                ],
                # Une figure refusée pour sa SPÉCIFICATION se dessinait — telle
                # que demandée, ou réparée : `pourquoi_irreparable` rendrait des
                # motifs vides. Le rapport dit laquelle, et la règle en cause.
                "reparation": (
                    f"réussie ({reparation}), puis refusée par la spécification"
                    if controle.ecarts and repare
                    else "non tentée : la figure se dessinait, sa spécification ne tient pas"
                    if controle.ecarts
                    else pourquoi_irreparable(socle, type_demande, demande.donnees_ids)
                ),
                "specification": [
                    {"regle": ecart.regle, "motif": ecart.motif} for ecart in controle.ecarts
                ],
            })
            # Le dessin est refusé — unités mélangées, radar sans notes, un
            # seul point. Les DONNÉES, elles, sont bonnes : elles viennent du
            # socle. Les jeter laissait un document sans une seule figure
            # (stratégie Zenitek, 12/09/2026 : 31 demandées, 31 abandonnées,
            # zéro rendue). On les imprime donc en tableau : le lecteur garde
            # l'information, et c'est tout ce qu'un graphique lui apportait.
            repli = None if titre_trahi else (
                _tableau_de_repli(socle, demande) or _tableau_des_notes(socle, demande)
            )
            if repli is not None and controle.titre_en_cause:
                # Le titre a été jugé FAUX — un découpage qui n'existe pas, une
                # année absente, un projet non comparé. En légende du tableau,
                # il imprimerait la même promesse : le tableau paraît sans lui,
                # comme ceux que les chapitres posent eux-mêmes.
                repli["titre"] = ""
            if repli is not None:
                if _poser_le_repli(repli, rapport, blocs):
                    rapport.graphiques_en_tableau.append(
                        f"{reference} · {demande.titre} : {resolution.motif}"
                    )
                else:
                    rapport.graphiques_en_double.append(
                        f"{reference} · {demande.titre} : ses données sont déjà "
                        "imprimées en tableau plus haut"
                    )
            continue

        deja_posee = rapport.signatures_dessinees.get(_signature(resolution))
        if deja_posee is not None:
            # La MÊME figure — même forme, mêmes données — est déjà dans le
            # document. Business plan ÉCLORE, 29/09/2026 : une image dessinée
            # deux fois (§ 3.11 du diagnostic). Les résolveurs qui ignorent
            # les identifiants (frise, carte des risques, radar sans sélecteur)
            # rendent la même image à chaque demande. On ne la redessine pas :
            # une ligne RENVOIE à elle, là où la prose du chapitre l'annonce ;
            # ses données passent en tableau si le lecteur ne les a pas déjà
            # sous les yeux.
            #
            # Le renvoi n'est écrit que s'il est À PROPOS. Business plan ÉCLORE
            # `28a257bf` (30/09/2026, 6.1) : « Figure présentée au chapitre 1 —
            # Repères financiers du lancement » sous « Taille et dynamique du
            # marché ». Le radar et la frise ignorent les identifiants demandés :
            # une figure de marché et une figure financière y rendent la même
            # image, et le renvoi envoyait le lecteur vers une autre question.
            # Le titre de la figure posée est jugé contre ce dont parle la
            # section et contre ce que le chapitre demandait ici — par la
            # fonction de la relecture, qui signale ceux qui restent (règle 5).
            from ..relecture.fuites import renvoi_sur_le_sujet  # noqa: PLC0415

            a_propos = renvoi_sur_le_sujet(deja_posee[1], [*sujets, demande.titre])
            if a_propos:
                blocs.append({"type": "renvoi", "texte": _renvoi(deja_posee, reference)})
            repli = _tableau_de_repli(socle, demande)
            deja_vues = set(demande.donnees_ids) <= rapport.identifiants_rendus
            if repli is not None and not deja_vues and _poser_le_repli(repli, rapport, blocs):
                devenir = "tableau de ses données" if not a_propos else (
                    "renvoi, et tableau de ses données"
                )
            elif a_propos:
                devenir = "renvoi à la figure"
            else:
                devenir = (
                    f"ni renvoi ni figure : la figure posée (« {deja_posee[1]} ») ne porte "
                    "pas sur le sujet de la section"
                )
            rapport.graphiques_en_double.append(
                f"{reference} · {demande.titre} : même figure "
                f"({resolution.type_graphique}, mêmes données) que plus haut "
                f"dans le document — {devenir}"
            )
            continue
        rapport.signatures_dessinees[_signature(resolution)] = (reference, demande.titre)

        if repare:
            rapport.graphiques_repares.append(reparation)
        if resolution.converti and (not repare or controle.rederivee):
            rapport.graphiques_convertis.append(
                f"{reference} · {demande.titre} : {type_demande} → "
                f"{resolution.type_graphique} ({resolution.motif})"
            )
        rapport.graphiques_rendus += 1
        rapport.identifiants_rendus.update(identifiants_traces)
        # Le commentaire est imprimé À LA PLACE DE LA SOURCE. Quand le modèle y
        # a écrit le brief du dessin, on ne l'imprime pas : un graphique sans
        # légende ne perd rien, un graphique sous lequel on lit « Illustre
        # l'écart… » montre au client la cuisine de sa fabrication. Le
        # commentaire écarté est tracé, pas perdu en silence (règle 1).
        from ..meta_discours import est_une_consigne_de_dessin  # noqa: PLC0415

        source = demande.commentaire
        if repare:
            # La légende a été écrite pour la figure DEMANDÉE — elle peut parler
            # de données que la réparation a laissées hors du dessin.
            source = ""
        elif est_une_consigne_de_dessin(source):
            rapport.consignes_de_dessin_retirees.append(
                f"{reference} · {demande.titre} : {source[:160]}"
            )
            source = ""
        blocs.append({
            "type": "graphique",
            "graphique": resolution.type_graphique,
            "titre": demande.titre,
            "source": source,
            "donnees": resolution.donnees,
        })
        if ecartes:
            # Les données laissées hors de la figure réparée restent sous les
            # yeux du lecteur : la réparation retire une forme, jamais un chiffre.
            reste = _tableau_de_repli(
                socle, demande.model_copy(update={"donnees_ids": list(ecartes)}),
            )
            if reste is not None:
                # Il suit la figure, dont l'image porte déjà le titre.
                reste["titre"] = ""
                _poser_le_repli(reste, rapport, blocs)
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
        BlocCanvas,
        BlocEncadre,
        BlocGraphique,
        BlocGrilleKpi,
        BlocParagraphe,
        BlocSousTitre,
        BlocTableau,
    )

    # Ce dont parle chaque sous-section : son intitulé et les en-têtes de ses
    # tableaux, lus d'avance — un tableau posé APRÈS la figure dit aussi le
    # sujet. Sert à ne renvoyer qu'à une figure à propos (`_blocs_graphique`).
    sujets_par_bloc: list[list[str]] = []
    sujets_courants: list[str] = [payload.titre]
    for bloc in payload.blocs:
        if isinstance(bloc, BlocSousTitre):
            sujets_courants = [bloc.intitule]
        elif isinstance(bloc, BlocTableau):
            sujets_courants.extend(bloc.tableau.entetes)
        sujets_par_bloc.append(sujets_courants)

    for rang, bloc in enumerate(payload.blocs):
        if isinstance(bloc, BlocSousTitre):
            blocs.append({
                "type": "sous_titre",
                "texte": f"{bloc.numero} {bloc.intitule}".strip(),
            })
        elif isinstance(bloc, BlocParagraphe):
            amorce = _amorce(bloc.texte, rapport)
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
        elif isinstance(bloc, BlocCanvas):
            # Le canvas passe ses NEUF briques telles quelles : c'est le
            # composant Word qui connaît la disposition d'Osterwalder, pas
            # l'assemblage. Séparer les deux permet de corriger la grille sans
            # toucher au contrat du modèle.
            rapport.tableaux += 1
            blocs.append({
                "type": "canvas",
                "canvas": bloc.canvas.model_dump(),
                "source": bloc.source,
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
                sujets=sujets_par_bloc[rang],
            ))

    return blocs


#: Intitulés dont l'encadré prend le fond soutenu de la référence. Comparaison
#: sur le début de l'intitulé, insensible à la casse : le modèle écrit aussi
#: bien « Verdict » que « Verdict — conditions de viabilité ».
_INTITULES_VERDICT = ("verdict", "conclusion", "décision", "decision")


def _completer_les_figures(
    blocs_par_chapitre: list[dict[str, Any]],
    payloads: Sequence[ChapitrePayload],
    socle: Socle,
    profil: secteurs.ProfilSectoriel,
    rapport: RapportAssemblage,
) -> None:
    """Ramène le document au plancher de figures, en place.

    La cliente a posé un quota : « au moins 17 à 25 graphes par document, c'est
    une obligation absolue ». La charte le demande au modèle — mais un modèle
    qui en déclare douze produisait jusqu'ici un document à douze figures, sans
    que rien ne le relève.

    La complétion ne fabrique AUCUN chiffre : elle ne trace que des données du
    socle, déjà vérifiées, et seulement celles que le chapitre a lui-même
    déclarées dans `donnees_utilisees`. Une figure ajoutée à un chapitre parle
    donc de ce dont ce chapitre parle.

    Elle sert d'abord les chapitres qui n'ont AUCUNE figure : c'est là que le
    lecteur voit un mur de texte, et c'est aussi là qu'une figure de plus
    apporte le plus. Les identifiants déjà tracés ailleurs passent en dernier —
    redessiner deux fois la même donnée tiendrait le compte sans rien apprendre.
    """
    if rapport.graphiques_rendus >= PLANCHER_FIGURES:
        return

    par_numero = {payload.chapitre: payload for payload in payloads}
    # Le chapitre 0 est la « Fiche projet » : elle récapitule le brief du
    # client, elle n'analyse rien. Une figure n'y a pas de sens — et surtout,
    # elle n'y arriverait pas : mesuré, le document sortait avec DIX-SEPT
    # figures au rapport et SEIZE sous les yeux du lecteur, la dix-septième
    # étant celle posée sur cette fiche, que le gabarit rend autrement.
    # Compter une figure que personne ne voit, c'est la règle 9 : le contrôle
    # et le document n'auraient plus jugé sur la même évidence.
    eligibles = [c for c in blocs_par_chapitre if c["numero"] != 0]
    # Un chapitre sans aucune figure d'abord ; les autres ensuite.
    sans_figure = [
        chapitre for chapitre in eligibles
        if not any(b.get("type") == "graphique" for b in chapitre["blocs"])
    ]
    avec_figure = [c for c in eligibles if c not in sans_figure]

    forme = 0
    # Ce que la complétion a déjà consommé, CHAPITRE PAR CHAPITRE. Une première
    # version retenait une signature globale « chapitre + identifiants » : elle
    # rendait la seconde passe inerte, puisqu'un chapitre repassait toujours
    # avec la même liste. Un chapitre qui cite six données doit pouvoir en
    # porter deux figures ; un chapitre qui n'en cite que deux, une seule.
    consommes: dict[int, set[str]] = {}

    # On repasse tant que la passe précédente a servi à quelque chose. Une
    # seule passe donnait une figure par chapitre au plus : suffisant pour une
    # étude de marché (vingt-et-un chapitres), pas pour une étude
    # concurrentielle, qui n'en a que neuf.
    progres = True
    while progres and rapport.graphiques_rendus < PLANCHER_FIGURES:
        progres = False
        for chapitre in [*sans_figure, *avec_figure]:
            if rapport.graphiques_rendus >= PLANCHER_FIGURES:
                return

            payload = par_numero.get(chapitre["numero"])
            if payload is None:
                continue

            deja_vus = consommes.setdefault(payload.chapitre, set())
            titre = f"{payload.titre} — repères chiffrés"

            # On essaie les candidats du chapitre JUSQU'À en trouver qui se
            # tracent, sans rendre la main entre deux essais.
            #
            # Une première version passait au chapitre suivant dès le premier
            # refus, en comptant sur une passe ultérieure. Elle ne revenait
            # jamais : une passe qui ne fait qu'épuiser des candidats n'ajoute
            # aucune figure, `progres` reste faux, et la boucle s'arrête. Mesuré
            # sur la stratégie : ses quatre premiers identifiants inédits mêlent
            # des pourcentages et un montant — rejetés à raison —, et la paire
            # traçable qui venait juste après n'était jamais atteinte. Quatorze
            # figures au lieu de dix-sept, sans qu'aucun abandon ne soit
            # consigné, puisque rien n'avait été demandé.
            resolution = None
            candidats: list[str] = []
            while resolution is None:
                restants = [i for i in payload.donnees_utilisees if i not in deja_vus]
                if len(restants) < 2:
                    break

                # Les identifiants encore jamais tracés dans TOUT le document
                # d'abord : c'est ce qui ajoute de l'information plutôt que de
                # la répétition. À défaut, on retrace ce que le chapitre cite —
                # une donnée peut légitimement paraître deux fois sous deux
                # angles.
                inedits = [i for i in restants if i not in rapport.identifiants_rendus]
                candidats = (
                    inedits if len(inedits) >= 2 else restants
                )[:_DONNEES_PAR_FIGURE]

                for decalage in range(len(_FORMES_DE_COMPLETION)):
                    type_graphique = _FORMES_DE_COMPLETION[
                        (forme + decalage) % len(_FORMES_DE_COMPLETION)
                    ]
                    if type_graphique in profil.graphiques_a_eviter:
                        continue
                    essai = resoudre(socle, type_graphique, candidats)
                    if essai.retenu:
                        # Le titre de la complétion est ÉCRIT PAR NOUS, depuis
                        # celui du chapitre : « Structure du marché — repères
                        # chiffrés » sur une seule trajectoire mentirait comme
                        # un titre du modèle. Ce qui refait le document après
                        # le contrôle se contrôle à son tour (règle 3, revue du
                        # 30/09/2026).
                        essai = controler_la_figure(
                            socle, essai, identifiants=candidats, titre=titre,
                        ).resolution
                    # Une figure déjà dans le document ne compte pas : elle
                    # tiendrait le plancher en redessinant la même image
                    # (29/09/2026, business plan ÉCLORE, § 3.11 du diagnostic).
                    if essai.retenu and _signature(essai) not in rapport.signatures_dessinees:
                        resolution = essai
                        forme += decalage + 1
                        break

                if resolution is None:
                    # Ces identifiants ne donnent rien — unités mêlées, le plus
                    # souvent. On les retire du chapitre et on essaie la suite ;
                    # sans cela, la boucle les représenterait indéfiniment.
                    deja_vus.update(candidats)

            if resolution is None or resolution.donnees is None:
                continue

            # AVANT les encadrés de fin, pas après : un chapitre se ferme sur
            # son verdict, et une figure posée dessous le repousse hors de vue.
            # La première version faisait `append` — le « Verdict » du chapitre
            # se retrouvait au milieu, suivi d'une image.
            blocs_du_chapitre_courant = chapitre["blocs"]
            position = len(blocs_du_chapitre_courant)
            while position and blocs_du_chapitre_courant[position - 1]["type"] == "encadre":
                position -= 1
            blocs_du_chapitre_courant.insert(position, {
                "type": "graphique",
                "graphique": resolution.type_graphique,
                "titre": titre,
                "source": _legende_des_sources(socle, candidats),
                "donnees": resolution.donnees,
            })
            deja_vus.update(candidats)
            progres = True
            rapport.signatures_dessinees[_signature(resolution)] = (
                f"Chapitre {payload.chapitre}", titre,
            )
            rapport.graphiques_rendus += 1
            rapport.identifiants_rendus.update(candidats)
            rapport.graphiques_completes.append(
                f"Chapitre {payload.chapitre} · {titre} "
                f"({resolution.type_graphique}, {len(candidats)} identifiants)"
            )


def _legende_des_sources(socle: Socle, identifiants: Sequence[str]) -> str:
    """« Source : … » des données tracées, ou rien : jamais l'état de notre entrepôt.

    Business plan ÉCLORE `28a257bf` (30/09/2026, 6.4 et 8.5) : chaque figure de
    complétion portait la légende « Données du socle vérifié », écrite en dur
    ici — une étiquette de la chaîne, lue par la cliente comme une source.
    Désormais la légende dit d'où viennent les chiffres, comme le tableau de
    repli (`_tableau_de_repli`), avec le libellé commun des sources
    (`composants.libelle_de_source`, règle 5). Sans source connue, aucune
    légende : une figure sans légende ne perd rien.

    `getattr` : les tests de la complétion isolent sa logique avec un socle
    réduit à rien (`object()`) ; il n'a pas de données, donc pas de source.
    """
    from .composants import libelle_de_source  # noqa: PLC0415 — python-docx, chargé à l'usage

    par_id = {donnee.id: donnee for donnee in getattr(socle, "donnees", ())}
    sources = dict.fromkeys(
        par_id[i].source.strip() for i in identifiants
        if i in par_id and par_id[i].source.strip()
    )
    return libelle_de_source(" ; ".join(sources)) if sources else ""


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

    # Le plancher de figures est une exigence de la cliente, pas une préférence
    # de mise en page. On le tient AVANT de figer la structure : après, il n'y
    # a plus qu'un fichier, et un contrôle qui constate le manque sans pouvoir
    # le réparer ne laisse le choix qu'entre bloquer et se taire.
    _completer_les_figures(blocs_par_chapitre, ordonnes, socle, profil, rapport)

    # L'annexe qui dit d'où vient chaque chiffre — vérifié, déclaré, estimé,
    # hypothèse — et qui montre les calculs. Demande de la cliente du
    # 08/09/2026. Construite depuis le socle verrouillé, sans aucun appel au
    # modèle : elle ne peut donc ni inventer, ni diverger du document.
    #
    # Rangée À PART des chapitres, sans numéro (décision D9, 29/09/2026). Elle
    # prenait le numéro suivant le dernier chapitre : le business plan ÉCLORE
    # affichait 22 chapitres numérotés pour 21 annoncés, et le même +1 valait
    # sur les quatre livrables.
    annexes: list[dict[str, Any]] = []
    annexe = blocs_annexe(socle)
    if annexe:
        annexes.append({"titre": annexe[0]["titre"], "blocs": annexe})
        rapport.tableaux += 1

    from datetime import date as _date  # noqa: PLC0415

    from core.dates import date_francaise  # noqa: PLC0415

    # La liste de mois qui vivait ici n'avait PAS d'accents : « 26 aout 2026 »
    # en page de couverture de chaque document (relecture du 26/09/2026).
    date_fr = date_francaise(_date.today())

    etude = {
        "titre": titre,
        "sous_titre": sous_titre or socle.secteur,
        "mention": mention,
        "date": date_fr,
        "secteur": socle.secteur,
        "profil_sectoriel": profil.code,
        "marque": marque or {},
        # Le document est livré en MARQUE BLANCHE : il porte le nom de
        # l'abonné, jamais celui de la plateforme. « EVKHA · Système d'analyse
        # de marché » était écrit en dur ici et serait donc parti sur chaque
        # document réel, signant le travail d'un tiers au nom d'un autre.
        "mentions_finales": mentions_finales(marque),
        "chapitres": blocs_par_chapitre,
        "annexes": annexes,
    }
    return etude, rapport
