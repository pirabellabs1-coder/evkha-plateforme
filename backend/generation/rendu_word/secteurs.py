"""Profils sectoriels : quels visuels ont du sens pour quel métier.

La cliente l'a posé comme une contrainte : « ça dépend toujours du secteur
d'activité ». Un plan de visuels figé par numéro de chapitre produirait une
saisonnalité mensuelle dans une étude sur le conseil aux entreprises et une
pyramide des âges dans une étude sur la logistique — deux graphiques justes
techniquement, absurdes sur le fond.

Ce module ne dessine rien. Il répond à une seule question : *pour ce secteur,
quels types de graphiques racontent quelque chose, et lesquels sont hors
sujet ?* Le rendu reste dans `graphiques.py`, le choix final revient au modèle
lors de la génération — ce profil lui est fourni dans le prompt, et sert de
repli déterministe quand aucun choix n'est exprimé.

Le rattachement se fait par mots-clés sur le champ libre du formulaire, en
insensible aux accents et à la casse : la cliente saisit « Bijouterie /
joaillerie », « restauration rapide » ou « cabinet d'ostéopathie », pas un code.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .graphiques import TYPES_DISPONIBLES

#: Repli quand le secteur n'est pas reconnu. Jamais vide : un document sans
#: graphique serait un échec silencieux (règle 1).
CODE_GENERIQUE = "generique"


def _sans_accent(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte.casefold())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class ProfilSectoriel:
    """Ce qu'un secteur appelle comme visuels, et ce qu'il n'appelle pas."""

    code: str
    libelle: str
    #: Mots-clés de rattachement, sans accent et en minuscules.
    mots_cles: tuple[str, ...]
    #: Types de `graphiques.RENDU_PAR_TYPE`, du plus au moins pertinent.
    graphiques_privilegies: tuple[str, ...]
    #: Types à ne pas proposer : ils n'ont pas de sens dans ce métier.
    graphiques_a_eviter: tuple[str, ...] = ()
    #: Ce que ces visuels doivent montrer, en clair. Repris dans le prompt.
    angles: tuple[str, ...] = field(default=())


#: Socle commun : présent dans presque toutes les études, quel que soit le
#: métier. Sert de base aux profils et de repli au profil générique.
_COMMUNS = ("entonnoir", "courbes", "barres", "matrice_positionnement", "carte_chaleur")


PROFILS: tuple[ProfilSectoriel, ...] = (
    ProfilSectoriel(
        code="luxe_joaillerie",
        libelle="Luxe, joaillerie et horlogerie",
        mots_cles=(
            "joaillerie", "bijou", "bijouterie", "horlogerie", "montre", "orfevre",
            "luxe", "haute couture", "maroquinerie", "pierre precieuse", "diamant",
        ),
        graphiques_privilegies=(
            "entonnoir", "matrice_positionnement", "courbes", "anneau",
            "barres_horizontales", "radar", "chronologie",
        ),
        graphiques_a_eviter=("pyramide_ages",),
        angles=(
            "segmentation du marché par gamme de prix",
            "positionnement des maisons concurrentes sur prix et notoriété",
            "poids des canaux : boutique, e-commerce, revendeurs",
            "saisonnalité des achats liés aux fêtes et aux moments de vie",
        ),
    ),
    ProfilSectoriel(
        code="restauration",
        libelle="Restauration et débits de boissons",
        mots_cles=(
            "restaurant", "restauration", "brasserie", "bar", "cafe", "traiteur",
            "food truck", "boulangerie", "patisserie", "snack", "pizzeria",
        ),
        graphiques_privilegies=(
            "aires", "barres_empilees", "camembert", "entonnoir",
            "barres_groupees", "jauges", "matrice_positionnement",
        ),
        graphiques_a_eviter=("pyramide_ages",),
        angles=(
            "saisonnalité du chiffre d'affaires mois par mois",
            "répartition du ticket moyen entre entrée, plat, dessert et boissons",
            "poids des services : midi, soir, livraison, vente à emporter",
            "densité concurrentielle dans la zone de chalandise",
        ),
    ),
    ProfilSectoriel(
        code="commerce_detail",
        libelle="Commerce de détail",
        mots_cles=(
            "commerce", "boutique", "magasin", "detail", "retail", "epicerie",
            "concept store", "franchise", "pret a porter", "vetement", "librairie",
        ),
        graphiques_privilegies=(
            "barres_empilees", "entonnoir", "aires", "camembert",
            "barres_horizontales", "matrice_positionnement",
        ),
        angles=(
            "structure du chiffre d'affaires par famille de produits",
            "saisonnalité et poids des périodes de soldes",
            "comparaison des enseignes présentes dans la zone",
            "part du commerce en ligne dans le marché",
        ),
    ),
    ProfilSectoriel(
        code="numerique",
        libelle="Numérique, logiciel et services en ligne",
        mots_cles=(
            "logiciel", "saas", "application", "plateforme", "numerique", "digital",
            "informatique", "web", "startup", "intelligence artificielle", "cybersecurite",
        ),
        graphiques_privilegies=(
            "entonnoir", "courbes", "radar", "barres_groupees",
            "matrice_positionnement", "chronologie", "jauges",
        ),
        graphiques_a_eviter=("pyramide_ages",),
        angles=(
            "entonnoir d'acquisition, de l'audience au client payant",
            "trajectoire du revenu récurrent sur trois à cinq ans",
            "comparaison fonctionnelle avec les solutions concurrentes",
            "jalons de la feuille de route produit",
        ),
    ),
    ProfilSectoriel(
        code="services_entreprises",
        libelle="Services aux entreprises",
        mots_cles=(
            "conseil", "consultant", "audit", "expertise comptable", "avocat",
            "agence", "communication", "marketing", "recrutement", "b2b",
            "ingenierie", "bureau d'etudes",
        ),
        graphiques_privilegies=(
            "entonnoir", "barres_horizontales", "radar", "matrice_positionnement",
            "courbes", "chronologie", "carte_chaleur",
        ),
        graphiques_a_eviter=("pyramide_ages", "aires"),
        angles=(
            "taille du marché adressable par typologie de client",
            "cycle de vente, de la prise de contact à la signature",
            "comparaison des offres et des grilles tarifaires concurrentes",
            "concentration du chiffre d'affaires sur les principaux clients",
        ),
    ),
    ProfilSectoriel(
        code="sante_bien_etre",
        libelle="Santé, bien-être et soins",
        mots_cles=(
            "sante", "medical", "paramedical", "osteopathe", "kinesitherapeute",
            "infirmier", "pharmacie", "bien-etre", "spa", "massage", "coiffure",
            "esthetique", "salon de beaute", "psychologue", "dentiste",
        ),
        graphiques_privilegies=(
            "pyramide_ages", "barres_horizontales", "carte_chaleur",
            "entonnoir", "camembert", "courbes", "jauges",
        ),
        angles=(
            "structure démographique du bassin de patientèle",
            "densité de praticiens pour cent mille habitants",
            "répartition des actes ou des prestations",
            "évolution de la demande liée au vieillissement",
        ),
    ),
    ProfilSectoriel(
        code="services_particuliers",
        libelle="Services à la personne",
        mots_cles=(
            "service a la personne", "aide a domicile", "garde d'enfant", "menage",
            "jardinage", "bricolage", "conciergerie", "petsitting", "coaching",
            "professeur", "cours particulier",
        ),
        graphiques_privilegies=(
            "pyramide_ages", "carte_chaleur", "barres_horizontales",
            "entonnoir", "aires", "camembert",
        ),
        angles=(
            "structure démographique et revenus du bassin de clientèle",
            "couverture géographique et zones mal desservies",
            "saisonnalité de la demande",
            "poids des dispositifs d'aide et du crédit d'impôt",
        ),
    ),
    ProfilSectoriel(
        code="artisanat_industrie",
        libelle="Artisanat, fabrication et industrie",
        mots_cles=(
            "artisan", "fabrication", "industrie", "atelier", "menuiserie",
            "batiment", "construction", "renovation", "plomberie", "electricite",
            "usine", "production", "textile", "cosmetique",
        ),
        graphiques_privilegies=(
            "barres_empilees", "chronologie", "courbes", "carte_chaleur",
            "barres_groupees", "matrice_positionnement",
        ),
        graphiques_a_eviter=("pyramide_ages",),
        angles=(
            "décomposition du prix de revient",
            "délais et jalons du cycle de production",
            "dépendance aux fournisseurs et aux matières premières",
            "comparaison des capacités des acteurs de la zone",
        ),
    ),
    ProfilSectoriel(
        code="tourisme_hebergement",
        libelle="Tourisme, hébergement et loisirs",
        mots_cles=(
            "tourisme", "hotel", "hebergement", "gite", "chambre d'hotes",
            "camping", "location saisonniere", "voyage", "loisir", "evenementiel",
            "salle de sport", "musee",
        ),
        graphiques_privilegies=(
            "aires", "courbes", "carte_chaleur", "camembert",
            "barres_groupees", "jauges", "matrice_positionnement",
        ),
        angles=(
            "saisonnalité du taux d'occupation",
            "origine géographique de la clientèle",
            "comparaison des prix moyens par nuitée",
            "poids des plateformes de réservation",
        ),
    ),
    ProfilSectoriel(
        code="immobilier",
        libelle="Immobilier",
        mots_cles=(
            "immobilier", "agence immobiliere", "promotion", "syndic",
            "gestion locative", "foncier", "marchand de biens",
        ),
        graphiques_privilegies=(
            "courbes", "carte_chaleur", "barres_horizontales",
            "matrice_positionnement", "entonnoir", "chronologie",
        ),
        graphiques_a_eviter=("pyramide_ages",),
        angles=(
            "évolution des prix au mètre carré par quartier",
            "volumes de transactions et tension du marché",
            "comparaison des honoraires pratiqués",
            "calendrier des programmes en cours",
        ),
    ),
    ProfilSectoriel(
        code="transport_logistique",
        libelle="Transport et logistique",
        mots_cles=(
            "transport", "logistique", "livraison", "fret", "messagerie",
            "vtc", "taxi", "demenagement", "entreposage", "supply chain",
        ),
        graphiques_privilegies=(
            "carte_chaleur", "courbes", "barres_empilees", "aires",
            "barres_groupees", "matrice_positionnement",
        ),
        graphiques_a_eviter=("pyramide_ages",),
        angles=(
            "flux et densité par axe géographique",
            "structure des coûts d'exploitation",
            "évolution du coût du carburant et de son impact",
            "délais moyens comparés à la concurrence",
        ),
    ),
    ProfilSectoriel(
        code="automobile_mobilite",
        libelle="Automobile et mobilité",
        # Manquait entièrement : « vente de voitures d'occasion » retombait sur
        # le profil générique, donc sur des visuels qui ne disaient rien du
        # métier. Repéré en préparant un aperçu pour cette niche précise.
        #
        # Distinct de `transport_logistique`, qui traite le déplacement de
        # marchandises : ici on VEND, on répare ou on loue le véhicule.
        mots_cles=(
            "automobile", "voiture", "vehicule", "concession", "concessionnaire",
            "garage", "carrosserie", "mecanique", "occasion", "mandataire",
            "moto", "deux roues", "location de voiture", "reparation automobile",
            "pieces detachees", "controle technique", "borne de recharge",
        ),
        # Le parc se raisonne en stock et en rotation, la demande en entonnoir
        # d'essai puis d'achat, et l'offre se compare modèle par modèle.
        graphiques_privilegies=(
            "barres_groupees", "entonnoir", "courbes", "barres_empilees",
            "matrice_positionnement", "camembert", "carte_chaleur",
        ),
        graphiques_a_eviter=("pyramide_ages",),
        angles=(
            "structure du parc par motorisation et par âge du véhicule",
            "effet des zones à faibles émissions sur la demande",
            "panier moyen et durée de rotation du stock",
            "part de la reprise et du financement dans la transaction",
            "densité des points de vente concurrents dans la zone",
        ),
    ),
    ProfilSectoriel(
        code="agroalimentaire",
        libelle="Agriculture et agroalimentaire",
        mots_cles=(
            "agriculture", "agricole", "agroalimentaire", "ferme", "elevage",
            "viticulture", "viticole", "vignoble", "vin", "brasserie artisanale",
            "maraichage", "bio",
        ),
        graphiques_privilegies=(
            "aires", "barres_empilees", "courbes", "camembert",
            "carte_chaleur", "chronologie",
        ),
        graphiques_a_eviter=("pyramide_ages",),
        angles=(
            "saisonnalité de la production et des ventes",
            "répartition entre circuits courts, grande distribution et export",
            "décomposition du prix payé par le consommateur",
            "calendrier cultural ou de production",
        ),
    ),
    ProfilSectoriel(
        code="formation",
        libelle="Formation et éducation",
        mots_cles=(
            "formation", "education", "ecole", "organisme de formation",
            "e-learning", "apprentissage", "certification", "qualiopi",
        ),
        graphiques_privilegies=(
            "entonnoir", "barres_horizontales", "jauges", "courbes",
            "camembert", "radar", "chronologie",
        ),
        angles=(
            "entonnoir de recrutement des apprenants",
            "répartition des financements : CPF, OPCO, entreprises, particuliers",
            "taux de complétion et de satisfaction",
            "comparaison des catalogues concurrents",
        ),
    ),
)


#: Repli. Ses graphiques sont ceux qui parlent dans n'importe quelle étude.
PROFIL_GENERIQUE = ProfilSectoriel(
    code=CODE_GENERIQUE,
    libelle="Secteur non spécifié",
    mots_cles=(),
    graphiques_privilegies=(*_COMMUNS, "camembert", "barres_horizontales", "radar"),
    angles=(
        "dimensionnement du marché du total à l'atteignable",
        "évolution du marché sur les dernières années",
        "positionnement des principaux concurrents",
        "criticité des risques identifiés",
    ),
)

_PAR_CODE = {profil.code: profil for profil in PROFILS}
_PAR_CODE[PROFIL_GENERIQUE.code] = PROFIL_GENERIQUE


#: Longueur du préfixe commun qui suffit à rapprocher deux mots.
#: Assez long pour ne pas confondre deux métiers, assez court pour absorber
#: les flexions du français.
_PREFIXE = 6


def _normaliser(texte: str) -> str:
    """Sans accent, ponctuation ramenée à des espaces, bordé d'espaces.

    Les espaces de bordure permettent de chercher « bar » sans capturer
    « barbecue » ni « cabaret » : on cherche `" bar "`, pas `"bar"`.
    """
    return f" {re.sub(r'[^a-z0-9]+', ' ', _sans_accent(texte)).strip()} "


def _correspond(mot_cle: str, aiguille: str) -> bool:
    """Le mot-clé est-il présent dans le champ saisi ?

    Une comparaison mot à mot exacte échoue sur toutes les flexions :
    « ostéopathie » ne vaut pas « ostéopathe », « transporteur » ne vaut pas
    « transport », « boulanger » ne vaut pas « boulangerie ». Énumérer ces
    variantes dans les listes de mots-clés reviendrait à corriger des cas au
    lieu de la classe de défaut (règle 4) : la liste raterait la variante
    suivante.

    La règle retenue est donc morphologique : deux mots d'au moins six
    caractères qui partagent leurs six premiers désignent le même métier.
    En dessous de ce seuil, et pour les mots-clés composés, on exige la
    présence littérale — « bar » ou « vin » ne peuvent pas être approchés sans
    produire des rattachements absurdes.
    """
    if f" {mot_cle} " in aiguille:
        return True
    if " " in mot_cle or len(mot_cle) < _PREFIXE:
        return False
    racine = mot_cle[:_PREFIXE]
    return any(
        len(mot) >= _PREFIXE and mot.startswith(racine) for mot in aiguille.split()
    )


def profil_du_secteur(secteur: str) -> ProfilSectoriel:
    """Profil correspondant au champ libre du formulaire.

    Le rattachement retient le profil qui cumule le plus de mots-clés trouvés,
    et à égalité le mot-clé le plus long — « boulangerie pâtisserie » doit
    donner la restauration, pas le commerce de détail au motif que le mot
    « commerce » traîne dans la phrase.
    """
    if not secteur or not secteur.strip():
        return PROFIL_GENERIQUE

    aiguille = _normaliser(secteur)
    meilleur: ProfilSectoriel | None = None
    meilleur_score = (0, 0)

    for profil in PROFILS:
        trouves = [mot for mot in profil.mots_cles if _correspond(mot, aiguille)]
        if not trouves:
            continue
        score = (len(trouves), max(len(mot) for mot in trouves))
        if score > meilleur_score:
            meilleur, meilleur_score = profil, score

    return meilleur or PROFIL_GENERIQUE


def profil_par_code(code: str) -> ProfilSectoriel:
    """Profil par son code. Un code inconnu retombe sur le profil générique."""
    return _PAR_CODE.get(code, PROFIL_GENERIQUE)


def graphiques_conseilles(
    profil: ProfilSectoriel, nombre: int | None = None
) -> list[str]:
    """Types de graphiques pour ce secteur, du plus au moins pertinent.

    Sert de repli déterministe : c'est ce que le document contiendra si la
    génération n'exprime aucun choix. L'ordre est : types privilégiés du
    secteur, puis socle commun, puis le reste du catalogue — le tout amputé de
    ce que le secteur proscrit.

    Sans `nombre`, renvoie **tous** les types pertinents, sans doublon. C'est
    la forme à utiliser pour composer un document : demander plus de
    graphiques que de types disponibles ferait réapparaître deux fois la même
    figure, ce qui se voit immédiatement à la lecture.
    """
    ordre = [*profil.graphiques_privilegies]
    for source in (_COMMUNS, TYPES_DISPONIBLES):
        ordre += [
            type_graphique for type_graphique in source if type_graphique not in ordre
        ]
    retenus = [
        type_graphique
        for type_graphique in ordre
        if type_graphique not in profil.graphiques_a_eviter
    ]
    if not retenus:  # ne peut arriver qu'avec un profil mal déclaré
        retenus = list(_COMMUNS)
    if nombre is None:
        return retenus
    return [retenus[index % len(retenus)] for index in range(max(nombre, 0))]


def consigne_visuelle(profil: ProfilSectoriel) -> str:
    """Le profil en texte, à insérer dans le prompt de chapitre.

    Le modèle reçoit ce qu'il peut employer et ce qu'il doit éviter, plutôt
    qu'une liste unique de types : sans la partie « à éviter », il propose une
    pyramide des âges dès qu'un chapitre parle de clientèle, y compris en B2B.
    """
    lignes = [
        f"Secteur d'activité : {profil.libelle}.",
        "Types de graphiques à privilégier, dans cet ordre : "
        + ", ".join(f"`{nom}`" for nom in profil.graphiques_privilegies)
        + ".",
    ]
    if profil.graphiques_a_eviter:
        lignes.append(
            "Types hors sujet pour ce secteur, à ne pas employer : "
            + ", ".join(f"`{nom}`" for nom in profil.graphiques_a_eviter)
            + "."
        )
    if profil.angles:
        lignes.append("Angles à couvrir en priorité par les visuels :")
        lignes.extend(f"- {angle}" for angle in profil.angles)
    return "\n".join(lignes)
