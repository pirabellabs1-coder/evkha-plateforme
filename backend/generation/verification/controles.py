"""Les contrôles de la passe de vérification (lot 4).

Chaque contrôle est une fonction indépendante qui reçoit le document **lu** et
le socle, et retourne des anomalies. Aucun ne modifie quoi que ce soit.

Deux principes gouvernent l'ensemble.

**Un contrôle qui n'a rien à comparer échoue.** Il ne se tait pas. La barrière
historique de ce projet faisait `continue` quand la donnée de référence
manquait et rendait `passed: True` sur des documents incohérents.

**Un contrôle et sa réparation ne jugent pas sur la même évidence.** Les
chiffres sont relus dans le fichier livré, pas dans les charges utiles qui ont
servi à le fabriquer. Si l'assemblage perd ou déforme une valeur, seule cette
lecture-là peut le voir.

### Ce que cette passe NE regarde PAS

À écrire noir sur blanc, parce que c'est exactement là où une réparation ne
cherchera pas non plus :

- les nombres **sans unité** (« trois axes », « 0-30 j », « chapitre 12 ») ne
  sont pas contrôlés : ce ne sont pas des affirmations de marché, et les
  traiter comme telles produirait des motifs faux ;
- l'**arithmétique interne** d'un chapitre (une somme, un écart calculé entre
  deux chiffres du socle) n'est pas recalculée ;
- la **véracité des sources** n'est pas vérifiable ici : la passe compare au
  socle, pas au monde.
"""
from __future__ import annotations

import re
import statistics
from bisect import bisect_left
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from itertools import zip_longest

from core.numbers import amounts_in

from ..checks_post_rendu import REFERENCE_JURIDIQUE, _sans_accents
from ..prompts import PLAFOND_FIGURES, PLANCHER_FIGURES
from ..socle.referentiel import identifiants_obligatoires
from ..socle.schema import DONNEE_MANQUANTE, Socle, valeur_en_unites_de_base
from .lecture import DocumentLu, Mesure, mesures_dans
from .rapport import Anomalie, Gravite

#: Écart relatif toléré entre une grandeur du document et une valeur du socle.
#: Couvre l'arrondi d'affichage (« 381,5 Md€ » écrit « 382 Md€ ») sans laisser
#: passer un chiffre différent. Au-delà de 1 %, ce n'est plus le même nombre.
TOLERANCE = 0.01

#: Sous ce seuil, deux valeurs sont considérées égales quel que soit l'écart
#: relatif : à zéro, le rapport n'a plus de sens.
EPSILON = 1e-9

#: Densité attendue, mesurée sur `references/joalie_2026.docx` et validée par
#: la cliente. Un document qui redevient un mur de texte est un défaut, même si
#: chacun de ses chiffres est juste.
PART_TABLEAUX_MIN = 0.40
MEDIANE_PARAGRAPHE_MAX = 25
PART_PARAGRAPHES_LONGS_MAX = 0.25


@dataclass(frozen=True)
class SeuilsDeDensite:
    part_tableaux_min: float
    mediane_paragraphe_max: int
    part_paragraphes_longs_max: float


#: Les seuils ci-dessus viennent de l'ÉTUDE DE MARCHÉ validée par la cliente
#: (Joalie : 52 % des mots en tableaux, paragraphe médian de douze mots) — le
#: livrable sur lequel elle a refusé « un mur de texte ».
#:
#: La STRATÉGIE a une autre méthode, écrite par la cliente elle-même dans son
#: document « Stratégies business automatisées » et reprise par chacun de ses
#: prompts : « paragraphes développés qui expliquent les implications de chaque
#: décision, listes réservées aux synthèses ». Lui appliquer les seuils de
#: l'étude de marché, c'était comparer à la mauvaise référence (règle 2) :
#: 44 signalements sur les 12 stratégies du corpus (14/09/2026), et comme la
#: densité fait réécrire, des chapitres repayés pour raccourcir ce que leur
#: prompt ordonne de développer — une réécriture qui ne pouvait pas converger.
#:
#: Faute de document de stratégie validé, seul le vrai mur de texte y reste
#: signalé : un paragraphe médian au-delà de soixante mots, ou une majorité de
#: paragraphes de plus de soixante mots.
_SEUILS_PAR_LIVRABLE: dict[str, SeuilsDeDensite] = {
    "business_strategy": SeuilsDeDensite(PART_TABLEAUX_MIN, 60, 0.60),
}
_SEUILS_PAR_DEFAUT = SeuilsDeDensite(
    PART_TABLEAUX_MIN, MEDIANE_PARAGRAPHE_MAX, PART_PARAGRAPHES_LONGS_MAX,
)


def seuils_de_densite(deliverable_type: str = "") -> SeuilsDeDensite:
    return _SEUILS_PAR_LIVRABLE.get(str(deliverable_type), _SEUILS_PAR_DEFAUT)


def _valeurs_de_reference(socle: Socle) -> list[tuple[float, str]]:
    """Toutes les valeurs du socle, ramenées à une unité comparable.

    Une valeur monétaire est convertie en unités de base ; une valeur non
    monétaire (pourcentage, note, effectif) est prise telle quelle. Comparer un
    pourcentage à un montant converti n'aurait aucun sens, d'où le second
    membre du couple, qui porte la famille.
    """
    references: list[tuple[float, str]] = []
    for donnee in socle.donnees:
        conversion = valeur_en_unites_de_base(donnee.valeur, donnee.unite)
        if conversion is None:
            references.append((donnee.valeur, "brut"))
        else:
            references.append((conversion[0], "monetaire"))
            # La valeur telle qu'écrite compte aussi : le document affiche
            # « 381,5 Md€ », pas « 381 500 000 000 ».
            references.append((donnee.valeur, "brut"))

    # Les CA de la base consolidée concurrents sont du socle au même titre
    # que ses données : le chapitre 6 d'une étude concurrentielle les reprend
    # et les compare — c'est sa raison d'être. Ils étaient pourtant absents de
    # cette référence : sur `6cb0fab3` (10/08/2026), des montants parfaitement
    # sourcés dans `ca_connu` sont partis en réserve « hors socle » par
    # dizaines. Un contrôle qui compare à une référence incomplète fabrique
    # des motifs faux (règle 2), et un rapport à trente-cinq réserves noie la
    # seule qui compte.
    for acteur in socle.concurrents:
        for montant in amounts_in(acteur.ca_connu):
            references.append((montant, "monetaire"))
            references.append((montant, "brut"))
    return references


#: Longueur du début de libellé qu'une phrase doit recopier pour CITER la donnée.
_DEBUT_DE_LIBELLE = 30


def _cite_un_libelle_du_socle(mesure: Mesure, socle: Socle) -> bool:
    """Le nombre est écrit dans le libellé d'une donnée que la phrase CITE.

    « Donnée : Prix moyen d'une baguette (fourchette observée 1,30 - 1,60 €,
    médiane retenue) | 1,45 EUR » recopie la donnée du socle avec son libellé,
    bornes comprises (corpus du 14/09/2026).

    Pas en référence générale : versés dans les références, les nombres des
    libellés — « 15 % », « 4 % », « 10 ans » — justifiaient la même valeur
    PARTOUT et alimentaient les dérivations. Mesuré en production le jour
    même : 113 chiffres blanchis d'un coup, dont « 9,4 % en année 3 » et
    « 10,5 % » de marge nette. Le nombre ne vaut que dans la phrase qui cite
    son libellé.
    """
    phrase = " ".join(mesure.phrase.casefold().split())
    for donnee in socle.donnees:
        libelle = " ".join(donnee.libelle.casefold().split())
        if len(libelle) < _DEBUT_DE_LIBELLE or libelle[:_DEBUT_DE_LIBELLE] not in phrase:
            continue
        if any(_proche(mesure.valeur, nombre) for nombre in amounts_in(donnee.libelle)):
            return True
    return False


def _proche(
    mesure: float, reference: float, tolerance: float = TOLERANCE
) -> bool:
    if abs(mesure - reference) <= EPSILON:
        return True
    echelle = max(abs(mesure), abs(reference))
    return echelle > 0 and abs(mesure - reference) / echelle <= tolerance


#: Au-delà, on ne calcule plus les combinaisons deux à deux : un socle de
#: quarante données produit déjà 1 600 couples, chacun donnant quatre
#: dérivations. C'est instantané ; à quatre cents données ce ne le serait plus.
#: Le plafond protège le temps de contrôle, pas la justesse.
_MAX_DONNEES_POUR_DERIVATIONS = 80

#: Tolérance appliquée aux valeurs CALCULÉES, cent fois plus serrée que celle
#: des valeurs lues du socle.
#:
#: ## Pourquoi elle ne peut pas être la même
#:
#: `TOLERANCE` vaut 1 %, pour absorber l'arrondi d'affichage d'un chiffre
#: RECOPIÉ (« 381,5 Md€ » écrit « 382 Md€ »). Appliquée aux dérivations, elle
#: fait s'effondrer le contrôle : un socle de vingt-neuf données produit près de
#: trois mille combinaisons, et chacune couvre une bande de ±1 %. Ensemble,
#: elles couvrent presque tout l'espace des nombres plausibles.
#:
#: **Mesuré, et par un test qui existait déjà** :
#: `test_la_passe_voit_un_chiffre_invente_dans_un_vrai_fichier` glisse « 777 M€ »
#: dans un document. Avec la tolérance à 1 %, il cessait d'être détecté — une
#: dérivation valant 781 250 000 passait à 0,55 % de lui. Le garde-fou existant
#: a attrapé ma propre régression, exactement là où je prévenais du risque pour
#: trois termes : il se produisait déjà à deux.
#:
#: ## Pourquoi 0,01 % est le bon ordre de grandeur
#:
#: Un chiffre CALCULÉ n'est pas approché : il EST le résultat. Quand un chapitre
#: écrit « SOM = 1,0 Md€ × 0,05 % = 0,5 M€ », la valeur tombe juste, au bit
#: près. La marge ne sert qu'à absorber la représentation décimale, pas un
#: arrondi éditorial — celui-là appartient aux valeurs recopiées, et il a déjà
#: sa tolérance.
TOLERANCE_DERIVATION = 0.0001


def _derivations(references: Sequence[tuple[float, str]]) -> set[float]:
    """Ce qu'un chapitre peut légitimement CALCULER à partir du socle.

    ## Pourquoi cette fonction existe

    Le contrôle des chiffres hors socle était volontairement un simple
    avertissement, et sa docstring disait pourquoi : « le contrôle ne recalcule
    pas l'arithmétique interne des chapitres, si bien qu'une somme légitime de
    deux valeurs du socle apparaît ici comme hors socle ».

    C'était juste, et c'était la bonne décision tant que rien ne calculait. Mais
    cela laissait le contrôle incapable de distinguer les deux seules choses qui
    comptent :

        « SOM = 1,0 Md€ × 0,05 % = 0,5 M€ »   — un calcul, parfaitement légitime
        « 26,3 millions de chiens et chats »  — un chiffre de marché INVENTÉ

    Les deux sortaient pareil. Sur le dossier réel `c8b4e60a`, quatorze réserves
    mélangeaient les unes et les autres, et il fallait les relire à la main pour
    savoir lesquelles comptaient.

    ## Ce qu'on calcule, et pourquoi on s'arrête là

    Les combinaisons DEUX À DEUX : produit, quotient, somme, différence, et
    l'application d'un taux (a × b/100). C'est la famille qui couvre
    l'écrasante majorité des dérivations réelles d'une étude — un SOM tiré d'un
    SAM et d'un taux de capture, un total tiré de deux segments.

    On ne va pas à trois termes, et c'est délibéré : le nombre de combinaisons
    explose, et surtout la probabilité qu'un chiffre INVENTÉ tombe par hasard
    sur l'une d'elles devient réelle. Un contrôle qui justifie tout ne justifie
    plus rien — ce serait remplacer un bruit par un silence.
    """
    # DÉDOUBLONNÉES avant la coupe. Chaque montant figure deux fois dans
    # `references` (famille « monetaire » et « brut ») : les 80 premières
    # places étaient prises par des doublons du socle, et les chiffres du BRIEF,
    # rangés après, n'entraient jamais dans une dérivation (audit du
    # 14/09/2026).
    valeurs = list(dict.fromkeys(valeur for valeur, _ in references))
    if len(valeurs) > _MAX_DONNEES_POUR_DERIVATIONS:
        valeurs = valeurs[:_MAX_DONNEES_POUR_DERIVATIONS]

    calculees: set[float] = set()
    for index, gauche in enumerate(valeurs):
        for droite in valeurs[index + 1:]:
            calculees.add(gauche + droite)
            calculees.add(abs(gauche - droite))
            calculees.add(gauche * droite)
            # Un taux s'applique en pourcentage : « 1,0 Md€ × 0,05 % ».
            calculees.add(gauche * droite / 100)
            calculees.add(droite * gauche / 100)
            for a, b in ((gauche, droite), (droite, gauche)):
                if abs(b) > EPSILON:
                    calculees.add(a / b)
                    # Une part exprimée en pourcentage : « 12 sur 48 = 25 % ».
                    calculees.add(a / b * 100)
    return calculees


def _justifiee(
    mesure: Mesure,
    references: Sequence[tuple[float, str]],
    derivations: Sequence[float] = (),
) -> bool:
    famille = "monetaire" if mesure.est_monetaire else "brut"
    if any(
        _proche(mesure.valeur, valeur)
        for valeur, nature in references
        if nature == famille or famille == "brut"
    ):
        return True
    # Un chiffre CALCULÉ à partir du socle n'est pas un chiffre hors socle : il
    # est exactement ce que le chapitre a le droit de faire avec ses données.
    # Tolérance BEAUCOUP plus serrée — voir `TOLERANCE_DERIVATION` : à 1 %, les
    # trois mille combinaisons d'un socle ordinaire justifient à peu près
    # n'importe quel nombre.
    return _dans_les_derivations(mesure.valeur, derivations)


def _dans_les_derivations(valeur: float, derivations: Sequence[float]) -> bool:
    """Recherche par dichotomie : les dérivations sont TRIÉES.

    Un parcours linéaire coûtait 2,5 s sur un document de 400 grandeurs face à
    24 000 dérivations (relecture du 14/09/2026).
    """
    marge = abs(valeur) * TOLERANCE_DERIVATION + EPSILON
    index = bisect_left(derivations, valeur - marge)
    return index < len(derivations) and derivations[index] <= valeur + marge


# ── Ce que la phrase elle-même justifie ──────────────────────────────────────
#
# Corpus de production mesuré le 13/09/2026 : 883 « chiffres hors socle » sur
# 37 dossiers — 393 sur sept business plans, 409 sur onze études
# concurrentielles. Relus un par un, presque aucun n'était une invention :
#
#   « 244 296 divisé par 269 721 donne 0,906, soit 90,6 % »   un calcul POSÉ
#   « 87,5 %, calculée comme (101 772 - 54 276) / 54 276 »     idem
#   « 18,65 % du marché local (6,25 + 7,40 + 5,00) »           une somme posée
#   « 273 000 euros HT, Crisalid 2025 »                         un chiffre SOURCÉ
#
# Or c'est la consigne elle-même — « UN CALCUL SE MONTRE », dans
# `COHERENCE_DES_CHIFFRES` — qui fait écrire le calcul dans la phrase : le
# prompt l'exigeait et le contrôle le punissait, la contradiction de la règle 5.
# Et ce contrôle fait partie des défauts que le contrôleur final RÉÉCRIT : il
# faisait repayer des chapitres justes.
#
# Deux justifications nouvelles, et leurs bornes :
#
# - un CALCUL POSÉ : la grandeur résulte de deux nombres de sa phrase, à
#   l'arrondi près de son écriture. Pour un MONTANT, les opérandes doivent le
#   PRÉCÉDER — ou suivre entre parenthèses (« 172,5 M€ (150 × 1,15) ») : sans
#   cette borne, trois chiffres inventés mais cohérents entre eux se
#   justifieraient mutuellement. La base d'un calcul (« un marché de
#   1 600 M€ ») n'a rien avant elle : elle reste signalée si le socle l'ignore.
#   Un POURCENTAGE, lui, est toujours un rapport : il peut citer ses
#   opérandes après lui. Qu'il tombe JUSTE est l'affaire de `calcul_faux`.
# - un chiffre SOURCÉ dans sa phrase (« selon », « d'après », « source : »,
#   ou une parenthèse qui nomme un organisme et une année). Il n'est pas « sans
#   source » : il en cite une. Que cette source porte vraiment le chiffre ne se
#   vérifie pas ici — c'est le rôle du contrôle des sources.

_NOMBRE_NU = re.compile(r"(?<![\w,.])-?\d+(?:[^\S\r\n]\d{3})*(?:,\d+)?(?![\w])")

#: Une année écrite en clair n'est jamais un opérande : « entre 2020 et 2025, le
#: marché est passé à 5 Md€ » se justifiait par 2025 − 2020 (relecture du
#: 14/09/2026, I5).
_ANNEE_NUE = re.compile(r"^(?:19|20)\d{2}$")

#: Ce qui dit qu'un calcul est POSÉ. Sans l'un de ces signes, deux nombres voisins
#: qui tombent juste sont une coïncidence : « sur les 12 derniers mois, les 4
#: leaders ont capté 48 % » ne calcule rien.
_MARQUE_DE_CALCUL = re.compile(
    r"\bsoit\b|=|divis|multipli|×|\bx\b|/|\brapport|calcul|\bdonne\b|\bsur\s+\d",
    re.IGNORECASE,
)

#: Une source NOMMÉE : « selon l'Insee », « d'après la Fédération », « Source :
#: », ou une parenthèse qui nomme un organisme et une année. « selon le canal »
#: n'en est pas une, ni « (Scénario central 2027) » (relecture du 14/09/2026).
_SOURCE_DANS_LA_PHRASE = re.compile(
    r"\b(?i:selon|d['’]apr[èe]s)\s+(?:l['’]\s*|la\s+|le\s+|les\s+|du\s+|des\s+)?[A-ZÉÈÀ]"
    r"|\b(?i:sources?)\s*:"
    # Une adresse, ou un texte de loi cité par son article : « 77 700 € (article
    # 50-0 du code général des impôts) », la ligne du chapitre Sources qui
    # porte son URL (corpus du 14/09/2026).
    r"|https?://\S"
    # La même expression que la traçabilité du chapitre Sources (règle 5).
    rf"|{REFERENCE_JURIDIQUE}"
    r"|\((?![^()]*\b(?i:sc[ée]nario|ann[ée]e|hypoth))"
    r"[^()]*\b[A-ZÉ][\w&'’.\-]{2,}[^()]*\b(?:19|20)\d{2}\b[^()]*\)",
)

#: Écart relatif toléré entre le calcul refait et la grandeur écrite, en plus
#: de l'arrondi de son écriture : les OPÉRANDES aussi sont arrondis.
_TOLERANCE_CALCUL_POSE = 0.005


@dataclass(frozen=True)
class _Nombre:
    position: int
    valeur: float
    unite: str  # vide pour un nombre nu

    @property
    def pourcentage(self) -> bool:
        return self.unite.strip() == "%"


def _nombres_de_la_phrase(phrase: str) -> list[_Nombre]:
    """Chaque nombre de la phrase, unités ramenées à la base — années exclues."""
    trouves: list[_Nombre] = []
    couverts: list[tuple[int, int]] = []
    for grandeur in mesures_dans(phrase):
        position = phrase.find(grandeur.texte)
        if position >= 0:
            trouves.append(_Nombre(position, grandeur.valeur, grandeur.unite))
            couverts.append((position, position + len(grandeur.texte)))
    for nu in _NOMBRE_NU.finditer(phrase):
        if any(debut <= nu.start() < fin for debut, fin in couverts):
            continue
        if _ANNEE_NUE.match(nu.group(0).strip()):
            continue
        valeur = _nombre(nu.group(0))
        if valeur is not None:
            trouves.append(_Nombre(nu.start(), valeur, ""))
    return trouves


def _resultats(a: float, b: float) -> list[float]:
    # La différence SIGNÉE aussi : « Dette résiduelle | 20 400 € | -6 600 €
    # (20 400 - 27 000) », « Écart | 30 000 € | 15 000 € | -15 000 € ». Seule
    # sa valeur absolue était essayée, et un écart négatif juste passait pour
    # un chiffre inventé (corpus du 14/09/2026). Limite : le SENS n'est pas
    # jugé — « +6 600 € » au lieu de « -6 600 € » passe, comme avant.
    calcules = [a + b, abs(a - b), a - b, b - a, a * b, a * b / 100]
    if abs(b) > EPSILON:
        calcules += [a / b, a / b * 100, (a - b) / b * 100, abs(a - b) / b * 100]
    if abs(a) > EPSILON:
        calcules += [b / a, b / a * 100, (b - a) / a * 100, abs(b - a) / a * 100]
    return calcules


#: Une case qui écrit un calcul : deux nombres liés par un opérateur.
_FORMULE_DANS_LA_CASE = re.compile(
    r"\d\s*[\u2212×x*/+=-]\s*\d|\d\s+(?:moins|plus|divis[ée]\w*\s+par|fois)\s+\d",
    re.IGNORECASE,
)


def _calculee_dans_sa_phrase(
    mesure: Mesure,
    dans_le_socle: Callable[[float], bool] = lambda _valeur: False,
) -> bool:
    """La grandeur est-elle le RÉSULTAT d'un calcul écrit dans sa phrase ?

    ## Le cercle, fermé (relecture du 14/09/2026, I5)

    Trois chiffres inventés mais cohérents ne doivent pas se justifier entre
    eux. Un OPÉRANDE est donc admis s'il est :

    - un nombre NU (« 244 296 divisé par 269 721 ») ;
    - une grandeur que le socle, le brief ou une dérivation justifie déjà ;
    - pour un résultat en MONTANT, un pourcentage — un taux s'applique ;
    - pour un résultat en POURCENTAGE, un montant — un rapport de deux montants
      est un calcul, et chacun des deux est jugé pour lui-même.

    Un pourcentage non justifié n'est jamais l'opérande d'un autre pourcentage
    (« 40 % contre 25 % et 15 % ») ; un montant non justifié jamais celui d'un
    autre montant (« 900 M€ = 600 M€ + 300 M€ »).
    """
    if not mesure.phrase or mesure.debut_dans_la_phrase < 0:
        return False
    position = mesure.debut_dans_la_phrase
    fin = position + len(mesure.texte)
    nombres = [n for n in _nombres_de_la_phrase(mesure.phrase) if n.position != position]
    # En tableau, l'en-tête d'un RÉSULTAT dit le calcul à la place de la
    # phrase : « Évolution : EY France | 480 000 | 550 000 | +15 % » est une
    # variation entre deux cellules de sa ligne, que le lecteur refait (sept
    # motifs des études concurrentielles, corpus du 14/09/2026).
    calcul_marque = bool(_MARQUE_DE_CALCUL.search(mesure.phrase)) or (
        mesure.dans_un_tableau
        and bool(_EN_TETE_DE_RESULTAT.search(mesure.phrase.partition(" : ")[0]))
    )

    # La parenthèse du calcul suit le résultat, pas forcément collée :
    # « 172,5 M€ un an plus tard (150 x 1,15) ». Bornée pour ne pas aller
    # chercher une parenthèse qui parle d'autre chose.
    parenthese = re.match(r"[^()]{0,40}?\(([^()]*)\)", mesure.phrase[fin:])
    dans_la_parenthese: list[_Nombre] = []
    if parenthese:
        debut_p = fin + parenthese.start(1)
        fin_p = fin + parenthese.end(1)
        dans_la_parenthese = [n for n in nombres if debut_p <= n.position < fin_p]
    elif mesure.dans_un_tableau:
        # En tableau, la « parenthèse » est la case suivante qui POSE le calcul :
        # « Marge brute unitaire moyenne | 163,75 € | 169,5 − 5,75, soit 96,6 %
        # du prix de vente » (business plan `9f8f144a`, corpus du 14/09/2026).
        # Les opérandes suivent le résultat ; seuls ceux d'une case qui porte un
        # opérateur comptent, jamais les nombres d'une case quelconque.
        curseur = fin
        for case in mesure.phrase[fin:].split(" | ")[1:]:
            curseur = mesure.phrase.find(case, curseur)
            if _FORMULE_DANS_LA_CASE.search(case):
                dans_la_parenthese = [
                    n for n in nombres if curseur <= n.position < curseur + len(case)
                ]
                break

    def admis(n: _Nombre) -> bool:
        if not n.unite or dans_le_socle(n.valeur):
            return True
        if mesure.est_un_pourcentage:
            return not n.pourcentage
        return n.pourcentage

    if mesure.est_un_pourcentage:
        candidats = nombres
    else:
        candidats = [n for n in nombres if n.position < position] + dans_la_parenthese
    operandes = [n for n in candidats if admis(n)]

    # Les décimales du NOMBRE écrit (« 90,6 % » → 1), lues par `_decimales`,
    # la même fonction que le contrôle des calculs annoncés (règle 5). Une
    # première version redéfinissait `_decimales` sous le même nom : la
    # définition du bas l'emportait, et « 90,6 % » comptait trois décimales.
    nombre_ecrit = re.match(r"-?[\d\s]+(?:,\d+)?", mesure.texte.strip())
    demi_unite = 0.5 * 10 ** -_decimales(nombre_ecrit.group(0) if nombre_ecrit else "")
    # Un MONTANT a lui aussi l'arrondi que le rédacteur a choisi, à son échelle :
    # « SAM (1 824 M€) × 0,03 % ≈ 0,55 M€ » tombe à 547 200 €, et « 0,55 M€ »
    # vaut à 5 000 € près. La tolérance fixe de 0,5 % le refusait pour 0,51 %
    # (étude de marché `ef567688`, corpus du 14/09/2026) — deux lectures de
    # l'arrondi, une pour les taux, une pour les montants (règle 5).
    valeur_ecrite = _nombre(nombre_ecrit.group(0)) if nombre_ecrit else None
    if mesure.est_un_pourcentage:
        ecart_ecrit = demi_unite
    elif valeur_ecrite:
        # Plafonnée à 2 % : un nombre écrit sans décimale (« 3 M€ ») laisserait
        # sinon ±500 000 €, et « 2 600 000 habitants, 12 % » tomberait juste
        # par addition (relecture du 14/09/2026).
        ecart_ecrit = min(
            demi_unite * abs(mesure.valeur / valeur_ecrite), abs(mesure.valeur) * 0.02,
        )
    else:
        ecart_ecrit = 0.0
    # L'ÉCHELLE écrite du résultat : dans « 172,5 M€ (150 x 1,15) », 150 veut
    # dire 150 millions. Comparaison au nombre ÉCRIT réservée à deux nombres
    # NUS dans un calcul marqué : sinon « 3 villes, 4 agences, 12 M€ » tombait
    # juste par hasard.
    ecrit = _nombre(re.sub(r"[^\d,\s-].*$", "", mesure.texte).strip())

    def tombe_juste(calcul: float, a: _Nombre, b: _Nombre) -> bool:
        if abs(calcul - mesure.valeur) <= ecart_ecrit + EPSILON:
            return True
        if _proche(calcul, mesure.valeur, _TOLERANCE_CALCUL_POSE):
            return True
        return (
            not mesure.est_un_pourcentage
            and ecrit is not None
            and not a.unite and not b.unite
            and (calcul_marque or bool(dans_la_parenthese))
            and _proche(calcul, ecrit, _TOLERANCE_CALCUL_POSE)
        )

    for index, a in enumerate(operandes):
        for b in operandes[index + 1:]:
            # Un calcul POSÉ : un opérande porte une unité, ou la phrase dit le
            # calcul, ou il est entre parenthèses.
            pose = (
                bool(a.unite or b.unite) or calcul_marque
                or (a in dans_la_parenthese and b in dans_la_parenthese)
            )
            if not pose:
                continue
            if any(tombe_juste(c, a, b) for c in _resultats(a.valeur, b.valeur)):
                return True
    # Une somme posée entre parenthèses : « 18,65 % (6,25 + 7,40 + 5,00) ».
    termes = [n for n in dans_la_parenthese if admis(n)]
    if parenthese and "+" in parenthese.group(1) and len(termes) >= 2:
        total = sum(n.valeur for n in termes)
        return (
            abs(total - mesure.valeur) <= ecart_ecrit + EPSILON
            or _proche(total, mesure.valeur, _TOLERANCE_CALCUL_POSE)
        )
    return False


def _posee_plus_loin_dans_sa_phrase(
    mesure: Mesure, dans_le_socle: Callable[[float], bool],
) -> bool:
    """La MÊME valeur, écrite plus loin dans la phrase comme résultat d'un calcul.

    « Scénario dégradé : CA année 1 | 54 276 € | 37 993 € | 54 276 € moins 30 %,
    soit 54 276 € × 0,70 = 37 993 € » : la cellule est jugée à sa première
    occurrence, où ses opérandes ne la précèdent pas encore ; le calcul qui la
    pose est dans la colonne suivante (business plan `9f8f144a`, corpus du
    14/09/2026). Chaque autre occurrence du même texte est éprouvée à son tour.
    """
    if not mesure.phrase:
        return False
    for autre in re.finditer(r"(?<![\d,.])" + re.escape(mesure.texte), mesure.phrase):
        if autre.start() <= mesure.debut_dans_la_phrase:
            continue
        ailleurs = replace(mesure, debut_dans_la_phrase=autre.start())
        if _calculee_dans_sa_phrase(ailleurs, dans_le_socle):
            return True
    return False


def _sourcee_dans_sa_phrase(mesure: Mesure) -> bool:
    return bool(mesure.phrase) and bool(_SOURCE_DANS_LA_PHRASE.search(mesure.phrase))


# ── Une estimation DÉCLARÉE n'est pas un chiffre avancé comme un fait ────────
#
# Re-mesure du corpus après la reconnaissance du calcul posé (14/09/2026) : 756
# « chiffres hors socle » restaient. Relus : « de l'ordre de 220 € par habitant —
# hypothèse construite à partir de… », « une part de marché estimée à 5,1 % »,
# « un objectif de 120 000 € ». La règle 1 de `SOURCES_ET_TRACABILITE` le
# demande : « sans adresse disponible, présente la valeur comme une
# estimation ». Le contrôle punissait l'obéissance à cette règle.
#
# Mais le mot seul ne suffit pas — la relecture l'a montré sur des phrases
# réalistes : « le potentiel national est estimé à 900 M€ », « le CA estimé de
# Boulangerie Dupont est de 850 000 € ». C'est l'invention que ce contrôle doit
# attraper, et « estimé » ne la justifie pas. D'où trois bornes :
#
# - un MONTANT estimé doit montrer sa BASE (« à partir de », « sur la base
#   de », un autre nombre dans la phrase) — et jamais s'il s'agit d'un marché ;
# - un montant DÉCIDÉ l'est juste avant le chiffre (« objectif de 120 000 € »,
#   « budget de 9 500 € ») — pas un « retenu » perdu ailleurs dans la phrase ;
# - un POURCENTAGE estimé est admis (une part se déduit), SAUF une croissance,
#   un TCAC ou une pénétration, qui sont des faits de marché.

#: Le MILIEU d'une fourchette et une PROJECTION sont des estimations qui disent
#: leur méthode : « CA de référence (2024, milieu de fourchette) », « CA projeté
#: 2026 » (études concurrentielles du corpus du 14/09/2026). « Médian » seul
#: n'en est pas une — « la médiane nationale de 4,25 € » est un fait à sourcer.
_ESTIMATION = re.compile(
    r"\b(?:estim[ée]e?s?|estimation|hypoth[èe]ses?|de\s+l['’]ordre\s+de|"
    r"milieu\s+de\s+(?:la\s+)?fourchette|projet[ée]e?s?|projections?)\b",
    re.IGNORECASE,
)
#: Le mot de décision, au plus trois mots, puis un CONNECTEUR juste avant le
#: chiffre : « objectif de 120 000 € », « budget : 9 500 € », « objectif de
#: chiffre d'affaires de 250 000 € ». Sans connecteur, « la clientèle cible
#: dépense en moyenne 85 € » passait : « cible » y est un nom.
_DECISION_JUSTE_AVANT = re.compile(
    r"\b(?:objectif|cible|vis[ée]e?s?|retenue?s?|pr[ée]vue?s?|"
    r"pr[ée]visionnel(?:le)?s?|budget)\b"
    r"(?:\s+[\w'’]+){0,3}?\s*(?:de|d['’]|[àa]|:|=)\s*$",
    re.IGNORECASE,
)
_BASE_MONTREE = re.compile(
    r"[àa]\s+partir\s+d|sur\s+la\s+base\s+d|en\s+retenant|calcul|construit|"
    r"fond[ée]e?\s+sur|appliqu",
    re.IGNORECASE,
)
_TAILLE_DE_MARCHE = re.compile(
    r"\b(?:march[ée]s?|secteur|fili[èe]re|TAM|SAM|SOM|population|consommation|"
    r"d[ée]penses?\s+des\s+m[ée]nages|potentiel|demande\s+totale)\b",
    re.IGNORECASE,
)
_FAIT_DE_CROISSANCE = re.compile(
    r"croissance|TCAC|CAGR|p[ée]n[ée]tration|progression\s+annuelle",
    re.IGNORECASE,
)


def cellule_jugee(mesure: Mesure) -> str:
    """La cellule qui porte la grandeur, trouvée par sa POSITION.

    Pas par son texte : « 0 % » est aussi dans « 40 % », « 0 € » dans
    « 1 500 € », et la première cellule qui le contenait était prise pour
    celle du zéro (relecture du 14/09/2026). Vide hors tableau.
    """
    phrase = mesure.phrase
    if not mesure.dans_un_tableau or " : " not in phrase:
        return ""
    en_tete, _, ligne = phrase.partition(" : ")
    curseur = len(en_tete) + 3
    for morceau in ligne.split(" | "):
        if curseur <= mesure.debut_dans_la_phrase < curseur + len(morceau):
            return morceau
        curseur += len(morceau) + 3
    return ""


def _portee_du_jugement(mesure: Mesure) -> str:
    """Ce qui QUALIFIE la grandeur : la phrase en prose ; en tableau, l'en-tête
    de sa colonne et le libellé de sa ligne.

    Corpus du 14/09/2026 : « CA médian 2026 (estimé) : France d'Or | 7,3 M€ |
    8,5 M€ | Croissance proche du marché » — la garde « taille de marché »
    lisait le commentaire de la dernière colonne et annulait l'estimation que
    l'en-tête déclarait. Une autre cellule ne qualifie pas celle-ci.
    """
    phrase = mesure.phrase
    if not mesure.dans_un_tableau or " : " not in phrase:
        return phrase
    en_tete, _, ligne = phrase.partition(" : ")
    # La cellule JUGÉE compte aussi : elle est souvent une phrase entière
    # (« le marché est estimé à 150 M€ … 0,46 % de ce total »). Seules les
    # AUTRES cellules sont écartées.
    cellule = cellule_jugee(mesure)
    libelle = ligne.split(" | ")[0]
    return f"{en_tete} : {libelle}" + (f" | {cellule}" if cellule and cellule != libelle else "")


#: L'en-tête d'une colonne de DÉCISIONS : « Seuil STOP », « Seuil ADJUST »,
#: « Objectif », « Indicateur de réussite ». La valeur y est fixée par le
#: projet ; la juger comme un fait de marché accusait les tableaux GO /
#: AJUSTER / STOP que le manuel impose (stratégies du corpus du 14/09/2026).
#: Un seuil nommé comme tel : « seuil d'alerte », « seuil de déclenchement ».
#: « Seuil » seul non : « Seuil de rentabilité | 18 667 € » est un CALCUL du
#: prévisionnel, que ce contrôle doit continuer de juger.
_SEUIL_D_ALERTE = (
    r"seuils?\s+(?:d['’]alerte|de\s+d[ée]clenchement|de\s+d[ée]cision|de\s+vigilance)"
)

_EN_TETE_DE_DECISION = re.compile(
    rf"(?i)^\s*(?:seuils?\s+(?:go|stop|adjust|ajust\w*)|{_SEUIL_D_ALERTE}|objectifs?|cibles?|"
    r"crit[èe]res?|indicateurs?\s+de\s+r[ée]ussite|niveau\s+vis[ée]|valeur\s+cible|budget)\b"
)

#: Le franchissement d'un SEUIL, collé à la valeur : « sous 6 % », « passe
#: au-dessus de 550 € ». Pas « plus de » ni « moins de » : « plus de 80 % du
#: marché » est un fait, pas une règle.
_OPERATEUR_DE_SEUIL = re.compile(
    r"(?i)(?:\bsous|\bau[-\s]dessous\s+d[eu]|\ben\s+dessous\s+d[eu]"
    r"|\bau[-\s]dessus\s+d[eu]|\bau[-\s]del[àa]\s+d[eu])"
    r"(?:\s+(?:les?|la|l['’]|un|une))?\s*$"
)

#: L'ACTION qu'un seuil déclenche, à l'infinitif — la forme d'une règle. Le
#: verbe conjugué (« ce qui déclenche une guerre des prix ») raconte un fait.
_ACTION_DE_PILOTAGE = (
    r"(?:revoir|r[ée]viser|suspendre|stopper|arr[êe]ter|ralentir|acc[ée]l[ée]rer|"
    r"r[ée]agir|d[ée]clencher)"
)
_ALERTE = re.compile(rf"(?i)\balertes?\b|\b{_SEUIL_D_ALERTE}")
_ACTION = re.compile(rf"(?i)\b{_ACTION_DE_PILOTAGE}\b")
_CONDITION = re.compile(r"(?i)\bsi\b|\bd[èe]s\s+que?\b|\btant\s+que?\b|\blorsqu|\bquand\b")
_CASE_D_ACTION = re.compile(rf"(?i)^\W*{_ACTION_DE_PILOTAGE}\b")


def _seuil_de_declenchement(mesure: Mesure, portee: str) -> bool:
    """La valeur est le SEUIL d'une règle de pilotage, fixé par le document.

    Corpus du 15/09/2026, études de marché :

    - « Ralentir si… : Marché adressable | La part de 8 % du marché national se
      maintient ou progresse | Elle recule sous 6 % du marché national »
      (`2cef0cbd`) ;
    - « Situation : Panier moyen sous 1 000 € par adhérent trois mois de suite |
      Revoir le mix abonnement/prestations avant tout nouvel investissement »
      (`f0064333`).

    6 % et 1 000 € disent QUAND agir, comme l'en-tête « Seuil STOP » d'un
    tableau de décision. Appelée APRÈS les gardes des tailles de marché et des
    croissances : un seuil ne fait pas d'un fait de marché une décision.

    Bornes, après relecture (15/09/2026) — un « si » seul admettait « si l'on
    en croit Xerfi, le marché est passé sous 25 Md€ » :

    - un franchissement collé à la valeur ;
    - en prose : « alerte » / « seuil d'alerte », ou une condition ET une action
      à l'infinitif (« si … sous 1 000 €, revoir le mix ») ;
    - en tableau : la même chose dans la PORTÉE de la case (en-tête, libellé,
      case — « Ralentir si… »), ou une AUTRE case qui commence par l'action,
      la colonne des réponses (« | Revoir le mix… »). Une case voisine qui ne
      fait que mentionner une alerte ne qualifie pas celle-ci.
    """
    if not mesure.phrase or mesure.debut_dans_la_phrase < 0:
        return False
    if not _OPERATEUR_DE_SEUIL.search(mesure.phrase[: mesure.debut_dans_la_phrase]):
        return False
    if _ALERTE.search(portee):
        return True
    if not mesure.dans_un_tableau:
        return bool(_CONDITION.search(portee) and _ACTION.search(portee))
    if _ACTION.search(portee):
        return True
    ligne = mesure.phrase.partition(" : ")[2]
    return any(_CASE_D_ACTION.match(case) for case in ligne.split(" | "))

#: Le vocabulaire d'un scénario de SENSIBILITÉ. Un pourcentage qui y figure est
#: le choc que l'on applique, choisi pour éprouver le plan.
_PARAMETRE_DE_SCENARIO = re.compile(
    # « Scénario : Prudent (-10 % de fréquentation) » : l'en-tête et la ligne
    # sont séparés par la ponctuation de la lecture en tableau.
    r"(?i)\bsc[ée]nario\W{1,4}(?:d[ée]grad[ée]|pessimiste|optimiste|favorable|prudent|"
    r"de\s+stress|bas|haut)|\bchoc\b|\bstress\b|\bsensibilit[ée]\b"
)


#: Distance maximale entre le mot du scénario et le choc qu'il annonce.
_PORTEE_DU_SCENARIO = 80


def _choc_de_scenario(avant: str) -> bool:
    """Le pourcentage est-il le CHOC qu'annonce un scénario juste avant lui ?

    Le premier pourcentage après « scénario dégradé », « choc », « stress » —
    pas n'importe lequel de la phrase. Mesuré en production (055519e) : « le
    scénario prudent (-10 % de fréquentation) laisse une marge de sécurité
    réduite à 8,7 % » passait en entier, alors que 8,7 % est un RÉSULTAT du
    scénario, que ce contrôle doit juger.
    """
    fenetre = avant[-_PORTEE_DU_SCENARIO:]
    termes = list(_PARAMETRE_DE_SCENARIO.finditer(fenetre))
    return bool(termes) and "%" not in fenetre[termes[-1].end():]


#: Écart toléré sur une répartition : trois parts arrondies à l'unité peuvent
#: faire 99 ou 101 %.
_REPARTITION_TOLERANCE = 1.0

#: Ce qui, entre deux pourcentages, en fait des BORNES ou une opposition.
_ENTRE_DEUX_BORNES = re.compile(r"(?i)\b(?:entre|contre|jusqu|[àa]u?|versus|vs)\b")


#: Ce qui annonce le COMPLÉMENT d'une part : « le reste », « l'espace restant ».
_COMPLEMENT = re.compile(r"(?i)\b(?:reste|restant\w*|solde|compl[ée]ment\w*|surplus)\b")


def _complement_a_cent(mesure: Mesure) -> bool:
    """Le pourcentage est le complément à 100 % d'une part écrite juste avant.

    « le canal en ligne (15 %, Les Échos Études). Le reste, soit 85 % de la
    dépense », « les onze parts atteignent environ 40,8 % du marché : l'espace
    restant, environ 59,2 % » (corpus du 14/09/2026). Le lecteur fait la
    soustraction ; 85 % n'avance rien que 15 % n'ait déjà dit — et si 15 % est
    faux, c'est lui que le contrôle signale.

    Le mot du complément doit précéder la valeur de près, et la part doit
    tomber juste à l'arrondi des deux écritures.
    """
    if not mesure.est_un_pourcentage or not mesure.contexte:
        return False
    position = mesure.contexte.rfind(mesure.texte)
    if position < 0:
        return False
    avant = mesure.contexte[:position]
    if not _COMPLEMENT.search(avant[-40:]):
        return False
    demi = 0.5 * 10 ** -_decimales(mesure.texte.replace("%", ""))
    for n in _nombres_de_la_phrase(avant):
        if not n.pourcentage:
            continue
        if abs(100 - n.valeur - mesure.valeur) <= demi + 0.05:
            return True
    return False


def _part_d_une_repartition(mesure: Mesure) -> bool:
    """Le pourcentage est une part d'une répartition COMPLÈTE posée dans sa phrase.

    « La structure d'offre proposée (45 % pain, 30 % viennoiserie, 25 %
    snacking) », « résidents 50 %, actifs de bureaux 35 %, restaurants 15 % » :
    trois parts qui font 100 %, que le lecteur additionne d'un coup d'œil. C'est
    le mix que le projet se donne, pas un fait avancé (business plan
    `b8da2640`, corpus du 14/09/2026).

    Au moins trois parts, dans la même parenthèse ou la même énumération, qui
    tombent sur 100 % : deux pourcentages quelconques n'y arrivent pas par
    hasard, et une énumération qui fait 90 % reste accusée.
    """
    if not mesure.est_un_pourcentage or not mesure.phrase:
        return False
    for bloc in re.split(r"[.;:()\n|]", mesure.phrase):
        parts = sorted(
            (n for n in _nombres_de_la_phrase(bloc) if n.pourcentage), key=lambda n: n.position,
        )
        if len(parts) < 3 or not any(abs(n.valeur - mesure.valeur) < EPSILON for n in parts):
            continue
        # Une ÉNUMÉRATION, pas des bornes : « entre 32 % et 43 % sur la période,
        # contre 8 % à 17 % » fait 100 par hasard (étude concurrentielle
        # `3a4df56c`, mesure de e6f9fa5). Chaque part est séparée de la
        # suivante par une virgule — un « et » n'est admis que pour la dernière.
        ecarts = [bloc[a.position:b.position] for a, b in zip(parts, parts[1:], strict=False)]
        enumeree = all(
            ("," in ecart or (rang == len(ecarts) - 1 and re.search(r"\bet\b", ecart)))
            and not _ENTRE_DEUX_BORNES.search(ecart)
            for rang, ecart in enumerate(ecarts)
        )
        if enumeree and abs(sum(n.valeur for n in parts) - 100) <= _REPARTITION_TOLERANCE:
            return True
    return False


def _estimation_declaree(mesure: Mesure) -> bool:
    """Une valeur présentée comme estimation fondée, ou comme décision du projet."""
    phrase = mesure.phrase
    if not phrase or mesure.debut_dans_la_phrase < 0:
        return False
    avant = phrase[: mesure.debut_dans_la_phrase]
    portee = _portee_du_jugement(mesure)

    decidee_par_l_en_tete = mesure.dans_un_tableau and bool(
        _EN_TETE_DE_DECISION.search(phrase.partition(" : ")[0])
    )

    if mesure.est_un_pourcentage:
        # Un choc de SCÉNARIO est un paramètre choisi, pas un fait avancé :
        # « Scénario dégradé (-30 %) », « absorbe un choc jusqu'à -66 % ».
        if _choc_de_scenario(avant):
            return True
        if _FAIT_DE_CROISSANCE.search(portee):
            return False
        if _seuil_de_declenchement(mesure, portee):
            return True
        return bool(
            _ESTIMATION.search(portee) or _DECISION_JUSTE_AVANT.search(avant)
            or decidee_par_l_en_tete
        )

    if _TAILLE_DE_MARCHE.search(portee):
        return False
    if _seuil_de_declenchement(mesure, portee):
        return True
    if _DECISION_JUSTE_AVANT.search(avant) or decidee_par_l_en_tete:
        return True
    if not _ESTIMATION.search(portee):
        return False
    autres = [
        n for n in _nombres_de_la_phrase(phrase)
        if n.position != mesure.debut_dans_la_phrase
    ]
    return bool(_BASE_MONTREE.search(phrase) or autres)


def _part_calculee_dans_sa_ligne(
    mesure: Mesure, references: Sequence[tuple[float, str]],
) -> bool:
    """Un pourcentage de tableau qui vaut un nombre de SA LIGNE rapporté à une référence.

    « Intégrateur IA | 200 000 | 0,024 % » sous « Part du marché national » :
    200 000 / 850 M€ du socle. « Emprunt bancaire | 120 000 € | 67 % » sous
    « Part du total » : 120 000 / 180 000 € du brief. Le calcul est juste, et le
    lecteur le refait ; il était compté comme un chiffre inventé (corpus du
    14/09/2026). La concordance doit tomber juste à l'arrondi de l'écriture :
    un pourcentage quelconque ne coïncide pas par hasard avec un rapport exact.
    """
    if not (mesure.dans_un_tableau and mesure.est_un_pourcentage and mesure.phrase):
        return False
    ecrit = mesure.valeur
    en_tete = mesure.phrase.partition(" : ")[0]
    if ecrit <= 0 or not _EN_TETE_DE_PART.search(en_tete):
        return False
    tolerance = _tolerance_d_une_part(mesure)
    ligne = mesure.phrase.partition(" : ")[2] or mesure.phrase
    numerateurs = [
        n for n in _nombres_de_la_phrase(ligne) if not n.pourcentage and n.valeur > 0
    ]
    # Des euros se rapportent à des euros ; un nombre nu (effectif, volume) à
    # une référence brute. Sans cette garde, cent références du socle offraient
    # à un pourcentage quelconque trop d'occasions de tomber juste.
    # La ligne du TOTAL vaut 100 % d'elle-même — « Investissement total |
    # 180 000 € | 100,0 % ». Elle seule : « Apport | 45 000 € | 100,0 % » reste
    # faux même si 45 000 € figure au brief.
    total = bool(_LIGNE_DE_TOTAL.search(ligne.split(" | ")[0]))
    return any(
        abs(numerateur.valeur / reference * 100 - ecrit) <= tolerance
        for numerateur in numerateurs
        for reference, famille in references
        if (numerateur.valeur < reference or (total and numerateur.valeur == reference))
        and famille == ("monetaire" if numerateur.unite else "brut")
    )


_LIGNE_DE_TOTAL = re.compile(r"\b(?:total|totaux|ensemble|cumul\w*)\b", re.IGNORECASE)


#: L'en-tête d'une colonne de PARTS : ce qu'elle rapporte, dit en clair.
_EN_TETE_DE_PART = re.compile(
    r"\b(?:part|parts|poids|r[ée]partition|rapport)\b|%\s*d[ue]s?\b|en\s*%\s*d",
    re.IGNORECASE,
)


#: Chiffres significatifs minimaux pour qu'une valeur reprise soit reconnue :
#: « 0,1 % » ou « 4 M€ » se croisent par hasard, « 0,029 % » ou « 250 000 € » non.
_CHIFFRES_SIGNIFICATIFS_MIN = 2


def _chiffres_significatifs(texte: str) -> int:
    chiffres = re.sub(r"\D", "", texte.split("%")[0]).lstrip("0")
    return len(chiffres.rstrip("0")) if "," not in texte and "." not in texte else len(chiffres)


def _estimations_etablies_en_tableau(
    document: DocumentLu, references: Sequence[tuple[float, str]],
) -> list[Etablie]:
    """Les valeurs qu'un TABLEAU établit avec leur méthode, et les mots de leur ligne.

    Le chapitre 6 d'une étude concurrentielle estime le chiffre d'affaires et
    la part de chaque acteur sous un en-tête qui le dit ; les chapitres suivants
    les REPRENNENT en prose — « le cabinet de Nantes (250 000 euros, 0,029 %) ».

    Deux bornes, apprises en production le jour même (8f8e2ed : 84 chiffres
    blanchis, dont « 9,4 % en année 3 » et « 3 300 000 € ») :

    - la méthode doit être DITE par l'en-tête (« estimé », « hypothèse ») ou
      refaite dans la ligne — pas une décision, pas un choc de scénario, qui
      ne valent que là où ils sont écrits ;
    - la reprise doit nommer l'ACTEUR de la ligne : une même valeur ailleurs,
      à propos d'autre chose, reste jugée pour elle-même.

    Une VARIATION que la ligne permet de refaire est établie aussi — voir
    `_variation_refaite_dans_sa_ligne`. Elle porte les années de son en-tête,
    que la reprise doit respecter.
    """
    etablies: list[Etablie] = []
    for mesure in document.mesures:
        if not mesure.dans_un_tableau or " : " not in mesure.phrase:
            continue
        if _chiffres_significatifs(mesure.texte) < _CHIFFRES_SIGNIFICATIFS_MIN:
            continue
        en_tete, _, ligne = mesure.phrase.partition(" : ")
        mots = frozenset(
            mot for mot in re.findall(r"[^\W\d_]{5,}", ligne.split(" | ")[0].casefold())
        )
        if _ESTIMATION.search(en_tete) or _part_calculee_dans_sa_ligne(mesure, references):
            if mots:
                etablies.append(Etablie(mesure.valeur, mesure.est_monetaire, mots))
            continue
        variation = _variation_refaite_dans_sa_ligne(mesure)
        # L'ACTEUR, pas le vocabulaire commun à toutes les lignes : « Marché
        # total », « Moyenne des acteurs » ne nomment personne (relecture du
        # 15/09/2026).
        acteur = frozenset(m for m in mots if _sans_accents(m) not in _MOTS_QUI_NE_NOMMENT_PERSONNE)
        if variation is not None and acteur:
            annees = frozenset(int(a) for a in _ANNEE_NOMMEE.findall(en_tete))
            annuelle = bool(_EN_TETE_ANNUEL.search(en_tete))
            etablies.append(Etablie(variation, False, acteur, annees, annuelle))
    return etablies


#: Un en-tête qui dit un RYTHME annuel : « Croissance annuelle », « TCAC ».
_EN_TETE_ANNUEL = re.compile(r"(?i)\bpar\s+an\b|\bannuel|/\s*an\b|\bTCAC\b|\bCAGR\b")


@dataclass(frozen=True)
class Etablie:
    """Une valeur qu'un tableau établit, les mots de son acteur, ses années."""

    valeur: float
    monetaire: bool
    mots: frozenset[str]
    annees: frozenset[int] = frozenset()
    annuelle: bool = False
    """L'en-tête dit un rythme annuel (« annuel », « par an », TCAC)."""


#: Les mots d'un libellé de ligne qui ne désignent aucun acteur.
_MOTS_QUI_NE_NOMMENT_PERSONNE = frozenset({
    "marche", "marches", "total", "totale", "totaux", "moyenne", "moyennes", "ensemble",
    "acteur", "acteurs", "secteur", "panel", "segment", "segments", "autres", "global",
    "globale", "national", "nationale", "regional", "regionale", "concurrent",
    "concurrents", "mediane", "reste", "cumul", "cumule", "cumules",
})


def _valeur_signee(mesure: Mesure) -> float:
    """La valeur avec le signe écrit juste devant : « −3,2 % », « -3,2 % »."""
    avant = mesure.phrase[: mesure.debut_dans_la_phrase] if mesure.debut_dans_la_phrase > 0 else ""
    if mesure.valeur > 0 and avant.endswith(("-", "−")):
        return -mesure.valeur
    return mesure.valeur


def _variation_refaite_dans_sa_ligne(mesure: Mesure) -> float | None:
    """La variation SIGNÉE d'une case, si deux montants de sa ligne la refont.

    « Évolution 2024-2026 : Zooplus | 5,0 M€ | 5,33 M€ | +6,6 % » : 5,0 → 5,33
    fait +6,6 %. La prose la reprend — « les généralistes (Amazon +7,0 %,
    Zooplus +6,6 %) croissent plus vite que le marché » (étude `1caf5b8a`,
    corpus du 15/09/2026) — et la comptait comme inventée.

    Le calcul général de la phrase (`_calculee_dans_sa_phrase`) essaie toutes
    les opérations sur toutes les paires ; il suffit à juger la case, pas à
    établir une valeur que la prose de tout le document pourra reprendre :
    « 12 | 15 | 27 % » y tombait juste par addition (relecture du 15/09/2026).
    Ici, une seule opération : (arrivée − départ) / départ, avec son SIGNE,
    entre deux montants en euros qui précèdent la case, dans l'ordre.
    """
    if not (mesure.dans_un_tableau and mesure.est_un_pourcentage) or " : " not in mesure.phrase:
        return None
    en_tete, _, ligne = mesure.phrase.partition(" : ")
    if not _EN_TETE_DE_RESULTAT.search(en_tete) or mesure.debut_dans_la_phrase < 0:
        return None
    ecrite = _valeur_signee(mesure)
    decalage = len(en_tete) + 3
    montants = [
        n.valeur for n in _nombres_de_la_phrase(ligne)
        if n.position + decalage < mesure.debut_dans_la_phrase
        and _UNITE_EURO.fullmatch(n.unite.strip()) and n.valeur > 0
    ]
    tolerance = _tolerance_d_une_part(mesure)
    for rang, depart in enumerate(montants):
        for arrivee in montants[rang + 1:]:
            if abs((arrivee - depart) / depart * 100 - ecrite) <= tolerance:
                return ecrite
    return None


def _reprend_une_estimation_etablie(mesure: Mesure, etablies: Sequence[Etablie]) -> bool:
    """La prose reprend à l'identique une estimation établie, EN NOMMANT son acteur.

    Une valeur établie pour des ANNÉES ne se reprend pas pour d'autres : une
    évolution 2024-2026 n'est ni une croissance « d'ici 2030 », ni un rythme
    « par an » (relecture du 15/09/2026).
    """
    if mesure.dans_un_tableau or not mesure.phrase:
        return False
    if _chiffres_significatifs(mesure.texte) < _CHIFFRES_SIGNIFICATIFS_MIN:
        return False
    mots_de_la_phrase = set(re.findall(r"[^\W\d_]{5,}", mesure.phrase.casefold()))
    annees_de_la_phrase = {int(a) for a in _ANNEE_NOMMEE.findall(mesure.phrase)}
    annuelle = bool(re.search(r"(?i)\bpar\s+an\b|\bannuel", mesure.phrase))

    def meme_periode(etablie: Etablie) -> bool:
        if not etablie.annees:
            # Sans années, la période n'est dite que par un en-tête ANNUEL : une
            # « Évolution » sans période ne se reprend pas « par an » —
            # « maintiennent une croissance de 56 % par an » (`9249e523`,
            # mesure du 15/09/2026).
            return not annuelle or etablie.annuelle
        return annees_de_la_phrase <= etablie.annees and not (
            annuelle and len(etablie.annees) > 1
        )

    return any(
        etablie.monetaire == mesure.est_monetaire
        and abs(etablie.valeur - _valeur_signee(mesure)) <= EPSILON + abs(etablie.valeur) * 1e-3
        and bool(etablie.mots & mots_de_la_phrase)
        and meme_periode(etablie)
        for etablie in etablies
    )


# ── Contrôle 1 : aucune valeur hors socle ────────────────────────────────────


#: Ce qui introduit la grandeur à laquelle une part se rapporte : « 36,3 % DU
#: chiffre d'affaires », « 23 % DE LA dépense », « 68,4 % DE L'excédent ».
_RAPPORTEE_A = re.compile(r"\s*(?:du|de\s+la|de\s+l['’]|des|d['’])\s*", re.IGNORECASE)

#: Ce qui FERME le nom de la grandeur : une case, une ponctuation, un tiret.
#: « 36 % des clients fidélisés, le chiffre d'affaires couvre… » ne nomme que
#: les clients (relecture du 15/09/2026).
_FIN_DU_NOM = re.compile(r"\s\|\s|[.;:,()]|\s[—–]\s")

#: Le nom tient dans ses premiers mots : au-delà, on lit la suite de la phrase.
_MOTS_DU_NOM = 4

#: Les mots d'un libellé qui DATENT la grandeur sans la nommer.
_MOTS_QUI_DATENT = frozenset({
    "exercice", "exercices", "annee", "annees", "annuel", "annuels", "annuelle", "annuelles",
})

#: Le repère d'exercice écrit après le nom : « de l'année 1 », « exercice 2 ».
_EXERCICE_NOMME = re.compile(r"\b(?:ann[ée]e|exercice|an)\s*(\d{1,2})\b", re.IGNORECASE)
_ANNEE_NOMMEE = re.compile(r"\b((?:19|20)\d{2})\b")

#: Les unités qui disent l'euro, et elles seules.
_UNITE_EURO = re.compile(r"(?:Mds€|Md€|M€|k€|kEUR|€|euros?|EUR)", re.IGNORECASE)


def _racines(mots: Iterable[str]) -> set[str]:
    """Les mots qui nomment, ramenés à leurs cinq premières lettres sans accent."""
    nus = (_sans_accents(mot) for mot in mots)
    return {mot[:5] for mot in nus if len(mot) >= 5 and mot not in _MOTS_QUI_DATENT}


def _tolerance_d_une_part(mesure: Mesure) -> float:
    """L'arrondi qu'une part écrite admet : ses décimales, ou l'écart d'un calcul posé.

    Une seule lecture pour les deux règles de parts (règle 5) : « 36,3 % » pour
    36,25 %, « 23 % » pour 23,08 %.
    """
    decimales = _decimales(mesure.texte.replace("%", ""))
    return max(0.5 * 10.0 ** -decimales, mesure.valeur * _TOLERANCE_CALCUL_POSE)


def _part_d_une_donnee_nommee(mesure: Mesure, socle: Socle) -> bool:
    """Un montant de la phrase rapporté à une donnée du socle que la phrase NOMME.

    Business plans du corpus du 15/09/2026 :

    - « le seuil de rentabilité (19 674 euros, 36,3 % du chiffre d'affaires de
      l'année 1) » — 19 674 / 54 276 € (`ca_previsionnel_an1`) ;
    - « une marge de sécurité de 55 000 euros représente environ 20,8 % du
      seuil de rentabilité annuel » — 55 000 / 265 000 €.

    Le dénominateur n'est pas écrit : il est NOMMÉ, et le socle le porte. Les
    dérivations ne le voyaient pas : elles comparent au bit près, la part est
    arrondie à l'écriture.

    Les bornes, pour qu'une part fausse ne tombe pas juste par hasard
    (relecture du 15/09/2026) :

    - le NOM suit la part (« du », « de la »…) et s'arrête à la première case,
      ponctuation ou incise ; ses quatre premiers mots portent au moins deux
      mots du libellé — un seul si le libellé n'en a qu'un ;
    - un montant écrit dans le nom (« du chiffre d'affaires de 385 000 euros »)
      exclut la règle : le calcul posé se juge dans sa phrase, pas ici ;
    - l'exercice ou l'année nommés doivent être ceux de la donnée ;
    - le numérateur est un montant en EUROS de la même phrase, plus petit que
      la donnée, et la part a au moins deux chiffres significatifs ;
    - le rapport tombe juste à l'arrondi écrit.

    Le numérateur reste jugé pour lui-même : cette règle ne justifie que la part.
    """
    if not (mesure.est_un_pourcentage and mesure.phrase) or mesure.debut_dans_la_phrase < 0:
        return False
    if _chiffres_significatifs(mesure.texte) < _CHIFFRES_SIGNIFICATIFS_MIN:
        return False
    fin = mesure.debut_dans_la_phrase + len(mesure.texte)
    lien = _RAPPORTEE_A.match(mesure.phrase, fin)
    if lien is None:
        return False
    suite = mesure.phrase[lien.end():]
    coupure = _FIN_DU_NOM.search(suite)
    groupe = suite[: coupure.start()] if coupure else suite
    if any(n.unite and not n.pourcentage for n in _nombres_de_la_phrase(groupe)):
        return False
    nom = _racines(re.findall(r"[^\W\d_]+", groupe)[:_MOTS_DU_NOM])
    if not nom:
        return False
    exercice = _EXERCICE_NOMME.search(groupe)
    annee = _ANNEE_NOMMEE.search(groupe)

    numerateurs = [
        n.valeur for n in _nombres_de_la_phrase(mesure.phrase)
        if n.valeur > 0 and n.position != mesure.debut_dans_la_phrase
        and _UNITE_EURO.fullmatch(n.unite.strip())
    ]
    if not numerateurs:
        return False
    tolerance = _tolerance_d_une_part(mesure)
    for donnee in socle.donnees:
        racines = _racines(re.findall(r"[^\W\d_]+", donnee.libelle))
        if not racines or len(racines & nom) < min(2, len(racines)):
            continue
        if exercice and not (
            donnee.id.endswith(f"_an{exercice.group(1)}")
            or re.search(rf"\b(?:ann[ée]e|exercice|an)\s*{exercice.group(1)}\b",
                         donnee.libelle, re.IGNORECASE)
        ):
            continue
        if annee and donnee.annee != int(annee.group(1)):
            continue
        base = valeur_en_unites_de_base(donnee.valeur, donnee.unite)
        if base is None or base[1] != "EUR" or base[0] <= 0:
            continue
        if any(
            numerateur < base[0]
            and abs(numerateur / base[0] * 100 - mesure.valeur) <= tolerance
            for numerateur in numerateurs
        ):
            return True
    return False


def controler_chiffres_hors_socle(
    document: DocumentLu, socle: Socle, chiffres_du_brief: Iterable[float] = ()
) -> list[Anomalie]:
    """Chaque grandeur chiffrée du document est-elle dans le socle ou le brief ?

    C'est le contrôle central du lot. Un chiffre qui n'a pas de source dans le
    socle est soit une invention, soit une donnée que le socle aurait dû porter
    et ne porte pas — dans les deux cas, il faut le savoir.

    Gravité : **avertissement**, pas blocage. Le contrôle ne recalcule pas
    l'arithmétique interne des chapitres, si bien qu'une somme légitime de deux
    valeurs du socle apparaît ici comme hors socle. Bloquer sur cette base
    arrêterait des livrables corrects, et une barrière qui crie à tort finit
    débranchée. Le rapport les nomme toutes, avec leur extrait.
    """
    if not socle.donnees:
        return [Anomalie(
            "chiffres_hors_socle", Gravite.BLOQUANTE,
            "Le socle ne porte aucune donnée : impossible de justifier le "
            "moindre chiffre du document.",
        )]
    if not document.mesures:
        return [Anomalie(
            "chiffres_hors_socle", Gravite.BLOQUANTE,
            "Aucune grandeur chiffrée dans le livrable. Une étude de marché "
            "sans un seul chiffre n'est pas une étude de marché.",
        )]

    # Le BRIEF en tête : `_derivations` coupe à 80 valeurs, et les chiffres du
    # client rangés après le socle n'entraient jamais dans une dérivation dès
    # que le socle en comptait 80 (relecture du 14/09/2026).
    references = [
        *((valeur, "brut") for valeur in chiffres_du_brief),
        *((valeur, "monetaire") for valeur in chiffres_du_brief),
        *_valeurs_de_reference(socle),
    ]

    # Les dérivations sont calculées UNE fois pour tout le document : elles ne
    # dépendent que du socle, et les recalculer par mesure coûterait le carré
    # du socle multiplié par le nombre de grandeurs relevées — quatre cent
    # trente-cinq sur le dossier `c8b4e60a`.
    derivations = sorted(_derivations(references))

    def dans_le_socle(valeur: float) -> bool:
        return any(_proche(valeur, r) for r, _ in references) or _dans_les_derivations(
            valeur, derivations,
        )

    etablies = _estimations_etablies_en_tableau(document, references)

    anomalies: list[Anomalie] = []
    deja_vues: set[str] = set()
    for mesure in document.mesures:
        if _justifiee(mesure, references, derivations):
            continue
        if _reprend_une_estimation_etablie(mesure, etablies):
            continue
        # Voir « Ce que la phrase elle-même justifie », plus haut.
        if (
            _calculee_dans_sa_phrase(mesure, dans_le_socle)
            or _posee_plus_loin_dans_sa_phrase(mesure, dans_le_socle)
            or _sourcee_dans_sa_phrase(mesure)
            or _estimation_declaree(mesure)
            or _part_calculee_dans_sa_ligne(mesure, references)
            or _part_d_une_repartition(mesure)
            or _complement_a_cent(mesure)
            or _cite_un_libelle_du_socle(mesure, socle)
            or _part_d_une_donnee_nommee(mesure, socle)
        ):
            continue
        if mesure.texte in deja_vues:
            continue
        deja_vues.add(mesure.texte)
        anomalies.append(Anomalie(
            "chiffres_hors_socle", Gravite.AVERTISSEMENT,
            f"« {mesure.texte} » n'a pas d'équivalent dans le socle, ni dans "
            "le brief, ni dans les documents du client.",
            extrait=mesure.contexte,
            chapitre=mesure.chapitre,
        ))
    return anomalies


# ── Contrôle 2 : le socle est-il employé ? ───────────────────────────────────


def controler_couverture_du_socle(
    document: DocumentLu,
    socle: Socle,
    deliverable_type: str,
    identifiants_en_figure: Iterable[str] = (),
) -> list[Anomalie]:
    """Les données OBLIGATOIRES du socle apparaissent-elles dans le document ?

    Le contrôle 1 cherche des chiffres sans source ; celui-ci cherche l'inverse
    — une source jamais citée. Les deux sont nécessaires : un document peut
    n'inventer aucun chiffre tout en passant à côté de l'essentiel.

    `identifiants_en_figure` répare un angle mort découvert en confrontant la
    passe à un vrai livrable : **un chiffre porté par un graphique est un
    pixel**. Il est parfaitement sous les yeux du lecteur, et parfaitement
    invisible à une relecture du texte. Sans cette liste — fournie par le
    rapport d'assemblage, qui sait quels identifiants ont alimenté quelle
    figure — le contrôle déclarerait absentes des données bel et bien
    présentes, c'est-à-dire produirait des motifs faux (règle 2).
    """
    en_figure = set(identifiants_en_figure)
    obligatoires = identifiants_obligatoires(deliverable_type)
    if not obligatoires:
        return [Anomalie(
            "couverture_socle", Gravite.BLOQUANTE,
            f"Aucun référentiel pour « {deliverable_type} » : la couverture du "
            "socle ne peut pas être jugée.",
        )]

    anomalies: list[Anomalie] = []
    for identifiant in sorted(obligatoires):
        donnee = socle.donnee(identifiant)
        if donnee is None:
            anomalies.append(Anomalie(
                "couverture_socle", Gravite.BLOQUANTE,
                f"`{identifiant}` est obligatoire et absente du socle.",
            ))
            continue
        if identifiant in en_figure:
            continue
        conversion = valeur_en_unites_de_base(donnee.valeur, donnee.unite)
        candidates = [donnee.valeur] + ([conversion[0]] if conversion else [])
        presente = any(
            _proche(mesure.valeur, valeur)
            for mesure in document.mesures
            for valeur in candidates
        )
        if not presente:
            anomalies.append(Anomalie(
                "couverture_socle", Gravite.AVERTISSEMENT,
                f"`{identifiant}` ({donnee.libelle} = {donnee.valeur:g} "
                f"{donnee.unite}) est établie au socle mais n'apparaît nulle "
                "part dans le livrable.",
            ))
    return anomalies


# ── Contrôle 3 : hiérarchie des marchés, relue dans le document ──────────────


#: Les trois niveaux d'emboîtement du marché, du plus large au plus étroit.
NIVEAUX_DE_MARCHE = ("tam", "sam", "som")


def controler_hierarchie_des_marches(
    document: DocumentLu, socle: Socle, identifiants_en_figure: Iterable[str] = ()
) -> list[Anomalie]:
    """Le marché total reste-t-il supérieur à l'adressable et à l'atteignable ?

    Le socle l'a déjà vérifié au lot 1. On le revérifie ici sur les valeurs
    telles qu'elles figurent dans le fichier : c'est une **seconde évidence**.
    Si l'assemblage a interverti deux figures ou perdu un ordre de grandeur, le
    socle reste juste et le document faux — et seul ce contrôle-là le voit.

    Trois issues, et il faut les distinguer sous peine de bloquer des
    livrables corrects :

    - une inversion lue dans le texte est **bloquante** : le document ment ;
    - des niveaux qui n'existent QUE dans un graphique sont signalés en
      **avertissement** : ils sont sous les yeux du lecteur, mais cette passe
      ne sait pas lire des pixels, et elle doit le dire au lieu de conclure ;
    - des niveaux absents partout sont **bloquants** : une étude de marché qui
      n'énonce nulle part son dimensionnement n'est pas livrable.
    """
    triplet = [socle.donnee(nom) for nom in NIVEAUX_DE_MARCHE]
    if any(donnee is None for donnee in triplet):
        return []  # ce socle ne déclare pas de hiérarchie : rien à vérifier

    en_figure = set(identifiants_en_figure)
    presentes: list[tuple[str, float]] = []
    seulement_en_figure: list[str] = []

    for nom, donnee in zip(NIVEAUX_DE_MARCHE, triplet, strict=True):
        assert donnee is not None
        conversion = valeur_en_unites_de_base(donnee.valeur, donnee.unite)
        cible = conversion[0] if conversion else donnee.valeur
        lisible = any(
            _proche(mesure.valeur, cible) or _proche(mesure.valeur, donnee.valeur)
            for mesure in document.mesures
        )
        if lisible:
            presentes.append((nom, cible))
        elif nom in en_figure:
            seulement_en_figure.append(nom)

    if len(presentes) < 2:
        if len(presentes) + len(seulement_en_figure) >= 2:
            return [Anomalie(
                "hierarchie_marches", Gravite.AVERTISSEMENT,
                "L'emboîtement des marchés n'est lisible que dans les "
                f"graphiques ({', '.join(sorted(seulement_en_figure))}) : la "
                "passe ne relit pas les images et ne peut pas le revérifier "
                "sur le document.",
            )]
        return [Anomalie(
            "hierarchie_marches", Gravite.BLOQUANTE,
            "Moins de deux niveaux de marché sont lisibles dans le livrable : "
            "la hiérarchie total / adressable / atteignable n'y figure ni en "
            "texte, ni en graphique.",
        )]

    anomalies: list[Anomalie] = []
    for (nom_a, valeur_a), (nom_b, valeur_b) in zip(
        presentes, presentes[1:], strict=False
    ):
        if valeur_a < valeur_b:
            anomalies.append(Anomalie(
                "hierarchie_marches", Gravite.BLOQUANTE,
                f"Hiérarchie inversée dans le livrable : {nom_a} "
                f"({valeur_a:g}) est inférieur à {nom_b} ({valeur_b:g}).",
            ))
    return anomalies


# ── Contrôle 4 : le document n'est pas amputé ────────────────────────────────


def controler_integrite_du_document(
    document: DocumentLu, chapitres_attendus: Sequence[int] = ()
) -> list[Anomalie]:
    """Le fichier livré est-il complet ?

    Né d'un défaut réel : `chunk_long_tables` détruisait les lignes des
    tableaux de plus de douze lignes, et le client recevait un compte de
    résultat vide. Le markdown, lui, était propre.
    """
    anomalies: list[Anomalie] = []

    if document.tableaux == 0:
        anomalies.append(Anomalie(
            "integrite", Gravite.BLOQUANTE,
            "Le livrable ne contient aucun tableau.",
        ))
    if document.tableaux_vides:
        anomalies.append(Anomalie(
            "integrite", Gravite.BLOQUANTE,
            f"{document.tableaux_vides} tableau(x) sans aucune cellule "
            "remplie : des lignes ont été perdues au rendu.",
        ))
    if not document.paragraphes:
        anomalies.append(Anomalie(
            "integrite", Gravite.BLOQUANTE, "Le livrable ne contient aucun texte."
        ))

    if chapitres_attendus:
        # Le marqueur vient du module qui l'ÉCRIT, jamais d'une copie locale.
        # Ce contrôle portait la sienne — « Chapitre 01 » — quand le rendu écrit
        # « CHAPITRE 01 » : il déclarait les vingt-trois chapitres absents d'un
        # document qui les contient tous, et bloquait toutes les livraisons.
        #
        # La comparaison reste insensible à la casse par-dessus le marché : si
        # demain le bandeau passe en petites capitales de STYLE plutôt qu'en
        # capitales de TEXTE, le texte stocké changera de casse sans que
        # personne y pense, et le contrôle recommencerait à mentir.
        from ..rendu_word.composants import marqueur_de_chapitre  # noqa: PLC0415

        texte = document.texte_integral.lower()
        manquants = [
            numero for numero in chapitres_attendus
            if marqueur_de_chapitre(numero).lower() not in texte
            and f"chapitre {numero}" not in texte
        ]
        if manquants:
            anomalies.append(Anomalie(
                "integrite", Gravite.BLOQUANTE,
                f"Chapitre(s) absent(s) du livrable : {manquants}.",
            ))
    return anomalies


# ── Le document ne parle pas de sa propre fabrication ───────────────────────


def controler_meta_discours(document: DocumentLu) -> list[Anomalie]:
    """Le livrable commente-t-il sa propre rédaction ?

    Dernier filet derrière le gate, qui fait réécrire le chapitre en amont. Il
    regarde le FICHIER que le client ouvrira, pas le texte validé (règle 3).

    **Avertissement, jamais blocage.** Décision cliente du 13/08/2026 : le
    document part sans action de sa part. Retenir un livrable payé pour une
    phrase serait lui faire porter notre défaut ; le signaler, avec l'extrait
    exact, lui permet de la retirer avant de remettre l'étude à son client.
    """
    from ..meta_discours import trouver  # noqa: PLC0415

    return [
        Anomalie(
            "meta_discours", Gravite.AVERTISSEMENT,
            "Passage qui semble parler de la rédaction du document plutôt que "
            "de l'affaire du client — à relire avant de remettre l'étude.",
            extrait=extrait,
            chapitre=_chapitre_du_passage(document, extrait),
        )
        for extrait in trouver(document.texte_integral)
    ]


def _chapitre_du_passage(document: DocumentLu, extrait: str) -> int | None:
    """Le chapitre du passage, quand on le retrouve dans le document.

    Sans numéro, une anomalie se lit mais ne se répare pas : la relecture
    finale réécrit un CHAPITRE, jamais un document.
    """
    reference = " ".join(extrait.split())[:80]
    if not reference:
        return None
    for texte, chapitre in _passages(document):
        if reference in " ".join(texte.split()):
            return chapitre
    return None


def _passages(document: DocumentLu) -> list[tuple[str, int | None]]:
    """Chaque passage du document avec SON chapitre, quand il est connu.

    `zip` strict ou non n'irait pas : un `DocumentLu` construit sans numéros de
    chapitre — une doublure de test, la chaîne HTML héritée — a des listes de
    chapitres VIDES, et l'appariement rendait alors zéro passage. Le contrôle
    des calculs annoncés cessait silencieusement de regarder quoi que ce soit,
    et trois tests l'ont vu. Un contrôle qui n'a rien à comparer doit échouer
    bruyamment, jamais se vider (règle 1).
    """
    apparies = [
        *zip_longest(document.paragraphes, document.chapitre_du_paragraphe),
        *zip_longest(document.cellules, document.chapitre_de_la_cellule),
    ]
    return [(texte, chapitre) for texte, chapitre in apparies if texte is not None]


# ── Contrôle 5 : la densité validée par la cliente ───────────────────────────


def controler_densite(document: DocumentLu, deliverable_type: str = "") -> list[Anomalie]:
    """Le document est-il resté « des tableaux reliés par de la prose courte » ?

    Ce contrôle ne porte pas sur l'exactitude mais sur la forme, et il a sa
    place ici : la cliente a refusé une première livraison pour cette raison
    seule. Un défaut qu'un client rejette est un défaut, même quand tous les
    chiffres sont bons.

    Les seuils sont plus larges que la référence — on attrape la dérive, pas
    l'écart.
    """
    anomalies: list[Anomalie] = []
    if document.mots == 0:
        return [Anomalie("densite", Gravite.BLOQUANTE, "Document vide.")]
    seuils = seuils_de_densite(deliverable_type)

    if document.part_en_tableaux < seuils.part_tableaux_min:
        anomalies.append(Anomalie(
            "densite", Gravite.AVERTISSEMENT,
            f"{document.part_en_tableaux:.0%} des mots seulement sont dans des "
            f"tableaux (plancher {seuils.part_tableaux_min:.0%}) : le livrable "
            "redevient un texte suivi.",
        ))
    if document.mediane_paragraphe > seuils.mediane_paragraphe_max:
        anomalies.append(Anomalie(
            "densite", Gravite.AVERTISSEMENT,
            f"Paragraphe médian de {document.mediane_paragraphe:.0f} mots "
            f"(plafond {seuils.mediane_paragraphe_max}).",
        ))
    if document.part_paragraphes_longs > seuils.part_paragraphes_longs_max:
        anomalies.append(Anomalie(
            "densite", Gravite.AVERTISSEMENT,
            f"{document.part_paragraphes_longs:.0%} des paragraphes dépassent "
            f"60 mots (plafond {seuils.part_paragraphes_longs_max:.0%}).",
        ))
    if anomalies:
        anomalies.extend(_chapitres_les_plus_denses(document, seuils.mediane_paragraphe_max))
    return anomalies


#: Combien de chapitres on renvoie à la réécriture quand le document redevient
#: un mur de texte. Trois : ce sont eux qui font la médiane, et réécrire tout
#: un document pour une question de forme coûterait plus qu'il ne rapporte.
_CHAPITRES_DENSES_MAX = 3


def _chapitres_les_plus_denses(
    document: DocumentLu, mediane_max: int = MEDIANE_PARAGRAPHE_MAX,
) -> list[Anomalie]:
    """Les chapitres qui portent le mur de texte, nommés un par un.

    Un constat de densité vaut pour tout le document : il n'a donc pas de
    chapitre, et la relecture finale ne peut rien en faire — « 32 % des
    paragraphes dépassent 60 mots » ne dit pas lesquels réécrire (mesuré sur
    la stratégie Zenitek, 11/09/2026).

    Le même calcul, chapitre par chapitre, le dit. On ne renvoie que les plus
    denses : réécrire un chapitre déjà aéré coûterait sans rien gagner.
    """
    par_chapitre: dict[int, list[int]] = {}
    for texte, chapitre in zip(
        document.paragraphes, document.chapitre_du_paragraphe, strict=False
    ):
        if chapitre and texte.strip():
            par_chapitre.setdefault(chapitre, []).append(len(texte.split()))

    denses = [
        (numero, statistics.median(longueurs))
        for numero, longueurs in par_chapitre.items()
        if len(longueurs) >= 3 and statistics.median(longueurs) > mediane_max
    ]
    denses.sort(key=lambda couple: couple[1], reverse=True)
    return [
        Anomalie(
            "densite", Gravite.AVERTISSEMENT,
            f"Chapitre {numero} : paragraphe médian de {mediane:.0f} mots "
            f"(plafond {mediane_max}). Le livrable doit rester des "
            "tableaux reliés par de la prose courte, pas un texte suivi.",
            chapitre=numero,
        )
        for numero, mediane in denses[:_CHAPITRES_DENSES_MAX]
    ]


# ── Contrôle 6 : les visuels abandonnés à l'assemblage ───────────────────────


def controler_visuels(
    graphiques_demandes: int,
    graphiques_rendus: int,
    abandonnes: Sequence[str],
    convertis: Sequence[str] = (),
) -> list[Anomalie]:
    """Reprend le rapport d'assemblage du lot 3 dans le rapport de contrôle.

    Sans cette reprise, un livrable dont la moitié des figures ont été
    abandonnées faute de données passerait pour complet : l'information existe
    au lot 3, elle doit remonter là où quelqu'un la lit.
    """
    # AVERTISSEMENT, plus blocage — décision du 12/09/2026, et elle prolonge
    # celle du 13/08 sur le gate : « tout doit être clean avant que le document
    # soit envoyé, et quand le contrôle est fini le document doit partir ».
    # Retenir un livrable payé pour un manque de figures n'appelait aucun geste
    # réparateur : l'administrateur ne réécrit pas le document. Les figures
    # refusées sont désormais imprimées en TABLEAU par l'assemblage
    # (`_tableau_de_repli`) : l'information reste, la forme seule est perdue.
    anomalies: list[Anomalie] = []
    if graphiques_demandes and graphiques_rendus == 0:
        anomalies.append(Anomalie(
            "visuels", Gravite.AVERTISSEMENT,
            f"Aucun des {graphiques_demandes} graphiques demandés n'a pu être "
            "dessiné ; leurs données sont imprimées en tableau.",
        ))
    elif graphiques_rendus < PLANCHER_FIGURES:
        # Le quota vient de la cliente : « au moins 17 à 25 graphes par
        # document, c'est une obligation absolue ». Il était demandé au modèle
        # et vérifié nulle part : ce contrôle ne se plaignait que d'un document
        # à ZÉRO figure, si bien qu'un livrable à cinq passait pour complet.
        #
        # Bloquant, et à raison : la passe de complétion de l'assemblage a déjà
        # eu l'occasion de tirer du socle tout ce qu'il pouvait donner. Si le
        # compte n'y est toujours pas, le document ne tient pas la promesse
        # faite au client, et le livrer en silence serait le pire des deux.
        anomalies.append(Anomalie(
            "visuels", Gravite.AVERTISSEMENT,
            f"{graphiques_rendus} figures dans le document, pour un plancher "
            f"de {PLANCHER_FIGURES} ({PLANCHER_FIGURES} à {PLAFOND_FIGURES} "
            "attendues). Le socle n'a pas pu en alimenter davantage.",
        ))
    anomalies.extend(
        Anomalie("visuels", Gravite.AVERTISSEMENT, f"Graphique abandonné — {motif}")
        for motif in abandonnes
    )
    anomalies.extend(
        Anomalie("visuels", Gravite.INFORMATION, f"Graphique converti — {motif}")
        for motif in convertis
    )
    return anomalies


# ── Contrôle 7 : les calculs annoncés sont-ils justes ? ──────────────────────

#: « 130 000 € sur 1,36 Md€, soit 0,0096 % » — un calcul que le document POSE.
#:
#: Le motif exige les trois pièces dans l'ordre : la part, le tout, le
#: pourcentage. C'est ce qui le rend vérifiable, et c'est aussi ce que la
#: consigne demande désormais d'écrire (« tout chiffre calculé montre son
#: calcul »). On ne devine jamais un calcul qui n'est pas écrit.
_CALCUL_ANNONCE = re.compile(
    r"([\d][\d\s\u202f\u00a0.,]*)\s*"
    r"(k€|M€|Md€|€|k EUR|MEUR|MdEUR|EUR|%)?\s*"
    r"(?:sur|/|rapport[ée]s? à|par rapport à)\s*"
    r"([\d][\d\s\u202f\u00a0.,]*)\s*"
    r"(k€|M€|Md€|€|k EUR|MEUR|MdEUR|EUR|%)?\s*"
    r"[,;:]?\s*(?:soit|c'est-à-dire|=)\s*"
    r"([\d][\d\s\u202f\u00a0.,]*)\s*%",
    re.IGNORECASE,
)

#: Facteurs d'échelle, écrits ici parce que le contrôle lit du TEXTE et non
#: des `DonneeSocle`. Ils sont dérivés du même vocabulaire que
#: `socle.schema.unites_monetaires` — jamais une seconde liste de devises.
_ECHELLES: dict[str, float] = {
    "": 1.0, "€": 1.0, "eur": 1.0, "%": 1.0,
    "k€": 1e3, "k eur": 1e3,
    "m€": 1e6, "meur": 1e6,
    "md€": 1e9, "mdeur": 1e9,
}


def _nombre(brut: str) -> float | None:
    """Un nombre écrit à la française, ramené à un flottant."""
    nettoye = (
        brut.replace("\u202f", "").replace("\u00a0", "")
        .replace(" ", "").replace(".", "").replace(",", ".")
    )
    try:
        return float(nettoye)
    except ValueError:
        return None


def _decimales(brut: str) -> int:
    _, virgule, apres = brut.strip().partition(",")
    return len(apres) if virgule else 0


def controler_les_calculs_annonces(document: DocumentLu) -> list[Anomalie]:
    """Un pourcentage que le document CALCULE doit tomber juste.

    ## Pourquoi ce contrôle existe

    Cliente, 11/08/2026 : « bien vérifier la cohérence des chiffres… il y a
    des erreurs dans les calculs et pourcentages ». Une extrapolation est
    légitime — le manuel l'autorise et elle est souvent nécessaire — mais une
    extrapolation FAUSSE ruine la crédibilité de tout le document : un
    pourcentage qui ne tombe pas juste se repère au premier coup d'œil et
    fait douter de chaque autre chiffre.

    ## Ce qu'il vérifie, et ce qu'il ne devine pas

    Uniquement les calculs que le document POSE lui-même, dans l'ordre part,
    tout, résultat : « 130 000 € sur 1,36 Md€, soit 0,0096 % ». C'est
    exactement la forme que la consigne demande d'écrire. Un pourcentage
    isolé n'est pas jugé : il n'y a rien à quoi le comparer, et inventer
    l'opération produirait des motifs faux (règle 2).

    ## La tolérance suit l'ÉCRITURE, pas un seuil choisi

    « 0,0096 % » est arrondi au dix-millième : l'écart admissible est la
    moitié de cette décimale. Un seuil fixe serait soit trop lâche pour les
    petits pourcentages — 0,05 accepterait n'importe quoi face à 0,0096 —
    soit trop serré pour les grands. On y ajoute un pour cent relatif, pour
    les arrondis faits sur les OPÉRANDES plutôt que sur le résultat.

    Gravité : **avertissement**. Le lecteur juge ; le contrôle nomme.
    """
    anomalies: list[Anomalie] = []
    deja_vues: set[str] = set()

    for texte, chapitre in _passages(document):
        for trouve in _CALCUL_ANNONCE.finditer(texte):
            part_brut, unite_part, tout_brut, unite_tout, resultat_brut = (
                trouve.groups()
            )
            part = _nombre(part_brut)
            tout = _nombre(tout_brut)
            annonce = _nombre(resultat_brut)
            if part is None or tout is None or annonce is None:
                continue

            part *= _ECHELLES.get((unite_part or "").strip().lower(), 1.0)
            tout *= _ECHELLES.get((unite_tout or "").strip().lower(), 1.0)
            if abs(tout) < EPSILON:
                continue

            calcule = part / tout * 100
            tolerance = 0.5 * 10 ** (-_decimales(resultat_brut)) + abs(calcule) * 0.01
            if abs(calcule - annonce) <= tolerance:
                continue

            extrait = trouve.group(0).strip()
            if extrait in deja_vues:
                continue
            deja_vues.add(extrait)
            anomalies.append(Anomalie(
                "calcul_faux", Gravite.AVERTISSEMENT,
                f"« {extrait} » : le calcul donne {calcule:.4g} %, "
                f"le document annonce {annonce:g} %.",
                extrait=extrait,
                chapitre=chapitre,
            ))
    return anomalies


# ── Contrôle 8 : un chiffre à zéro dans un document payé ─────────────────────


#: Un zéro peut être VRAI — « aucun emprunt », « 0 € d'apport ». Ce qui ne
#: l'est jamais, c'est un zéro qu'aucune phrase n'assume : le document affiche
#: alors un calcul non fait, une donnée manquante rendue en « 0 € », et le
#: lecteur croit lire une valeur.
_ZERO_ASSUME = re.compile(
    r"(?i)aucun|aucune|nul|nulle|z[ée]ro|pas d[e’']|ni\b|sans\b|"
    r"n[e’']a (?:pas|aucun)|absen(?:ces?|te?s?)\b|"
    # Un financement ou une ligne ÉCARTÉS par décision : « Emprunt bancaire |
    # 0 € | 0 % | Non priorisé dans le scénario central » (corpus du 14/09/2026).
    # « Recrutement salarié | Non engagé à ce stade | 0 € » dit la même chose.
    r"non\s+(?:retenu|prioris|mobilis|sollicit|activ|engag|lanc|appli)\w*"
)

#: Un zéro qui est un RÉSULTAT : l'écart entre deux montants égaux, un solde,
#: une variation. « Écart : Total du plan | 27 600 € | 27 600 € | 0 € » vérifie
#: l'équilibre du plan ; le signaler faisait réécrire un chapitre juste.
#:
#: Une ÉVOLUTION nulle est le même résultat : « Évolution : Boulangerie Bosc |
#: 255 000 € | 255 000 € | 0 % (stable) » — six études concurrentielles du
#: corpus du 14/09/2026. Et le mot peut nommer la LIGNE plutôt que la colonne :
#: « Montant : Écart | 0 € ».
_EN_TETE_DE_RESULTAT = re.compile(
    r"(?i)^\s*(?:[ée]cart|diff[ée]rence|variation|[ée]volution|progression|solde|reste)\b"
)

#: Ce qui, dans la cellule d'un zéro, ne fait que COMPLÉTER son unité :
#: « 0 € par client », « 0 % du CA », « 0 € HT ». Pas un commentaire.
_COMPLEMENT_D_UNITE = re.compile(
    r"(?i)(?:\b(?:par|du|de\s+la|des|de|sur|en)\s+|\bd['’]|/\s*)[^\W\d_]+"
    r"|\b(?:HT|TTC|EUR|euros?|pts?|points?)\b"
)

#: Ce qui, DANS la cellule, dit que la donnée manque — au-delà de
#: `_DONNEE_MANQUANTE` : « 0 € (non chiffré) », « 0 € (à déterminer) ». Une
#: négation suivie d'un participe, sauf les décisions déjà assumées.
_MANQUE_DANS_LA_CELLULE = re.compile(
    r"(?i)[àa]\s+(?:d[ée]terminer|venir|chiffrer|estimer|compl[ée]ter)|"
    r"en\s+(?:attente|cours)|"
    r"non\s+(?!retenu|prioris|mobilis|sollicit|activ|engag|lanc|appli)\w+[ée]e?s?\b"
)


def _zero_commente_dans_sa_cellule(mesure: Mesure) -> bool:
    """Le rédacteur a-t-il écrit, À CÔTÉ du zéro, ce qu'il signifie ?

    « 0 € (déjà en place) », « 0 % avant lancement », « 0 % — revenu
    transactionnel » : la cellule dit elle-même pourquoi la valeur est nulle.
    C'est l'assomption que le contrôle réclame (« écris-le en toutes
    lettres »), et la réclamer une seconde fois produisait un motif faux sur
    onze tableaux du corpus du 14/09/2026. Le cas d'une donnée manquante
    (« non mesuré (0 €) ») est tranché AVANT, par `_DONNEE_MANQUANTE`.
    """
    cellule = cellule_jugee(mesure)
    if not cellule or _DONNEE_MANQUANTE.search(cellule) or _MANQUE_DANS_LA_CELLULE.search(cellule):
        return False
    reste = _COMPLEMENT_D_UNITE.sub(" ", cellule.replace(mesure.texte, " ", 1))
    return bool(re.search(r"[^\W\d_]{2,}", reste))

#: Ce qui dit qu'une donnée MANQUE : le zéro qui l'accompagne est une valeur
#: fabriquée, même si la phrase contient « aucun » par ailleurs. « Coût
#: d'acquisition : non mesuré à ce jour… | 0 EUR » passait-il ? Il ne doit pas.
_DONNEE_MANQUANTE = DONNEE_MANQUANTE

#: Un zéro qui BORNE un intervalle est assumé lui aussi : « entre −20 % et
#: 0 % » annonce une fourchette, pas une donnée manquante. Relevé sur le
#: premier document réel passé au contrôle (Zenitek, 11/09/2026) : c'était son
#: unique zéro, et le signaler aurait fait réécrire un chapitre juste.
_BORNE_D_INTERVALLE = re.compile(
    r"(?i)(?:entre|de|entre\s+environ)\s+[-–+]?[\d\s.,]+\s*(?:%|€|M€|k€|Md€)?\s*"
    r"(?:et|[àa]|–|—|-)\s*[-–+]?\s*$"
)


def controler_les_valeurs_nulles(document: DocumentLu) -> list[Anomalie]:
    """Un montant ou un taux à zéro que rien n'assume dans la phrase.

    Demande du 12/09/2026 : « s'il y a des zéros ou des incohérences dedans,
    l'agent va corriger ». Aucun contrôle ne les voyait — pire, un zéro
    trouvait toujours son équivalent dans le socle (`abs(0 - 0) <= EPSILON`)
    et passait donc pour justifié.

    Un zéro ASSUMÉ reste accepté : « aucun emprunt : 0 € » est une
    information, pas un défaut. C'est le zéro nu — dans une cellule de
    tableau, au milieu d'un calcul — qui signale une donnée manquante rendue
    comme une valeur. Gravité : avertissement, et le chapitre est nommé pour
    que la relecture finale le fasse réécrire.
    """
    anomalies: list[Anomalie] = []
    deja_vues: set[str] = set()
    for mesure in document.mesures:
        if abs(mesure.valeur) > EPSILON:
            continue
        manquante = bool(_DONNEE_MANQUANTE.search(mesure.contexte))
        if not manquante and _ZERO_ASSUME.search(mesure.contexte):
            continue
        if not manquante and mesure.dans_un_tableau:
            en_tete, _, ligne = mesure.phrase.partition(" : ")
            if _EN_TETE_DE_RESULTAT.search(en_tete) or _EN_TETE_DE_RESULTAT.search(ligne):
                continue
            if _zero_commente_dans_sa_cellule(mesure):
                continue
        # L'occurrence CHERCHÉE, pas la première : « 0 % » se trouve aussi à
        # l'intérieur de « -20 % », et le texte d'avant devenait « Entre -2 ».
        trouve = re.search(
            r"(?<![\d,.])" + re.escape(mesure.texte), mesure.contexte
        )
        avant = mesure.contexte[: trouve.start()] if trouve else ""
        if _BORNE_D_INTERVALLE.search(avant):
            continue
        if mesure.texte in deja_vues:
            continue
        deja_vues.add(mesure.texte)
        anomalies.append(Anomalie(
            "valeur_nulle", Gravite.AVERTISSEMENT,
            f"« {mesure.texte} » : un zéro que la phrase n'assume pas. Si la "
            "valeur est réellement nulle, écris-le en toutes lettres ; sinon "
            "c'est une donnée manquante rendue comme un chiffre.",
            extrait=mesure.contexte,
            chapitre=mesure.chapitre,
        ))
    return anomalies
