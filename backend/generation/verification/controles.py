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

from collections.abc import Iterable, Sequence

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
    return references


def _proche(mesure: float, reference: float) -> bool:
    if abs(mesure - reference) <= EPSILON:
        return True
    echelle = max(abs(mesure), abs(reference))
    return echelle > 0 and abs(mesure - reference) / echelle <= TOLERANCE


def _justifiee(mesure: Mesure, references: Sequence[tuple[float, str]]) -> bool:
    famille = "monetaire" if mesure.est_monetaire else "brut"
    return any(
        _proche(mesure.valeur, valeur)
        for valeur, nature in references
        if nature == famille or famille == "brut"
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

    anomalies: list[Anomalie] = []
    deja_vues: set[str] = set()
    for mesure in document.mesures:
        if _justifiee(mesure, references):
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
        texte = document.texte_integral
        manquants = [
            numero for numero in chapitres_attendus
            if f"Chapitre {numero:02d}" not in texte
            and f"Chapitre {numero}" not in texte
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
    anomalies.extend(
        Anomalie("visuels", Gravite.AVERTISSEMENT, f"Graphique abandonné — {motif}")
        for motif in abandonnes
    )
    anomalies.extend(
        Anomalie("visuels", Gravite.INFORMATION, f"Graphique converti — {motif}")
        for motif in convertis
    )
    return anomalies
