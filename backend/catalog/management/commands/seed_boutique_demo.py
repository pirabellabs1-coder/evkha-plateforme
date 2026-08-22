"""python manage.py seed_boutique_demo

Remplit les fiches creees par `seed_boutique` avec de quoi MONTRER la boutique :
description, sommaire, couverture, document, extrait et avis. Les neuf etudes
du catalogue.

## Ce que cette commande est, et ce qu'elle n'est pas

C'est un jeu de DEMONSTRATION. Les documents qu'elle depose sont de vrais PDF,
mis en page, avec la structure d'une etude EVKHA — mais leur contenu est
generique, et leur page de garde le dit en toutes lettres. Ils servent a faire
la visite de la boutique, pas a etre vendus.

D'ou le choix par defaut : les etudes sont mises **EN LIGNE**, parce qu'une
demonstration sur une boutique vide ne montre rien. Elles sont donc
ACHETABLES. Tant que le lien de la boutique n'est pas dans le menu du site
vitrine, personne n'y arrive par hasard ; le jour ou il y sera, ces documents
doivent avoir ete remplaces par les vrais.

## Rejouable sans rien casser

Elle tourne a CHAQUE demarrage du conteneur, comme `seed_boutique`. Une fiche
qui porte deja un document n'est donc plus touchee : le jour ou la cliente
depose sa vraie etude, la demonstration s'efface d'elle-meme du chemin. Sans ce
garde-fou, chaque deploiement remplacerait son document par un PDF generique et
effacerait les avis qu'elle a saisis.

`--hors-ligne` cree tout sans publier, pour preparer sans exposer.
`--forcer` passe outre le garde-fou, pour refaire le jeu de demonstration.
`--effacer` retire les etudes de demonstration qui n'ont jamais ete vendues —
celles qui l'ont ete sont conservees, leur acheteur y a droit.

## Pourquoi generer les fichiers plutot que les livrer avec le depot

Neuf PDF, neuf extraits et neuf images pesent quelques megaoctets, qui
vivraient dans l'historique git pour toujours. Ils sont donc fabriques a
l'execution, avec les memes bibliotheques que la production (reportlab,
Pillow).
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import AchatProduit, AvisProduit, ProduitBoutique

#: Marqueur porte par la page de garde de chaque document de demonstration.
#: Ecrit une seule fois, ici : deux formulations differentes finiraient par ne
#: plus dire la meme chose.
MENTION_DEMO = (
    "Document de demonstration. Le contenu definitif est depose par EVKHA "
    "depuis l'administration de la boutique."
)

#: La charte, reprise de `theme/tokens.css`. Ces valeurs ne sont pas
#: importables depuis du CSS ; elles sont recopiees ici et nulle part ailleurs.
OR = (0.973, 0.773, 0.110)
#: La meme couleur, en composantes 0-255 pour Pillow. Derivee de `OR` plutot
#: que reecrite : deux ecritures d'une meme couleur finissent par diverger.
OR_RVB = tuple(round(c * 255) for c in OR)
NOIR = (0.043, 0.043, 0.043)
BLANC = (1, 1, 1)

#: Fonds des couvertures, un par etude, pour qu'une grille de neuf vignettes ne
#: soit pas neuf fois la meme image.
FONDS = [
    (28, 28, 32),
    (26, 52, 64),
    (58, 36, 28),
    (30, 46, 38),
    (48, 30, 52),
    (24, 40, 58),
    (54, 44, 24),
    (34, 34, 44),
    (40, 28, 30),
]

#: Une entree par etude : slug, description, sommaire et avis.
#:
#: Le slug est celui de `seed_boutique` : cette commande REMPLIT des fiches
#: existantes plutot que d'en creer de nouvelles. Creer un second jeu ferait
#: deux catalogues, dont un a nettoyer a la main.
ETUDES: list[dict[str, Any]] = [
    {
        "slug": "marche-foodtrucks-2026",
        "description": (
            "Le foodtruck attire parce qu'il demande moins de capital qu'un "
            "restaurant et parce qu'il va chercher ses clients la ou ils sont. "
            "C'est vrai, et c'est incomplet : l'emplacement se negocie, la "
            "licence se merite, et la marge se joue sur des details que "
            "personne ne raconte.\n\n"
            "Cette etude reprend le marche francais du foodtruck secteur par "
            "secteur : combien ils sont, ou ils s'installent, ce qu'ils "
            "vendent, a quel prix, et ce qu'il reste en fin de mois. Les "
            "chiffres d'investissement sont donnes en fourchette, du camion "
            "d'occasion amenage au vehicule neuf equipe.\n\n"
            "Elle s'adresse a qui envisage de se lancer dans les douze mois et "
            "veut savoir, avant d'engager quoi que ce soit, si le modele tient "
            "dans sa ville."
        ),
        "sommaire": [
            "Taille du marche et dynamique depuis 2020",
            "Qui achete : profils, moments, panier moyen",
            "Emplacements : marches, zones d'activite, evenementiel",
            "Reglementation, licences et autorisations de voirie",
            "Investissement de depart et charges mensuelles",
            "Trois modeles economiques compares",
            "Cartographie des acteurs et des franchises",
            "Risques identifies et signaux a surveiller",
        ],
        "avis": [
            (
                "Claire Meunier",
                "Restauratrice, Lyon",
                5,
                "J'hesitais entre deux emplacements. Les chiffres de "
                "frequentation par zone ont tranche en une soiree.",
            ),
            (
                "Sofiane Belkacem",
                "Createur, Marseille",
                5,
                "La partie reglementation m'a evite un dossier refuse en "
                "mairie. A elle seule elle valait le prix.",
            ),
            (
                "Marine Delaunay",
                "En reconversion",
                4,
                "Tres complet. J'aurais aime deux pages de plus sur le "
                "financement, mais rien a redire sur le reste.",
            ),
        ],
    },
    {
        "slug": "marche-micro-creches-2026",
        "description": (
            "Une micro-creche se remplit rarement par manque de demande : elle "
            "se remplit ou non selon l'agrement obtenu, le quartier choisi et "
            "le taux d'occupation reel des premiers mois. Ce sont ces trois "
            "points que la banque regarde.\n\n"
            "L'etude donne le cadre : le nombre de places manquantes par "
            "region, les regles d'agrement PMI, les deux modes de financement "
            "(PSU et PAJE) et ce qu'ils changent pour le compte de resultat, "
            "les ratios d'encadrement, et un montage financier complet sur "
            "trois ans.\n\n"
            "Elle est ecrite pour etre lue par quelqu'un du metier comme par "
            "quelqu'un qui n'en vient pas : chaque terme technique est "
            "explique la premiere fois qu'il apparait."
        ),
        "sommaire": [
            "Places manquantes, region par region",
            "Agrement PMI : ce qui est exige, dans quel ordre",
            "PSU ou PAJE : deux modeles, deux comptes de resultat",
            "Locaux, normes et ratios d'encadrement",
            "Investissement, subventions et aides mobilisables",
            "Montage financier sur trois ans",
            "Recrutement et masse salariale",
            "Ce qui fait echouer les projets, et quand",
        ],
        "avis": [
            (
                "Nadia Hamdi",
                "Educatrice de jeunes enfants",
                5,
                "Le montage financier et le taux d'occupation moyen : c'est "
                "exactement ce que ma banque m'a demande.",
            ),
            (
                "Elodie Ferrand",
                "Porteuse de projet, Nantes",
                5,
                "Lisible du premier coup, meme sans etre du metier.",
            ),
        ],
    },
    {
        "slug": "marche-conciergeries-airbnb-2026",
        "description": (
            "La conciergerie de location courte duree s'est professionnalisee "
            "en cinq ans : le proprietaire qui confiait ses cles a un voisin "
            "signe aujourd'hui avec une societe qui gere l'annonce, le prix, "
            "le menage et le linge.\n\n"
            "L'etude decrit ce marche : combien de logements sont concernes, "
            "quelles commissions se pratiquent selon les villes, quelles "
            "prestations sont attendues, et comment les reglementations "
            "locales — numero d'enregistrement, quotas, compensation — "
            "redessinent la carte.\n\n"
            "Elle sert autant a se lancer qu'a repositionner une offre "
            "existante : les grilles tarifaires sont donnees par ville et par "
            "niveau de service."
        ),
        "sommaire": [
            "Le parc concerne et sa repartition",
            "Commissions pratiquees, ville par ville",
            "Les trois niveaux de prestation du marche",
            "Reglementations locales et leurs effets",
            "Structure de couts : menage, linge, deplacements",
            "Acquisition de proprietaires : ce qui marche",
            "Outils et automatisation",
            "Scenarios de rentabilite a 20, 50 et 100 logements",
        ],
        "avis": [
            (
                "Thomas Rivet",
                "Conciergerie, Bordeaux",
                4,
                "Bon panorama des acteurs. Les grilles tarifaires m'ont servi "
                "a repositionner mon offre.",
            ),
        ],
    },
    {
        "slug": "marche-agences-nettoyage-2026",
        "description": (
            "Le nettoyage professionnel est un marche qu'on croit sature et "
            "qui ne l'est pas : il est fragmente. Quelques grands groupes, des "
            "milliers de structures de moins de dix salaries, et des segments "
            "entiers ou la demande depasse l'offre disponible.\n\n"
            "L'etude separe ces segments — bureaux, commerces, copropriete, "
            "remise en etat, fin de chantier — et donne pour chacun le prix au "
            "metre carre pratique, la marge observee et la difficulte de "
            "recrutement.\n\n"
            "La partie sociale est traitee serieusement : convention "
            "collective, reprise du personnel a la perte d'un marche, et cout "
            "reel d'une heure travaillee."
        ),
        "sommaire": [
            "Structure du marche et fragmentation",
            "Cinq segments, cinq economies differentes",
            "Prix au metre carre et marges observees",
            "Convention collective et reprise du personnel",
            "Cout reel d'une heure travaillee",
            "Gagner ses premiers contrats",
            "Materiel, produits et logistique",
            "Croissance : embaucher ou sous-traiter",
        ],
        "avis": [
            (
                "Sandra Kouadio",
                "Gerante, Lille",
                5,
                "Le calcul du cout horaire reel m'a fait revoir tous mes "
                "devis. Je facturais a perte sur un segment.",
            ),
            (
                "Patrick Vasseur",
                "Repreneur d'entreprise",
                4,
                "Utile pour comprendre la reprise du personnel avant de "
                "signer. Ce point n'est explique nulle part ailleurs.",
            ),
        ],
    },
    {
        "slug": "marche-ecommerce-animaux-2026",
        "description": (
            "Le budget consacre aux animaux de compagnie augmente d'annee en "
            "annee, et une part croissante passe en ligne. Le marche est "
            "pourtant difficile : le poids des produits pese sur la logistique, "
            "les grandes enseignes cassent les prix sur les references "
            "courantes, et la fidelite se gagne ailleurs que sur le tarif.\n\n"
            "L'etude montre ou se trouvent les marges : l'alimentation "
            "specialisee, l'abonnement, les gammes veterinaires, et les niches "
            "que les generalistes ne servent pas.\n\n"
            "Elle detaille aussi la logistique, qui decide de la rentabilite "
            "plus surement que le catalogue."
        ),
        "sommaire": [
            "Le marche et sa croissance par segment",
            "Comportement d'achat et frequence de reappro",
            "Ou se trouvent les marges reelles",
            "Le modele par abonnement",
            "Logistique : poids, frais de port, seuils",
            "Reglementation des gammes veterinaires",
            "Acquisition et fidelisation",
            "Trois positionnements possibles, chiffres",
        ],
        "avis": [
            (
                "Julie Bertrand",
                "E-commercante",
                5,
                "La partie logistique m'a evite une erreur de tarification des "
                "frais de port qui m'aurait coute cher.",
            ),
        ],
    },
    {
        "slug": "marche-bien-etre-2026",
        "description": (
            "Le bien-etre recouvre des activites qui n'ont ni les memes "
            "clients, ni les memes couts, ni la meme reglementation : un "
            "cabinet de sophrologie, un spa urbain et une residence services "
            "seniors n'ont en commun que le rayon ou on les range.\n\n"
            "L'etude les traite separement, avec pour chacun le profil de "
            "clientele, le ticket moyen, l'investissement initial et le point "
            "mort. Le vieillissement de la population y est traite comme ce "
            "qu'il est : une donnee de marche, avec ses chiffres.\n\n"
            "Une attention particuliere est portee aux titres et "
            "qualifications, terrain ou les projets se bloquent souvent apres "
            "avoir engage les frais."
        ),
        "sommaire": [
            "Perimetre : ce que recouvre le bien-etre",
            "Vieillissement et demande : les chiffres",
            "Quatre activites, quatre economies",
            "Titres, qualifications et cadre legal",
            "Investissement et point mort par activite",
            "Emplacement et zone de chalandise",
            "Tarification et abonnements",
            "Passerelles avec le secteur medical",
        ],
        "avis": [
            (
                "Anne-Sophie Girard",
                "Sophrologue, Toulouse",
                5,
                "Le chapitre sur les titres m'a fait gagner un temps fou. "
                "J'allais m'engager sur une formation inutile.",
            ),
            (
                "Karim Toumi",
                "Projet de spa urbain",
                4,
                "Bien fait. Le point mort par activite est ce que je "
                "cherchais depuis des semaines.",
            ),
        ],
    },
    {
        "slug": "entreprises-moins-5000-euros-2026",
        "description": (
            "Vingt activites qu'on peut lancer avec moins de cinq mille "
            "euros, presentees de la meme facon : ce qu'il faut vraiment "
            "debourser, combien de temps avant le premier client, ce que "
            "l'activite rapporte une fois lancee, et ce qui la fait echouer.\n\n"
            "Aucune n'est presentee comme facile. Certaines demandent une "
            "qualification, d'autres une clientele qu'on met des mois a "
            "constituer. Le tableau comparatif final permet de trier selon "
            "trois criteres : capital, delai, competence exigee.\n\n"
            "C'est le document a lire avant de choisir, pas apres."
        ),
        "sommaire": [
            "Methode : comment les vingt ont ete retenues",
            "Services aux particuliers (6 activites)",
            "Services aux entreprises (5 activites)",
            "Commerce et artisanat (4 activites)",
            "Activites en ligne (5 activites)",
            "Tableau comparatif : capital, delai, competence",
            "Statuts juridiques et charges",
            "Les cinq erreurs de demarrage les plus couteuses",
        ],
        "avis": [
            (
                "Fatou Ndiaye",
                "En reconversion",
                5,
                "Le tableau comparatif m'a permis d'eliminer douze idees en "
                "une heure. C'est exactement ce dont j'avais besoin.",
            ),
            (
                "Vincent Aubry",
                "Salarie en projet",
                4,
                "Honnete : ca ne vend pas du reve, ca donne les chiffres.",
            ),
        ],
    },
    {
        "slug": "marche-services-domicile-2026",
        "description": (
            "Menage, garde d'enfants, aide aux personnes agees, petit "
            "bricolage : les services a domicile forment un marche porte par "
            "le vieillissement et par un avantage fiscal que peu de secteurs "
            "connaissent. Il est aussi tres contraint — agrement, convention "
            "collective, avance immediate de credit d'impot.\n\n"
            "L'etude separe les activites soumises a agrement de celles qui ne "
            "le sont pas, explique le mecanisme du credit d'impot et son effet "
            "sur le prix percu par le client, et donne les taux horaires "
            "pratiques par activite et par region.\n\n"
            "Le recrutement, qui est le vrai facteur limitant du secteur, est "
            "traite a part avec les leviers qui fonctionnent."
        ),
        "sommaire": [
            "Le marche, ses activites et sa croissance",
            "Agrement, declaration : qui doit quoi",
            "Credit d'impot et avance immediate",
            "Taux horaires pratiques par activite",
            "Convention collective et cout du travail",
            "Mandataire ou prestataire : deux modeles",
            "Recruter et garder ses intervenants",
            "Compte de resultat type sur trois ans",
        ],
        "avis": [
            (
                "Christelle Roux",
                "Gerante, Angers",
                5,
                "L'explication de l'avance immediate est la plus claire que "
                "j'aie lue. J'ai enfin pu l'expliquer a mes clients.",
            ),
            (
                "Mohamed Sylla",
                "Createur, Ile-de-France",
                4,
                "Le comparatif mandataire/prestataire m'a fait changer de "
                "modele avant de deposer les statuts.",
            ),
        ],
    },
    {
        "slug": "marche-chatbot-2026",
        "description": (
            "Vendre un agent conversationnel a une entreprise ne se heurte "
            "plus a la technique : les modeles sont accessibles, l'integration "
            "est documentee. Le probleme est ailleurs — dans la preuve de "
            "valeur, le cout au message et la responsabilite en cas de reponse "
            "fausse.\n\n"
            "L'etude decrit le marche du point de vue de qui vend : quels "
            "secteurs achetent, a quel prix, sous quelle forme (projet, "
            "abonnement, au message), et ce que les acheteurs exigent "
            "desormais en matiere de donnees et de conformite.\n\n"
            "Elle chiffre aussi le cout de revient reel d'un assistant en "
            "production, poste par poste."
        ),
        "sommaire": [
            "Etat du marche et maturite des acheteurs",
            "Secteurs qui achetent, et pour quels usages",
            "Trois modeles de facturation compares",
            "Cout de revient reel d'un assistant en production",
            "Donnees, conformite et responsabilite",
            "Concurrence : editeurs, integrateurs, independants",
            "Cycle de vente et preuve de valeur",
            "Ce qui fera bouger le marche dans les 24 mois",
        ],
        "avis": [
            (
                "Laurent Pichon",
                "Integrateur, Rennes",
                4,
                "Le cout de revient poste par poste est la seule chose "
                "serieuse que j'aie lue sur le sujet.",
            ),
        ],
    },
]


def _meme_texte(un: str, autre: str) -> bool:
    """Deux textes disent-ils la meme chose, aux blancs pres ?

    Cette comparaison decide si une fiche est encore celle de la demonstration
    — donc si on a le droit d'y toucher. Faite caractere pour caractere, elle a
    echoue sur UN retour a la ligne : la base portait un retour Windows la ou le
    code ecrit un retour Unix. La couverture illisible de
    « marche-agences-nettoyage-2026 » est ainsi restee en production alors que
    les huit autres etaient refaites.

    Rien ne le signalait : la commande annoncait « INTACT », ce qui est
    exactement ce qu'elle dit quand la cliente a fait sien le produit. Un
    controle qui compare a une donnee mal normalisee est pire qu'absent — il
    rend une reponse fausse avec l'assurance d'une reponse juste (regle 2).

    On compare donc sur la SUBSTANCE : fins de ligne unifiees, blancs de bord
    otes. Le sens du texte decide, pas son encodage.
    """

    def _propre(texte: str) -> str:
        unifie = texte.replace("\r\n", "\n").replace("\r", "\n")
        return "\n".join(ligne.strip() for ligne in unifie.split("\n")).strip()

    return _propre(un) == _propre(autre)


def _police(taille: int, grasse: bool = False) -> Any:
    """Une police VECTORIELLE a la taille demandee.

    ## Pourquoi ce n'est pas une ligne

    La premiere version demandait `arialbd.ttf`, et retombait sur
    `ImageFont.load_default()` en cas d'echec. Sur mon poste, Arial existe ; le
    conteneur Linux ne l'a pas. Le repli est une police BITMAP de onze pixels
    que Pillow ne sait pas agrandir : les couvertures deployees portaient donc
    leur titre en corps 11 sur une image de 1200 pixels de large — un filet de
    texte illisible, la ou le code demandait du 62.

    Rien n'echouait. Le fichier etait valide, la commande rendait « OK », et
    seul un oeil sur l'image le voyait. C'est la regle 3 : verifier ce que le
    lecteur va REGARDER, pas ce que la fonction a rendu.

    DejaVu est cherche dans les donnees de matplotlib, qui est une dependance
    DECLAREE de ce projet (extra `word`) : la police voyage donc avec
    l'installation, sur n'importe quel systeme. Les polices du systeme restent
    essayees d'abord, parce qu'elles sont plus jolies quand elles existent.
    """
    from PIL import ImageFont  # noqa: PLC0415

    candidates = ["arialbd.ttf", "Arial.ttf"] if grasse else ["arial.ttf", "Arial.ttf"]
    for nom in candidates:
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            continue

    import matplotlib  # noqa: PLC0415

    fichier = "DejaVuSans-Bold.ttf" if grasse else "DejaVuSans.ttf"
    chemin = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / fichier
    # Pas de repli silencieux vers `load_default()` : une police absente doit
    # se voir ici, pas sur l'image livree (regle 1).
    return ImageFont.truetype(str(chemin), taille)


def _couverture(titre: str, theme: str, fond: tuple[int, int, int]) -> bytes:
    """Une couverture 1200x800, au format des cartes de la boutique.

    Elle porte ce qui identifie l'etude : son theme, son titre en grand, et la
    collection. Une couverture qui ne porte qu'un aplat de couleur ne dit rien
    de plus qu'un cadre vide.
    """
    from PIL import Image, ImageDraw  # noqa: PLC0415

    image = Image.new("RGB", (1200, 800), fond)
    dessin = ImageDraw.Draw(image)
    dessin.rectangle([0, 726, 1200, 800], fill=OR_RVB)

    titre_police = _police(66, grasse=True)
    theme_police = _police(28, grasse=True)
    pied_police = _police(26)

    # Le theme, en haut, sur un filet d'or : il situe l'etude avant qu'on lise
    # le titre, comme le fanion de la carte en boutique.
    if theme:
        dessin.rectangle([84, 96, 92, 130], fill=OR_RVB)
        dessin.text((110, 98), theme.upper(), font=theme_police, fill=OR_RVB)

    lignes: list[str] = []
    courante = ""
    for mot in titre.split():
        essai = f"{courante} {mot}".strip()
        if dessin.textlength(essai, font=titre_police) > 1010:
            lignes.append(courante)
            courante = mot
        else:
            courante = essai
    lignes.append(courante)

    # Bloc de titre centre verticalement dans la zone sombre : deux lignes ou
    # quatre, il reste a sa place.
    hauteur = len(lignes) * 84
    y = 380 - hauteur // 2
    for ligne in lignes:
        dessin.text((84, y), ligne, font=titre_police, fill=(255, 255, 255))
        y += 84

    dessin.text((84, 648), "ÉTUDE DE MARCHÉ · EVKHA", font=pied_police, fill=OR_RVB)

    tampon = io.BytesIO()
    image.save(tampon, format="JPEG", quality=90)
    return tampon.getvalue()


def _document(titre: str, sommaire: list[str], extrait: bool = False) -> bytes:
    """Un PDF mis en page : garde, sommaire, puis une page par chapitre.

    `extrait` s'arrete apres le deuxieme chapitre et annonce la suite — c'est
    ce que fait un extrait : il montre assez pour juger, pas assez pour se
    passer du document.
    """
    from reportlab.lib.pagesizes import A4  # noqa: PLC0415
    from reportlab.lib.units import mm  # noqa: PLC0415
    from reportlab.pdfgen import canvas as toile  # noqa: PLC0415

    tampon = io.BytesIO()
    page = toile.Canvas(tampon, pagesize=A4)
    largeur, hauteur = A4

    def _texte_replie(contenu: str, x: float, y: float, taille: float, max_car: int) -> float:
        mots, ligne = contenu.split(), ""
        for mot in mots:
            essai = f"{ligne} {mot}".strip()
            if len(essai) > max_car:
                page.drawString(x, y, ligne)
                y -= taille * 1.5
                ligne = mot
            else:
                ligne = essai
        if ligne:
            page.drawString(x, y, ligne)
            y -= taille * 1.5
        return y

    # ── Page de garde ────────────────────────────────────────────────────────
    page.setFillColorRGB(*NOIR)
    page.rect(0, 0, largeur, hauteur, fill=1, stroke=0)
    page.setFillColorRGB(*OR)
    page.rect(0, 0, largeur, 18 * mm, fill=1, stroke=0)

    page.setFillColorRGB(*BLANC)
    page.setFont("Helvetica-Bold", 26)
    y = hauteur - 90 * mm
    for ligne in _decouper(titre, 30):
        page.drawString(22 * mm, y, ligne)
        y -= 12 * mm

    page.setFillColorRGB(*OR)
    page.setFont("Helvetica-Bold", 12)
    page.drawString(22 * mm, y - 6 * mm, "ETUDE DE MARCHE - EVKHA")

    page.setFillColorRGB(0.65, 0.65, 0.65)
    page.setFont("Helvetica", 9)
    y = 30 * mm
    for ligne in _decouper(MENTION_DEMO, 70):
        page.drawString(22 * mm, y, ligne)
        y -= 5 * mm
    page.showPage()

    # ── Sommaire ─────────────────────────────────────────────────────────────
    page.setFillColorRGB(*NOIR)
    page.setFont("Helvetica-Bold", 18)
    page.drawString(22 * mm, hauteur - 30 * mm, "Sommaire")
    page.setFillColorRGB(*OR)
    page.rect(22 * mm, hauteur - 34 * mm, 30 * mm, 2, fill=1, stroke=0)

    page.setFillColorRGB(*NOIR)
    y = hauteur - 50 * mm
    chapitres = sommaire[:2] if extrait else sommaire
    for numero, entree in enumerate(sommaire, start=1):
        page.setFont("Helvetica-Bold", 10)
        page.setFillColorRGB(0.72, 0.54, 0.04)
        page.drawString(22 * mm, y, f"{numero:02d}")
        page.setFillColorRGB(*NOIR)
        page.setFont("Helvetica", 11)
        page.drawString(32 * mm, y, entree)
        y -= 9 * mm
    if extrait:
        page.setFont("Helvetica-Oblique", 10)
        page.setFillColorRGB(0.4, 0.4, 0.4)
        page.drawString(
            22 * mm, y - 6 * mm, "Cet extrait presente les deux premiers chapitres."
        )
    page.showPage()

    # ── Un chapitre par page ─────────────────────────────────────────────────
    for numero, entree in enumerate(chapitres, start=1):
        page.setFillColorRGB(*OR)
        page.rect(0, hauteur - 26 * mm, largeur, 26 * mm, fill=1, stroke=0)
        page.setFillColorRGB(*NOIR)
        page.setFont("Helvetica-Bold", 15)
        page.drawString(22 * mm, hauteur - 17 * mm, f"{numero}. {entree}")

        page.setFont("Helvetica", 10.5)
        page.setFillColorRGB(0.15, 0.15, 0.15)
        y = hauteur - 42 * mm
        for paragraphe in _PARAGRAPHES:
            y = _texte_replie(paragraphe, 22 * mm, y, 10.5, 95)
            y -= 4 * mm
        page.showPage()

    page.save()
    return tampon.getvalue()


#: Le corps des pages de demonstration. Volontairement generique, et il le dit.
_PARAGRAPHES = [
    "Ce chapitre presente les donnees collectees sur le perimetre etudie, leur "
    "source et la periode couverte. Chaque chiffre avance est rattache a sa "
    "source, et les estimations sont signalees comme telles.",
    "Les ordres de grandeur sont donnes en fourchette lorsque les sources "
    "divergent, avec la mediane retenue. Une fourchette large est un "
    "renseignement en soi : elle indique un marche mal mesure.",
    "Les elements chiffres de ce chapitre sont repris dans la synthese "
    "finale, ou ils sont mis en regard des autres chapitres pour faire "
    "apparaitre les arbitrages.",
    "Dans le document definitif, cette page porte les tableaux, les graphiques "
    "et les sources du chapitre. La presente version sert a montrer la "
    "structure et la mise en page de la collection.",
]


def _decouper(texte: str, largeur: int) -> list[str]:
    """Coupe un texte en lignes d'au plus `largeur` caracteres."""
    lignes: list[str] = []
    courante = ""
    for mot in texte.split():
        essai = f"{courante} {mot}".strip()
        if len(essai) > largeur:
            lignes.append(courante)
            courante = mot
        else:
            courante = essai
    if courante:
        lignes.append(courante)
    return lignes


class Command(BaseCommand):
    help = "Remplit les fiches de la boutique avec un jeu de demonstration."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--hors-ligne",
            action="store_true",
            help="Cree tout sans publier : la boutique reste vide pour le public.",
        )
        parser.add_argument(
            "--forcer",
            action="store_true",
            help=(
                "Remplace meme les fiches qui portent deja un document. "
                "A n'utiliser que pour refaire le jeu de demonstration."
            ),
        )
        parser.add_argument(
            "--effacer",
            action="store_true",
            help=(
                "Retire les etudes de demonstration jamais vendues, et leurs "
                "avis. Celles qui ont ete vendues sont conservees."
            ),
        )

    def handle(self, *args: object, **options: object) -> None:
        if options.get("effacer"):
            self._effacer()
            return

        # Les deux bibliotheques qui fabriquent les fichiers sont verifiees
        # AVANT d'ecrire quoi que ce soit, et leur absence rend un refus lisible
        # plutot qu'une pile d'appels.
        #
        # Cette commande tourne au demarrage du conteneur. Le 22/08/2026,
        # `reportlab` n'etait declare dans aucun extra : `ModuleNotFoundError`
        # a arrete la chaine de demarrage et gunicorn n'a jamais demarre — la
        # plateforme entiere a rendu 503 pour un jeu de donnees de
        # demonstration. La dependance est declaree depuis, et le compose ne
        # relie plus cette etape par un `&&` sec ; ce controle-ci est la
        # troisieme ligne, celle qui NOMME ce qui manque.
        for module, extra in (("reportlab", "word"), ("PIL", "word")):
            try:
                __import__(module)
            except ImportError:
                self.stderr.write(
                    self.style.ERROR(
                        f"{module} est absent : le jeu de demonstration n'a pas "
                        f"ete depose. Installez l'extra « {extra} » "
                        "(pip install -e \".[word]\"). Rien d'autre n'est "
                        "affecte — la boutique fonctionne, elle est simplement "
                        "vide."
                    )
                )
                return

        en_ligne = not options.get("hors_ligne")
        aujourdhui = timezone.now().date()
        intacts = 0

        for rang, etude in enumerate(ETUDES):
            produit = ProduitBoutique.objects.filter(slug=etude["slug"]).first()
            if produit is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [ABSENT] {etude['slug']} — lancez d'abord seed_boutique."
                    )
                )
                continue

            # UNE FICHE QUI PORTE DEJA UN DOCUMENT N'EST PLUS TOUCHEE. C'est ce
            # qui rend la commande rejouable a chaque demarrage du conteneur
            # sans jamais ecraser le vrai travail : le jour ou la cliente
            # depose sa vraie etude, la demonstration s'efface d'elle-meme du
            # chemin. Sans ce garde-fou, chaque deploiement remplacerait son
            # document par un PDF generique et effacerait les avis qu'elle a
            # saisis a la main.
            if produit.fichier and not options.get("forcer"):
                # ... a une exception pres : la COUVERTURE d'une fiche restee
                # entierement de demonstration.
                #
                # Les premieres couvertures deployees portaient leur titre en
                # corps 11 sur 1200 pixels, faute d'une police vectorielle dans
                # le conteneur (voir `_police`). Elles sont illisibles, et sans
                # ce rattrapage elles le resteraient pour toujours : la fiche
                # porte un fichier, donc elle est protegee.
                #
                # DEUX conditions, et il faut les deux : la description doit
                # etre encore MOT POUR MOT celle de la demonstration — la
                # cliente n'y a donc pas touche —, et l'image doit etre celle
                # que cette commande depose. Le jour ou elle ecrit sa propre
                # description ou depose sa propre couverture, on ne touche plus
                # a rien. Le document vendu, lui, n'est jamais remplace.
                encore_demo = _meme_texte(produit.description, etude["description"])
                notre_image = "-couverture" in (produit.image.name or "")
                if encore_demo and notre_image:
                    produit.image.save(
                        f"{produit.slug}-couverture.jpg",
                        SimpleUploadedFile(
                            "couverture.jpg",
                            _couverture(
                                produit.titre,
                                produit.theme,
                                FONDS[rang % len(FONDS)],
                            ),
                            "image/jpeg",
                        ),
                        save=True,
                    )
                    self.stdout.write(
                        f"  [COUVERTURE] {produit.slug} — refaite, le reste intact."
                    )
                else:
                    self.stdout.write(
                        f"  [INTACT] {produit.slug} — un document est deja depose."
                    )
                intacts += 1
                continue

            produit.description = etude["description"]
            produit.sommaire = "\n".join(etude["sommaire"])
            produit.mise_a_jour_le = aujourdhui

            fond = FONDS[rang % len(FONDS)]
            produit.image.save(
                f"{produit.slug}-couverture.jpg",
                SimpleUploadedFile(
                    "couverture.jpg", _couverture(produit.titre, produit.theme, fond), "image/jpeg"
                ),
                save=False,
            )
            produit.fichier.save(
                f"{produit.slug}.pdf",
                SimpleUploadedFile(
                    "etude.pdf",
                    _document(produit.titre, etude["sommaire"]),
                    "application/pdf",
                ),
                save=False,
            )
            produit.extrait.save(
                f"{produit.slug}-extrait.pdf",
                SimpleUploadedFile(
                    "extrait.pdf",
                    _document(produit.titre, etude["sommaire"], extrait=True),
                    "application/pdf",
                ),
                save=False,
            )
            produit.en_ligne = en_ligne and produit.est_publiable
            produit.save()

            # Les avis de demonstration : ceux saisis en administration, donc
            # publies. On efface d'abord CEUX DE DEMONSTRATION uniquement —
            # ceux deposes par une acheteuse portent un `achat` et restent.
            produit.avis.filter(achat__isnull=True).delete()
            for auteur, qualite, note, texte in etude["avis"]:
                AvisProduit.objects.create(
                    produit=produit,
                    auteur=auteur,
                    qualite=qualite,
                    note=note,
                    texte=texte,
                    publie=True,
                )

            produit.refresh_from_db()
            etat = "en ligne" if produit.en_ligne else "hors ligne"
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [OK] {produit.slug} — {etat}, {produit.nombre_d_avis} avis, "
                    f"note {produit.note_moyenne}"
                )
            )

        publies = ProduitBoutique.objects.filter(en_ligne=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{len(ETUDES) - intacts} etudes preparees, {intacts} laissees "
                f"intactes, {publies} en ligne au total."
            )
        )
        # L'avertissement ne vaut que pour ce qui vient d'etre depose. Sur un
        # rejeu ou tout est intact, il ferait croire que les documents en ligne
        # sont generiques alors qu'ils sont ceux de la cliente.
        if en_ligne and intacts < len(ETUDES):
            self.stdout.write(
                self.style.WARNING(
                    "\nCes documents sont ACHETABLES et leur contenu est generique.\n"
                    "Remplacez-les par les vrais depuis /admin/boutique avant de "
                    "mettre le lien de la boutique dans le menu du site."
                )
            )

    def _effacer(self) -> None:
        """Retire ce qui n'a jamais ete vendu. Le reste appartient a quelqu'un."""
        retires = gardes = 0
        for etude in ETUDES:
            produit = ProduitBoutique.objects.filter(slug=etude["slug"]).first()
            if produit is None:
                continue
            if AchatProduit.objects.filter(produit=produit).exists():
                gardes += 1
                self.stdout.write(
                    f"  [GARDE] {produit.slug} — vendue, son acheteur y a droit."
                )
                continue
            produit.avis.all().delete()
            produit.image.delete(save=False)
            produit.fichier.delete(save=False)
            produit.extrait.delete(save=False)
            produit.description = ""
            produit.sommaire = ""
            produit.en_ligne = False
            produit.save()
            retires += 1
            self.stdout.write(f"  [VIDE]  {produit.slug}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{retires} fiches vidées, {gardes} conservées car vendues."
            )
        )
