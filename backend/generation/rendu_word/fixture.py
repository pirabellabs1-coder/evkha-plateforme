"""Fixture de démonstration — 22 chapitres, volume calibré sur la référence.

Le volume compte autant que la structure, mais le **rapport** entre prose et
tableaux compte encore plus. Mesures relevées sur `references/joalie_2026.docx` :

| Indicateur                        | Référence    |
|-----------------------------------|--------------|
| Mots au total                     | 10 129       |
| Paragraphes de prose              | 200          |
| Longueur médiane d'un paragraphe  | 12 mots      |
| Paragraphes de plus de 60 mots    | 12 %         |
| Mots situés dans des tableaux     | 5 293 (52 %) |

Autrement dit : c'est un document **de tableaux, relié par de la prose
courte**. Une première version de cette fixture produisait 26 758 mots avec une
médiane à 112 mots — un mur de texte. Le retour de la cliente a été immédiat :
« toujours trop de texte ». Ces cibles sont donc contraignantes, pas
indicatives, et `test_lot0_rendu.py` les vérifie.
"""
from __future__ import annotations

from typing import Any

from .secteurs import graphiques_conseilles, profil_du_secteur

CHAPITRES = [
    ("Fiche projet", "La demande du client, reformulée et cadrée."),
    ("Marché mondial et continent pertinent",
     "Un marché large, mais une niche définie par le positionnement."),
    ("Marché national, local et marché accessible",
     "Du marché théorique au marché réellement atteignable."),
    ("Segmentation approfondie",
     "La segmentation croise motivation, occasion et niveau de confiance."),
    ("Avantages et contraintes structurelles du secteur",
     "Un secteur à forte valeur, fondé sur la réputation et l'expertise."),
    ("Défis et opportunités 2026-2030",
     "La période favorise les maisons capables de prouver ce qu'elles avancent."),
    ("Réglementation, normes et conformité",
     "La conformité est une preuve de sérieux et un levier de conversion."),
    ("Tendances à court terme 2026-2027",
     "Sept tendances à convertir rapidement en tests commerciaux."),
    ("Perspectives et scénarios à horizon 2030",
     "Trois trajectoires pour piloter l'incertitude."),
    ("Les 12 chiffres clés", "Les repères à retenir pour décider."),
    ("Clientèle cible et comportements d'achat",
     "L'achat combine découverte, projection et réduction du risque."),
    ("Deux personas fondés sur les données",
     "Des outils d'arbitrage pour le contenu, l'offre et les partenariats."),
    ("Risques et plan de maîtrise",
     "La viabilité dépend de la rapidité de détection des risques."),
    ("Cartographie des risques externes",
     "Les risques critiques cumulent coût, dépendance et attention."),
    ("Potentiel de viabilité",
     "Un potentiel réel, conditionné par l'économie unitaire."),
    ("Tableau de bord visuel du marché",
     "Un diagnostic simple pour aligner l'équipe."),
    ("Analyse de l'offre et de la demande",
     "Un marché fragmenté où la position d'interface est à prendre."),
    ("Analyse géographique avancée",
     "Prioriser l'accessibilité avant la taille théorique du marché."),
    ("SWOT de synthèse", "Une singularité à transformer en système commercial."),
    ("Analyse stratégique et recommandations",
     "Une feuille de route en trois temps : clarifier, convertir, développer."),
    ("Conclusion analytique", "Le verdict et ses conditions."),
    ("Sources et méthodologie",
     "Une étude triangulée, avec distinction des statuts de donnée."),
]

#: Sous-titres de section, très courts : ils pèsent lourd dans la médiane de
#: 12 mots relevée sur la référence.
_SOUS_TITRES = [
    "Deux périmètres à ne pas confondre",
    "Une base culturelle et productive cohérente",
    "Une composante désormais normale du marché",
    "Une filière puissante, un marché domestique stable",
    "Le marché local élargi",
    "Estimation du marché accessible",
    "Segments par proposition de valeur",
    "Segments de clientèle prioritaires",
    "Intensité de la demande",
    "Espace stratégique",
    "Ordre de priorité",
    "Conditions de réussite communes",
]

#: Paragraphes de corps : 55 à 90 mots. Ce sont les 12 % de paragraphes longs
#: de la référence — il y en a peu, jamais deux à la suite.
_CORPS = [
    "Le périmètre le plus proche du projet est celui de la niche premium. Les "
    "estimations disponibles situent ce segment nettement en dessous du marché "
    "large, avec une croissance supérieure. Cette surperformance s'explique par "
    "la dimension émotionnelle de l'achat, la durabilité perçue et l'intérêt "
    "pour les pièces personnalisables. Elle ne dispense pas de vérifier la "
    "capacité commerciale réelle de la structure sur son territoire.",
    "La valeur unitaire impose un besoin de confiance disproportionné par "
    "rapport à une jeune marque. Le client évalue simultanément l'esthétique, "
    "la qualité, le prix, l'origine, la sécurité de paiement et la possibilité "
    "de revente. L'absence de notoriété peut donc ralentir la décision même "
    "lorsque l'intérêt est acquis.",
    "Les statistiques publiques ne séparent pas les sous-segments visés. La "
    "méthode retenue est donc triangulée : marché national, poids de la zone, "
    "cohérence avec les prix observés, puis capacité commerciale réaliste en "
    "phase de lancement. Chaque niveau est présenté comme un ordre de grandeur "
    "à valider, jamais comme une mesure.",
]

#: Notes courtes, 10 à 25 mots : ce sont elles qui tirent la médiane vers le bas.
_NOTES = [
    "Périmètres emboîtés : la niche est incluse dans le marché large.",
    "Sources en devises courantes, périmètres non strictement comparables.",
    "Fourchette large : aucune source publique ne détaille ce sous-segment.",
    "Les ordres de grandeur priment ici sur la précision décimale.",
    "À recalculer dès les premières données comptables réelles.",
    "Estimation à valider par marge, stock et capacité de service.",
]

_LISTES = [
    ["Clarifier la promesse et la rendre reformulable par un tiers.",
     "Documenter la preuve avant d'élargir la gamme.",
     "Mesurer la marge par offre, jamais le seul volume."],
    ["Une proposition immédiatement compréhensible.",
     "Un pilotage par l'économie unitaire de chaque projet.",
     "Une base clients structurée autour des goûts et des jalons de vie.",
     "Une capacité à produire de la confiance avant l'achat."],
    ["Établir le coût complet et la marge contributive des offres.",
     "Fixer des règles de stock et un seuil de remise en cause.",
     "Installer un tableau de bord mensuel avec seuils d'alerte."],
]

_ENCADRES = [
    ("Lecture EVKHA", [
        "Opportunité — la dynamique de marché est favorable au positionnement.",
        "Limite — les chiffres globaux surestiment le marché accessible.",
        "Décision — piloter sur un périmètre étroit et une clientèle affinitaire.",
    ], False),
    ("À retenir", [
        "Le marché ne manque pas de volume ; la difficulté est d'être identifiable.",
        "La preuve documentée vaut mieux que l'élargissement de la gamme.",
    ], False),
    ("Verdict", [
        "Potentiel favorable sous conditions. La priorité n'est pas de réinventer "
        "l'offre mais de rendre la singularité visible et achetable.",
    ], True),
]

#: Tableaux riches : c'est là que vivent 52 % des mots de la référence.
_TABLEAUX = [
    (["Segment", "Besoin dominant", "Preuve attendue", "Rôle dans le modèle"], [
        ["Création contemporaine", "Singularité, auteur, style personnel",
         "Biographie, démarche, atelier, rareté, essayage",
         "Image, renouvellement, fidélisation"],
        ["Vintage expertisé", "Histoire, collection, durabilité, trouvaille",
         "Authenticité, époque, état, provenance, restauration",
         "Différenciation, acquisition de collectionneurs"],
        ["Sur-mesure", "Symboliser un lien ou une étape de vie",
         "Processus, budget, calendrier, dessins, garanties",
         "Panier élevé, relation longue, recommandation"],
    ]),
    (["Risque", "Indicateur d'alerte", "Prévention", "Réponse"], [
        ["Notoriété insuffisante", "Trafic non qualifié, peu de rendez-vous",
         "Partenariats, presse, événements ciblés",
         "Concentrer le budget sur deux canaux qui convertissent"],
        ["Message trop complexe", "Clients incapables de reformuler l'offre",
         "Promesse courte, trois portes d'entrée",
         "Tests de compréhension et refonte des pages"],
        ["Stock lent", "Rotation supérieure à douze mois",
         "Dépôt-vente, quotas, revue mensuelle",
         "Rotation, événements privés, arrêt des achats"],
        ["Marge insuffisante", "Service élevé non facturé",
         "Coût complet par offre",
         "Repricing, minimum de projet, abandon de références"],
        ["Volatilité des matières", "Écart entre devis et coût réel",
         "Durée de validité, acompte, couverture",
         "Révision contractuelle et alternatives"],
    ]),
    (["Horizon", "Action", "Livrable", "Indicateur de réussite"], [
        ["0-30 j", "Clarifier la promesse et la navigation",
         "Accueil bilingue, trois portes d'entrée, page rendez-vous",
         "80 % des testeurs reformulent l'offre"],
        ["0-45 j", "Formaliser la preuve",
         "Passeport de pièce, checklist, fiche atelier",
         "100 % des pièces documentées"],
        ["0-60 j", "Rendre le sur-mesure achetable",
         "Processus, budgets d'orientation, délais, FAQ",
         "Demandes qualifiées, moins d'allers-retours"],
        ["30-90 j", "Tester trois formats de rendez-vous",
         "Trois consultations cadrées",
         "Conversion supérieure à 25 %"],
        ["6-18 mois", "Tester un marché proche",
         "Événement sur invitation",
         "Trois ventes ou pipeline couvrant trois fois les coûts"],
    ]),
    (["Critère", "Note / 5", "Justification"], [
        ["Attractivité du segment", "4,4",
         "Marché en croissance, seconde main structurée, personnalisation recherchée"],
        ["Différenciation", "4,6",
         "Triple offre rare et cohérente autour d'un même récit"],
        ["Accès à la clientèle", "3,1",
         "Zone favorable, mais notoriété et prescription encore à construire"],
        ["Capacité de preuve", "3,8",
         "Expertise et ateliers solides ; formalisation à renforcer"],
        ["Économie du modèle", "3,3",
         "Panier élevé mais risque de stock, de marge et de temps de service"],
        ["Scalabilité", "2,9",
         "Curation peu industrialisable ; croissance sélective préférable"],
    ]),
]

_KPI = [
    ("381,5 Md$", "Marché mondial du secteur en 2025", "Grand View Research"),
    ("32 Md€", "Segment premium mondial en 2025", "Bain"),
    ("+4 à +6 %", "Croissance 2025 du segment premium", "Bain"),
    ("50 Md€", "Marché mondial de la seconde main", "Bain"),
    ("83 %", "Part des catégories concernées", "Bain"),
    ("6,16 Md€", "Production nationale en 2025", "Francéclat"),
    ("+8 %", "Croissance de la production nationale", "Francéclat"),
    ("5,92 Md€", "Ventes nationales en 2025", "Francéclat"),
    ("+38 %", "Hausse du coût des intrants", "Francéclat"),
    ("75 %", "Préférence pour des offres différenciées", "McKinsey"),
    ("36,3 M", "Fréquentation annuelle de la zone", "Observatoire"),
    ("251 000", "Occasions d'achat annuelles", "Insee"),
]


#: Matrices à quatre cases. Le composant est générique : SWOT, effort/gain,
#: probabilité/impact passent par la même forme.
_QUADRANTS = [
    [
        ("Forces", ["Triple offre rare et cohérente",
                    "Expertise reconnue sur le vintage",
                    "Capacité de sur-mesure interne"]),
        ("Faiblesses", ["Notoriété à construire",
                        "Preuve peu formalisée",
                        "Trésorerie immobilisée en stock"]),
        ("Opportunités", ["Seconde main désormais structurée",
                          "Demande de personnalisation",
                          "Prescription par les partenaires"]),
        ("Menaces", ["Volatilité du coût des intrants",
                     "Plateformes à forte audience",
                     "Allongement du cycle de décision"]),
    ],
    [
        ("Gain élevé, effort faible", ["Clarifier la promesse",
                                       "Formaliser le passeport de pièce"]),
        ("Gain élevé, effort fort", ["Rendre le sur-mesure achetable en ligne",
                                     "Ouvrir un second marché"]),
        ("Gain faible, effort faible", ["Harmoniser les fiches produit",
                                        "Recueillir les avis clients"]),
        ("Gain faible, effort fort", ["Élargir la gamme d'entrée",
                                      "Industrialiser la curation"]),
    ],
]

#: Barres de répartition : une bande unique découpée au prorata. Moins
#: encombrante qu'un graphique, plus lisible qu'un tableau à deux colonnes.
_REPARTITIONS = [
    ([("Boutique", 46.0), ("En ligne", 31.0), ("Partenaires", 15.0),
      ("Événements", 8.0)],
     "Répartition estimée du chiffre d'affaires par canal."),
    ([("Création contemporaine", 38.0), ("Vintage expertisé", 34.0),
      ("Sur-mesure", 28.0)],
     "Poids relatif des trois lignes d'offre."),
    ([("Matière", 42.0), ("Main-d'œuvre", 27.0), ("Structure", 19.0),
      ("Marge", 12.0)],
     "Décomposition du prix de revient d'une pièce type."),
]


def _donnees_graphique(type_graphique: str, numero: int) -> dict[str, Any]:
    """Données plausibles pour chacun des types du catalogue.

    Ce sont des données factices : le lot 0 se construit sans appel d'API. Leur
    seul rôle est de faire sortir chaque type de graphique dans des proportions
    réalistes, pour qu'un défaut de rendu se voie à l'œil.
    """
    ecart = numero * 3
    jeux: dict[str, tuple[str, str, dict[str, Any]]] = {
        "courbes": (
            "Trajectoire du marché 2021-2030",
            "Estimations EVKHA à partir des données publiques.",
            {"abscisses": ["2021", "2022", "2023", "2024", "2025", "2030"],
             "series": [
                 ("Mondial", [318 + ecart, 337 + ecart, 352 + ecart,
                              366 + ecart, 381 + ecart, 578 + ecart]),
                 ("Continental", [31, 33, 35, 36 + numero, 37 + numero, 57]),
             ],
             "unite": "Md€"},
        ),
        "aires": (
            "Saisonnalité de l'activité",
            "Répartition mensuelle observée sur le segment.",
            {"abscisses": ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin",
                           "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."],
             "series": [
                 ("Boutique", [42, 38, 45, 51, 63, 58, 49, 37, 55, 61, 78, 96]),
                 ("En ligne", [28, 26, 31, 34, 41, 38, 33, 29, 37, 44, 62, 81]),
             ],
             "unite": "indice base 100"},
        ),
        "entonnoir": (
            "Du marché total au marché atteignable",
            "Calcul EVKHA, méthode descendante puis ascendante.",
            {"etapes": [("Marché total", 4000.0 - ecart * 20),
                        ("Marché adressable", 250.0 - numero),
                        ("Marché atteignable", max(3.0 - numero * 0.1, 0.4))],
             "unite": " M€"},
        ),
        "barres_horizontales": (
            "Poids des segments du marché",
            "Analyse EVKHA à partir des sources citées.",
            {"etiquettes": ["Création contemporaine", "Vintage expertisé",
                            "Sur-mesure", "Entrée de gamme", "Grande diffusion"],
             "valeurs": [38 + numero % 6, 27, 21, 14, 9],
             "unite": " %"},
        ),
        "barres": (
            "Répartition par segment",
            "Analyse EVKHA.",
            {"etiquettes": ["Segment A", "Segment B", "Segment C", "Segment D"],
             "valeurs": [38 + numero % 7, 27, 21 - numero % 5, 14],
             "unite": " %"},
        ),
        "barres_groupees": (
            "Comparaison des acteurs de la zone",
            "Relevé EVKHA, notation de 1 à 5.",
            {"etiquettes": ["Prix", "Choix", "Service", "Notoriété", "Preuve"],
             "series": [("Acteurs installés", [3.1, 4.4, 3.0, 4.6, 2.8]),
                        ("Spécialistes", [3.8, 2.9, 4.3, 2.6, 4.1]),
                        ("Projet", [3.4, 3.2, 4.6, 1.9, 4.4])]},
        ),
        "barres_empilees": (
            "Structure du chiffre d'affaires par exercice",
            "Projection EVKHA, hypothèse médiane.",
            {"etiquettes": ["Année 1", "Année 2", "Année 3"],
             "series": [("Création", [62, 88, 121]),
                        ("Vintage", [45, 71, 96]),
                        ("Sur-mesure", [28, 59, 104])],
             "unite": "k€"},
        ),
        "camembert": (
            "Origine des demandes entrantes",
            "Estimation EVKHA sur la base des canaux actifs.",
            {"etiquettes": ["Recommandation", "Recherche en ligne",
                            "Réseaux sociaux", "Passage en boutique"],
             "valeurs": [34, 28, 23, 15]},
        ),
        "anneau": (
            "Répartition du panier moyen",
            "Structure observée sur le segment premium.",
            {"etiquettes": ["Pièce principale", "Personnalisation",
                            "Service et garantie", "Écrin et logistique"],
             "valeurs": [58, 22, 13, 7],
             "centre": "1 840 €"},
        ),
        "radar": (
            "Diagnostic du positionnement",
            "Évaluation EVKHA, notation de 1 à 5.",
            {"axes_noms": ["Attractivité", "Différenciation", "Accès clientèle",
                           "Capacité de preuve", "Économie", "Scalabilité"],
             "series": [("Projet", [4.4, 4.6, 3.1, 3.8, 3.3, 2.9]),
                        ("Moyenne du secteur", [3.6, 2.8, 3.9, 3.1, 3.7, 3.8])]},
        ),
        "jauges": (
            "Notation des critères de viabilité",
            "Évaluation EVKHA, notation de 1 à 5.",
            {"notes": [("Attractivité du segment", 4.4),
                       ("Différenciation", 4.6),
                       ("Accès à la clientèle", 3.1),
                       ("Capacité de preuve", 3.8),
                       ("Économie du modèle", 3.3),
                       ("Scalabilité", 2.9)]},
        ),
        "matrice_positionnement": (
            "Matrice de positionnement",
            "Évaluation EVKHA, notation de 1 à 5.",
            {"points": [("Acteurs installés", 4.2, 2.1 + numero * 0.02),
                        ("Spécialistes", 2.8, 3.9),
                        ("Plateformes", 4.6 - numero * 0.03, 1.4),
                        ("Projet", 2.2, 4.4)],
             "axe_x": "Notoriété", "axe_y": "Différenciation"},
        ),
        "carte_chaleur": (
            "Criticité des risques identifiés",
            "Probabilité × impact, notation de 1 à 5.",
            {"lignes": ["Notoriété", "Message", "Stock", "Marge", "Matières"],
             "colonnes": ["Probabilité", "Impact", "Détectabilité", "Criticité"],
             "valeurs": [[4, 4, 3, 4.0], [3, 5, 2, 3.8], [4, 3, 4, 3.5],
                         [3, 5, 3, 4.2], [4, 4, 2, 3.9]]},
        ),
        "pyramide_ages": (
            "Structure démographique du bassin de clientèle",
            "Insee, population de la zone de chalandise.",
            {"tranches": ["18-24", "25-34", "35-44", "45-54", "55-64", "65 et +"],
             "gauche": [7.4, 14.1, 15.8, 14.9, 13.2, 16.6],
             "droite": [7.1, 13.4, 15.1, 14.2, 12.4, 13.8]},
        ),
        "chronologie": (
            "Feuille de route à trois horizons",
            "Plan EVKHA, jalons validés avec le client.",
            {"jalons": [("0-30 j", "Clarifier la promesse"),
                        ("0-60 j", "Formaliser la preuve"),
                        ("3-6 mois", "Rendre le sur-mesure achetable"),
                        ("6-18 mois", "Tester un marché proche")]},
        ),
    }
    titre, source, donnees = jeux.get(type_graphique, jeux["barres"])
    return {
        "type": "graphique", "graphique": type_graphique,
        "titre": titre, "source": source, "donnees": donnees,
    }


def construire_fixture(
    nombre_chapitres: int = 22, secteur: str = "joaillerie"
) -> dict[str, Any]:
    """Étude complète, calibrée sur les mesures de la référence.

    Le patron d'un chapitre est celui du document de référence :
    bandeau, puis trois sections faites d'un sous-titre court, d'une amorce
    brève et d'un **tableau** qui porte l'information — pas d'un paragraphe.

    Les visuels, eux, **dépendent du secteur** : `secteur` est rattaché à un
    profil (`secteurs.profil_du_secteur`) qui dicte les types de graphiques
    retenus. Une fixture « restauration » sort une saisonnalité et un mix de
    ticket moyen ; une fixture « joaillerie » sort un entonnoir de marché et
    une matrice de positionnement. C'est la contrainte posée par la cliente :
    le visuel n'est pas décoratif, il doit parler du métier.
    """
    profil = profil_du_secteur(secteur)
    # Un graphique par type pertinent pour le secteur, jamais deux fois le
    # même : la référence en compte dix, la cliente en a demandé davantage une
    # fois la densité de texte réglée. Les chapitres porteurs sont répartis sur
    # tout le document plutôt que groupés en tête.
    types = graphiques_conseilles(profil)
    candidats = [n for n in range(nombre_chapitres) if n % 22 not in (0, 21)]
    pas = max(len(candidats) // max(len(types), 1), 1)
    porteurs = candidats[:: pas][: len(types)]
    plan = dict(zip(porteurs, types, strict=False))

    chapitres: list[dict[str, Any]] = []

    for numero in range(nombre_chapitres):
        titre, accroche = CHAPITRES[numero % len(CHAPITRES)]
        blocs: list[dict[str, Any]] = [
            {"type": "bandeau", "numero": numero, "titre": titre, "accroche": accroche}
        ]

        for section in range(3):
            index = numero + section
            blocs.append({
                "type": "sous_titre",
                "texte": f"{numero}.{section + 1} {_SOUS_TITRES[index % len(_SOUS_TITRES)]}",
            })
            # Une amorce au plus par section, jamais deux paragraphes de suite.
            if section == 0 or numero % 2 == 0:
                blocs.append({"type": "paragraphe", "texte": _CORPS[index % len(_CORPS)]})
            # Deux tableaux de données par chapitre, trois pour un tiers :
            # la référence en compte 49 hors bandeaux, encadrés et grilles.
            if section < 2 or numero % 3 == 0:
                entetes, lignes = _TABLEAUX[index % len(_TABLEAUX)]
                blocs.append({
                    "type": "tableau", "entetes": entetes, "lignes": lignes,
                    "source": _NOTES[index % len(_NOTES)],
                })
            # Un encadré de section sur deux chapitres : la référence en
            # compte 39, soit près de deux par chapitre.
            if section == 1 and numero % 2 == 0:
                lib, lig, verd = _ENCADRES[(numero + 1) % len(_ENCADRES)]
                blocs.append({"type": "encadre", "libelle": lib,
                              "lignes": lig, "verdict": verd})
            if section == 2 and numero % 3 == 0:
                blocs.append({"type": "paragraphe",
                              "texte": _CORPS[(index + 1) % len(_CORPS)]})

        if numero % 3 == 0:
            blocs.append({"type": "liste", "elements": _LISTES[numero % len(_LISTES)]})

        if numero in plan:
            blocs.append({"type": "saut"})
            blocs.append(_donnees_graphique(plan[numero], numero))

        # Bande de répartition : un visuel de plus, sans coût en volume de
        # texte, là où un graphique entier serait disproportionné.
        if numero % 7 == 3:
            parts, note = _REPARTITIONS[(numero // 7) % len(_REPARTITIONS)]
            blocs.append({
                "type": "repartition",
                "parts": [{"libelle": libelle, "valeur": valeur}
                          for libelle, valeur in parts],
                "source": note,
            })

        # Matrice à quatre cases : SWOT de synthèse, puis grille effort/gain.
        if numero % 11 == 7:
            blocs.append({
                "type": "quadrants",
                "cases": [{"intitule": intitule, "lignes": list(lignes)}
                          for intitule, lignes in
                          _QUADRANTS[(numero // 11) % len(_QUADRANTS)]],
            })

        if numero == 9:
            blocs.append({"type": "kpi", "chiffres": [list(k) for k in _KPI]})

        libelle, lignes_encadre, verdict = _ENCADRES[numero % len(_ENCADRES)]
        blocs.append({
            "type": "encadre", "libelle": libelle,
            "lignes": lignes_encadre, "verdict": verdict,
        })
        if numero % 4 == 1:
            l2, li2, v2 = _ENCADRES[2]
            blocs.append({"type": "encadre", "libelle": l2, "lignes": li2, "verdict": v2})

        chapitres.append({"numero": numero, "titre": titre, "blocs": blocs})

    return {
        "titre": "Étude de marché",
        "sous_titre": "Joaillerie de créateurs · Vintage · Sur-mesure",
        "mention": "Document confidentiel — usage stratégique interne",
        "marque": {
            "nom": "Joalie",
            "couleur_principale": "#3A132C",
            "couleur_secondaire": "#B98B4E",
            "couleur_fond": "#F1EEDB",
        },
        "mentions_finales": [
            "EVKHA · Système d'analyse de marché",
            "Méthode déposée à l'INPI",
            "Document confidentiel — reproduction interdite",
        ],
        "chapitres": chapitres,
    }
