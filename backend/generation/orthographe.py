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

## Pourquoi ce module existe à part

Deux modules s'en servent, et la règle 5 interdit qu'ils en portent chacun leur
version :

- `chapitres.typographie` RÉPARE, chapitre par chapitre, avant le gate et sans
  rien coûter — la doctrine du dépôt est de réparer ce qui se répare ;
- `relecture.redaction` SIGNALE ce qui reste, sur le document entier, là où un
  mot juste vit dans un autre chapitre que sa faute.

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
    "entraine entrainer entrainement entrainee"
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
    return bool(rangs) and rangs == [len(mot) - 1]


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


def _accorder_la_casse(juste: str, fautif: str) -> str:
    """La graphie juste, sous la casse du mot qu'elle remplace.

    « Precise » en tête de phrase doit devenir « Précise », pas « précise » :
    une réparation ne déplace pas une majuscule.
    """
    return juste[0].upper() + juste[1:] if fautif[:1].isupper() else juste


def reparer_les_accents(texte: str, suspectes: dict[str, str]) -> str:
    """Remplace chaque graphie fautive par celle que le corpus accentue.

    Remplacement mot à mot et non par chaîne : « etude » remplacé partout
    abîmerait « etudes » et le nom d'un fichier.
    """
    if not texte or not suspectes:
        return texte

    def _remplacer(trouve: re.Match[str]) -> str:
        mot = trouve.group(0)
        juste = suspectes.get(mot)
        if juste is not None:
            return _accorder_la_casse(juste, mot)
        # Le corpus a pu voir « Precise » sans voir « precise » : on rapproche
        # alors par la casse repliée, sinon une faute en tête de phrase
        # échapperait à la réparation de la même faute en milieu de phrase.
        for fautif, correct in suspectes.items():
            if fautif.casefold() == mot.casefold():
                return _accorder_la_casse(correct, mot)
        return mot

    return MOT.sub(_remplacer, texte)
