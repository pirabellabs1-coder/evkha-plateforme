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

from integrations.claude import SYSTEM_CACHE_BREAK

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
    # Business plan `2a8872d0` (12/08/2026) : le chapitre 7 est mort en trois
    # tentatives sur `critere_accessibilite_evkha`. Le modele n'avait rien
    # invente — il avait DECORE le code : un prefixe qui dit la nature, un
    # suffixe qui dit la maison. Le resolveur repare desormais ce cas ; la
    # consigne existe pour qu'il n'ait pas a le faire.
    "Un identifiant se recopie EXACTEMENT tel qu'il t'est donné : pas de "
    "préfixe (`critere_`, `donnee_`), pas de suffixe, jamais un nom de "
    "marque. `accessibilite` reste `accessibilite`.\n"
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
    # Retour cliente du 11/08/2026 : « socle bloqué / pipeline système » sont
    # ressortis dans un document livré. La regle vaut pour la CLASSE.
    "Ne nomme JAMAIS nos rouages : ni socle verrouillé ou bloqué, ni hors "
    "socle, ni pipeline système, ni gate qualité, ni prompt système, ni "
    "chapitre 0, ni livrable bloqué. Le client lit une étude de marché, pas "
    "le journal de la machine qui l'a écrite. Si une donnée manque, dis ce "
    "qui manque et ce que tu retiens à la place — jamais « le socle ne la "
    "porte pas ».\n"
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
    # Le gate refuse ces locutions (`detecter_ton_publicitaire`) et la
    # consigne ne les nommait pas : le modele les decouvrait en payant une
    # reprise — « incontournable » corrige en cours de route sur `026fecea`.
    "TON DESCRIPTIF, JAMAIS PUBLICITAIRE. Aucun superlatif marketing — "
    "« leader incontestable », « incontournable », « révolutionnaire », "
    "« unique en son genre », « sans équivalent », « meilleur du marché » — "
    "pas même pour décrire un concurrent. À la place, le FAIT CHIFFRÉ qui "
    "justifierait l'adjectif : « cité par 9 comparateurs sur 12 » dit plus "
    "qu'« incontournable ».\n"
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


#: La consigne qui manquait sous le socle, et qui a coûté un défaut de forme.
#:
#: Retour cliente du 12/08/2026 sur un business plan noté 8/10 : « des traces
#: techniques internes. Des mentions telles que "socle EVKHA",
#: ca_previsionnel_an1, marche_national_taille apparaissent sous des tableaux ».
#:
#: LE MODÈLE N'A RIEN FAIT DE MAL. Les lignes qui suivent lui montrent, côte à
#: côte, un identifiant entre accents graves et le mot « source ». Quand il
#: remplit le champ `source` d'un tableau, il écrit ce qu'il a sous les yeux.
#: On lui a montré la notation de stockage sans jamais lui dire qu'elle ne se
#: recopie pas — exactement la leçon déjà tirée des unités (`Md€` et non
#: `MdEUR`), une ligne plus haut dans ce même fichier, et jamais étendue aux
#: identifiants eux-mêmes.
#:
#: Le garde-fou du schéma refuse ces fuites. Il arrive après : il fait perdre
#: une tentative et de l'argent là où une phrase de consigne suffit (règle 3 —
#: la cause dans la consigne, le contrôle en dernière ligne).
_CE_QUI_NE_SE_RECOPIE_PAS = (
    "\n\nCE QUI NE SE RECOPIE JAMAIS DANS LE DOCUMENT :\n"
    # AUCUN IDENTIFIANT EN EXEMPLE ICI.
    #
    # Cette consigne en citait deux — `ca_previsionnel_an1` et
    # `marche_national_taille` — pour illustrer ce qu'il ne faut pas recopier.
    # Étude concurrentielle `b6cb8076`, 13/08/2026 : le chapitre 8 a cité
    # `ca_previsionnel_an1`, un identifiant de BUSINESS PLAN absent du socle
    # d'une étude de concurrence. Le contrôle a eu raison de le refuser.
    #
    # Le modèle ne l'a pas inventé : il l'a lu ICI. En lui interdisant de
    # recopier les identifiants, on lui en montrait un qu'il ne connaissait
    # pas — et l'exemple d'une interdiction se recopie comme le reste.
    #
    # C'est la leçon déjà écrite dans `schema.py` à propos de la notation entre
    # crochets : « tout ce qu'on ajoute au prompt pour aider le modèle peut
    # ressortir dans le document ». Elle vaut aussi pour les exemples d'une
    # règle qui interdit de recopier.
    #
    # La consigne DÉSIGNE désormais les lignes qui suivent, sans en nommer
    # aucune : le modèle a la liste réelle sous les yeux, elle lui suffit.
    "- Les identifiants entre accents graves dans les lignes ci-dessous sont "
    "des ÉTIQUETTES POUR TOI, qui te servent à "
    "retrouver la même valeur d'un chapitre à l'autre. Ils ne s'écrivent nulle "
    "part dans le texte : ni dans une phrase, ni dans un titre, ni sous un "
    "tableau, ni dans le commentaire d'une figure. Dis la CHOSE — « le chiffre "
    "d'affaires prévisionnel de la première année » — jamais son étiquette.\n"
    "- Le mot « socle », et le nom de la plateforme qui produit ce document, "
    "n'apparaissent jamais. Le livrable est remis en marque blanche : son "
    "lecteur croit — et doit croire — que son auteur l'a écrit lui-même.\n"
    "- Le champ `source` d'un tableau ou d'un indicateur cite une source "
    "RÉELLE et vérifiable : « INSEE, base Sirene 2025 », « Xerfi, panorama du "
    "secteur, mars 2026 », ou l'une des sources web fournies pour ce chapitre. "
    "Si la valeur vient du dossier client, écris « données du projet ». Si tu "
    "n'as pas de source à citer, LAISSE LE CHAMP VIDE — un champ vide se lit, "
    "une référence interne trahit la machine.\n"
    "\nTU NE RECALCULES RIEN. Les chiffres ci-dessous sont arrêtés pour tout le "
    "document : un seuil de rentabilité, une marge, un total de financement ne "
    "se redérivent pas au fil des chapitres. Reprends la valeur telle qu'elle "
    "est. Si un chiffre dont tu as besoin n'y figure pas, ÉCRIS QU'IL MANQUE — "
    "n'en produis pas un de ton côté : ton voisin en produirait un autre, et le "
    "document se contredirait d'un chapitre à l'autre. Les lignes marquées "
    "« Calculé : » portent leur formule ; cite-la si le lecteur doit pouvoir "
    "refaire l'opération, mais ne refais pas le calcul toi-même."
)


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
        + _CE_QUI_NE_SE_RECOPIE_PAS
    )
    return (
        entete + "\n" + "\n".join(lignes)
        + _bloc_concurrents(socle)
        + _bloc_grille(socle)
    )


def _bloc_concurrents(socle: Socle) -> str:
    """La base consolidée concurrents, transmise aux chapitres.

    Elle ne l'était PAS. Le socle porte onze acteurs — noms, emplacements,
    CA connus, méthodes d'estimation — et les chapitres n'en voyaient que les
    notes de la grille. Mesuré sur `6cb0fab3` (10/08/2026) : le chapitre 9
    présente 7 concurrents directs au lieu de 8 et 6 indirects au lieu de 3,
    parce que le modèle recompose sa propre liste de mémoire, chapitre après
    chapitre. Le gate compte, la liste dérive, le document est bloqué — pour
    une donnée que le socle portait depuis la passe 1 (règle 8 : écrit,
    validé, jamais transmis ; c'est la sixième fois sur ce projet).
    """
    if not socle.concurrents:
        return ""

    # Comptés par leur TYPE, jamais par soustraction.
    #
    # `indirects = len(concurrents) - directs` a tenu tant que la base ne
    # portait que des concurrents. Depuis le 13/08/2026 elle porte aussi
    # l'entreprise du dossier, de type `projet`, pour qu'elle figure sur ses
    # propres graphiques — et la soustraction la comptait comme un indirect.
    # Chaque chapitre aurait reçu « 8 directs et 4 indirects, ni plus ni
    # moins », un compte faux que le socle dément à trois lignes de là.
    directs = sum(1 for a in socle.concurrents if a.type == "direct")
    indirects = sum(1 for a in socle.concurrents if a.type == "indirect")
    projet = next((a for a in socle.concurrents if a.type == "projet"), None)
    lignes = []
    for a in socle.concurrents:
        tete = f"- {a.nom} ({a.type}" + (f", {a.emplacement}" if a.emplacement else "") + ")"
        morceaux = [tete]
        if a.ca_connu:
            morceaux.append(f"CA : {a.ca_connu}")
        elif a.methode_estimation:
            morceaux.append(f"CA non publié — à estimer par : {a.methode_estimation}")
        if a.positionnement:
            morceaux.append(a.positionnement)
        lignes.append(" — ".join(morceaux))

    return (
        f"\n\nBASE CONSOLIDÉE CONCURRENTS — liste FERMÉE : {directs} directs "
        f"et {indirects} indirects, ni plus ni moins.\n"
        "Tout chapitre qui compare, compte ou classe reprend CES acteurs et "
        "ces comptes tels quels. Personne d'autre n'entre, personne ne sort : "
        "ajouter un acteur ou en omettre un fait rejeter le document.\n"
        + (
            f"L'entreprise du dossier, « {projet.nom} », figure dans la liste "
            "avec le type `projet`. Elle NE COMPTE PAS dans les deux nombres "
            "ci-dessus — ce n'est pas un concurrent d'elle-même — mais elle "
            "apparaît sur toute figure qui compare des acteurs, pour que le "
            "lecteur voie où elle se situe.\n"
            if projet is not None else ""
        )
        + "\n".join(lignes)
    )


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
        + ", ".join(
            f"{note.critere} {note.note}/5"
            for note in sorted(acteur.notes, key=lambda n: n.critere)
        )
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
        # Quatre radars identiques dans un meme document (chapitres 1, 2.3,
        # 7.6, 7.7), dont un intitule « concurrents indirects » qui affichait
        # des directs : rien ne permettait de dire QUELS acteurs comparer.
        # Retour cliente du 13/08/2026 : « lorsqu'un graphique sert à démontrer
        # le positionnement concurrentiel, le lecteur doit immédiatement
        # pouvoir voir : où se situe mon entreprise par rapport à ses
        # concurrents ? » Le socle la note désormais comme douzième acteur ;
        # reste à dire qu'elle ne se retire jamais d'une comparaison.
        "- L'ENTREPRISE DU DOSSIER, notée `projet` dans la base, figure sur "
        "TOUTE figure qui compare des acteurs — radar, carte de "
        "positionnement, matrice, comparatif chiffré. C'est le point de "
        "référence du lecteur : un benchmark sans elle lui montre le marché "
        "sans lui dire où il se trouve. Elle s'ajoute AUX acteurs que tu "
        "compares, même quand tu restreins la figure aux directs ou aux "
        "indirects.\n"
        "- QUELS acteurs : ajoute `directs` ou `indirects` à tes identifiants "
        "pour ne comparer que ceux-là, ou cite leurs NOMS exacts tels qu'ils "
        "figurent dans la base consolidée. Sans cette précision, la figure "
        "prend tous les acteurs notés — et deux chapitres qui comparent des "
        "groupes différents obtiendraient la MÊME image. Le titre d'une "
        "figure doit décrire ce qu'elle montre vraiment.\n"
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
        "cette liste.\n"
        # La même exigence que le socle, à l'endroit où les sources sont
        # RÉELLEMENT citées. Demande de la cliente du 13/08/2026, posée pour
        # les quatre livrables ; la mettre dans le seul prompt du socle
        # l'aurait laissée sans effet sur les tableaux et les notes de bas de
        # figure, c'est-à-dire là où le lecteur la voit.
        "QUALITÉ DES SOURCES, quand plusieurs disent la même chose : prends la "
        "plus PRIMAIRE et la plus RÉCENTE — statistiques publiques et "
        "organismes officiels d'abord, puis fédérations professionnelles, puis "
        "sites officiels des acteurs, puis études sectorielles ; la presse et "
        "les blogs en dernier, et jamais pour un chiffre qu'une source des "
        "rangs supérieurs pourrait donner.\n"
        "LA SOURCE DOIT PORTER CE QUE TU LUI FAIS DIRE. Une page qui traite du "
        "sujet sans donner la valeur n'étaye pas la valeur : la citer ferait "
        "passer ton raisonnement pour un fait publié. Dans ce cas, écris que "
        "c'est une estimation et dis sur quoi elle s'appuie, ou ne cite "
        "rien.\n\n" + utile
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
        "« Hypothèses » vaut mieux qu'une note de bas de tableau.\n"
        # Le gate `fourchette_interdite` punissait ce que la consigne ne disait
        # pas : « 3-5 % » au chapitre 7 de `6cb0fab3`, corrigé deux fois, revenu
        # deux fois — le modèle ne savait pas que c'était interdit.
        "- Un montant se DÉCIDE : jamais de fourchette (« 100-120 k€ », "
        "« 3-5 % »). Un chiffre unique, et l'hypothèse qui le porte. La plage "
        "appartient à l'étude de marché ; un prévisionnel tranche."
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
        "quelles priorités avant le lancement ?\n"
        "- Un chiffre se DÉCIDE : jamais de fourchette nue (« 3-5 % »). Quand "
        "une source donne une plage, écris le chiffre retenu et dis pourquoi "
        "celui-là.\n"
        # Retours de la cliente du 11/08/2026, apres analyse de la V2.
        "- Une part de marché ne se compare qu'à PÉRIMÈTRE IDENTIQUE : même "
        "pays, même année, même secteur, même canal, même périmètre de "
        "produits ou de services, même unité. Avant tout classement, dis en "
        "une phrase le périmètre commun retenu. Deux parts de périmètres "
        "différents ne se soustraient pas, ne s'additionnent pas et ne se "
        "classent pas — si un acteur n'est connu que sur un autre périmètre, "
        "dis-le et sors-le du classement.\n"
        "- Le comparatif s'appuie sur des FAITS OBSERVABLES avant toute "
        "notation : prix de produits ou de prestations RÉELLEMENT comparables "
        "(même contenance, même durée, même niveau de service), notes et "
        "volumes d'avis, niveau de gamme, délais, garanties. La note de 1 à 5 "
        "RÉSUME ces faits, elle ne les remplace pas : chaque note s'appuie sur "
        "au moins un fait cité.\n"
        "- Les sources de première main passent AVANT tout agrégateur : site "
        "officiel du concurrent, conditions générales de vente, page tarifs, "
        "page livraison, page fidélité ou abonnement. C'est là que se lisent "
        "le vrai prix, les frais annexes et les engagements — pas dans un "
        "comparatif tiers.\n"
        "- Un espace de différenciation se QUALIFIE sur cinq niveaux : libre, "
        "peu occupé, occupé mais sous-exploité, mature, saturé. Jamais "
        "« personne n'est présent » ni « tout est pris » : ces formules "
        "binaires sont presque toujours fausses et ne se décident pas.\n"
        "- La conclusion permet au porteur de répondre SEUL à ces questions : "
        "qui sont mes vrais concurrents ? qui domine ? qui est le plus "
        "dangereux pour moi ? où sont-ils meilleurs ? quels standards dois-je "
        "égaler ? sur quoi ne dois-je surtout pas les affronter ? quel espace "
        "reste réellement disponible ? quel positionnement est le plus "
        "crédible ? mon marché est-il saturé ? ai-je une vraie chance "
        "d'entrer ? quelle stratégie de lancement est la plus logique ? "
        "Chacune reçoit une réponse explicite, pas une allusion."
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
        "lecteur.\n"
        "- Un objectif chiffré se DÉCIDE : jamais de fourchette nue "
        "(« 3-5 % »). Une stratégie qui vise « entre 100 et 150 k€ » n'a pas "
        "choisi — écris le chiffre visé et l'hypothèse qui le porte.\n"
        # Le gate STR verifie ces trois structures (structure_chapitre,
        # lecture_strategique_absente, pilier_manquant) et la consigne ne les
        # disait pas : la meme surdite que la fourchette, mesuree sur la
        # repetition a blanc du 10/08/2026.
        "- Chaque chapitre porte AU MOINS DEUX sous-parties nommées (blocs "
        "`titre_sous_section`) et se ferme sur un bloc de recul — « À "
        "retenir » ou « Lecture stratégique » : conséquences futures, lien "
        "aux décisions.\n"
        "- Les QUATRE PILIERS structurent le document et chacun y apparaît en "
        "toutes lettres : positionnement et différenciation, structuration de "
        "l'offre, visibilité et acquisition, rentabilité du modèle économique."
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
    # Quatre des sept CHECK bloquants de `cc0dfe14` (11/08/2026) portaient sur
    # CE point, sous quatre formes : « inverser l'ordre logique », « nommer le
    # taux de capture », « boucler l'emboitement », « trancher le scenario
    # central ». Le relecteur redemandait la meme chose a quatre chapitres
    # differents, et chaque demande coutait une reprise.
    "- Un marche atteignable se DEDUIT, il ne se justifie pas apres coup. "
    "Ecris toujours dans cet ordre : un taux de capture du marche accessible, "
    "puis le montant qui en decoule, puis sa traduction concrete. « Un taux "
    "de capture de 0,01 % du marche accessible donne 130 000 €, soit environ "
    "2 000 commandes a 65 € » — jamais l'inverse. Ce taux se REPETE dans le "
    "verdict de viabilite : c'est lui qui rend l'objectif discutable.\n"
    # « Preciser explicitement si le taux compare est celui du marche francais
    # ou du marche mondial. » Un taux nu oblige le lecteur a deviner.
    "- Tout taux et tout montant nomme SON PERIMETRE a chaque occurrence : "
    "« 3,4 % par an (France) », jamais « 3,4 % » seul quand le document porte "
    "aussi un chiffre mondial. Deux perimetres compares dans la meme phrase "
    "se nomment tous les deux.\n"
    # « Ne pas enoncer de nouveau les chiffres presents tels quels, mais
    # expliquer en quoi ces contraintes se transforment a horizon 2026-2030. »
    "- Une section sur l'AVENIR ne redit pas les chiffres du present : elle "
    "dit ce qu'ils deviennent. Un defi se projette — s'aggrave, s'attenue, "
    "sature — avec l'horizon et le mecanisme. Reciter le present sous un "
    "titre d'avenir ne repond pas a la question posee.\n"
    # « Citer les references precises des textes evoques. »
    "- Une regle de droit se cite avec SA REFERENCE : numero de reglement, "
    "de directive ou article de code. « Le delai de retractation de 14 jours "
    "(article L221-18 du code de la consommation) » — une obligation sans "
    "reference n'est pas verifiable, donc pas opposable.\n"
    # « Dedupliquer les deux entrees Xerfi, memes lien et code d'etude, titres
    # differents. » Une source citee deux fois gonfle le compte sans rien
    # ajouter, et fait douter des autres.
    "- Une SOURCE n'apparait qu'UNE FOIS dans la bibliographie. Deux entrees "
    "au meme lien ou au meme numero d'etude se fondent en une, sous le titre "
    "exact de l'editeur.\n"
    # Deux troncatures sur le meme dossier : un chapitre fini sur un intitule
    # en gras, un autre sur une cellule de tableau. Le lecteur y voit une
    # coupure, et le controle aussi.
    "- Un chapitre se termine par une PHRASE, jamais par un titre, une "
    "etiquette en gras, une cellule de tableau ou une figure. La derniere "
    "ligne porte un point final.\n"
    # « Il y a des erreurs dans les calculs et pourcentages » (cliente,
    # 11/08/2026). Une extrapolation est legitime ; une extrapolation FAUSSE
    # ruine la credibilite de tout le document.
    "- Tout chiffre CALCULÉ montre son calcul, en clair, dans la phrase ou "
    "juste après : « 130 000 € sur 1,36 Md€, soit 0,0096 % ». Une part se "
    "vérifie en divisant, une évolution en soustrayant puis divisant par la "
    "valeur de DÉPART, une projection en multipliant. Relis chaque opération "
    "avant de l'écrire : un pourcentage faux se repère au premier coup d'œil "
    "et fait douter de tout le reste.\n"
    # « Renforcer les points d'estimation avec des donnees REELLES : trafic,
    # CA groupe/pays, reseau, nombre de commandes, avis. Ce sont des donnees
    # concretes que les clients aiment bien » (cliente, 11/08/2026).
    "- Une taille d'acteur ou de marché s'ESTIME sur des traces observables, "
    "et tu les cites : trafic du site, chiffre d'affaires du groupe ou du "
    "pays, nombre de points de vente ou d'agences, effectif, nombre de "
    "commandes ou d'abonnés, volume et note des avis, ancienneté, levées de "
    "fonds. Une estimation qui ne dit pas SUR QUOI elle repose n'est qu'une "
    "opinion chiffrée — et deux traces valent mieux qu'une, parce qu'elles se "
    "recoupent.\n"
    # « Un point non traité n'est pas très acceptable dans une étude qui dit
    # qu'elle va le faire » — et il l'était par simple oubli de relecture.
    # « Le texte de legende admet lui-meme que c'est un placeholder jamais
    # complete » (cliente, 11/08/2026). Un provisoire livre est un aveu.
    "- Aucune figure, aucun tableau, aucune légende n'est PROVISOIRE. Pas de "
    "« à compléter », « exemple générique », « données à insérer », « placeholder ». "
    "Si tu ne peux pas alimenter un visuel, ne le demande pas et dis en une "
    "phrase ce qui manquerait pour le produire. Une légende qui avoue son "
    "propre inachèvement décrédibilise tout le document.\n"
    "- Ne déclare JAMAIS « non traité » un sujet que le document aborde "
    "ailleurs. Avant de statuer sur une demande du client, relis les résumés "
    "des chapitres précédents : s'ils la couvrent, le statut est « traitée » "
    "et tu nommes le chapitre. « Non traité » ne se dit que d'un sujet absent "
    "de tout le document, et s'accompagne alors de ce qui manque pour le "
    "traiter.\n"
    "- Une hypothèse ou une extrapolation est PERMISE, à trois conditions : "
    "elle se dit hypothèse, elle nomme la donnée de départ et le raisonnement "
    "appliqué, et son résultat reste cohérent avec les autres chiffres du "
    "document. Un chiffre extrapolé qui contredit un chiffre établi ailleurs "
    "est une erreur, pas une nuance.\n"
    # « La SWOT doit deboucher sur de vraies priorites strategiques, pas sur
    # une liste de limites. » Une SWOT qui s'arrete au tableau laisse au
    # lecteur le travail qu'il a paye : croiser les quatre cases.
    "- Une SWOT ne s'arrête JAMAIS au tableau. Elle se ferme sur deux ou "
    "trois priorités, tirées du CROISEMENT des cases : quelle force sert "
    "quelle opportunité, quelle faiblesse expose à quelle menace, et donc "
    "par où commencer. Une SWOT qui énumère sans conclure laisse au lecteur "
    "le travail qu'il a payé.\n"
    # « Rendre l'etude plus accessible, moins de tournures techniques »
    # (cliente, 12/08/2026), avec SON exemple : « l'abonnement CRM sort de
    # cette lecture comme la verticale la plus scalable » -> « l'abonnement
    # CRM apparait comme l'activite la plus facile a developper a grande
    # echelle sans augmenter les couts au meme rythme ».
    #
    # Le lecteur du livrable est un DIRIGEANT, pas un consultant. Ce qu'il ne
    # comprend pas, il ne l'applique pas — et une strategie qu'on n'applique
    # pas ne vaut rien, quelle que soit sa justesse. La regle vaut pour les
    # quatre livrables : « ca doit s'appliquer sur toutes les etudes »
    # (cliente, 11/08/2026).
    "- Écris pour un DIRIGEANT, pas pour un consultant. Chaque terme technique "
    "ou anglais est soit remplacé par son équivalent courant, soit expliqué "
    "dans la phrase même — jamais laissé nu. « La verticale la plus scalable » "
    "devient « l'activité la plus facile à développer à grande échelle sans "
    "augmenter les coûts au même rythme ». Même traitement pour churn, lead, "
    "funnel, ARR, CAC, LTV, scalabilité, verticale, pricing, benchmark, "
    "top-of-funnel. Le test : une phrase qu'un lecteur doit relire deux fois "
    "pour la comprendre est à réécrire, même si elle est juste."
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


class PromptChapitre(str):
    """Le prompt complet d'un chapitre, découpé pour le cache.

    ## Pourquoi une chaîne qui se connaît en deux morceaux

    Le prompt d'un chapitre pèse dix à vingt fois le rôle système, et sa plus
    grande part — socle, base concurrents, grille, consigne de livrable,
    brief — est IDENTIQUE pour les dix à vingt-trois chapitres d'un même
    dossier. Elle partait pourtant entière dans le message utilisateur, que
    rien ne met en cache : seuls les blocs système portent `cache_control`
    (`integrations/claude.py`, TTL 1 h). Mesuré sur le dossier réel
    `2490c7cf` : 24 % de lecture cache — le rôle système, rien d'autre.
    Chaque chapitre repayait le socle entier au tarif plein.

    `generer_chapitre` envoie donc `par_job` dans le SYSTÈME, derrière
    `SYSTEM_CACHE_BREAK` : écrit une fois au premier chapitre du dossier,
    relu à un dixième du prix par tous les suivants. `par_chapitre` reste
    dans le message utilisateur, puisqu'il change à chaque appel — sources du
    chapitre, résumés accumulés, instruction, motifs de reprise.

    La chaîne elle-même reste le prompt COMPLET, blocs dans l'ordre : tout
    consommateur existant — tests, script de vérification des demandes de la
    cliente — qui la lit comme un texte y trouve tout ce qu'il y trouvait.
    """

    par_job: str
    par_chapitre: str

    def __new__(cls, par_job: str, par_chapitre: str) -> PromptChapitre:
        complet = par_job + "\n\n" + par_chapitre if par_job else par_chapitre
        instance = super().__new__(cls, complet)
        instance.par_job = par_job
        instance.par_chapitre = par_chapitre
        return instance


def construire_prompt_chapitre(
    chapter: ChapterGeneration,
    *,
    socle: Socle,
    variables: Mapping[str, object],
    document: TypeDocument,
    motifs_precedents: list[str] | None = None,
) -> tuple[PromptChapitre, list[str]]:
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

    # PAR_JOB : strictement identique pour tous les chapitres du dossier —
    # le socle est verrouillé, la consigne de livrable est une constante, le
    # brief est figé à l'intake. C'est la condition du cache : un octet qui
    # varie invalide tout le préfixe.
    par_job = "\n\n".join([
        _bloc_socle(socle),
        *([consigne_livrable] if consigne_livrable else []),
        f"BRIEF_CLIENT :\n{json.dumps(dict(variables), ensure_ascii=False, sort_keys=True)}",
    ])

    # PAR_CHAPITRE : tout ce qui change d'un appel à l'autre — les sources
    # collectées pour CE chapitre, les résumés qui s'accumulent, l'instruction,
    # les formes déjà employées, le verdict du dernier chapitre, les motifs
    # d'une reprise.
    blocs = [
        _bloc_sources(chapter.job, chapter.chapter_number),
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

    return PromptChapitre(par_job, "\n\n".join(blocs)), manquantes


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

    # Le bloc par-job passe dans le SYSTÈME, derrière le point de coupe du
    # cache : `_cacheable_system` en fait un second bloc `cache_control`,
    # écrit au premier chapitre, relu à un dixième du prix par les suivants.
    # Voir `PromptChapitre` pour la mesure qui a motivé ce découpage.
    resultat = client.complete_structured(
        system=_SYSTEME + SYSTEM_CACHE_BREAK + prompt.par_job,
        prompt=prompt.par_chapitre,
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
        identifiants_socle=frozenset(socle.identifiants_citables),
        resume_mots_min=document.resume_mots_min,
        resume_mots_max=document.resume_mots_max,
        # Le secteur de CETTE étude, pour que le contrôle de secteur étranger
        # vaille sur les QUATRE livrables et pas seulement sur l'étude de
        # marché — la seule que le modèle de forme décrive.
        secteur=socle.secteur,
        # Au dernier essai, un identifiant hors socle fait jeter la DÉCLARATION
        # et non le chapitre : perdre une analyse concurrentielle entière pour
        # une métadonnée est le mauvais prix (business plan `2a8872d0`).
        derniere_tentative=derniere_tentative,
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
        socle_ids = frozenset(socle_du_job.identifiants_citables)

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
