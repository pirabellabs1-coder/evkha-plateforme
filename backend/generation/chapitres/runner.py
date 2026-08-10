"""Production d'un chapitre : contrat structuré, adossé au socle verrouillé.

Un chapitre reçoit (§6.1) : le socle complet, les résumés des chapitres déjà
rédigés, son prompt propre, et le contexte client. Il rend un objet structuré,
pas du texte libre.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ValidationError

from ..modele.conformite import Arbitrage, arbitrer
from ..models import ChapterGeneration, ChapterStatus, GenerationJob
from ..socle.schema import Socle, famille_de_l_unite, unite_lisible
from .configuration import TypeDocument, type_document
from .fichiers_prompts import rendre_prompt
from .schema import ChapitrePayload, raccourcir_le_resume, valider_chapitre
from .typographie import reparer_typographie

_log = logging.getLogger(__name__)

OUTIL_NOM = "rendre_chapitre"
OUTIL_DESCRIPTION = (
    "Enregistre le chapitre rédigé : ses sections, les identifiants de données "
    "du socle qu'il exploite, les graphiques qu'il demande, et son résumé."
)

_SYSTEME = (
    # Sans nommer la plateforme : le livrable est remis en marque blanche, et
    # un modèle amorcé avec ce nom finit par l'écrire dans le texte.
    "Tu rédiges un chapitre d'étude professionnelle : "
    "ton mentor, données chiffrées et sourcées, concret et exploitable.\n"
    "\n"
    "RÈGLE ABSOLUE — tu n'as pas le droit de produire un chiffre de marché. "
    "Le SOCLE joint contient tous les chiffres de référence de l'étude, déjà "
    "établis et verrouillés. Tu les EXPLOITES ; tu ne les recalcules pas, tu "
    "ne les arrondis pas, tu n'en inventes pas d'autres. Chaque identifiant de "
    "donnée que tu mobilises doit être listé dans `donnees_utilisees`.\n"
    "\n"
    "Les graphiques que tu demandes ne portent AUCUNE valeur : seulement des "
    "identifiants du socle. Le rendu résout les valeurs lui-même, ce qui rend "
    "impossible qu'un graphique contredise le texte qui l'entoure.\n"
    "\n"
    # Les fichiers d'instruction montrent des exemples de tableaux HTML. Ils
    # datent du moteur HERITE, qui produisait du HTML et pour lequel ils etaient
    # justes. Le modele fait ce qu'on lui montre : les deux livrables valides du
    # 08/08/2026 portaient des `<table style="...">` IMPRIMES EN TOUTES LETTRES
    # dans le document — dix dans l'etude de marche, quarante-quatre dans le
    # business plan. On le dit donc explicitement, plutot que d'esperer que la
    # forme du contrat suffise a l'en dissuader.
    "AUCUN FORMAT DE DONNÉES DANS TES TEXTES. Les instructions de chapitre te "
    "montrent parfois des tableaux écrits en HTML (`<table style=…>`) : ils "
    "viennent d'un moteur précédent et ne te concernent PAS. Tu ne produis "
    "jamais de balise — ni `<table>`, ni `<div>`, ni `<td>` — et pas davantage "
    "de données brutes : pas de lignes séparées par des points-virgules ou des "
    "barres verticales, pas de tabulations, pas de JSON, pas de bloc de code. "
    "Un tableau se demande avec un bloc `tableau` et ses cellules ; un encadré "
    "avec un bloc `encadre`. Tout ce qui ressemble à un fichier de données est "
    "imprimé tel quel dans le document du client, et fait rejeter le "
    "chapitre.\n"
    "\n"
    # Demande de la cliente : « ne jamais rencontrer d'incident dans la
    # generation ». L'espacement fautif est REPARE en aval (`typographie.py`) —
    # refuser un chapitre pour une double espace couterait une reprise. Ce qui
    # suit vise ce qu'aucune reparation ne peut rattraper : une faute d'accord,
    # un chiffre recopie de travers, un nom propre mal orthographie.
    # Retour de la cliente du 09/08/2026 : « ma cible, ce sont de JEUNES
    # PORTEURS DE PROJET ; l'ideal est qu'un novice comprenne bien l'etude ».
    # Une etude de marche est pleine de termes qui vont de soi pour qui en lit
    # tous les jours — TAM, SAM, SOM, churn, panier moyen, taux de captation —
    # et qui arretent net celui qui decouvre.
    # Retour de la cliente du 09/08/2026 : segmentation, personas, risques,
    # segments porteurs, opportunites accessibles et facteurs cles de succes
    # « restent encore un peu trop generaux ». Le socle porte souvent le chiffre
    # qui aurait tranche — le chapitre n'est simplement pas alle le chercher.
    "CHIFFRE D'ABORD, QUALIFICATIF ENSUITE. Avant d'écrire « le segment premium "
    "est porteur », regarde si le socle porte de quoi le DIRE : une taille, une "
    "part, une croissance, un panier. S'il l'a, la phrase devient « le segment "
    "premium pèse X et croît de Y % par an » — et le qualificatif suit le "
    "chiffre au lieu de le remplacer. C'est ce qui sépare une analyse d'un "
    "commentaire, et cela vaut d'abord pour la segmentation de clientèle, les "
    "profils clients, les risques, les segments les plus porteurs, les "
    "opportunités accessibles et les facteurs clés de succès. Quand le socle ne "
    "porte rien sur un point, dis-le : « le socle ne documente pas ce point » "
    "vaut mieux qu'une généralité qui en prend la place.\n"
    "\n"
    # Retour de la cliente du 09/08/2026 sur la V2 : « l'etude passe son temps
    # a dire donnees a definir, a verifier — je n'aime pas cela, j'aime apporter
    # de vraies reponses. Le client doit sortir de l'etude avec une direction et
    # des conclusions, pas avec une liste de choses a verifier ensuite. »
    #
    # La V2 etait devenue trop prudente : la rigueur s'y lisait comme une
    # derobade. Une etude qui enumere ses incertitudes n'est pas plus honnete
    # qu'une etude qui tranche en les assumant — elle est seulement inutile.
    "TU CONCLUS, TU N'INVENTORIES PAS. Ton lecteur veut savoir si son marché "
    "est porteur, accessible, rentable, saturé, et par où commencer. Chaque "
    "développement suit donc la même chaîne : ce que montre la donnée, ce que "
    "cela signifie POUR CE PROJET, l'ordre de grandeur à retenir, la décision "
    "qui en découle. Un constat qui ne débouche sur rien n'a pas sa place.\n"
    "\n"
    "CES FORMULATIONS SONT INTERDITES, sans exception :\n"
    "« aucune donnée disponible », « le socle ne documente pas », « donnée à "
    "définir », « reste à vérifier », « à confirmer avec un professionnel », "
    "« cette donnée ne peut pas être utilisée », « hypothèse à tester ».\n"
    "\n"
    "Quand un chiffre manque ou reste fragile, tu ne le signales pas : tu "
    "PRENDS POSITION, prudemment. Une fourchette assumée, un ordre de grandeur "
    "raisonné, un scénario central — et tu dis sur quoi tu t'appuies. Écris "
    "« nous retenons une hypothèse prudente comprise entre X et Y », « au vu "
    "des éléments disponibles, le marché apparaît favorable sous conditions », "
    "« le scénario central paraît aujourd'hui le plus cohérent ». Jamais « la "
    "donnée n'est pas disponible ».\n"
    "\n"
    "Une estimation n'est pas un aveu : c'est un travail d'analyste. Le socle "
    "distingue ce qui est observé de ce qui est estimé — sers-t'en pour "
    "calibrer ta prudence, jamais pour t'abriter derrière.\n"
    "\n"
    "AUCUNE TRACE DE FABRICATION dans le document. Les identifiants du socle "
    "(`tam`, `sam`, `som`, `marche_national_taille`…) sont des noms internes : "
    "écris « le marché national », « le marché adressable », jamais leur "
    "identifiant. Pas davantage de « analyse à dire d'expert », de « socle "
    "verrouillé », ni d'aucune mention du dispositif qui produit l'étude.\n"
    "\n"
    "ÉCRIT POUR QUELQU'UN QUI DÉCOUVRE. Ton lecteur porte un projet, il n'est "
    "pas analyste. La PREMIÈRE fois qu'un terme technique apparaît dans "
    "l'étude, explique-le en une demi-phrase, entre parenthèses ou entre "
    "tirets, puis emploie-le librement ensuite : « le SOM (la part de marché "
    "que le projet peut réalistement capter les premières années) ». Cela vaut "
    "pour le vocabulaire d'analyse — TAM, SAM, SOM, churn, taux de captation, "
    "panier moyen, marge brute — comme pour le jargon du secteur étudié. "
    "N'explique pas deux fois le même terme : les résumés des chapitres "
    "précédents te disent ce qui a déjà été posé. Une phrase que le lecteur "
    "doit relire pour la comprendre est une phrase à réécrire.\n"
    "\n"
    "FRANÇAIS IRRÉPROCHABLE. Ce document est remis tel quel à un client final. "
    "Relis chaque phrase avant de la rendre : accords en genre et en nombre, "
    "conjugaison, participes passés, noms propres et raisons sociales écrits "
    "exactement comme dans le brief. Un nombre recopié du socle se recopie au "
    "signe près — ni arrondi, ni reformulé. En cas de doute sur un mot, emploie "
    "celui dont tu es sûr : une phrase simple et juste vaut mieux qu'une "
    "tournure savante et fautive.\n"
    "\n"
    f"Tu réponds exclusivement par un appel de l'outil `{OUTIL_NOM}`."
)


class ChapitreInvalideError(RuntimeError):
    """Le chapitre produit ne respecte pas son contrat.

    Porte la CONSOMMATION de la tentative refusée. Anthropic facture un appel
    dont la réponse est rejetée exactement comme un appel réussi : sans ce
    transport, la dépense disparaissait entre le `raise` et la reprise. Six
    appels perdus sur le seul chapitre 19 du dossier `b561c2d6`, absents du
    grand livre — le plafond de dépense portait donc sur un chiffre inférieur à
    la facture réelle, et il échouait en silence (règle 1).
    """

    def __init__(
        self, motifs: list[str], consommation: Mapping[str, int] | None = None
    ) -> None:
        self.motifs = motifs
        self.consommation: Mapping[str, int] = consommation or {}
        super().__init__(" ; ".join(motifs))


def schema_outil() -> dict[str, Any]:
    return ChapitrePayload.model_json_schema()


def _motif_de_validation(item: Mapping[str, Any]) -> str:
    """Motif de refus qui dit ce qui est ATTENDU, pas seulement ce qui est refusé.

    Pydantic écrit « intitulo : Extra inputs are not permitted ». Ce motif part
    au modèle sous « TENTATIVE PRÉCÉDENTE REFUSÉE » et lui demande de deviner le
    nom qu'il aurait dû écrire.

    Mesuré le 05/08/2026, génération réelle `5ed4f03f` : le modèle a répété la
    même faute de frappe TROIS fois de suite, et l'étude est morte au chapitre
    18 pour 2,10 EUR. Un motif qui ne dit pas quoi corriger ne corrige rien
    (règle 2).

    On y ajoute donc les champs admis à cet emplacement. La liste vient du
    modèle lui-même, jamais d'une copie : elle suivra le contrat sans que
    personne y pense.
    """
    emplacement = ".".join(str(part) for part in item.get("loc", ()))
    message = str(item.get("msg", ""))
    if item.get("type") != "extra_forbidden":
        return f"{emplacement} : {message}"

    modele = _modele_de_l_emplacement(item.get("loc", ()))
    if modele is None:
        return f"{emplacement} : {message}"
    admis = ", ".join(
        sorted(champ.alias or nom for nom, champ in modele.model_fields.items())
    )
    return f"{emplacement} : {message}. Champs admis ici : {admis}."


def _modele_de_l_emplacement(loc: Sequence[Any]) -> type[BaseModel] | None:
    """Le modèle qui refuse la clé, déduit du chemin d'erreur de Pydantic.

    Le chemin d'un bloc discriminé ressemble à
    `('blocs', 4, 'titre_sous_section', 'intitulo')` : l'avant-dernier élément
    nomme le variant. On s'appuie sur le discriminant plutôt que sur une table
    de correspondance, qui divergerait au premier bloc ajouté (règle 5).
    """
    from .schema import BLOC_PAR_TYPE  # noqa: PLC0415

    for part in reversed(list(loc)[:-1]):
        modele = BLOC_PAR_TYPE.get(str(part))
        if modele is not None:
            return modele
    return None


#: Nature affichée quand l'unité n'est reconnue par aucune famille.
#:
#: Elle ne se tait PAS (règle 1) : « inconnue » se voit dans le prompt, alors
#: qu'une chaîne vide se lirait comme « pas de contrainte » et inviterait le
#: modèle à mélanger. Une nature qu'on ne sait pas nommer est un motif de
#: prudence, jamais une permission.
NATURE_INCONNUE = "inconnue"


def _nature(unite: str) -> str:
    """Famille de grandeur d'une unité, telle que le modèle doit la lire.

    Dérivée de l'unité et non lue au référentiel, pour la raison déjà établie
    par `rendu_word.donnees_graphiques._famille` : le référentiel s'indexe par
    type de livrable, information que le socle rechargé depuis la base ne porte
    plus. L'unité, elle, est toujours là.

    C'est la MÊME fonction que celle qui décide, au rendu, si une figure est
    abandonnée — `famille_de_l_unite`. Le modèle voit donc exactement le critère
    auquel il sera jugé, et non une paraphrase. Deux formulations du même test
    auraient fini par diverger (règle 5), et le modèle aurait été refusé sur un
    critère qu'on ne lui avait pas montré.
    """
    famille = famille_de_l_unite(unite)
    return str(famille) if famille is not None else NATURE_INCONNUE


def _bloc_socle(socle: Socle) -> str:
    """Socle sérialisé, lisible et exhaustif.

    Format tabulaire plutôt que JSON brut : à contenu égal il consomme moins
    de jetons et se lit mieux, or ce bloc est réinjecté à CHAQUE chapitre.

    `libelle` MANQUAIT, et c'était une perte sèche. Le prompt du socle y loge
    expressément deux choses (`socle/prompt.py`, règles 5 et 7) : la MÉTHODE
    d'une valeur `estimee` — « explique la méthode dans `libelle` » — et la
    FOURCHETTE quand la donnée en est une, dont seule la médiane part dans
    `valeur`. Le champ est obligatoire au contrat, il est produit, il est
    stocké, et il était jeté avant le premier chapitre.

    Le manuel demande l'inverse : « construire une estimation prudente et
    expliquer clairement la méthode » (p. 4), « donner une fourchette lorsque
    la précision exacte serait artificielle » (p. 8), et le CHECK 1 interroge
    « les estimations sont-elles expliquées sans présenter une déduction comme
    une donnée officielle ? ». La matière pour y répondre existait ; elle
    n'atteignait personne. Un chiffre estimé arrivait donc au chapitre nu,
    impossible à distinguer d'un chiffre observé.
    """
    # L'unite est donnee TELLE QU'ELLE DOIT APPARAITRE dans le document —
    # `Md€`, pas `MdEUR`. Le modele recopie ce qu'il lit : lui montrer la
    # notation de stockage, c'est la retrouver dans la prose du client, et
    # aucun rendu ne la rattrape a ce stade (retour cliente du 09/08/2026).
    lignes = [
        f"- `{d.id}` = {d.valeur} {unite_lisible(d.unite)} [{_nature(d.unite)}]"
        f" ({d.annee}, {d.perimetre}, {d.fiabilite})"
        + (f" — {d.libelle}" if d.libelle else "")
        + (f" — source : {d.source}" if d.source else "")
        + (f" — dérivé de {', '.join(d.derivee_de)}" if d.derivee_de else "")
        for d in socle.donnees
    ]
    entete = (
        f"SOCLE VERROUILLÉ — {socle.secteur}, {socle.zone.pays}"
        + (f" / {socle.zone.region}" if socle.zone.region else "")
        + (f" / {socle.zone.ville}" if socle.zone.ville else "")
        + f" (arrêté au {socle.date_socle.isoformat()})"
    )
    return entete + "\n" + "\n".join(lignes) + _bloc_grille(socle)


def _bloc_grille(socle: Socle) -> str:
    """La grille de notation et les acteurs notés, pour les figures.

    Sans ce bloc, la grille existerait dans le socle sans que le chapitre
    puisse la citer : les radars et les cartes de positionnement resteraient
    exactement aussi impossibles qu'avant. C'est le défaut que ce projet a
    rencontré quatre fois — écrit, stocké, jamais transmis (règle 8).
    """
    if not socle.grille_notation:
        return ""

    lignes = [
        f"- `{critere.code}` — {critere.intitule} "
        f"(1 = {critere.note_1} … 5 = {critere.note_5})"
        for critere in socle.grille_notation
    ]
    notes = [
        f"- {acteur.nom} : "
        + ", ".join(f"{code} {acteur.notes[code]}/5" for code in sorted(acteur.notes))
        for acteur in socle.concurrents
        if acteur.notes
    ]
    return (
        "\n\nGRILLE DE NOTATION — ces codes s'emploient comme identifiants de "
        "figure, à la place des identifiants chiffrés :\n"
        + "\n".join(lignes)
        + "\n- carte de positionnement : cite DEUX codes, abscisse puis "
        "ordonnée.\n"
        "- radar : cite TROIS codes ou plus ; chaque acteur noté devient une "
        "série.\n"
        "Ces notes font foi : tu les reprends telles quelles et tu n'en "
        "réinventes aucune. Le premier chapitre qui s'en sert reproduit la "
        "grille dans un tableau — intitulé, ce que vaut 1, ce que vaut 5 — "
        "pour que le lecteur puisse refaire la notation lui-même.\n"
        "Les notes déjà attribuées :\n" + "\n".join(notes)
    )


def _bloc_resumes(job: GenerationJob, numero: int) -> str:
    precedents = (
        job.chapters.filter(chapter_number__lt=numero)
        .exclude(operational_summary="")
        .order_by("chapter_number")
    )
    # Le chapitre 0 — la fiche projet — N'EST PAS PUBLIÉ : le sommaire ne le
    # porte pas, le document ne le contient pas. Le presenter ici comme
    # « Chapitre 0 » amenait le modele a y RENVOYER dans sa prose, et le lecteur
    # cherchait dans le sommaire un chapitre qui n'y figure pas. Signale par la
    # cliente le 09/08/2026 sur l'etude concurrentielle.
    #
    # On garde son contenu — c'est le cadrage du projet, il sert a tous les
    # chapitres — mais on lui retire son numero, qui est un repere interne.
    lignes = [
        (
            f"Cadrage du projet (non publié, ne le cite jamais) :\n"
            f"{c.operational_summary}"
            if c.chapter_number == 0
            else f"Chapitre {c.chapter_number} — {c.chapter_title} :\n"
                 f"{c.operational_summary}"
        )
        for c in precedents
    ]
    if not lignes:
        return "CHAPITRES PRÉCÉDENTS : aucun, tu ouvres l'étude."
    return "CHAPITRES PRÉCÉDENTS (résumés) :\n\n" + "\n\n".join(lignes)


def _bloc_sources(job: GenerationJob, numero: int) -> str:
    """Sources web réelles utiles à CE chapitre.

    Ce bloc manquait, et c'est la cause la plus lourde des redites relevées par
    la cliente. Mesuré : dans le moteur structuré — celui qui tourne —, le seul
    matériau qu'un chapitre recevait était `_bloc_socle`, soit **vingt-neuf
    emplacements de données pour l'étude entière**, plus les résumés des
    chapitres précédents. Le brief de recherche, lui, était consommé UNE fois
    pour remplir ces vingt-neuf cases, puis jeté : aucun chapitre ne le voyait.

    Deux conséquences directes.

    1. Vingt-et-un chapitres de trois à cinq pages écrits à partir de
       vingt-neuf chiffres n'ont rien de neuf à dire passé le troisième. Ce
       n'est pas le modèle qui se répète, c'est la matière qui manque.
    2. Le manuel exige « 35 à 60 sources distinctes » au chapitre 21. Avec au
       plus vingt-neuf données portant chacune une source — souvent la même —,
       la cible était hors d'atteinte par construction.

    Le socle reste l'AUTORITÉ sur les chiffres : il est verrouillé, contrôlé,
    et c'est lui qui garantit qu'un montant ne change pas d'un chapitre à
    l'autre. Ces sources servent à tout ce que le socle ne porte pas — une
    obligation réglementaire, un comportement d'achat, un signal de tendance —
    et à la bibliographie du chapitre 21. La règle de préséance est écrite dans
    le bloc, sans quoi le modèle citerait un chiffre du web contre un chiffre
    verrouillé.
    """
    from ..research import brief_pour_chapitre  # noqa: PLC0415

    utile = brief_pour_chapitre(
        job.research_brief or "", numero, job.deliverable_type
    )
    if not utile.strip():
        return (
            "SOURCES WEB : aucune source collectée pour ce chapitre. N'invente "
            "ni URL ni date de publication ; n'avance aucun fait daté que le "
            "socle ne porte pas."
        )
    return (
        "SOURCES WEB RÉELLES POUR CE CHAPITRE — matière de première main, "
        "collectée pour lui.\n"
        "Préséance : sur tout CHIFFRE que le socle porte déjà, le socle gagne, "
        "toujours. Ces sources servent à ce que le socle ne porte pas — "
        "obligations, comportements, prix observés, signaux de tendance — et à "
        "la bibliographie du chapitre 21. Ne cite jamais une URL absente de "
        "cette liste.\n\n" + utile
    )


#: Ce que chaque livrable NON DÉCRIT par le modèle doit porter en propre.
#:
#: Le repli était le MÊME texte pour le business plan, la stratégie et l'étude
#: concurrentielle. Or ces trois documents n'ont ni le même objet, ni le même
#: lecteur, ni les mêmes tableaux : un plan d'affaires se juge sur des chiffres
#: qui s'enchaînent d'un chapitre à l'autre, une étude concurrentielle sur des
#: comparaisons à critères constants, une stratégie sur des décisions datées et
#: assignées. Leur servir une consigne moyenne produisait trois documents de la
#: même forme, et c'est le reproche que la cliente adresse depuis le début.
#:
#: Ce n'est PAS un modèle de référence et cela n'en tient pas lieu : aucune de
#: ces lignes n'est mesurée sur un document validé, aucun contrôle de conformité
#: ne s'y adosse. C'est une consigne, pas un étalon — et la distinction compte,
#: parce qu'un jour quelqu'un lira ce fichier en croyant y trouver le second.
_FORME_PAR_LIVRABLE: dict[str, str] = {
    "business_plan": (
        "- Les chiffres s'ENCHAÎNENT d'un chapitre à l'autre : un montant posé "
        "au prévisionnel doit se retrouver au plan de financement et au seuil "
        "de rentabilité, à l'identique. Un tableau qui recommence à zéro rend "
        "le document incrédible.\n"
        "- Chaque tableau financier porte ses ANNÉES en colonnes (N, N+1, N+2) "
        "et ses postes en lignes. Jamais l'inverse.\n"
        "- Toute hypothèse chiffrée dit sur quoi elle repose — un encadré "
        "« Hypothèses » vaut mieux qu'une note de bas de tableau."
    ),
    "competitor_study": (
        "- Les concurrents se comparent sur des CRITÈRES CONSTANTS : les mêmes "
        "colonnes d'un tableau à l'autre, d'un chapitre à l'autre. Un critère "
        "qui n'apparaît que pour un concurrent transforme la comparaison en "
        "plaidoyer.\n"
        "- Une case sans donnée s'écrit « non communiqué », jamais un tiret "
        "seul ni une estimation présentée comme un fait.\n"
        "- Chaque chapitre se ferme sur ce que la comparaison IMPLIQUE pour le "
        "client, pas sur le classement lui-même.\n"
        # Ajouts demandes par la cliente le 09/08/2026, apres analyse de la
        # premiere etude concurrentielle reelle. Ce ne sont pas des correctifs :
        # ce sont les analyses qui font la valeur du dossier et qui manquaient.
        "- Un chiffre d'affaires indisponible n'arrête pas la comparaison : "
        "prends des INDICATEURS OBSERVABLES — nombre de points de vente ou "
        "d'agences, effectif, avis clients, abonnés, trafic estimé, largeur de "
        "gamme, fréquence de publication, téléchargements d'application, levées "
        "de fonds, ancienneté. Choisis ceux qui existent DANS CE SECTEUR.\n"
        "- Une COMPARAISON TARIFAIRE est obligatoire, avec les variables du "
        "métier étudié : prix d'entrée, abonnement, commission, frais annexes, "
        "livraison, installation, garantie, stockage, maintenance. Compare "
        "quand c'est possible le coût réel pour deux ou trois profils de "
        "clients types — le prix affiché ne dit pas ce que le client paie.\n"
        "- Analyse COMMENT chaque concurrent trouve ses clients : référencement, "
        "publicité, réseaux sociaux, points de vente, prescripteurs, "
        "affiliation, partenariats, événements, places de marché, contenu, "
        "bouche-à-oreille. Là encore, les canaux du secteur, pas une liste "
        "générique.\n"
        "- Les AVIS CLIENTS font partie du comparatif : note, nombre d'avis, "
        "plateformes, motifs récurrents de satisfaction et d'insatisfaction. "
        "Un irritant qui revient chez tous les acteurs est une opportunité.\n"
        "- La conclusion répond à ces questions, nommément : qui sont les "
        "concurrents les plus dangereux ? sur quels critères le projet est-il "
        "réellement différent ? où le marché est-il déjà saturé ? sur quoi "
        "faut-il être meilleur ? quelles pratiques reprendre, quelles erreurs "
        "éviter ? quel concurrent peut neutraliser rapidement l'avantage ? "
        "quelles priorités avant le lancement ?"
    ),
    "business_strategy": (
        "- Une recommandation sans ÉCHÉANCE ni RESPONSABLE n'est pas une "
        "recommandation. Chaque tableau d'actions porte au minimum : action, "
        "échéance, ressource engagée, indicateur de réussite.\n"
        "- Les priorités s'ordonnent et se justifient : dire ce qu'on ne fait "
        "PAS d'abord vaut autant que dire ce qu'on fait.\n"
        "- Un encadré par chapitre porte la décision, au présent de l'indicatif "
        "et à la première personne du pluriel.\n"
        "- Un SCÉNARIO est RECOMMANDÉ, nommément, et les autres disent ce qu'il "
        "faudrait pour qu'ils le deviennent. Trois scénarios présentés à "
        "égalité ne sont pas une stratégie : c'est un renvoi de la décision au "
        "lecteur."
    ),
}


#: Règles de FOND, valables pour les quatre livrables ET pour tout chapitre —
#: décrit par le modèle de forme ou non.
#:
#: ## Pourquoi elles vivent ici et plus dans `_forme_commune`
#:
#: Elles y étaient, et **l'étude de marché ne les recevait pas**. `_bloc_forme`
#: n'est employé que pour les livrables que le modèle de forme NE décrit PAS ;
#: l'étude de marché, elle, reçoit le plan du chapitre à la place. Les deux
#: règles atteignaient donc le business plan, la stratégie et l'étude
#: concurrentielle — et pas le seul livrable sur lequel la cliente les avait
#: demandées.
#:
#: Trouvé en construisant le prompt RÉELLEMENT envoyé et en cherchant dedans,
#: le 09/08/2026. Les tests passaient : ils appelaient `_bloc_forme`
#: directement. C'est le motif qui a coûté dix-huit figures deux jours plus
#: tôt — écrit, testé, jamais transmis (règle 8).
REGLES_DE_FOND = (
    # « Chaque chapitre doit idealement repondre a quatre questions » : la
    # structure d'une etude qui DECIDE, par opposition a une etude qui decrit.
    "- Chaque chapitre répond, dans l'ordre, à QUATRE questions : que "
    "montre le marché ? qu'est-ce que cela signifie pour ce projet ? quel "
    "ordre de grandeur retenir ? quelle décision en découle ? Un chapitre "
    "qui s'arrête à la première n'a fait que le quart du travail.\n"
    # « Une note ne doit jamais etre attribuee parce que l'acteur SEMBLE
    # premium. » Une note sans echelle n'est pas une mesure, c'est une
    # impression — et une impression chiffree trompe plus qu'une impression
    # assumee.
    "- Toute NOTE — radar, score, matrice, classement — repose sur une seule "
    "échelle. Si une GRILLE DE NOTATION t'est donnée avec le socle, c'est "
    "elle qui fait foi, critère par critère, et tu n'en inventes pas d'autre. "
    "À défaut : 1 absent · 2 faible · 3 moyen · "
    "4 développé · 5 référence du secteur. Et chaque note s'appuie sur un "
    "fait OBSERVABLE, cité : un nombre, une présence, une absence. Jamais "
    "sur une impression — « semble premium » n'est pas un critère. Quand "
    "une échelle sert dans un chapitre, le tableau qui la porte dit ce que "
    "chaque niveau signifie.\n"
    # « La SWOT doit deboucher sur de vraies priorites strategiques, pas sur
    # une liste de limites. » Une SWOT qui s'arrete au tableau laisse au
    # lecteur le travail qu'il a paye : croiser les quatre cases.
    "- Une SWOT ne s'arrête JAMAIS au tableau. Elle se ferme sur deux ou "
    "trois priorités, tirées du CROISEMENT des cases : quelle force sert "
    "quelle opportunité, quelle faiblesse expose à quelle menace, et donc "
    "par où commencer. Une SWOT qui énumère sans conclure laisse au lecteur "
    "le travail qu'il a payé."
)


def _bloc_forme(code_livrable: str = "") -> str:
    """Consigne de forme, commune à tous, PLUS ce qui est propre au livrable.

    Elle vit ici et pas dans les 72 fichiers de prompt : la répéter soixante-douze
    fois garantirait qu'elle finisse par diverger d'un fichier à l'autre
    (règle 5). Elle traduit une mesure, pas un goût — le document de référence
    validé par la cliente porte 52 % de ses mots dans des tableaux et une
    médiane de douze mots par paragraphe. Un chapitre qui ne rend que de la
    prose produit le mur de texte qu'elle a explicitement refusé.

    La partie commune reste commune ; ce qui distingue un plan d'affaires d'une
    étude concurrentielle s'ajoute par-dessus. Un livrable inconnu de la table
    reçoit la partie commune seule — pas de silence, pas d'invention.
    """
    propre = _FORME_PAR_LIVRABLE.get(code_livrable, "")
    return _forme_commune() + (f"\n{propre}" if propre else "")


def _forme_commune() -> str:
    return (
        "FORME ATTENDUE — contrainte mesurée sur le livrable de référence, "
        "pas une préférence de style :\n"
        "- L'information vit dans les TABLEAUX. Chaque section porte un "
        "`tableau` de 3 à 5 colonnes ; ce sont ses lignes qui portent les "
        "chiffres, les critères et les comparaisons.\n"
        "- Le champ `contenu` d'une section est une AMORCE, pas un "
        "développement : deux à trois phrases qui annoncent ce que le tableau "
        "montre. Au-delà, il sera tronqué au rendu.\n"
        "- Un encadré au moins par chapitre, avec un verdict actionnable "
        "(opportunité, limite, décision) — jamais un résumé de ce qui précède."
    ) + "\n" + REGLES_DE_FOND


def _blocs_du_modele(code_livrable: str, numero: int) -> list[str]:
    """Plan du chapitre et exemple de référence, quand le modèle les porte.

    Remplace la consigne générique par la forme PROPRE à ce chapitre. Le modèle
    de référence décrit vingt-et-une structures différentes ; une consigne
    unique ne pouvait en produire qu'une, répétée partout — c'est ce que
    mesurait le validateur de conformité, à zéro chapitre conforme sur
    vingt-et-un.

    Le repli sur `_bloc_forme()` n'est pas silencieux : il vaut pour les
    livrables que le modèle ne décrit pas (business plan, stratégie) et pour la
    fiche projet, qui n'a pas d'équivalent dans le document validé. Dans ces
    cas, la consigne moyenne reste ce qu'on a de mieux.
    """
    from ..modele.chargement import ModeleIntrouvableError, modele_couvre  # noqa: PLC0415
    from ..modele.consigne import exemple_de_reference, plan_du_chapitre  # noqa: PLC0415

    try:
        if not modele_couvre(code_livrable):
            return [_bloc_forme(code_livrable)]
        plan = plan_du_chapitre(numero)
        exemple = exemple_de_reference(numero)
    except ModeleIntrouvableError as erreur:
        # Le modèle est censé être dans l'image — `test_image_dependances.py`
        # le vérifie. S'il manque quand même, on le DIT dans la consigne au
        # lieu de rendre une forme moyenne en faisant croire à la forme
        # imposée (règle 1).
        return [
            _bloc_forme(code_livrable),
            f"NOTE INTERNE — modèle de référence indisponible : {erreur}",
        ]

    if not plan:
        return [_bloc_forme(code_livrable)]
    # Le plan remplace la FORME moyenne — il décrit celle de ce chapitre-là.
    # Il ne remplace pas les règles de FOND : quatre questions par chapitre et
    # échelle de notation valent partout, et l'étude de marché ne les recevait
    # PAS, faute d'avoir jamais vu `_bloc_forme`. C'est le seul livrable sur
    # lequel la cliente les avait demandées.
    return [REGLES_DE_FOND, plan, exemple] if exemple else [REGLES_DE_FOND, plan]


def formes_deja_employees(job: GenerationJob, avant: int) -> list[str]:
    """Types de figures déjà demandés par les chapitres précédents de ce job.

    Le modèle écrit un chapitre à la fois et ne voit pas les autres : il n'a
    aucun moyen de savoir quelle forme il a déjà employée. Lui demander de « ne
    pas se répéter » était donc lui demander l'impossible.

    Mesuré sur le livrable réel `4b827759`, dix figures rendues : deux
    entonnoirs quasi identiques, l'un « du marché mondial au marché
    atteignable », l'autre « du marché national au marché atteignable ». La
    cliente l'a vu immédiatement — « on voit un certain graphe même plusieurs
    fois ».

    On le lui dit donc. La liste vient des payloads déjà écrits, seule source
    qui sache ce que l'étude porte réellement (règle 5).
    """
    from .schema import ChapitrePayload  # noqa: PLC0415

    formes: list[str] = []
    requete = (
        job.chapters.filter(chapter_number__lt=avant, status=ChapterStatus.DONE)
        .exclude(payload={})
        .order_by("chapter_number")
    )
    for chapitre in requete:
        try:
            payload = ChapitrePayload.model_validate(chapitre.payload)
        except ValidationError:
            continue  # un chapitre illisible ne doit pas priver le suivant
        formes.extend(str(graphique.type) for graphique in payload.graphiques)
    return formes


#: Les six axes du verdict de clôture, avec leur vocabulaire FERMÉ.
#:
#: Demande de la cliente du 09/08/2026 : « en fin d'étude, ajouter un verdict
#: synthétique, avec une justification courte pour chaque point ».
#:
#: Le vocabulaire est imposé pour une raison simple : un verdict libre redevient
#: une nuance. « Plutôt favorable dans certaines conditions » ne se compare pas
#: d'une étude à l'autre et ne décide rien. Trois mots par axe, et le lecteur
#: sait où il est.
AXES_DU_VERDICT: tuple[tuple[str, tuple[str, str, str]], ...] = (
    ("Marché porteur", ("Oui", "Modérément", "Non")),
    ("Potentiel pour un nouvel entrant", ("Fort", "Moyen", "Faible")),
    ("Niveau de concurrence", ("Faible", "Moyen", "Élevé")),
    ("Marché saturé", ("Oui", "Partiellement", "Non")),
    ("Potentiel de rentabilité", ("Favorable", "À sécuriser", "Fragile")),
    ("Viabilité globale", (
        "Favorable", "Favorable sous conditions", "Défavorable",
    )),
)


def _bloc_verdict(job: GenerationJob, numero: int) -> str:
    """Consigne du verdict de clôture — DERNIER chapitre seulement.

    ## Pourquoi il est demandé ici et pas au rendu

    Le tableau du verdict n'est pas décoratif : chaque ligne est un JUGEMENT sur
    le marché, et seul le modèle qui vient d'écrire vingt-trois chapitres peut le
    porter. Le rendu, lui, ne saurait qu'imprimer une case vide.

    ## Pourquoi il n'apparaît qu'une fois

    La consigne n'est injectée que pour le dernier chapitre. Confiée à tous, elle
    produirait vingt-trois verdicts contradictoires — le même défaut que la
    recommandation de clôture, qu'on a justement sortie du modèle de langage
    pour cette raison.
    """
    dernier = job.chapters.order_by("-chapter_number").values_list(
        "chapter_number", flat=True
    ).first()
    if dernier is None or numero != dernier:
        return ""

    lignes = "\n".join(
        f"- {axe} : {' / '.join(valeurs)}" for axe, valeurs in AXES_DU_VERDICT
    )
    return (
        "VERDICT DE CLÔTURE — ce chapitre ferme l'étude, il doit donc TRANCHER.\n"
        "Produis un bloc `tableau` à trois colonnes — Critère, Verdict, "
        "Pourquoi — portant EXACTEMENT ces six lignes, dans cet ordre, et "
        "n'employant que les mots proposés en face de chacune :\n"
        f"{lignes}\n"
        "La colonne « Pourquoi » tient en une phrase et s'appuie sur ce que "
        "l'étude a établi — un chiffre, un segment, un constat de concurrence. "
        "Pas de nuance ajoutée au verdict lui-même : le mot choisi EST la "
        "réponse. Le lecteur doit pouvoir lire ces six lignes seules et savoir "
        "s'il se lance."
    )


def _bloc_visuels(socle: Socle, job: GenerationJob, numero: int) -> str:
    """Catalogue des visuels, consigne sectorielle, et MÉMOIRE des formes.

    Le choix d'un type de graphique dépend du SECTEUR, jamais du numéro de
    chapitre : une saisonnalité mensuelle n'a pas de sens dans une étude sur le
    conseil, une pyramide des âges n'en a pas dans la logistique. Le profil est
    déduit du secteur porté par le socle.
    """
    from ..rendu_word import secteurs  # noqa: PLC0415
    from ..rendu_word.graphiques import TYPES_DISPONIBLES, resume_catalogue  # noqa: PLC0415

    profil = secteurs.profil_du_secteur(socle.secteur)
    deja = formes_deja_employees(job, numero)
    memoire = ""
    if deja:
        compte = Counter(deja)
        vues = ", ".join(
            f"`{forme}`" + (f" ×{n}" if n > 1 else "") for forme, n in compte.most_common()
        )
        libres = [t for t in TYPES_DISPONIBLES if t not in compte]
        memoire = (
            f"\n\nFORMES DÉJÀ EMPLOYÉES dans cette étude : {vues}.\n"
            "Choisis une forme ENCORE INEMPLOYÉE dès que le propos s'y prête — "
            "une étude qui répète deux fois le même graphique se lit comme un "
            "gabarit, pas comme une analyse. "
            + (f"Encore libres : {', '.join(f'`{t}`' for t in libres)}."
               if libres else
               "Toutes ont servi : reprends alors celle qui sert le mieux CE propos.")
        )
    # L'objectif chiffre vient de `prompts.OBJECTIF_FIGURES_TEXTE`, et c'est le
    # SEUL endroit du chemin structure qui le transmet. Il vivait exclusivement
    # dans `build_system_prompt` — que seul le moteur herite envoie : le moteur
    # qui rend les figures n'a donc JAMAIS recu l'objectif « quinze figures »
    # d'hier. Les onze figures du dossier 9be9a422 venaient du seul profil
    # sectoriel. Motif Gamma, encore (regle 8) : ecrit, teste, jamais transmis.
    #
    # `REGLES_IDENTIFIANTS_FIGURES` est arrive ici pour la MEME raison, et il a
    # fallu un second dossier reel pour s'en apercevoir. Les regles de selection
    # — deux identifiants minimum, natures homogenes, notes pour le radar,
    # periodes completes pour les courbes — vivaient elles aussi dans le seul
    # `build_system_prompt`. Dix-huit figures abandonnees sur `b561c2d6`, presque
    # toutes pour « unites heterogenes », parce que la consigne etait MUETTE et
    # non parce qu'elle etait ignoree.
    from ..prompts import OBJECTIF_FIGURES_TEXTE, REGLES_IDENTIFIANTS_FIGURES  # noqa: PLC0415

    return (
        "VISUELS — un graphique ne porte AUCUNE valeur : il porte des "
        "identifiants du socle, résolus au rendu. Un identifiant absent du "
        "socle fait abandonner la figure entière.\n\n"
        + OBJECTIF_FIGURES_TEXTE + "\n\n"
        + REGLES_IDENTIFIANTS_FIGURES + "\n\n"
        "Types disponibles :\n" + resume_catalogue() + "\n\n"
        + secteurs.consigne_visuelle(profil)
        + memoire
    )


def _valeurs_interpolation(
    chapter: ChapterGeneration, variables: Mapping[str, object]
) -> dict[str, object]:
    from ..blueprints import get_blueprint  # noqa: PLC0415

    blueprint = get_blueprint(chapter.job.deliverable_type, chapter.chapter_number)
    return {
        "secteur": variables.get("SECTEUR", ""),
        "pays": variables.get("PAYS", ""),
        "zone": variables.get("ZONE", ""),
        "projet": variables.get("PROJET", ""),
        "titre_chapitre": chapter.chapter_title,
        "numero_chapitre": chapter.chapter_number,
        "cible_mots": (blueprint.max_words if blueprint else 0) or "non bornée",
    }


def construire_prompt_chapitre(
    chapter: ChapterGeneration,
    *,
    socle: Socle,
    variables: Mapping[str, object],
    document: TypeDocument,
    motifs_precedents: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Prompt utilisateur du chapitre. Retourne (prompt, variables manquantes)."""
    instruction, manquantes = rendre_prompt(
        document.code,
        chapter.chapter_number,
        _valeurs_interpolation(chapter, variables),
    )

    # La consigne propre au livrable — dont la regle STRICTE anti-fourchettes
    # du BP, de l'EC et de la STR — vivait dans `build_system_prompt`, que seul
    # le moteur herite envoie. Sans elle, le gate `_check_fourchettes` (strict
    # hors EM) bloquerait des chapitres auxquels la regle n'a jamais ete dite :
    # le meme trou de transmission que l'objectif de figures, corrige le meme
    # jour (motif Gamma, regle 8). Vide pour l'EM — sa charte la porte deja.
    from ..prompts import _consigne_specifique_livrable  # noqa: PLC0415

    consigne_livrable = _consigne_specifique_livrable(
        str(chapter.job.deliverable_type)
    )

    blocs = [
        _bloc_socle(socle),
        *( [consigne_livrable] if consigne_livrable else [] ),
        _bloc_sources(chapter.job, chapter.chapter_number),
        f"BRIEF_CLIENT :\n{json.dumps(dict(variables), ensure_ascii=False, sort_keys=True)}",
        _bloc_resumes(chapter.job, chapter.chapter_number),
        f"CHAPITRE À RÉDIGER : {chapter.chapter_number} — {chapter.chapter_title}",
        f"INSTRUCTION DU CHAPITRE :\n{instruction}",
        *_blocs_du_modele(str(chapter.job.deliverable_type), chapter.chapter_number),
        # Vide pour tous les chapitres sauf le dernier : un verdict repete
        # vingt-trois fois ne serait plus un verdict.
        *(
            [verdict]
            if (verdict := _bloc_verdict(chapter.job, chapter.chapter_number))
            else []
        ),
        _bloc_visuels(socle, chapter.job, chapter.chapter_number),
        (
            f"RÉSUMÉ : termine par un résumé de {document.resume_mots_min} à "
            f"{document.resume_mots_max} mots. Il sera relu par tous les "
            "chapitres suivants : fais-y figurer les chiffres et les "
            "conclusions qu'ils devront reprendre à l'identique."
        ),
    ]

    if motifs_precedents:
        motifs = "\n".join(f"- {motif}" for motif in motifs_precedents)
        blocs.append(
            "TENTATIVE PRÉCÉDENTE REFUSÉE. Corrige EXACTEMENT ces points :\n" + motifs
        )

    return "\n\n".join(blocs), manquantes


def payload_vers_markdown(payload: ChapitrePayload) -> str:
    """Rendu markdown du chapitre, consommable par la chaîne de rendu actuelle.

    Sert de pont : le lot 3 remplacera ce rendu par un gabarit Word, mais tant
    qu'il n'est pas là, le document doit rester assemblable.
    """
    from .schema import (
        BlocEncadre,
        BlocGraphique,
        BlocGrilleKpi,
        BlocParagraphe,
        BlocSousTitre,
        BlocTableau,  # noqa: PLC0415 — importés seulement pour le pont
    )

    morceaux: list[str] = []
    # Dans l'ORDRE des blocs : le markdown est un pont, il ne doit pas
    # réorganiser ce que le chapitre a composé.
    for bloc in payload.blocs:
        if isinstance(bloc, BlocSousTitre):
            morceaux.append(f"## {bloc.numero} {bloc.intitule}")
        elif isinstance(bloc, BlocParagraphe):
            morceaux.append(bloc.texte.strip())
        elif isinstance(bloc, BlocTableau):
            # Sans cette reprise, le pont vers l'ancienne chaîne perdrait
            # silencieusement la moitié de l'information du chapitre.
            entetes = " | ".join(bloc.tableau.entetes)
            separateur = " | ".join(["---"] * len(bloc.tableau.entetes))
            lignes = "\n".join(
                "| " + " | ".join(ligne) + " |" for ligne in bloc.tableau.lignes
            )
            morceaux.append(f"| {entetes} |\n| {separateur} |\n{lignes}")
            if bloc.tableau.source:
                morceaux.append(f"*{bloc.tableau.source}*")
        elif isinstance(bloc, BlocEncadre):
            lignes = "\n".join(f"- {ligne}" for ligne in bloc.encadre.lignes)
            morceaux.append(f"**{bloc.encadre.intitule}**\n\n{lignes}")
        elif isinstance(bloc, BlocGrilleKpi):
            morceaux.append("\n".join(
                f"**{c.valeur}** — {c.libelle}" + (f" *({c.source})*" if c.source else "")
                for c in bloc.cellules
            ))
        elif isinstance(bloc, BlocGraphique):
            # Marqueur explicite : le rendu résoudra les identifiants en valeurs.
            morceaux.append(
                f"<!-- graphique:{bloc.graphique.type} "
                f"titre=\"{bloc.graphique.titre}\" "
                f"donnees=\"{','.join(bloc.graphique.donnees_ids)}\" -->"
            )
    return "\n\n".join(morceaux)


#: Borne de sortie d'un chapitre structure. **C'est un PLAFOND, pas une
#: depense** : le relever ne coute rien tant que le modele n'ecrit pas
#: davantage. Ce qu'il evite, lui, coute cher.
#:
#: Elle valait 8 192, et aucun appelant ne l'a jamais surchargee : chaque
#: chapitre recevait la meme borne, quelle que soit sa cible editoriale. Or
#: `complete_structured` ne fait QU'UN SEUL appel — pas de boucle de
#: continuation, contrairement a `complete()`. Un chapitre qui demande plus rend
#: donc un appel d'outil tronque, dont l'`input` perd ses derniers champs.
#:
#: Mesure du 08/08/2026, etude de marche `b561c2d6` : le chapitre 19 a echoue
#: SIX fois de suite sur << blocs : champ requis ; resume : champ requis >>,
#: alors que ses voisins consommaient 5 400 a 6 400 jetons — assez pres de la
#: borne pour que le suivant la depasse.
#:
#: 16 000 et pas davantage : au-dela, un appel NON diffuse en flux risque
#: d'expirer avant de rendre sa reponse, et ce client n'utilise pas le flux.
MAX_TOKENS_CHAPITRE = 16000


def motif_de_troncature(stop_reason: str, max_tokens: int) -> list[str]:
    """Rend le motif d'une reponse COUPEE, ou rien si elle s'est terminee.

    Fonction a part, et non trois lignes dans `generer_chapitre` : c'est la
    seule facon de l'eprouver sans monter tout le chemin d'appel — client,
    socle, variables, prompt. Un test qui doit simuler cinq collaborateurs pour
    verifier une condition finit par tester le montage, pas la condition.
    """
    if stop_reason != "max_tokens":
        return []
    return [
        f"reponse tronquee a {max_tokens} jetons de sortie : le modele n'a pas "
        "pu terminer son appel d'outil, les derniers champs du schema "
        "manquent. Ce n'est PAS un defaut de schema — relever la borne de "
        "sortie de ce chapitre, ou resserrer sa cible editoriale."
    ]


def generer_chapitre(
    *,
    client: Any,
    chapter: ChapterGeneration,
    socle: Socle,
    variables: Mapping[str, object],
    max_tokens: int = MAX_TOKENS_CHAPITRE,
    derniere_tentative: bool | None = None,
) -> tuple[ChapitrePayload, dict[str, int], Arbitrage]:
    """Produit UN chapitre. Lève `ChapitreInvalideError` si le contrat est rompu.

    Ne fait qu'une tentative : la reprise est portée par la tâche Celery, qui
    seule sait temporiser et compter les échecs (§6.2).
    """
    job = chapter.job
    document = type_document(str(job.deliverable_type))

    motifs_precedents = _motifs_stockes(chapter)
    prompt, manquantes = construire_prompt_chapitre(
        chapter,
        socle=socle,
        variables=variables,
        document=document,
        motifs_precedents=motifs_precedents,
    )
    if manquantes:
        _log.warning(
            "Chapitre %s : variables de prompt non résolues %s",
            chapter.chapter_number, manquantes,
        )

    resultat = client.complete_structured(
        system=_SYSTEME,
        prompt=prompt,
        outil_nom=OUTIL_NOM,
        outil_description=OUTIL_DESCRIPTION,
        schema=schema_outil(),
        max_tokens=max_tokens,
    )
    consommation = {
        "input_tokens": resultat.input_tokens,
        "output_tokens": resultat.output_tokens,
        # Le cache n'atteignait pas la base. `ClaudeResult` le porte depuis le
        # debut ; personne ne le transportait plus loin. Les deux compteurs sont
        # separes a dessein : une ECRITURE coute 25 % de plus qu'un jeton
        # normal, une LECTURE 90 % de moins. Leur somme ne veut rien dire.
        # `getattr` : plusieurs doublures de test rendent leur propre objet de
        # resultat, sans ces champs. Une doublure qui ne simule pas le cache
        # n'en a pas — zero est la lecture juste, pas un silence.
        "cache_write_tokens": getattr(resultat, "cache_creation_input_tokens", 0),
        "cache_read_tokens": getattr(resultat, "cache_read_input_tokens", 0),
    }

    # La reponse a-t-elle ete COUPEE ? `complete_structured` ne fait qu'un seul
    # appel — pas de boucle de continuation, contrairement a `complete()`. Un
    # chapitre qui demande plus que `max_tokens` rend donc un appel d'outil
    # tronque, dont l'`input` perd ses derniers champs.
    #
    # Sans ce controle, la validation accuse le mauvais coupable : elle annonce
    # << blocs : champ requis ; resume : champ requis >>, ce qui envoie chercher
    # un defaut de schema alors que le schema est intact. Mesure du 08/08/2026,
    # etude de marche `b561c2d6`, chapitre 19 : SIX tentatives, six fois ce
    # motif, et le vrai motif — `stop_reason: max_tokens` — etait capture par
    # `StructuredResult` sans que personne ne le lise. Un motif faux coute plus
    # cher qu'un motif absent (regle 2).
    tronquee = motif_de_troncature(resultat.stop_reason, max_tokens)
    if tronquee:
        raise ChapitreInvalideError(tronquee, consommation)

    try:
        payload = ChapitrePayload.model_validate(dict(resultat.payload))
    except ValidationError as erreur:
        motifs = [_motif_de_validation(item) for item in erreur.errors()[:12]]
        raise ChapitreInvalideError(motifs, consommation) from erreur

    # Reparer AVANT de juger : un resume trop long est ramene dans sa borne,
    # ce qui atteint exactement le but que la borne poursuit. Le refuser
    # detruirait le chapitre — et l'etude, puisque ce runner ne reessaie pas.
    # Reparer AVANT de juger, suite : la typographie se corrige, elle ne se
    # refuse pas. Une double espace ou une ponctuation collee ferait rejouer un
    # appel a six centimes pour un defaut que trois caracteres corrigent. Le
    # compte part au journal : si l'entrainement de la consigne sert, il baisse.
    retouches = reparer_typographie(payload)
    if retouches:
        _log.info(
            "Chapitre %s : %s retouche(s) typographique(s).",
            chapter.chapter_number, retouches,
        )

    mention_resume = raccourcir_le_resume(
        payload, maximum=document.resume_mots_max
    )
    if mention_resume:
        _log.warning(
            "Chapitre %s : %s", chapter.chapter_number, mention_resume
        )

    motifs = valider_chapitre(
        payload,
        numero_attendu=chapter.chapter_number,
        identifiants_socle=frozenset(socle.identifiants),
        resume_mots_min=document.resume_mots_min,
        resume_mots_max=document.resume_mots_max,
        # Le secteur de CETTE étude, pour que le contrôle de secteur étranger
        # vaille sur les QUATRE livrables et pas seulement sur l'étude de
        # marché — la seule que le modèle de forme décrive.
        secteur=socle.secteur,
    )
    if motifs:
        raise ChapitreInvalideError(motifs, consommation)

    arbitrage = _arbitrer_conformite(
        chapter, payload, document, derniere_tentative=derniere_tentative
    )
    if arbitrage.bloque:
        raise ChapitreInvalideError(arbitrage.refus, consommation)

    return payload, consommation, arbitrage


def _arbitrer_conformite(
    chapter: ChapterGeneration,
    payload: ChapitrePayload,
    document: TypeDocument,
    *,
    derniere_tentative: bool | None = None,
) -> Arbitrage:
    """Passe de conformité au modèle, branchée sur la boucle de reprise.

    Elle ne remplace pas `valider_chapitre` : celle-ci juge le CONTRAT (un
    chapitre bien formé), celle-ci juge la FORME (le chapitre attendu). Un
    chapitre peut satisfaire le contrat et ne rien avoir du chapitre 09.

    Le compte des tentatives est lu sur le chapitre, pas passé en argument :
    c'est la seule valeur que la tâche Celery et cette fonction partagent
    réellement. Sur la dernière, les écarts de forme sont acceptés — voir
    `Arbitrage` pour ce que coûterait l'inverse.
    """
    from ..modele.chargement import ModeleIntrouvableError, modele_couvre  # noqa: PLC0415
    from ..modele.conformite import verifier_chapitre  # noqa: PLC0415

    if not modele_couvre(str(chapter.job.deliverable_type)):
        return Arbitrage(non_controle="type de livrable non décrit par le modèle")

    socle_ids: frozenset[str] = frozenset()
    from ..socle.services import socle_verrouille  # noqa: PLC0415

    socle_du_job = socle_verrouille(chapter.job)
    if socle_du_job is not None:
        socle_ids = frozenset(socle_du_job.identifiants)

    try:
        rapport = verifier_chapitre(payload, identifiants_socle=socle_ids)
    except ModeleIntrouvableError as erreur:
        # Sans modèle il n'y a rien à comparer. On ne laisse pas passer en
        # silence — mais on ne bloque pas non plus une étude entière sur un
        # fichier manquant côté serveur : on le nomme (règle 1).
        _log.error("Conformité chapitre %s : %s", chapter.chapter_number, erreur)
        return Arbitrage(non_controle=f"modèle indisponible : {erreur}")

    # QUI SAIT s'il y aura une autre tentative ? L'appelant, et lui seul.
    #
    # Cette valeur était déduite de `chapter.retry_count`, un compteur que
    # **seule** la tâche Celery par chapitre incrémente. Or le chemin qui tourne
    # réellement est le runner synchrone, qui appelle `produire_chapitre` UNE
    # fois et propage l'exception : `retry_count` y reste à zéro, `derniere`
    # y est donc toujours faux, et l'étage « accepter puis consigner » n'était
    # jamais atteint.
    #
    # Conséquence mesurée sur la première génération réelle : l'étude est morte
    # au chapitre 1 sur un écart de volume de 20 %, après 0,0574 € — un écart
    # de dosage, sur un chapitre parfaitement lisible. Exactement ce que la
    # docstring d'`Arbitrage` disait vouloir éviter, et exactement ce que la
    # règle 9 décrit : le contrôle et sa réparation jugeaient sur la même
    # évidence, et la doublure produisait des chapitres conformes — la branche
    # de refus n'a donc jamais tourné avant le premier vrai dossier (règle 7).
    if derniere_tentative is None:
        derniere = chapter.retry_count + 1 >= document.tentatives_max
    else:
        derniere = derniere_tentative
    arbitrage = arbitrer(rapport, derniere_tentative=derniere)

    if arbitrage.acceptes:
        _log.warning(
            "Chapitre %s accepté avec %s écart(s) de forme après %s tentatives : %s",
            chapter.chapter_number, len(arbitrage.acceptes),
            chapter.retry_count + 1, " ; ".join(arbitrage.acceptes),
        )
    return arbitrage


_PREFIXE_MOTIFS = "[contrat] "


def _motifs_stockes(chapter: ChapterGeneration) -> list[str] | None:
    """Motifs du refus précédent, relus depuis `error_message`.

    On ne redemande pas « fais mieux » : on redonne la liste exacte de ce qui
    a été refusé, comme pour le socle.
    """
    if not chapter.error_message.startswith(_PREFIXE_MOTIFS):
        return None
    reste = chapter.error_message[len(_PREFIXE_MOTIFS):]
    return [motif for motif in reste.split(" ; ") if motif] or None


def formater_motifs(motifs: list[str]) -> str:
    return (_PREFIXE_MOTIFS + " ; ".join(motifs))[:2000]
