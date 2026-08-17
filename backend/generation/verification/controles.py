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
from collections.abc import Iterable, Sequence

from core.numbers import amounts_in

from ..prompts import PLAFOND_FIGURES, PLANCHER_FIGURES
from ..socle.referentiel import identifiants_obligatoires
from ..socle.schema import Socle, valeur_en_unites_de_base
from .lecture import DocumentLu, Mesure
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
    valeurs = [valeur for valeur, _ in references]
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
        if mesure.texte in deja_vues:
            continue
        deja_vues.add(mesure.texte)
        anomalies.append(Anomalie(
            "chiffres_hors_socle", Gravite.AVERTISSEMENT,
            f"« {mesure.texte} » n'a pas d'équivalent dans le socle ni dans "
            "le brief client.",
            extrait=mesure.contexte,
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
    return anomalies


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
    anomalies: list[Anomalie] = []
    if graphiques_demandes and graphiques_rendus == 0:
        anomalies.append(Anomalie(
            "visuels", Gravite.BLOQUANTE,
            f"Aucun des {graphiques_demandes} graphiques demandés n'a pu être "
            "alimenté par le socle.",
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
            "visuels", Gravite.BLOQUANTE,
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

    for texte in (*document.paragraphes, *document.cellules):
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
            ))
    return anomalies
