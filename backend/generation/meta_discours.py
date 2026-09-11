"""Le document ne parle jamais de sa propre fabrication.

## Le défaut

Retour de la cliente sur une stratégie livrée le 08/09/2026 (dossier
`f7f2fad9`) : le document gardait « une trace de ses propres corrections — "ce
que ce chapitre corrige", "version précédente affirmait que…", une note de mise
à jour listant les changements ». Le client doit lire une stratégie, pas le
journal de nos corrections.

Vérifié sur le fichier réellement livré : un intertitre « CE QUE CE CHAPITRE
CHANGE » — qu'aucun prompt ni gabarit ne demande —, et quatre graphiques
portant sous eux le brief de leur propre dessin.

## La cause, et pourquoi ce module en porte la correction

Quand un chapitre est refusé et réécrit, les DEUX chaînes de génération le
disaient au modèle, en dernier et en priorité absolue : « Ta version précédente
de ce chapitre a été REJETÉE » (chaîne HTML), « TENTATIVE PRÉCÉDENTE REFUSÉE »
(chaîne Word, celle de la production). Un rédacteur à qui l'on parle de sa
version précédente écrit en fonction d'elle. La correction de fond est
`consigne_de_correction`, commune aux deux chaînes (règle 5).

## Deux détecteurs, parce qu'un faux positif n'a pas le même prix partout

Le filet de sécurité existe en deux sévérités, et la frontière entre elles est
le COÛT d'un faux positif — la règle 2 appliquée à la dépense.

`trouver_au_gate` alimente le gate, dont chaque échec fait RÉÉCRIRE le chapitre
à nos frais, avec l'ordre d'en retirer le passage : un faux positif y paie une
régénération ET détruit du contenu juste, sans trace une fois le gate repassé
vert. Il ne retient donc que les formes où le sujet est sans ambiguïté le
chapitre lui-même : « ce que ce chapitre change », « ce chapitre a été
corrigé », « la première version de ce chapitre », et la formule de notre
propre ancienne consigne.

`trouver` alimente l'avertissement du contrôle final, qui ne coûte rien et ne
bloque rien : il ajoute les formes probables mais ambiguës (« par rapport à la
version précédente », « nous avons corrigé ce chiffre »…), que la cliente
tranche en relisant.

## Ce qu'aucun des deux n'attrape, et c'est voulu

Relecture du 11/09/2026 : une première version de ce module signalait « Windows
11 : cette version corrige plusieurs failles », « la version précédente posait
des problèmes de compatibilité », « tout lot rejeté par le contrôle qualité est
détruit », « ce rapport révise à la baisse la croissance ». Ce sont des phrases
de CONTENU — maintenance informatique, industrie, source citée —, et la
contre-épreuve qui les avait ratées avait été écrite pour ne pas les frôler.
D'où les exclusions : aucun référent « cette version », « ce document » ou
« ce rapport » (un produit, une offre ou une source en portent autant que nous) ;
aucun « contrôle qualité » ; aucun verbe qu'un logiciel « fait » (poser,
présenter, indiquer) après « version précédente ».
"""
from __future__ import annotations

import re

#: Le chapitre lui-même, et rien d'autre. « Ce document », « ce rapport »,
#: « cette version » en ont été retirés : une source citée, un logiciel ou une
#: offre commerciale en portent autant que notre texte.
_CE_CHAPITRE = r"(?:ce|le\s+pr[ée]sent)\s+chapitre"

#: Ce qu'on fait à un TEXTE qu'on édite, au passif : « ce chapitre a été
#: corrigé ». Au passif, le chapitre est l'objet de la retouche — il n'y a pas
#: de lecture rhétorique possible, à la différence de l'actif « ce chapitre
#: corrige une idée reçue ».
_RETOUCHE_PASSIVE = (
    r"corrig[ée]e?s?|rectifi[ée]e?s?|r[ée]vis[ée]e?s?|modifi[ée]e?s?|remani[ée]e?s?"
    r"|r[ée][ée]crite?s?|actualis[ée]e?s?|mise?s?\s+[àa]\s+jour|rejet[ée]e?s?"
)

_VERSION_ANTERIEURE = r"(?:pr[ée]c[ée]dente|ant[ée]rieure|initiale)"

#: Ce qu'une version d'un TEXTE fait et qu'un logiciel ne fait pas : elle
#: affirme, chiffre, conclut. « Posait », « présentait », « indiquait » sont
#: exclus — la version précédente de Windows fait tout cela.
_ASSERTION = r"affirm|avan[çc]|chiffr|conclu|retenai|surestim|sous-estim"


def _motif(expression: str) -> re.Pattern[str]:
    return re.compile(expression, re.IGNORECASE)


#: Ceux dont le déclenchement fait réécrire un chapitre. Chacun doit être
#: sans lecture légitime possible dans un livrable.
_MOTIFS_GATE: tuple[re.Pattern[str], ...] = (
    # L'intertitre relevé sur le document livré, et sa famille.
    _motif(
        r"\bce\s+(?:que|qu')\s*" + _CE_CHAPITRE
        + r"\s+(?:change|corrige|rectifie|modifie|remplace|r[ée]vise"
        r"|apporte\s+de\s+nouveau)"
    ),
    _motif(
        r"\b" + _CE_CHAPITRE
        + r"\s+(?:a\s+[ée]t[ée]|est|a)\s+(?:" + _RETOUCHE_PASSIVE + r")\b"
    ),
    _motif(
        r"\b(?:premi[èe]re|pr[ée]c[ée]dente|ancienne|derni[èe]re)\s+version\s+"
        r"(?:de\s+ce|du\s+pr[ée]sent)\s+chapitre"
        r"|\bversion\s+" + _VERSION_ANTERIEURE + r"\s+(?:de\s+ce|du\s+pr[ée]sent)\s+chapitre"
    ),
    # « La version précédente affirmait que… » : la citation de la cliente.
    _motif(
        r"\b(?:la|une|cette)\s+version\s+" + _VERSION_ANTERIEURE
        + r"\s+(?:" + _ASSERTION + r")\w*"
    ),
    # Notre propre ancienne consigne, recopiée telle quelle.
    _motif(r"\bcorrection\s+imp[ée]rative|\btentative\s+pr[ée]c[ée]dente\s+refus[ée]e"),
)

#: Ceux qui ne font qu'avertir la cliente. Probables, mais une phrase de contenu
#: peut les porter : c'est à une lecture humaine de trancher.
_MOTIFS_AVERTISSEMENT: tuple[re.Pattern[str], ...] = (
    # « Ce chapitre corrige… » à l'actif : souvent une fuite, parfois de la
    # rhétorique (« ce chapitre corrige une idée reçue sur le marché »).
    _motif(r"\b" + _CE_CHAPITRE + r"\s+(?:corrige|rectifie)\b"),
    _motif(r"\bcette\s+section\s+(?:a\s+[ée]t[ée]\s+)?(?:" + _RETOUCHE_PASSIVE + r")\b"),
    _motif(r"\bdans\s+la\s+version\s+" + _VERSION_ANTERIEURE + r"\s*,"),
    _motif(r"\bpar\s+rapport\s+[àa]\s+(?:la|une)\s+version\s+" + _VERSION_ANTERIEURE),
    _motif(
        r"\b(?:ce\s+qu'|qu')(?:indiquait|affirmait|avan[çc]ait|disait|retenait)\s+"
        r"la\s+version\s+" + _VERSION_ANTERIEURE
    ),
    # « Note de mise à jour : » comme ÉTIQUETTE ; « la note de mise à jour de
    # Windows » est du contenu dans un document de maintenance informatique.
    _motif(r"\bnote\s+de\s+mise\s+[àa]\s+jour\b(?!\s+(?:de|du|des|d')\b)"),
    _motif(r"\bjournal\s+des\s+(?:corrections|r[ée]visions)\b"),
    _motif(
        r"\b(?:modifications|corrections|changements|r[ée]visions)\s+apport[ée]e?s\s+"
        r"(?:(?:[àa]|dans)\s+(?:ce|cette|le|la|la\s+pr[ée]sente)\s+|au\s+)"
        r"(?:chapitre|document|version|section)"
    ),
    # « Nous avons corrigé ce chiffre » : corriger suppose une version fausse.
    # « Nous avons actualisé les données », « nous avons révisé les
    # estimations » sont exclus — c'est la méthode du consultant, du contenu.
    _motif(
        r"\bnous\s+avons\s+(?:corrig[ée]|rectifi[ée])\s+(?:ce|cette|ces|le|la|les)\b"
    ),
)


def _extraits(texte: str, motifs: tuple[re.Pattern[str], ...]) -> list[str]:
    """Les passages reconnus, dans l'ordre du texte, chacun une seule fois.

    Rend l'EXTRAIT exact, pas un booléen : un motif doit pouvoir être retrouvé
    dans le document par qui le lit (règle 2).
    """
    positions: list[tuple[int, int]] = []
    for motif in motifs:
        positions.extend((m.start(), m.end()) for m in motif.finditer(texte or ""))
    positions.sort()

    extraits: list[str] = []
    fin_precedente = -1
    for debut, fin in positions:
        if debut < fin_precedente:
            continue
        extraits.append(texte[debut:fin])
        fin_precedente = fin
    return extraits


def trouver_au_gate(texte: str) -> list[str]:
    """Les fuites certaines — celles qui justifient de réécrire le chapitre."""
    return _extraits(texte, _MOTIFS_GATE)


def trouver(texte: str) -> list[str]:
    """Toutes les fuites, certaines et probables — pour l'avertissement final."""
    return _extraits(texte, _MOTIFS_GATE + _MOTIFS_AVERTISSEMENT)


#: Un commentaire de graphique qui COMMANDE un dessin au lieu de le commenter.
#:
#: Cherché seulement en tête du champ `commentaire`, qui est imprimé sous la
#: figure. Deux formes : l'impératif (« Illustre l'écart ») et l'obligation
#: (« Ce graphique doit montrer »). Le présent descriptif — « Ce graphique
#: montre que… » — est une vraie phrase de lecture et n'est jamais visé.
_VERBES_DE_DESSIN = (
    r"repr[ée]sent|illustr|compar|positionn|montr|visualis|trac|situ|affich"
    r"|mat[ée]rialis"
)
_DETERMINANT = r"(?:le|la|les|l'|l’|un|une|des|du|au|aux|ce|cette|ces|chaque)\b"
#: L'IMPÉRATIF seulement — le document vouvoie, il ne tutoie jamais : un
#: « Illustre l'écart » ne peut s'adresser qu'au dessinateur.
#:
#: L'infinitif a été essayé puis retiré (11/09/2026). Rejoué sur une vraie
#: stratégie, il prenait pour des consignes « Comparer chaque mois à la
#: trajectoire… » et « Illustrer l'argumentaire par des exemples concrets… » :
#: c'est ainsi qu'une stratégie RECOMMANDE au dirigeant, et une telle phrase
#: sous un graphique peut être un vrai conseil de lecture. Les quatre fuites
#: réelles relevées étaient toutes à l'impératif.
_ORDRE = "|".join((
    r"(?:" + _VERBES_DE_DESSIN + r")e",
    r"fais\s+appara[îi]tre",
    r"mets\s+en\s+(?:[ée]vidence|regard)",
))
_OBLIGATION = (
    r"(?:ce\s+|le\s+)?graphique\s+(?:doit|devra|devrait)\s+(?:"
    + _VERBES_DE_DESSIN + r")er\b"
)
_DESSIN = re.compile(
    r"^\s*(?:(?:" + _ORDRE + r")\s+" + _DETERMINANT + r"|" + _OBLIGATION + r")",
    re.IGNORECASE,
)

def est_une_consigne_de_dessin(texte: str) -> bool:
    """Ce commentaire de graphique est-il un ordre adressé au dessinateur ?

    Stratégie livrée le 08/09/2026 : quatre graphiques portaient sous eux
    « Représente les grandes étapes… », « Illustre l'écart… », « Compare le
    chiffre d'affaires… ». Le champ `commentaire` est imprimé À LA PLACE DE LA
    SOURCE ; le modèle y avait mis le brief du graphique.
    """
    return bool(_DESSIN.match(texte or ""))


def consigne_de_correction(motifs: list[str]) -> str:
    """Les exigences d'une réécriture, formulées pour ne rien laisser au lecteur.

    **Aucune mention de version précédente, de refus, ni de contrôle.** Ce qu'on
    dit au modèle de sa première tentative, il le répète au client : lui
    annoncer qu'elle a été « REJETÉE » produisait « la version précédente
    affirmait que… » dans le document livré.

    Les motifs restent donnés en entier et à la lettre — ils sont ce qui rend
    la réécriture utile. Une note déjà mise en liste (« - motif ») est
    dépliée ligne à ligne plutôt que préfixée une seconde fois.
    """
    lignes: list[str] = []
    for motif in motifs:
        for ligne in str(motif).splitlines():
            propre = ligne.strip().lstrip("-•").strip()
            if propre:
                lignes.append(f"- {propre}")
    if not lignes:
        return ""
    liste = "\n".join(lignes)
    return (
        "EXIGENCES IMPÉRATIVES POUR CE CHAPITRE — chacune doit être satisfaite, "
        "sans rien dégrader de ce qui était juste :\n"
        f"{liste}\n\n"
        "Rédige le chapitre comme s'il était écrit pour la première fois. Le "
        "lecteur ne sait pas qu'il a été réécrit et ne doit jamais l'apprendre : "
        "n'écris pas que le chapitre corrige, remplace, change ou met à jour quoi "
        "que ce soit, ne mentionne aucune version antérieure, aucun contrôle, "
        "aucune correction, et n'ajoute aucune note de mise à jour."
    )
