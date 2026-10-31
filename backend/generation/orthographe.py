"""Les accents, jugés sans dictionnaire : le texte contre lui-même.

## Le défaut, mesuré

Étude de marché à l'export, cliente, 26/10/2026 : « toutefise », « precise »,
« acheteurs transfrontalier ». Aucun dictionnaire français n'est installé dans
l'image, et en ajouter un est une décision d'infrastructure qui appartient au
client.

Mais une faute d'accent se trahit seule : le texte écrit « précise » ailleurs.
**Le corpus de référence, c'est le document lui-même.** Deux graphies du même
mot sont un défaut quelle que soit celle qui est juste, et la graphie accentuée
est celle qui a raison.

## On SIGNALE, on ne répare pas — et c'est la doctrine du dépôt qui le dit

`chapitres.typographie` ouvre par la règle inverse : « on répare, on ne refuse
pas ». J'y avais donc greffé la réparation des accents le 27/10/2026. C'était
une erreur, et le critère qui la condamne est écrit dans ce même fichier : il
ne répare que les classes qui n'ont **aucune exception légitime** en français.

Les accents en ont plusieurs, et la revue les a mesurées sur du contenu réel :

    « Credit Suisse Research Institute » → « Crédit Suisse Research Institute »
    « General Motors »                  → « Général Motors »
    « theme park »                      → « thème park »
    « ACCES AU MARCHE »                 → « Accès AU MARCHE »

Un nom propre, une marque, un terme anglais, un bandeau en capitales : la
réparation prenait un mot JUSTE et en faisait une faute, dans un livrable
payant — et elle effaçait du même coup la preuve que le contrôle aurait pu
lire. Falsifier le nom d'une source est plus grave que lui laisser un accent.

Ce module ne fait donc que fournir la MESURE, à un seul lecteur :
`relecture.redaction`, qui signale sur le document entier et ne touche à rien.

## Ce que ce module ne voit pas, et pourquoi c'est écrit ici

Une faute écrite de façon CONSTANTE — « toutefise » partout, un mot dont la
forme juste n'apparaît nulle part — reste invisible : il n'y a rien à comparer
(règle 1). La fermer demande un dictionnaire français.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

#: Longueur minimale d'un mot jugé. En dessous, l'accent sépare presque
#: toujours deux mots français bien réels — « a / à », « ou / où »,
#: « la / là », « des / dès », « du / dû », « sur / sûr » — et le code n'a pas
#: de quoi choisir.
LONGUEUR_JUGEABLE = 5

#: Les mots dont les DEUX graphies existent en français, accent non final.
#:
#: Deux familles, et toutes deux fermées — ce ne sont pas des cas observés mais
#: des faits de langue (règle 4) :
#:
#: - les homographes : « tache » et « tâche », « cotes » et « côtes », « foret »
#:   et « forêt », « notre » et « nôtre », « roder » et « rôder » ;
#: - les graphies admises par la réforme de 1990, où l'accent circonflexe est
#:   devenu facultatif : « cout », « aout », « boite », « maitre », « chaine »,
#:   « paraitre », « gout », « bruler », « surement », « fraiche ».
#:
#: Dans les deux cas, écrire le mot des deux façons n'est pas une faute
#: d'orthographe, et le code ne doit ni le dire ni le corriger.
DEUX_GRAPHIES = frozenset((
    "tache taches tacher tachent tachait "
    "cotes coter cotee cotees cotent "
    "foret forets jeune jeunes jeunesse mures "
    "notre votre mater matez haler halez roder rodent rodage "
    "cout couts couteux couteuse couteuses aout boite boites boitier "
    "maitre maitres maitrise maitriser maitrisee maitrisees "
    "chaine chaines chainon chainons "
    "paraitre paraissent connaitre apparaitre disparaitre naitre reconnaitre "
    "gout gouts goutte bruler brulure brulant surement piqure voute croute "
    "fraiche fraicheur traine trainer trainee abime abimer plait "
    "entraine entrainer entrainement entrainee "
    # « croit » (croire) et « croît » (croître) : signalé à tort dans trois
    # études de test sur quatre (30/10/2026).
    "croit"
).split())

#: Un mot écrit en capitales est un sigle ou un bandeau : les capitales perdent
#: couramment leurs accents sans que ce soit une faute.
_SIGLE = re.compile(r"^[A-Z0-9&.\-]+$")

MOT = re.compile(r"[^\W\d_]{2,}")


def sans_accents(mot: str) -> str:
    decompose = unicodedata.normalize("NFD", mot)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def accent_final_seulement(mot: str) -> bool:
    """L'accent ne porte-t-il QUE sur la dernière lettre ?

    C'est la question qui rend tout ceci utilisable en français. « marche » et
    « marché », « entre » et « entré », « note » et « noté », « cible » et
    « ciblé » : tout verbe du premier groupe oppose son présent à son participe
    sur ce seul accent final, et les deux graphies sont justes. Un contrôle qui
    les signalerait crierait à chaque page ; une réparation qui les corrigerait
    changerait le sens des phrases.

    Un accent AILLEURS dans le mot, en revanche, n'a presque jamais de jumeau
    légitime : « precise » n'existe pas à côté de « précise », ni « donnees » à
    côté de « données », ni « etude » à côté de « étude ».
    """
    plat = sans_accents(mot)
    if len(plat) != len(mot):
        return False
    rangs = [i for i, (accentue, nu) in enumerate(zip(mot, plat, strict=True)) if accentue != nu]
    if len(rangs) != 1:
        return False
    # Le participe au masculin pluriel porte le même accent, suivi d'un « s » :
    # « commandés » / « commandes », « limités » / « limites ». Étude IA
    # `e30fce14` (31/10/2026) : 8 des 22 « fautes » signalées étaient ces
    # paires. Le féminin, lui, ne se dédouble pas : sans son accent,
    # « données » devient « donnees », qui n'est pas un mot.
    rang = rangs[0]
    return mot[rang].casefold() == "é" and mot[rang + 1:].casefold() in ("", "s")


def graphies_suspectes(textes: Iterable[str]) -> dict[str, str]:
    """Pour chaque graphie SANS accent fautive, la graphie accentuée du corpus.

    Le corpus est ce qu'on lui donne : les textes d'un chapitre quand on répare
    avant le gate, ceux du document entier quand on relit après rendu.
    """
    formes: dict[str, set[str]] = {}
    for texte in textes:
        for mot in MOT.findall(texte or ""):
            if len(mot) < LONGUEUR_JUGEABLE or _SIGLE.match(mot):
                continue
            formes.setdefault(sans_accents(mot).casefold(), set()).add(mot)

    suspectes: dict[str, str] = {}
    for variantes in formes.values():
        accentuees = sorted(
            mot for mot in variantes
            if sans_accents(mot) != mot and not accent_final_seulement(mot)
        )
        if not accentuees:
            continue
        for mot in variantes:
            if sans_accents(mot) == mot and mot.casefold() not in DEUX_GRAPHIES:
                suspectes[mot] = accentuees[0]
    return suspectes
