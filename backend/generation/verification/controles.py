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
from collections.abc import Iterable, Sequence
from itertools import zip_longest

from core.numbers import amounts_in

from ..prompts import PLAFOND_FIGURES, PLANCHER_FIGURES
from ..socle.referentiel import identifiants_obligatoires
from ..socle.schema import Socle, valeur_en_unites_de_base
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
    return any(
        _proche(mesure.valeur, valeur, TOLERANCE_DERIVATION)
        for valeur in derivations
    )


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

_SOURCE_DANS_LA_PHRASE = re.compile(
    r"\b(?:selon|d['’]apr[èe]s|source\s*:|sources\s*:)"
    r"|\([^()]*\b[A-ZÉ][\w&'’.\-]{2,}[^()]*\b(?:19|20)\d{2}\b[^()]*\)",
)

#: Écart relatif toléré entre le calcul refait et la grandeur écrite, en plus
#: de l'arrondi de son écriture : les OPÉRANDES aussi sont arrondis.
_TOLERANCE_CALCUL_POSE = 0.005


def _nombres_de_la_phrase(phrase: str) -> list[tuple[int, float]]:
    """(position, valeur) de chaque nombre de la phrase, unités ramenées à la base."""
    trouves: list[tuple[int, float]] = []
    couverts: list[tuple[int, int]] = []
    for grandeur in mesures_dans(phrase):
        position = phrase.find(grandeur.texte)
        if position >= 0:
            trouves.append((position, grandeur.valeur))
            couverts.append((position, position + len(grandeur.texte)))
    for nu in _NOMBRE_NU.finditer(phrase):
        if any(debut <= nu.start() < fin for debut, fin in couverts):
            continue
        valeur = _nombre(nu.group(0))
        if valeur is not None:
            trouves.append((nu.start(), valeur))
    return trouves


def _resultats(a: float, b: float) -> list[float]:
    calcules = [a + b, abs(a - b), a * b, a * b / 100]
    if abs(b) > EPSILON:
        calcules += [a / b, a / b * 100, (a - b) / b * 100, abs(a - b) / b * 100]
    if abs(a) > EPSILON:
        calcules += [b / a, b / a * 100, (b - a) / a * 100, abs(b - a) / a * 100]
    return calcules


def _calculee_dans_sa_phrase(mesure: Mesure) -> bool:
    """La grandeur est-elle le RÉSULTAT d'un calcul écrit dans sa phrase ?"""
    if not mesure.phrase or mesure.debut_dans_la_phrase < 0:
        return False
    position = mesure.debut_dans_la_phrase
    fin = position + len(mesure.texte)
    nombres = [(p, v) for p, v in _nombres_de_la_phrase(mesure.phrase) if p != position]

    # La parenthèse du calcul suit le résultat, pas forcément collée :
    # « 172,5 M€ un an plus tard (150 x 1,15) ». Bornée pour ne pas aller
    # chercher une parenthèse qui parle d'autre chose.
    parenthese = re.match(r"[^()]{0,40}?\(([^()]*)\)", mesure.phrase[fin:])
    dans_la_parenthese = []
    if parenthese:
        debut_p = fin + parenthese.start(1)
        fin_p = fin + parenthese.end(1)
        dans_la_parenthese = [(p, v) for p, v in nombres if debut_p <= p < fin_p]
    if mesure.est_un_pourcentage:
        operandes = nombres
    else:
        operandes = [(p, v) for p, v in nombres if p < position] + dans_la_parenthese
    valeurs = [v for _, v in operandes]

    # Les décimales du NOMBRE écrit (« 90,6 % » → 1), lues par `_decimales`,
    # la même fonction que le contrôle des calculs annoncés (règle 5). Une
    # première version redéfinissait `_decimales` sous le même nom : la
    # définition du bas l'emportait, et « 90,6 % » comptait trois décimales.
    nombre_ecrit = re.match(r"-?[\d\s]+(?:,\d+)?", mesure.texte.strip())
    ecart_ecrit = (
        0.5 * 10 ** -_decimales(nombre_ecrit.group(0) if nombre_ecrit else "")
        if mesure.est_un_pourcentage else 0.0
    )

    # L'ÉCHELLE écrite du résultat : dans « 172,5 M€ (150 x 1,15) », 150 veut
    # dire 150 millions. Le calcul refait sur les nombres nus se compare donc
    # aussi au nombre ÉCRIT, avant sa conversion en unités de base.
    ecrit = _nombre(re.sub(r"[^\d,\s-].*$", "", mesure.texte).strip())

    def tombe_juste(calcul: float) -> bool:
        return (
            abs(calcul - mesure.valeur) <= ecart_ecrit + EPSILON
            or _proche(calcul, mesure.valeur, _TOLERANCE_CALCUL_POSE)
            or (
                not mesure.est_un_pourcentage
                and ecrit is not None
                and _proche(calcul, ecrit, _TOLERANCE_CALCUL_POSE)
            )
        )

    for index, a in enumerate(valeurs):
        for b in valeurs[index + 1:]:
            if any(tombe_juste(calcul) for calcul in _resultats(a, b)):
                return True
    # Une somme posée entre parenthèses : « 18,65 % (6,25 + 7,40 + 5,00) ».
    if parenthese and "+" in parenthese.group(1) and len(dans_la_parenthese) >= 2:
        return tombe_juste(sum(v for _, v in dans_la_parenthese))
    return False


def _sourcee_dans_sa_phrase(mesure: Mesure) -> bool:
    return bool(mesure.phrase) and bool(_SOURCE_DANS_LA_PHRASE.search(mesure.phrase))


# ── Contrôle 1 : aucune valeur hors socle ────────────────────────────────────


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

    references = [
        *_valeurs_de_reference(socle),
        *((valeur, "brut") for valeur in chiffres_du_brief),
        *((valeur, "monetaire") for valeur in chiffres_du_brief),
    ]

    # Les dérivations sont calculées UNE fois pour tout le document : elles ne
    # dépendent que du socle, et les recalculer par mesure coûterait le carré
    # du socle multiplié par le nombre de grandeurs relevées — quatre cent
    # trente-cinq sur le dossier `c8b4e60a`.
    derivations = sorted(_derivations(references))

    anomalies: list[Anomalie] = []
    deja_vues: set[str] = set()
    for mesure in document.mesures:
        if _justifiee(mesure, references, derivations):
            continue
        # Voir « Ce que la phrase elle-même justifie », plus haut.
        if _calculee_dans_sa_phrase(mesure) or _sourcee_dans_sa_phrase(mesure):
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


def controler_densite(document: DocumentLu) -> list[Anomalie]:
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

    if document.part_en_tableaux < PART_TABLEAUX_MIN:
        anomalies.append(Anomalie(
            "densite", Gravite.AVERTISSEMENT,
            f"{document.part_en_tableaux:.0%} des mots seulement sont dans des "
            f"tableaux (plancher {PART_TABLEAUX_MIN:.0%}) : le livrable "
            "redevient un texte suivi.",
        ))
    if document.mediane_paragraphe > MEDIANE_PARAGRAPHE_MAX:
        anomalies.append(Anomalie(
            "densite", Gravite.AVERTISSEMENT,
            f"Paragraphe médian de {document.mediane_paragraphe:.0f} mots "
            f"(plafond {MEDIANE_PARAGRAPHE_MAX}).",
        ))
    if document.part_paragraphes_longs > PART_PARAGRAPHES_LONGS_MAX:
        anomalies.append(Anomalie(
            "densite", Gravite.AVERTISSEMENT,
            f"{document.part_paragraphes_longs:.0%} des paragraphes dépassent "
            f"60 mots (plafond {PART_PARAGRAPHES_LONGS_MAX:.0%}).",
        ))
    if anomalies:
        anomalies.extend(_chapitres_les_plus_denses(document))
    return anomalies


#: Combien de chapitres on renvoie à la réécriture quand le document redevient
#: un mur de texte. Trois : ce sont eux qui font la médiane, et réécrire tout
#: un document pour une question de forme coûterait plus qu'il ne rapporte.
_CHAPITRES_DENSES_MAX = 3


def _chapitres_les_plus_denses(document: DocumentLu) -> list[Anomalie]:
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
        if len(longueurs) >= 3 and statistics.median(longueurs) > MEDIANE_PARAGRAPHE_MAX
    ]
    denses.sort(key=lambda couple: couple[1], reverse=True)
    return [
        Anomalie(
            "densite", Gravite.AVERTISSEMENT,
            f"Chapitre {numero} : paragraphe médian de {mediane:.0f} mots "
            f"(plafond {MEDIANE_PARAGRAPHE_MAX}). Le livrable doit rester des "
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
    r"n[e’']a (?:pas|aucun)|absence"
)

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
        if _ZERO_ASSUME.search(mesure.contexte):
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
