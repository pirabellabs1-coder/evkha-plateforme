"""Un langage simple, réparé avant de juger : sigles d'analyse et gras brut.

## Le défaut

Cliente, 29/10/2026, sur deux études de marché : « c'est toujours très
technique, avec des termes très analytiques. Un porteur de projet qui demande
une étude de base ne va pas comprendre, et ce n'est pas le but. » Mesuré le
même jour : TAM, SAM et SOM reviennent 26 fois dans l'étude `6832779f` et 25
fois dans `99a142b0`, jusqu'au chapitre 22 ; et les deux études impriment en
toutes lettres « **Formule et dérivation SOM depuis le SAM** », astérisques
compris — Word n'interprète pas le Markdown.

La consigne commune (`runner._SYSTEME`) a été réécrite le même jour. Mais une
consigne ne commande pas : le jargon interdit vingt fois dans les prompts
revenait quand même. Ce que trois mots remplacent sans ambiguïté se répare
donc ici, comme la typographie (`typographie.py`) : avant le contrôle, sans
rejouer d'appel.

## Ce qui est réparé, et seulement cela (règle 2, valable pour une réparation)

1. **Le gras Markdown** (`**mot**`) : le texte reste,
   les marques partent. Aucune exception : le document est un Word.
2. **TAM, SAM, SOM** hors du chapitre qui les pose (`CHAPITRES_DES_SIGLES`) :
   « le marché total », « le marché accessible », « le chiffre d'affaires
   visé ». Les trois noms sont masculins et commencent par une consonne,
   comme les sigles se lisent (« le TAM », « du SAM ») : le déterminant reste
   juste sans retouche. Un « (TAM) » placé après son nom en clair est retiré,
   sinon on écrirait « marché total (marché total) ».

Ce qui n'est PAS réparé ici, à dessein : les anglicismes et les termes dont le
remplacement change le genre ou demande une élision (« le sourcing » →
« l'approvisionnement », « le taux de capture » → « la part visée »). Le
déterminant y change avec le mot ; un remplacement mot à mot fabriquerait une
faute de français dans un document qui en était exempt. Ils relèvent de la
consigne et de la mesure de lisibilité.

## Ce que la réparation ne fait PAS, pour ne pas fabriquer de faute (règle 2)

Relecture du 29/10/2026, sur des formes que l'ancienne consigne a installées :

- « 30 000 M€ (TAM), dont 2 400 M€ (SAM) » : la parenthèse QUALIFIE le
  montant. Elle n'est retirée que si elle suit le nom en clair (« marché
  total (TAM) ») ; sinon elle devient « (marché total) ».
- « le SAM (marché accessible) », « le marché accessible, ou SAM, » : le nom
  n'est pas écrit deux fois.
- « les SOM », « des SAM », « une SAM » (une société anonyme monégasque),
  « le SOM visé » : le remplacement mot à mot ferait une faute d'accord ou un
  « visé visé ». Le sigle reste ; la consigne et la relecture s'en chargent.

## Ce que la réparation coûte à un autre contrôle (règle 9)

Aucun. `coherence._TAM_SAM_SOM_UNIVERSAL`, qui lit les sigles dans le texte,
ne tourne que dans l'ancien moteur (`generation/runner.py`) ; les quatre
livrables passent par le moteur structuré, où les tailles de marché se
contrôlent par le socle (`tam`, `sam`, `som`) et par les chiffres hors socle.
Le libellé STOCKÉ du socle garde ses sigles ; seul l'AFFICHÉ change
(`rendu_word.texte.libelle_affiche`). Un contrôle qui compare l'affiché au
stocké doit simplifier les deux côtés (`controles._cite_un_libelle_du_socle`).
"""
from __future__ import annotations

import re
from typing import Any

from catalog.models import DeliverableType

from .typographie import _CHAMPS_IDENTIFIANTS, _borne

#: Les chapitres où le cahier des charges IMPOSE les sigles, une fois, avec
#: leur explication (CDC étude de marché, « chapitre 2 bis — TAM / SAM / SOM »,
#: règle de vulgarisation obligatoire ; `prompts/etude_marche/chapitre_02.md`).
CHAPITRES_DES_SIGLES: frozenset[tuple[str, int]] = frozenset({
    (str(DeliverableType.MARKET_STUDY), 2),
})

#: Le nom simple de chaque sigle — LA source de ces trois noms (règle 5) :
#: la consigne commune (`runner._SYSTEME`) les lit ici. Masculins et commençant
#: par une consonne, comme le sigle se lit au singulier : « le SAM » devient
#: « le marché accessible » sans toucher au déterminant.
NOMS_SIMPLES: dict[str, str] = {
    "TAM": "marché total",
    "SAM": "marché accessible",
    "SOM": "chiffre d'affaires visé",
}

#: Les façons d'écrire en clair un niveau de marché, sigle mis à part.
_EN_CLAIR = (
    r"(?:march[ée] (?:total|accessible|adressable|servi|atteignable|obtenable)"
    r"(?: th[ée]orique)?|chiffre d'affaires vis[ée])"
)

_SIGLE = re.compile(r"(?<![\w/-])(TAM|SAM|SOM)(?![\w/-])")

#: « marché total (TAM) » : le sigle entre parenthèses, JUSTE après son nom en
#: clair. Ailleurs (« 30 000 M€ (TAM) ») la parenthèse qualifie : elle reste.
_SIGLE_APRES_SON_NOM = re.compile(
    rf"({_EN_CLAIR})[ \t\u00a0\u202f]*\((?:TAM|SAM|SOM)\)", re.IGNORECASE
)

#: « le marché accessible, ou SAM, » : l'apposition qui redit le nom.
_APPOSITION = re.compile(
    rf"({_EN_CLAIR}),?[ \t\u00a0\u202f]+(?:ou|soit|c'est-à-dire|dit)[ \t\u00a0\u202f]+"
    r"(?:le[ \t\u00a0\u202f]+)?(?:TAM|SAM|SOM)\b,?",
    re.IGNORECASE,
)

#: « le SAM (marché accessible) » : le nom en clair entre parenthèses, juste
#: après le sigle — le sigle et la parenthèse ne font qu'un nom.
_SIGLE_PUIS_SON_NOM = re.compile(
    rf"(?<![\w/-])(?:TAM|SAM|SOM)[ \t\u00a0\u202f]*\(({_EN_CLAIR})\)", re.IGNORECASE
)

#: Un sigle au pluriel ou au féminin, ou suivi de « visé » : le remplacer
#: ferait une faute. Il reste tel quel.
_DETERMINANT_QUI_ACCORDE = re.compile(
    r"(?:^|[\s(])(?:les|des|une|ces|aux|deux|trois|leurs|vos|nos)[ \t\u00a0\u202f]+$",
    re.IGNORECASE,
)
_SUIVI_DE_VISE = re.compile(r"[ \t\u00a0\u202f]+vis[ée]", re.IGNORECASE)

#: Début de phrase, de cellule ou d'élément : là, le nom simple prend une
#: majuscule (« SAM — TPE prêtes à payer » → « Marché accessible — … »). Pas
#: après un deux-points : en français, la phrase continue en minuscule.
_DEBUT_DE_PHRASE = re.compile(r"(?:^|[.!?]\s+|\n\s*|\|\s*)$")

#: Gras Markdown, sur une même ligne. Les doubles astérisques SEULEMENT : le
#: double tiret bas est la forme que les deux études fautives n'emploient pas,
#: et il emportait `__init__` ou un nom de fichier (contre-épreuve du test).
_GRAS = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")


def sans_gras(texte: str) -> str:
    """Le texte sans gras Markdown. Ne fait que raccourcir : toujours applicable."""
    return _GRAS.sub(r"\1", texte) if texte else texte


def simplifier_texte(texte: str, *, sigles_admis: bool) -> str:
    """Le texte sans gras brut et, hors du chapitre qui les pose, sans sigles.

    Idempotente : la rejouer ne change rien.
    """
    simple = sans_gras(texte)
    if not simple or sigles_admis:
        return simple
    simple = _SIGLE_APRES_SON_NOM.sub(r"\1", simple)
    simple = _APPOSITION.sub(r"\1", simple)
    simple = _SIGLE_PUIS_SON_NOM.sub(lambda m: m.group(1), simple)

    def _nom(m: re.Match[str]) -> str:
        avant = simple[: m.start()]
        if _DETERMINANT_QUI_ACCORDE.search(avant) or _SUIVI_DE_VISE.match(simple, m.end()):
            return m.group(0)
        nom = NOMS_SIMPLES[m.group(1)]
        if _DEBUT_DE_PHRASE.search(avant):
            return nom[0].upper() + nom[1:]
        return nom

    return _SIGLE.sub(_nom, simple)


def simplifier_le_langage(payload: Any, *, deliverable_type: str) -> int:
    """Simplifie tous les textes d'un chapitre EN PLACE. Rend le nombre de retouches.

    Le compte part au journal, comme celui de la typographie : si la consigne
    sert, il baisse ; s'il ne baisse pas, c'est la réparation qui fait le
    travail et il faut le savoir (règle 9).
    """
    sigles_admis = (str(deliverable_type), int(getattr(payload, "chapitre", -1))) in (
        CHAPITRES_DES_SIGLES
    )
    retouches = 0
    for champ in ("titre", "accroche", "resume"):
        retouches += _simplifier_champ(payload, champ, sigles_admis)
    for bloc in getattr(payload, "blocs", ()) or ():
        retouches += _simplifier_modele(bloc, sigles_admis)
    return retouches


def _simplifier_champ(modele: Any, nom: str, sigles_admis: bool) -> int:
    texte = getattr(modele, nom, None)
    if not isinstance(texte, str):
        return 0
    simple = simplifier_texte(texte, sigles_admis=sigles_admis)
    borne = _borne(modele, nom)
    # Un nom simple est plus long que son sigle. Au-delà de la borne du champ,
    # le rendu Word refuserait le chapitre ENTIER : on garde alors les sigles,
    # mais le gras part quand même — le retirer ne fait que raccourcir (voir
    # `typographie._reparer_dans_la_borne`).
    if borne is not None and len(simple) > borne:
        simple = sans_gras(texte)
    if simple == texte:
        return 0
    setattr(modele, nom, simple)
    return 1


def _simplifier_modele(modele: Any, sigles_admis: bool) -> int:
    champs = getattr(type(modele), "model_fields", None)
    if not champs:
        return 0
    retouches = 0
    for nom in champs:
        if nom in _CHAMPS_IDENTIFIANTS:
            continue
        valeur = getattr(modele, nom, None)
        if isinstance(valeur, str):
            retouches += _simplifier_champ(modele, nom, sigles_admis)
        elif isinstance(valeur, list):
            nouvelle, compte = _simplifier_liste(valeur, sigles_admis)
            if compte:
                setattr(modele, nom, nouvelle)
                retouches += compte
        elif getattr(type(valeur), "model_fields", None):
            retouches += _simplifier_modele(valeur, sigles_admis)
    return retouches


def _simplifier_liste(valeurs: list[Any], sigles_admis: bool) -> tuple[list[Any], int]:
    """Une liste de chaînes (cellules d'une ligne) ou de modèles imbriqués.

    Pas de borne ici : sur une liste, `max_length` compte des ÉLÉMENTS."""
    retouches = 0
    sortie: list[Any] = []
    for element in valeurs:
        if isinstance(element, str):
            simple = simplifier_texte(element, sigles_admis=sigles_admis)
            retouches += int(simple != element)
            sortie.append(simple)
        elif isinstance(element, list):
            sous_liste, compte = _simplifier_liste(element, sigles_admis)
            retouches += compte
            sortie.append(sous_liste)
        else:
            retouches += _simplifier_modele(element, sigles_admis)
            sortie.append(element)
    return sortie, retouches
